/**
 * ConfidenceScoreCard — mobile/components/cv/ConfidenceScoreCard.tsx
 *
 * Responsibility: Display the CV confidence scoring result.
 *
 * Shows:
 *   - Animated circular score gauge (0–100%)
 *   - Authenticity verdict (Genuine / Suspicious / Fake)
 *   - Fake review flag indicator
 *   - Matching stock photo thumbnail (if available)
 *   - Computed timestamp
 */

import React, { useEffect, useRef } from 'react';
import {
  View,
  Text,
  Image,
  StyleSheet,
  Animated,
  Easing,
} from 'react-native';
import type { CVScoreResult } from '../../types';

interface ConfidenceScoreCardProps {
  result: CVScoreResult;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getVerdict(score: number): {
  label: string;
  color: string;
  emoji: string;
} {
  if (score >= 0.8) return { label: 'Genuine Match', color: '#22C55E', emoji: '✅' };
  if (score >= 0.5) return { label: 'Partial Match', color: '#F59E0B', emoji: '⚠️' };
  return { label: 'Low Confidence', color: '#EF4444', emoji: '❌' };
}

function formatScore(score: number): string {
  return `${Math.round(score * 100)}%`;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

// ---------------------------------------------------------------------------
// Score gauge — simple animated arc using border-radius tricks + rotation
// ---------------------------------------------------------------------------

function ScoreGauge({ score }: { score: number }) {
  const rotAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(rotAnim, {
      toValue: score,
      duration: 1000,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    }).start();
  }, [score, rotAnim]);

  const { color, label, emoji } = getVerdict(score);
  const scoreText = formatScore(score);

  return (
    <View style={styles.gaugeContainer}>
      {/* Outer ring */}
      <View style={[styles.gaugeRing, { borderColor: '#24242E' }]}>
        {/* Colored fill ring — we cheat with a simple border overlay */}
        <View
          style={[
            styles.gaugeFill,
            {
              borderColor: color,
              // Show arc by clipping with opacity trick
              opacity: score > 0 ? 1 : 0,
            },
          ]}
        />
        {/* Center text */}
        <View style={styles.gaugeCenter}>
          <Text style={[styles.gaugeScore, { color }]}>{scoreText}</Text>
          <Text style={styles.gaugeLabel}>confidence</Text>
        </View>
      </View>
      <Text style={styles.gaugeVerdict}>
        {emoji}  {label}
      </Text>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Main card
// ---------------------------------------------------------------------------

export default function ConfidenceScoreCard({ result }: ConfidenceScoreCardProps) {
  const { color } = getVerdict(result.confidence_score);

  return (
    <View style={styles.card}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>CV Analysis Result</Text>
        <Text style={styles.headerSub}>Powered by CLIP + FAISS</Text>
      </View>

      {/* Score gauge */}
      <ScoreGauge score={result.confidence_score} />

      {/* Divider */}
      <View style={styles.divider} />

      {/* Metrics row */}
      <View style={styles.metricsRow}>
        <View style={styles.metric}>
          <Text style={[styles.metricValue, { color }]}>
            {formatScore(result.confidence_score)}
          </Text>
          <Text style={styles.metricLabel}>Stock Match</Text>
        </View>

        <View style={styles.metricDivider} />

        <View style={styles.metric}>
          <Text
            style={[
              styles.metricValue,
              { color: result.fake_review_flag ? '#EF4444' : '#22C55E' },
            ]}
          >
            {result.fake_review_flag ? 'Flagged' : 'Clean'}
          </Text>
          <Text style={styles.metricLabel}>Review Signal</Text>
        </View>

        <View style={styles.metricDivider} />

        <View style={styles.metric}>
          <Text style={styles.metricValue}>#{result.job_id.slice(-6).toUpperCase()}</Text>
          <Text style={styles.metricLabel}>Job ID</Text>
        </View>
      </View>

      {/* Fake review alert */}
      {result.fake_review_flag && (
        <View style={styles.fakeReviewAlert}>
          <Text style={styles.fakeReviewIcon}>⚠️</Text>
          <Text style={styles.fakeReviewText}>
            Review images appear to mismatch stock photos — possible fake reviews detected.
          </Text>
        </View>
      )}

      {/* Matching stock image */}
      {result.matching_stock_url && (
        <View style={styles.stockImageSection}>
          <Text style={styles.stockImageLabel}>Best Matching Stock Photo</Text>
          <Image
            source={{ uri: result.matching_stock_url }}
            style={styles.stockImage}
            resizeMode="cover"
          />
        </View>
      )}

      {/* Footer */}
      <Text style={styles.computedAt}>Computed: {formatDate(result.computed_at)}</Text>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#16161C',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#24242E',
    padding: 24,
    gap: 16,
  },

  // Header
  header: {
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: '#E8E8F0',
    letterSpacing: 0.3,
  },
  headerSub: {
    fontSize: 12,
    color: '#505058',
    marginTop: 2,
  },

  // Gauge
  gaugeContainer: {
    alignItems: 'center',
    gap: 10,
  },
  gaugeRing: {
    width: 140,
    height: 140,
    borderRadius: 70,
    borderWidth: 8,
    justifyContent: 'center',
    alignItems: 'center',
    position: 'relative',
  },
  gaugeFill: {
    position: 'absolute',
    width: 140,
    height: 140,
    borderRadius: 70,
    borderWidth: 8,
    borderTopColor: 'transparent',
    borderRightColor: 'transparent',
    transform: [{ rotate: '-45deg' }],
  },
  gaugeCenter: {
    alignItems: 'center',
  },
  gaugeScore: {
    fontSize: 32,
    fontWeight: '900',
    letterSpacing: -1,
  },
  gaugeLabel: {
    fontSize: 11,
    color: '#60606A',
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  gaugeVerdict: {
    fontSize: 15,
    color: '#E8E8F0',
    fontWeight: '600',
  },

  // Divider
  divider: {
    height: 1,
    backgroundColor: '#24242E',
  },

  // Metrics
  metricsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignItems: 'center',
  },
  metric: {
    alignItems: 'center',
    flex: 1,
  },
  metricValue: {
    fontSize: 16,
    fontWeight: '800',
    color: '#E8E8F0',
    marginBottom: 2,
  },
  metricLabel: {
    fontSize: 11,
    color: '#505058',
    textAlign: 'center',
  },
  metricDivider: {
    width: 1,
    height: 36,
    backgroundColor: '#24242E',
  },

  // Fake review alert
  fakeReviewAlert: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    backgroundColor: 'rgba(239,68,68,0.1)',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(239,68,68,0.3)',
    padding: 12,
  },
  fakeReviewIcon: {
    fontSize: 16,
  },
  fakeReviewText: {
    flex: 1,
    fontSize: 12,
    color: '#FCA5A5',
    lineHeight: 18,
  },

  // Stock image
  stockImageSection: {
    gap: 8,
  },
  stockImageLabel: {
    fontSize: 12,
    color: '#60606A',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  stockImage: {
    width: '100%',
    height: 160,
    borderRadius: 12,
    backgroundColor: '#0B0B0E',
  },

  // Footer
  computedAt: {
    fontSize: 11,
    color: '#3A3A44',
    textAlign: 'center',
  },
});
