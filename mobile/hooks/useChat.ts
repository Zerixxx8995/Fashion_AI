/**
 * useChat — mobile/hooks/useChat.ts
 *
 * Responsibility: Manage chat history + loading/error state for the agent.
 *
 * Architecture rules:
 *   - Chat history lives in React state ONLY — never persisted to DB (spec NF18)
 *   - Cleared when component unmounts (app close/screen exit)
 *   - All network calls go through agentService (never raw fetch here)
 *   - mlClient obtained from useHttpClients() inside the hook
 *   - activeToolCalls tracks current tool calls for ToolCallIndicator rendering
 */

import { useState, useRef, useCallback } from 'react';
import { useHttpClients } from '../services/httpClient';
import { sendAgentMessage, type SessionMessage, type ProductCited } from '../services/agentService';

// ---------------------------------------------------------------------------
// Chat message shape used by the UI
// ---------------------------------------------------------------------------

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  products_cited?: ProductCited[];
  tools_called?: string[];
  timestamp: number;
}

// ---------------------------------------------------------------------------
// Hook return shape
// ---------------------------------------------------------------------------

export interface UseChatResult {
  /** All messages in the current session */
  messages: ChatMessage[];
  /** True while the agent request is in flight */
  loading: boolean;
  /** Current tool calls being executed (for ToolCallIndicator) */
  activeToolCalls: string[];
  /** Error string if the last call failed */
  error: string | null;
  /** Send a new user message */
  sendMessage: (text: string, userId: string) => Promise<void>;
  /** Clear the conversation (on screen exit or explicit reset) */
  clearChat: () => void;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

let _messageCounter = 0;
function nextId(): string {
  _messageCounter += 1;
  return `msg-${Date.now()}-${_messageCounter}`;
}

export function useChat(): UseChatResult {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeToolCalls, setActiveToolCalls] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Session messages in backend format — kept in sync with messages state
  // This is the authoritative history we send to the agent on each turn
  const sessionMessagesRef = useRef<SessionMessage[]>([]);
  const isMounted = useRef(true);

  const { getClients } = useHttpClients();

  const sendMessage = useCallback(
    async (text: string, userId: string) => {
      if (!text.trim() || loading) return;

      setError(null);

      // 1. Optimistically add user message to UI
      const userMessage: ChatMessage = {
        id: nextId(),
        role: 'user',
        content: text.trim(),
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, userMessage]);

      // 2. Update session history ref (used in next API call)
      const currentSession = sessionMessagesRef.current;

      // 3. Start loading — show generic indicator first
      setLoading(true);
      setActiveToolCalls(['similarity_search']); // optimistic — shows immediately

      try {
        const { mlClient } = await getClients();

        const response = await sendAgentMessage(mlClient, {
          user_id: userId,
          message: text.trim(),
          session_messages: currentSession,
        });

        if (!isMounted.current) return;

        // 4. Show actual tool calls while "waiting" (we now have the result)
        setActiveToolCalls(response.tools_called ?? []);

        // 5. Add assistant message to UI
        const assistantMessage: ChatMessage = {
          id: nextId(),
          role: 'assistant',
          content: response.reply,
          products_cited: response.products_cited,
          tools_called: response.tools_called,
          timestamp: Date.now(),
        };

        setMessages((prev) => [...prev, assistantMessage]);

        // 6. Sync session history from server response (server appends both turns)
        sessionMessagesRef.current = response.session_messages;

      } catch (err) {
        if (!isMounted.current) return;
        const message = err instanceof Error ? err.message : 'Something went wrong. Please try again.';
        setError(message);

        // Add error message as assistant bubble
        setMessages((prev) => [
          ...prev,
          {
            id: nextId(),
            role: 'assistant',
            content: 'Sorry, I ran into an issue. Please try again.',
            timestamp: Date.now(),
          },
        ]);
      } finally {
        if (isMounted.current) {
          setLoading(false);
          setActiveToolCalls([]);
        }
      }
    },
    [loading, getClients]
  );

  const clearChat = useCallback(() => {
    setMessages([]);
    setError(null);
    setLoading(false);
    setActiveToolCalls([]);
    sessionMessagesRef.current = [];
  }, []);

  return {
    messages,
    loading,
    activeToolCalls,
    error,
    sendMessage,
    clearChat,
  };
}
