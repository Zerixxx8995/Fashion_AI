/**
 * Trends Discovery Feed Screen — mobile/app/(tabs)/index.tsx
 *
 * Responsibility: Main tab homepage displaying trending clothing items.
 * Includes horizontal filters for categories and fetches signals from FastApi.
 */

import React, { useEffect, useState } from 'react';
import {
  StyleSheet,
  Text,
  View,
  SafeAreaView,
  ScrollView,
  TouchableOpacity,
  StatusBar,
} from 'react-native';
import { useHttpClients } from '../../services/httpClient';
import { getTrends } from '../../services/trendsService';
import type { TrendItem } from '../../types';
import TrendFeed from '../../components/trends/TrendFeed';

// Categories supported in filters
const FILTER_CATEGORIES = [
  { id: 'all', label: '⚡ All Trends' },
  { id: 'tops', label: 'Tops' },
  { id: 'tshirts', label: 'T-Shirts' },
  { id: 'kurtas', label: 'Kurtas & Ethnic' },
  { id: 'dresses', label: 'Dresses' },
  { id: 'jeans', label: 'Denims & Jeans' },
  { id: 'sneakers', label: 'Sneakers' },
  { id: 'footwear', label: 'Casual Footwear' },
  { id: 'accessories', label: 'Accessories' },
  { id: 'bottomwear', label: 'Bottomwear' },
];

export default function DiscoverTrendsScreen() {
  const { getClients } = useHttpClients();

  const [trends, setTrends] = useState<TrendItem[]>([]);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [isLoading, setIsLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchTrends = async (cat: string, isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setIsLoading(true);
    setErrorMsg(null);

    try {
      const { mlClient } = await getClients();
      // If 'all' category is selected, pass undefined to fetch all
      const categoryFilter = cat === 'all' ? undefined : cat;
      const response = await getTrends(mlClient, {
        category: categoryFilter,
        limit: 25,
      });

      setTrends(response.trends || []);
    } catch (err: any) {
      console.error('[DiscoverTrends] Failed to fetch trends:', err);
      setErrorMsg(err?.apiError?.detail || err?.message || 'Failed to load trends.');
    } finally {
      setIsLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchTrends(selectedCategory);
  }, [selectedCategory]);

  const handleRefresh = () => {
    fetchTrends(selectedCategory, true);
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar barStyle="light-content" backgroundColor="#0B0B0E" />
      <View style={styles.container}>
        {/* Premium Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.headerTitle}>ZEST</Text>
            <Text style={styles.headerSubtitle}>Discover Indian Fashion Trends</Text>
          </View>
          <View style={styles.liveIndicator}>
            <View style={styles.liveDot} />
            <Text style={styles.liveText}>LIVE</Text>
          </View>
        </View>

        {/* Horizontal Scroll Categories Filters */}
        <View style={styles.filterWrapper}>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.filterScroll}
          >
            {FILTER_CATEGORIES.map((cat) => {
              const isSelected = selectedCategory === cat.id;
              return (
                <TouchableOpacity
                  key={cat.id}
                  onPress={() => setSelectedCategory(cat.id)}
                  style={[
                    styles.filterChip,
                    isSelected && styles.filterChipSelected,
                  ]}
                  activeOpacity={0.8}
                >
                  <Text
                    style={[
                      styles.filterLabel,
                      isSelected && styles.filterLabelSelected,
                    ]}
                  >
                    {cat.label}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </ScrollView>
        </View>

        {/* Error Alert Info box */}
        {errorMsg && (
          <View style={styles.errorContainer}>
            <Text style={styles.errorText}>{errorMsg}</Text>
          </View>
        )}

        {/* Scrollable Trend Feed list */}
        <TrendFeed
          trends={trends}
          isLoading={isLoading}
          refreshing={refreshing}
          onRefresh={handleRefresh}
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#0B0B0E',
  },
  container: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderColor: '#16161C',
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: '900',
    color: '#FF3F6C',
    letterSpacing: 2,
  },
  headerSubtitle: {
    fontSize: 12,
    color: '#A0A0A5',
    marginTop: 2,
  },
  liveIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#EF444415',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    borderWidth: 0.5,
    borderColor: '#EF444455',
  },
  liveDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#EF4444',
    marginRight: 6,
  },
  liveText: {
    fontSize: 10,
    fontWeight: 'bold',
    color: '#EF4444',
    letterSpacing: 0.5,
  },
  filterWrapper: {
    backgroundColor: '#0B0B0E',
    borderBottomWidth: 1,
    borderColor: '#16161C',
  },
  filterScroll: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    gap: 8,
  },
  filterChip: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: '#16161C',
    borderWidth: 1,
    borderColor: '#24242E',
  },
  filterChipSelected: {
    backgroundColor: '#FF3F6C',
    borderColor: '#FF3F6C',
  },
  filterLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: '#A0A0A5',
  },
  filterLabelSelected: {
    color: '#FFF',
  },
  errorContainer: {
    backgroundColor: '#EF444415',
    padding: 12,
    marginHorizontal: 16,
    marginTop: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#EF444444',
  },
  errorText: {
    color: '#EF4444',
    fontSize: 13,
    textAlign: 'center',
  },
});
