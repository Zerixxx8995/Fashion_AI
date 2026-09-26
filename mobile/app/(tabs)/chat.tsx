/**
 * ChatScreen — mobile/app/(tabs)/chat.tsx
 *
 * Responsibility: Full-screen conversational shopping assistant.
 *
 * Layout:
 *   [Header — "Shopping Assistant"]
 *   [FlatList — chat messages]
 *   [ToolCallIndicators — shown per tool while loading]
 *   [ChatInput — text input + send button]
 *
 * Architecture rules:
 *   - Chat history lives in useChat hook — never persisted to DB (spec NF18)
 *   - ToolCallIndicator shown per tool call — not one generic spinner (spec constraint)
 *   - Cleared on screen unmount
 *   - userId comes from Clerk useUser hook
 */

import React, { useCallback, useEffect, useRef } from 'react';
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  StatusBar,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useUser } from '@clerk/expo';
import { useRouter } from 'expo-router';

import { useChat } from '../../hooks/useChat';
import ChatBubble, { type ChatMessage } from '../../components/chat/ChatBubble';
import ChatInput from '../../components/chat/ChatInput';
import ToolCallIndicator from '../../components/chat/ToolCallIndicator';
import { useState } from 'react';

// ---------------------------------------------------------------------------
// Welcome message — shown before the user sends their first message
// ---------------------------------------------------------------------------

const WELCOME_MESSAGE: ChatMessage = {
  id: 'welcome',
  role: 'assistant',
  content:
    "Hi! I'm your personal shopping assistant. Ask me anything — like \"find me a kurta under ₹1500\" or \"what goes with blue jeans for a party\".",
  timestamp: Date.now(),
};

// ---------------------------------------------------------------------------
// Screen
// ---------------------------------------------------------------------------

export default function ChatScreen() {
  const { user } = useUser();
  const userId = user?.id ?? 'guest';
  const router = useRouter();

  const { messages, loading, activeToolCalls, error, sendMessage, clearChat } = useChat();
  const [inputValue, setInputValue] = useState('');

  const flatListRef = useRef<FlatList>(null);

  // Clear on unmount
  useEffect(() => {
    return () => {
      clearChat();
    };
  }, [clearChat]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (messages.length > 0) {
      setTimeout(() => {
        flatListRef.current?.scrollToEnd({ animated: true });
      }, 100);
    }
  }, [messages.length, loading]);

  const handleSend = useCallback(async () => {
    const text = inputValue.trim();
    if (!text) return;
    setInputValue('');
    await sendMessage(text, userId);
  }, [inputValue, sendMessage, userId]);

  // Combine welcome message + real messages for the list
  const displayMessages: ChatMessage[] = messages.length === 0
    ? [WELCOME_MESSAGE]
    : messages;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <StatusBar barStyle="light-content" backgroundColor="#0B0B0E" />

      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <View style={styles.headerDot} />
          <Text style={styles.headerTitle}>Shopping Assistant</Text>
        </View>
        <TouchableOpacity
          style={styles.clearButton}
          onPress={clearChat}
          activeOpacity={0.7}
          accessibilityRole="button"
          accessibilityLabel="Clear chat"
        >
          <Text style={styles.clearButtonText}>Clear</Text>
        </TouchableOpacity>
      </View>

      {/* Chat messages */}
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 0 : 0}
      >
        <FlatList
          ref={flatListRef}
          data={displayMessages}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => <ChatBubble message={item} />}
          contentContainerStyle={styles.listContent}
          showsVerticalScrollIndicator={false}
          ListFooterComponent={
            loading ? (
              <View style={styles.toolCallsContainer}>
                {activeToolCalls.length > 0 ? (
                  activeToolCalls.map((toolName) => (
                    <ToolCallIndicator key={toolName} toolName={toolName} />
                  ))
                ) : (
                  <ToolCallIndicator toolName="similarity_search" />
                )}
              </View>
            ) : null
          }
        />

        {/* Chat input */}
        <ChatInput
          value={inputValue}
          onChangeText={setInputValue}
          onSend={handleSend}
          loading={loading}
        />
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0B0B0E',
  },
  flex: {
    flex: 1,
  },
  // Header
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    backgroundColor: '#0B0B0E',
    borderBottomWidth: 1,
    borderBottomColor: '#16161C',
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  headerDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#FF3F6C',
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: '700',
    color: '#FFFFFF',
    letterSpacing: 0.3,
  },
  clearButton: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#24242E',
  },
  clearButtonText: {
    fontSize: 12,
    color: '#70707A',
    fontWeight: '600',
  },
  // FlatList
  listContent: {
    paddingTop: 12,
    paddingBottom: 8,
  },
  // Tool call indicators container
  toolCallsContainer: {
    paddingHorizontal: 16,
    paddingVertical: 4,
    gap: 2,
  },
});
