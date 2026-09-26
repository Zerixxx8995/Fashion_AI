/**
 * agentService — mobile/services/agentService.ts
 *
 * Responsibility: HTTP call to POST /agent/chat.
 *
 * Architecture rules:
 *   - Only HTTP logic lives here — no state, no caching
 *   - Calls the ml-backend via mlClient (FastAPI)
 *   - Full session history is sent on every request (spec constraint)
 */

export type MlClient = {
  post<T>(path: string, opts?: { body?: unknown }): Promise<T>;
};

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SessionMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ProductCited {
  name: string;
  price_inr: number;
  platform: string;
  url: string;
}

export interface AgentChatRequest {
  user_id: string;
  message: string;
  session_messages: SessionMessage[];
}

export interface AgentChatResponse {
  reply: string;
  tools_called: string[];
  products_cited: ProductCited[];
  session_messages: SessionMessage[];
}

// ---------------------------------------------------------------------------
// API call
// ---------------------------------------------------------------------------

/**
 * Send a message to the conversational shopping agent.
 *
 * The full session_messages array must be included — the agent uses it
 * for conversation continuity. The response includes the updated session_messages
 * with the new turn appended — store this and send it on the next call.
 *
 * @param mlClient   Configured axios-based HTTP client (from httpClient.ts)
 * @param request    User ID, message, and full session history
 */
export async function sendAgentMessage(
  mlClient: MlClient,
  request: AgentChatRequest
): Promise<AgentChatResponse> {
  return mlClient.post<AgentChatResponse>('/agent/chat', { body: request });
}
