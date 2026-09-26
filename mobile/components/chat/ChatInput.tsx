/**
 * ChatInput — mobile/components/chat/ChatInput.tsx
 *
 * Responsibility: Text input + send button for the chat screen.
 *
 * Architecture rules:
 *   - Controlled input — parent manages value and onSend
 *   - Send button disabled while loading or message is empty
 *   - Auto-grows to 4 lines max, then scrolls
 */

import React from 'react';
import {
  View,
  TextInput,
  TouchableOpacity,
  Text,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ChatInputProps {
  value: string;
  onChangeText: (text: string) => void;
  onSend: () => void;
  loading: boolean;
  placeholder?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ChatInput({
  value,
  onChangeText,
  onSend,
  loading,
  placeholder = 'Ask me anything about fashion...',
}: ChatInputProps) {
  const canSend = !loading && value.trim().length > 0;

  return (
    <View style={styles.container}>
      <TextInput
        style={styles.input}
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor="#505058"
        multiline
        maxLength={500}
        returnKeyType="send"
        onSubmitEditing={canSend ? onSend : undefined}
        blurOnSubmit={false}
        editable={!loading}
        accessibilityLabel="Chat message input"
        accessibilityHint="Type your fashion question here"
      />
      <TouchableOpacity
        style={[styles.sendButton, !canSend && styles.sendButtonDisabled]}
        onPress={canSend ? onSend : undefined}
        activeOpacity={0.8}
        disabled={!canSend}
        accessibilityRole="button"
        accessibilityLabel="Send message"
        accessibilityState={{ disabled: !canSend }}
      >
        {loading ? (
          <ActivityIndicator size="small" color="#FFFFFF" />
        ) : (
          <Text style={[styles.sendArrow, !canSend && styles.sendArrowDisabled]}>↑</Text>
        )}
      </TouchableOpacity>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: '#0B0B0E',
    borderTopWidth: 1,
    borderTopColor: '#16161C',
    gap: 10,
  },
  input: {
    flex: 1,
    backgroundColor: '#16161C',
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingTop: 10,
    paddingBottom: 10,
    fontSize: 14,
    color: '#E0E0EC',
    maxHeight: 100,
    borderWidth: 1,
    borderColor: '#24242E',
    lineHeight: 20,
  },
  sendButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#FF3F6C',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 0,
  },
  sendButtonDisabled: {
    backgroundColor: '#24242E',
  },
  sendArrow: {
    fontSize: 18,
    color: '#FFFFFF',
    fontWeight: '700',
  },
  sendArrowDisabled: {
    color: '#505058',
  },
});
