/**
 * LifecycleBadge Component — mobile/components/trends/LifecycleBadge.tsx
 *
 * Responsibility: Display the trend lifecycle stage with premium,
 * high-contrast visual status indicators.
 *
 * Stages:
 *   - emerging: Rising trend popularity (Vibrant Emerald Green)
 *   - peaking: Peak popularity (Electric Purple/Violet)
 *   - dying: Fading popularity (Warm Amber/Orange)
 */

import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import type { LifecycleStage } from '../../types';

interface LifecycleBadgeProps {
  stage: LifecycleStage;
}

const STAGE_CONFIG = {
  emerging: {
    label: 'Emerging',
    textColor: '#10B981',
    bgColor: '#10B9811A',
    borderColor: '#10B98133',
  },
  peaking: {
    label: 'Peaking',
    textColor: '#8B5CF6',
    bgColor: '#8B5CF61A',
    borderColor: '#8B5CF633',
  },
  dying: {
    label: 'Fading',
    textColor: '#EF4444',
    bgColor: '#EF44441A',
    borderColor: '#EF444433',
  },
};

export default function LifecycleBadge({ stage }: LifecycleBadgeProps) {
  const config = STAGE_CONFIG[stage] || STAGE_CONFIG.emerging;

  return (
    <View
      style={[
        styles.badge,
        {
          backgroundColor: config.bgColor,
          borderColor: config.borderColor,
        },
      ]}
    >
      <View style={[styles.dot, { backgroundColor: config.textColor }]} />
      <Text style={[styles.text, { color: config.textColor }]}>{config.label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 9999,
    borderWidth: 1,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginRight: 6,
  },
  text: {
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.5,
    textTransform: 'uppercase',
  },
});
