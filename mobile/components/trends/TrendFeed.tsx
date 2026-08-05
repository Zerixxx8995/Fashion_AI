/**
 * TrendFeed Component — mobile/components/trends/TrendFeed.tsx
 *
 * Responsibility: Renders a scrollable feed list of TrendCards.
 * Manages loading spinners, empty states, and Pull-to-Refresh controllers.
 */

import React from 'react';
import {
  FlatList,
  StyleSheet,
  Text,
  View,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import type { TrendItem } from '../../types';
import TrendCard from './TrendCard';

interface TrendFeedProps {
  trends: TrendItem[];
  isLoading: boolean;
  refreshing: boolean;
  onRefresh: () => void;
  onSelectTrend?: (trend: TrendItem) => void;
}

export default function TrendFeed({
  trends,
  isLoading,
  refreshing,
  onRefresh,
  onSelectTrend,
}: TrendFeedProps) {
  if (isLoading && trends.length === 0) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#FF3F6C" />
        <Text style={styles.loadingText}>Analyzing social signals & price feeds...</Text>
      </View>
    );
  }

  return (
    <FlatList
      data={trends}
      keyExtractor={(item) => item.category}
      renderItem={({ item }) => (
        <TrendCard
          trend={item}
          onPress={() => onSelectTrend?.(item)}
        />
      )}
      contentContainerStyle={styles.listContent}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={onRefresh}
          tintColor="#FF3F6C"
          colors={['#FF3F6C']}
          progressBackgroundColor="#16161C"
        />
      }
      ListEmptyComponent={
        <View style={styles.emptyContainer}>
          <Text style={styles.emptyTitle}>No Social Signals Found</Text>
          <Text style={styles.emptySubtitle}>
            We couldn't detect active fashion trends. Pull down to refresh or check back later.
          </Text>
        </View>
      }
    />
  );
}

const styles = StyleSheet.create({
  listContent: {
    padding: 16,
    paddingBottom: 32,
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
    backgroundColor: '#0B0B0E',
  },
  loadingText: {
    color: '#A0A0A5',
    fontSize: 14,
    marginTop: 16,
    textAlign: 'center',
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 80,
    paddingHorizontal: 24,
  },
  emptyTitle: {
    color: '#FFF',
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  emptySubtitle: {
    color: '#707075',
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 20,
  },
});
