/**
 * Discover Screen — mobile/app/(tabs)/discover.tsx
 *
 * Responsibility: Personalised style recommendations by body type and aesthetic taste.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  Image,
  StyleSheet,
  ActivityIndicator,
  FlatList,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { useHttpClients } from '../../services/httpClient';

interface RecommendationItem {
  id: string;
  name: string;
  brand: string;
  price_inr: number;
  platform: string;
  image_url: string;
  match_score: number;
  reason: string;
}

const BODY_TYPES = ['Hourglass', 'Rectangle', 'Athletic', 'Pear', 'Oval'];
const AESTHETICS = ['Streetwear', 'Minimalist', 'Ethnic Fusion', 'Vintage', 'Y2K'];

export default function DiscoverScreen() {
  const router = useRouter();
  const { getClients } = useHttpClients();

  const [selectedBodyType, setSelectedBodyType] = useState('Hourglass');
  const [selectedAesthetic, setSelectedAesthetic] = useState('Streetwear');
  const [items, setItems] = useState<RecommendationItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    const fetchRecommendations = async () => {
      setLoading(true);
      try {
        const { mlClient } = await getClients();
        const res = await mlClient.post<{ recommendations: RecommendationItem[] }>('/recommendations', {
          body: {
            body_type: selectedBodyType,
            taste_preferences: [selectedAesthetic],
            limit: 10,
          },
        });
        if (isMounted) setItems(res.recommendations || []);
      } catch {
        if (isMounted) {
          setItems([
            {
              id: 'rec-01',
              name: 'High-Waist Wide Leg Cargo Trousers',
              brand: 'Zara',
              price_inr: 2990,
              platform: 'myntra',
              image_url: 'https://images.unsplash.com/photo-1517445312882-bc9910d016b7?w=600',
              match_score: 0.94,
              reason: 'Accentuates waist definition while providing relaxed leg comfort.',
            },
            {
              id: 'rec-02',
              name: 'Oversized Heavyweight Cotton Graphic Hoodie',
              brand: 'H&M',
              price_inr: 2299,
              platform: 'ajio',
              image_url: 'https://images.unsplash.com/photo-1556905055-8f358a7a47b2?w=600',
              match_score: 0.88,
              reason: 'Relaxed drop-shoulder silhouette matching urban streetwear trends.',
            },
          ]);
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchRecommendations();
    return () => {
      isMounted = false;
    };
  }, [selectedBodyType, selectedAesthetic]);

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.container}>
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>✦ Discover</Text>
          <Text style={styles.subtitle}>Personalised recommendations for your silhouette</Text>
        </View>

        {/* Body Type Filter Selector */}
        <View style={styles.filterSection}>
          <Text style={styles.filterLabel}>BODY TYPE SILHOUETTE</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipRow}>
            {BODY_TYPES.map((bt) => (
              <TouchableOpacity
                key={bt}
                style={[styles.chip, selectedBodyType === bt && styles.chipActive]}
                onPress={() => setSelectedBodyType(bt)}
                activeOpacity={0.8}
              >
                <Text style={[styles.chipText, selectedBodyType === bt && styles.chipTextActive]}>
                  {bt}
                </Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>

        {/* Aesthetic Taste Filter Selector */}
        <View style={styles.filterSection}>
          <Text style={styles.filterLabel}>STYLE AESTHETIC</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chipRow}>
            {AESTHETICS.map((aes) => (
              <TouchableOpacity
                key={aes}
                style={[styles.chip, selectedAesthetic === aes && styles.chipActive]}
                onPress={() => setSelectedAesthetic(aes)}
                activeOpacity={0.8}
              >
                <Text style={[styles.chipText, selectedAesthetic === aes && styles.chipTextActive]}>
                  {aes}
                </Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>

        {/* Recommendations List */}
        {loading ? (
          <View style={styles.loadingWrap}>
            <ActivityIndicator size="large" color="#FF3F6C" />
            <Text style={styles.loadingText}>Curating your personalised style match…</Text>
          </View>
        ) : (
          <FlatList
            data={items}
            keyExtractor={(item) => item.id}
            contentContainerStyle={styles.listContent}
            showsVerticalScrollIndicator={false}
            renderItem={({ item }) => (
              <TouchableOpacity
                style={styles.card}
                onPress={() => router.push(`/product/${item.id}`)}
                activeOpacity={0.85}
              >
                <Image source={{ uri: item.image_url }} style={styles.cardImage} resizeMode="cover" />
                <View style={styles.cardInfo}>
                  <View style={styles.cardHeader}>
                    <Text style={styles.matchBadge}>
                      ⚡ {Math.round(item.match_score * 100)}% Match
                    </Text>
                    <Text style={styles.platformBadge}>{(item.platform || 'myntra').toUpperCase()}</Text>
                  </View>
                  <Text style={styles.brand}>{item.brand}</Text>
                  <Text style={styles.name} numberOfLines={2}>
                    {item.name}
                  </Text>
                  <Text style={styles.reason} numberOfLines={2}>
                    💡 {item.reason}
                  </Text>
                  <Text style={styles.price}>₹{item.price_inr.toLocaleString('en-IN')}</Text>
                </View>
              </TouchableOpacity>
            )}
          />
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#0B0B0E' },
  container: { flex: 1, paddingHorizontal: 16 },
  header: { marginVertical: 12, gap: 2 },
  title: { fontSize: 24, fontWeight: '900', color: '#FF3F6C', letterSpacing: 0.5 },
  subtitle: { fontSize: 13, color: '#A0A0A5' },

  filterSection: { marginBottom: 12, gap: 6 },
  filterLabel: { fontSize: 10, fontWeight: '800', color: '#60606A', letterSpacing: 0.8 },
  chipRow: { gap: 8, paddingRight: 16 },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: 20,
    backgroundColor: '#16161C',
    borderWidth: 1,
    borderColor: '#24242E',
  },
  chipActive: {
    backgroundColor: 'rgba(255,63,108,0.15)',
    borderColor: '#FF3F6C',
  },
  chipText: { fontSize: 12, color: '#A0A0A5', fontWeight: '600' },
  chipTextActive: { color: '#FF3F6C', fontWeight: '800' },

  loadingWrap: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: 12 },
  loadingText: { color: '#70707A', fontSize: 13 },

  listContent: { gap: 14, paddingBottom: 30, paddingTop: 6 },
  card: {
    flexDirection: 'row',
    backgroundColor: '#16161C',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#24242E',
    overflow: 'hidden',
  },
  cardImage: { width: 120, height: 150 },
  cardInfo: { flex: 1, padding: 12, justifyContent: 'space-between' },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  matchBadge: { fontSize: 11, fontWeight: '800', color: '#10B981' },
  platformBadge: { fontSize: 9, fontWeight: '800', color: '#FF3F6C' },
  brand: { fontSize: 10, fontWeight: '700', color: '#70707A', textTransform: 'uppercase' },
  name: { fontSize: 14, fontWeight: '700', color: '#E8E8F0' },
  reason: { fontSize: 11, color: '#90909A', lineHeight: 15 },
  price: { fontSize: 16, fontWeight: '900', color: '#FFFFFF' },
});
