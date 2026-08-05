/**
 * TrendCard Component — mobile/components/trends/TrendCard.tsx
 *
 * Responsibility: Render a premium card displaying fashion trend analytics.
 * Includes score indicator, platform badges, product count, and image cover.
 */

import React from 'react';
import { StyleSheet, Text, View, Image, TouchableOpacity } from 'react-native';
import type { TrendItem } from '../../types';
import LifecycleBadge from './LifecycleBadge';
import { PLATFORMS } from '../../constants/platforms';

interface TrendCardProps {
  trend: TrendItem;
  onPress?: () => void;
}

export default function TrendCard({ trend, onPress }: TrendCardProps) {
  // Format trend score to percentage display (e.g. 0.85 -> 85%)
  const percentageScore = Math.round(trend.trend_score * 100);

  return (
    <TouchableOpacity
      activeOpacity={0.85}
      onPress={onPress}
      style={styles.card}
    >
      {/* Cover Image with gradient overlay placeholder */}
      <View style={styles.imageContainer}>
        {trend.representative_image_url ? (
          <Image
            source={{ uri: trend.representative_image_url }}
            style={styles.image}
            resizeMode="cover"
          />
        ) : (
          <View style={styles.placeholderImage}>
            <Text style={styles.placeholderText}>
              {trend.category.substring(0, 2).toUpperCase()}
            </Text>
          </View>
        )}
        <View style={styles.badgeOverlay}>
          <LifecycleBadge stage={trend.lifecycle_stage} />
        </View>
      </View>

      {/* Card Content details */}
      <View style={styles.content}>
        <View style={styles.titleRow}>
          <Text style={styles.categoryTitle}>{trend.category}</Text>
          <View style={styles.scoreContainer}>
            <Text style={styles.scoreText}>{percentageScore}%</Text>
            <Text style={styles.scoreLabel}>Score</Text>
          </View>
        </View>

        <Text style={styles.productCount}>
          {trend.product_count} listings indexed & analyzed
        </Text>

        <View style={styles.footer}>
          <View style={styles.platformsRow}>
            {trend.platforms.map((plat) => {
              const config = PLATFORMS[plat];
              if (!config) return null;
              return (
                <View
                  key={plat}
                  style={[styles.platformBadge, { backgroundColor: `${config.color}20` }]}
                >
                  <Text style={[styles.platformText, { color: config.color }]}>
                    {config.displayName}
                  </Text>
                </View>
              );
            })}
          </View>
        </View>
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#16161C',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#24242E',
    marginBottom: 20,
    overflow: 'hidden',
  },
  imageContainer: {
    height: 180,
    width: '100%',
    backgroundColor: '#0B0B0E',
    position: 'relative',
  },
  image: {
    width: '100%',
    height: '100%',
  },
  placeholderImage: {
    width: '100%',
    height: '100%',
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#1A1A24',
  },
  placeholderText: {
    color: '#FF3F6C',
    fontSize: 40,
    fontWeight: 'bold',
    letterSpacing: 2,
  },
  badgeOverlay: {
    position: 'absolute',
    top: 12,
    left: 12,
  },
  content: {
    padding: 16,
  },
  titleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  categoryTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#FFF',
    textTransform: 'capitalize',
    flex: 1,
  },
  scoreContainer: {
    alignItems: 'flex-end',
    backgroundColor: '#FF3F6C10',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#FF3F6C33',
  },
  scoreText: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#FF3F6C',
  },
  scoreLabel: {
    fontSize: 9,
    color: '#A0A0A5',
    textTransform: 'uppercase',
    fontWeight: '600',
  },
  productCount: {
    fontSize: 13,
    color: '#707075',
    marginTop: 6,
    marginBottom: 16,
  },
  footer: {
    borderTopWidth: 1,
    borderColor: '#24242E',
    paddingTop: 12,
  },
  platformsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  platformBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  platformText: {
    fontSize: 11,
    fontWeight: '700',
  },
});
