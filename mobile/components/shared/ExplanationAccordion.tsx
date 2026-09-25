/**
 * ExplanationAccordion — mobile/components/shared/ExplanationAccordion.tsx
 *
 * Responsibility: Reusable collapsible component for LLM-generated explanations.
 * Shows a tappable label. On tap: calls useExplanation hook, shows loading spinner,
 * renders explanation text + "AI generated" label.
 *
 * Architecture rules:
 *   - NEVER pre-fetches on mount — fetch is triggered only on first user tap (lazy)
 *   - Explanation is cached in component state after first fetch (instant on re-tap)
 *   - Always shows "AI generated" label — spec constraint NF14
 *
 * Props:
 *   title       — tappable label text (e.g. "Why is this trending?")
 *   id          — trend_id or product_id (string UUID)
 *   type        — "trend" | "recommendation"
 *   userId      — required for "recommendation" type; optional for "trend"
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ActivityIndicator,
  StyleSheet,
  Animated,
  LayoutAnimation,
  Platform,
  UIManager,
} from 'react-native';
import { useExplanation } from '../../hooks/useExplanation';

// Enable LayoutAnimation on Android
if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

interface ExplanationAccordionProps {
  /** Display label for the expandable trigger row */
  title: string;
  /** trend_id or product_id */
  id: string;
  /** Determines which endpoint is called */
  type: 'trend' | 'recommendation';
  /** Required when type === "recommendation" */
  userId?: string;
}

export default function ExplanationAccordion({
  title,
  id,
  type,
  userId,
}: ExplanationAccordionProps) {
  const [expanded, setExpanded] = useState(false);
  const [hasTapped, setHasTapped] = useState(false);

  // Only fetch when the user has tapped — never on mount
  const { explanation, loading, error } = useExplanation({
    id,
    type,
    userId,
    enabled: hasTapped,
  });

  const handlePress = () => {
    if (!hasTapped) {
      setHasTapped(true);
    }
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setExpanded((prev) => !prev);
  };

  return (
    <View style={styles.container}>
      {/* Divider */}
      <View style={styles.divider} />

      {/* Trigger row */}
      <TouchableOpacity
        style={styles.trigger}
        onPress={handlePress}
        activeOpacity={0.7}
        accessibilityRole="button"
        accessibilityLabel={title}
        accessibilityState={{ expanded }}
      >
        <Text style={styles.triggerText}>{title}</Text>
        <Text style={styles.chevron}>{expanded ? '▴' : '▾'}</Text>
      </TouchableOpacity>

      {/* Expanded content */}
      {expanded && (
        <View style={styles.content}>
          {loading && (
            <View style={styles.loadingRow}>
              <ActivityIndicator size="small" color="#FF3F6C" />
              <Text style={styles.loadingText}>Generating insight…</Text>
            </View>
          )}

          {!loading && error && (
            <Text style={styles.errorText}>
              Could not load explanation. Tap to retry.
            </Text>
          )}

          {!loading && !error && explanation && (
            <View>
              <Text style={styles.explanationText}>{explanation}</Text>
              {/* Spec constraint NF14: always show "AI generated" label */}
              <View style={styles.aiLabelRow}>
                <View style={styles.aiDot} />
                <Text style={styles.aiLabel}>AI generated</Text>
              </View>
            </View>
          )}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    // No extra margin — parent card controls spacing
  },
  divider: {
    height: 1,
    backgroundColor: '#24242E',
    marginHorizontal: 0,
  },
  trigger: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#16161C',
  },
  triggerText: {
    fontSize: 13,
    fontWeight: '600',
    color: '#FF3F6C',
    letterSpacing: 0.2,
  },
  chevron: {
    fontSize: 11,
    color: '#FF3F6C',
    fontWeight: '700',
  },
  content: {
    paddingHorizontal: 16,
    paddingBottom: 14,
    paddingTop: 4,
    backgroundColor: '#13131A',
  },
  loadingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 6,
  },
  loadingText: {
    fontSize: 12,
    color: '#70707A',
    fontStyle: 'italic',
  },
  errorText: {
    fontSize: 12,
    color: '#FF3F6C80',
    fontStyle: 'italic',
    paddingVertical: 6,
  },
  explanationText: {
    fontSize: 13,
    color: '#C8C8D4',
    lineHeight: 20,
    paddingTop: 4,
    paddingBottom: 8,
  },
  aiLabelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    marginTop: 2,
  },
  aiDot: {
    width: 5,
    height: 5,
    borderRadius: 3,
    backgroundColor: '#4C4CF0',
  },
  aiLabel: {
    fontSize: 10,
    color: '#4C4CF0',
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
});
