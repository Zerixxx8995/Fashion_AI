/**
 * TrustScoreBadge — mobile/components/product/TrustScoreBadge.tsx
 *
 * Responsibility: Renders product trust & authenticity score badge.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

interface TrustScoreBadgeProps {
  score?: number; // 0..1 or 0..100
  label?: string;
  compact?: boolean;
}

export default function TrustScoreBadge({
  score = 0.85,
  label,
  compact = false,
}: TrustScoreBadgeProps) {
  const percentage = score <= 1 ? Math.round(score * 100) : Math.round(score);
  const isHigh = percentage >= 75;
  const isModerate = percentage >= 50 && percentage < 75;

  const badgeColor = isHigh ? '#10B981' : isModerate ? '#F59E0B' : '#EF4444';
  const bgColor = isHigh
    ? 'rgba(16,185,129,0.12)'
    : isModerate
    ? 'rgba(245,158,11,0.12)'
    : 'rgba(239,68,68,0.12)';
  const borderColor = isHigh
    ? 'rgba(16,185,129,0.3)'
    : isModerate
    ? 'rgba(245,158,11,0.3)'
    : 'rgba(239,68,68,0.3)';

  const defaultLabel = isHigh
    ? 'Verified Authentic Listing'
    : isModerate
    ? 'Moderate Trust Score'
    : 'Deceptive Listing Risk';

  if (compact) {
    return (
      <View style={[styles.compactBadge, { backgroundColor: bgColor, borderColor }]}>
        <Text style={[styles.compactText, { color: badgeColor }]}>
          ✓ {percentage}% Trust
        </Text>
      </View>
    );
  }

  return (
    <View style={[styles.container, { backgroundColor: bgColor, borderColor }]}>
      <View style={styles.scoreRow}>
        <Text style={styles.starIcon}>🛡️</Text>
        <Text style={[styles.scoreValue, { color: badgeColor }]}>{percentage}%</Text>
        <Text style={styles.scoreTitle}>Listing Trust Score</Text>
      </View>

      <Text style={[styles.statusText, { color: badgeColor }]}>
        {label || defaultLabel}
      </Text>

      <Text style={styles.subtext}>
        Calculated from CLIP stock image match & verified buyer photo reviews
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 16,
    borderRadius: 16,
    borderWidth: 1,
    gap: 6,
  },
  scoreRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  starIcon: {
    fontSize: 18,
  },
  scoreValue: {
    fontSize: 22,
    fontWeight: '900',
  },
  scoreTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#E8E8F0',
  },
  statusText: {
    fontSize: 13,
    fontWeight: '700',
  },
  subtext: {
    fontSize: 11,
    color: '#70707A',
    lineHeight: 15,
  },
  compactBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    borderWidth: 1,
  },
  compactText: {
    fontSize: 11,
    fontWeight: '800',
  },
});
