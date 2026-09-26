/**
 * ToolCallIndicator — mobile/components/chat/ToolCallIndicator.tsx
 *
 * Responsibility: Show an animated "Searching similar products..." indicator
 * while the agent is running tools. One indicator per tool call — spec constraint.
 *
 * Architecture rules:
 *   - Purely visual — no state management, no API calls
 *   - Animated pulsing dot to communicate activity
 *   - Per-tool labels map tool_name → human-readable message
 */

import React, { useEffect, useRef } from 'react';
import { View, Text, StyleSheet, Animated } from 'react-native';

// ---------------------------------------------------------------------------
// Tool name → human-readable status message
// ---------------------------------------------------------------------------

const TOOL_LABELS: Record<string, string> = {
  similarity_search: 'Searching similar products...',
  budget_optimizer: 'Calculating budget split...',
  wardrobe_fetcher: 'Checking your wardrobe...',
};

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ToolCallIndicatorProps {
  /** Tool name — maps to a human-readable label */
  toolName: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ToolCallIndicator({ toolName }: ToolCallIndicatorProps) {
  const label = TOOL_LABELS[toolName] ?? `Running ${toolName}...`;
  const pulse = useRef(new Animated.Value(0.4)).current;

  useEffect(() => {
    const animation = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, {
          toValue: 1,
          duration: 600,
          useNativeDriver: true,
        }),
        Animated.timing(pulse, {
          toValue: 0.4,
          duration: 600,
          useNativeDriver: true,
        }),
      ])
    );
    animation.start();
    return () => animation.stop();
  }, [pulse]);

  return (
    <View style={styles.container}>
      <Animated.View style={[styles.dot, { opacity: pulse }]} />
      <Text style={styles.label}>{label}</Text>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 6,
    gap: 8,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#FF3F6C',
  },
  label: {
    fontSize: 12,
    color: '#70707A',
    fontStyle: 'italic',
  },
});
