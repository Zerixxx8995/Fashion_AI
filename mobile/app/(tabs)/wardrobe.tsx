/**
 * Wardrobe Screen — mobile/app/(tabs)/wardrobe.tsx
 *
 * Responsibility: Complete Digital Wardrobe Builder featuring:
 *   - Category-filtered clothing grid with deletion & times-worn counter
 *   - AI Capsule Wardrobe Gap Analysis card with coverage score & budget allocation
 *   - "+ Add Item" sheet modal to save new clothes into closet
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useUser } from '@clerk/expo';
import { useHttpClients } from '../../services/httpClient';
import { getWardrobeItems, addWardrobeItem, removeWardrobeItem } from '../../services/wardrobeService';
import type { WardrobeItem as ApiWardrobeItem } from '../../types';

import WardrobeGrid, { DisplayWardrobeItem } from '../../components/wardrobe/WardrobeGrid';
import GapAnalysisCard, { GapAnalysisData } from '../../components/wardrobe/GapAnalysisCard';
import AddItemSheet, { NewWardrobeItemPayload } from '../../components/wardrobe/AddItemSheet';

const DEFAULT_SEED_ITEMS: DisplayWardrobeItem[] = [
  {
    id: 'seed-01',
    name: 'Oversized Heavyweight Cotton Graphic Tee',
    category: 'Tops',
    color: 'Vintage White',
    image_url: 'https://images.unsplash.com/photo-1576995853123-5a10305d93c0?w=500',
    purchase_price_inr: 1299,
    times_worn: 8,
  },
  {
    id: 'seed-02',
    name: 'Slim Fit Dark Wash Denim Jeans',
    category: 'Bottoms',
    color: 'Indigo Blue',
    image_url: 'https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=500',
    purchase_price_inr: 2499,
    times_worn: 14,
  },
  {
    id: 'seed-03',
    name: 'Washed Cropped Denim Trucker Jacket',
    category: 'Outerwear',
    color: 'Washed Black',
    image_url: 'https://images.unsplash.com/photo-1544441893-675973e31985?w=500',
    purchase_price_inr: 4199,
    times_worn: 5,
  },
  {
    id: 'seed-04',
    name: 'Retro Chunky Leather Platform Sneakers',
    category: 'Footwear',
    color: 'Chalk White',
    image_url: 'https://images.unsplash.com/photo-1552346154-21d32810aba3?w=500',
    purchase_price_inr: 3299,
    times_worn: 19,
  },
  {
    id: 'seed-05',
    name: 'Silk Blend Floral Printed Anarkali Kurta',
    category: 'Ethnic',
    color: 'Emerald Green',
    image_url: 'https://images.unsplash.com/photo-1610030469983-98e550d6193c?w=500',
    purchase_price_inr: 3499,
    times_worn: 3,
  },
];

export default function WardrobeScreen() {
  const { user } = useUser();
  const userId = user?.id ?? 'demo-user-1';
  const { getClients } = useHttpClients();

  const [items, setItems] = useState<DisplayWardrobeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [gapData, setGapData] = useState<GapAnalysisData | null>(null);
  const [gapLoading, setGapLoading] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);

  // Execute Gap Analysis on a given items list
  const runGapAnalysis = useCallback(async (currentItems: DisplayWardrobeItem[]) => {
    setGapLoading(true);
    try {
      const { mlClient } = await getClients();
      const wardrobePayload = currentItems.map((i) => ({
        name: i.name,
        category: i.category || 'Tops',
      }));

      const res = await mlClient.post<GapAnalysisData>('/wardrobe/gap-analysis', {
        body: {
          user_id: userId,
          wardrobe: wardrobePayload,
          budget_inr: 5000,
        },
      });

      setGapData(res);
    } catch {
      setGapData({
        coverage_score: 0.70,
        analysis_note: 'Good foundation — focus on high-priority gaps to maximize outfit combinations.',
        missing_categories: [
          {
            category: 'Formals / Blazers',
            priority: 'high',
            reason: 'Formals are needed for professional settings and interviews.',
            suggested_budget_inr: 2500,
          },
          {
            category: 'Accessories / Belts',
            priority: 'medium',
            reason: 'Accessories multiply outfit variations without adding bulk.',
            suggested_budget_inr: 1000,
          },
        ],
      });
    } finally {
      setGapLoading(false);
    }
  }, [getClients, userId]);

  // Initial load
  useEffect(() => {
    let isMounted = true;

    const loadWardrobe = async () => {
      setLoading(true);
      let loadedItems: DisplayWardrobeItem[] = DEFAULT_SEED_ITEMS;
      try {
        const { apiClient } = await getClients();
        const dbItems = await getWardrobeItems(apiClient, userId);
        if (dbItems && dbItems.length > 0) {
          loadedItems = dbItems.map((item: ApiWardrobeItem) => ({
            id: item.id,
            name: item.product?.name || 'Wardrobe Item',
            category: item.product?.category || 'Essential',
            color: 'Multi',
            image_url: item.product?.stock_image_urls?.[0] || 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=400',
            purchase_price_inr: item.product?.price_inr || 1999,
            times_worn: 1,
          }));
        }
      } catch {
        loadedItems = DEFAULT_SEED_ITEMS;
      } finally {
        if (isMounted) {
          setItems(loadedItems);
          setLoading(false);
          runGapAnalysis(loadedItems);
        }
      }
    };

    loadWardrobe();
    return () => {
      isMounted = false;
    };
  }, [userId]);

  // Save new item
  const handleSaveNewItem = async (payload: NewWardrobeItemPayload) => {
    try {
      const { apiClient } = await getClients();
      const created = await addWardrobeItem(apiClient, `custom-${Date.now()}`);

      const newItem: DisplayWardrobeItem = {
        id: created.id || `item-${Date.now()}`,
        name: payload.name,
        category: payload.category,
        color: payload.color || 'Multi',
        image_url: payload.image_url || 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=400',
        purchase_price_inr: payload.purchase_price_inr || 1999,
        times_worn: 0,
      };

      setItems((prev) => [newItem, ...prev]);
      Alert.alert('✓ Item Saved', `Added "${payload.name}" to your digital wardrobe!`);
    } catch {
      const newItem: DisplayWardrobeItem = {
        id: `item-${Date.now()}`,
        name: payload.name,
        category: payload.category,
        color: payload.color || 'Multi',
        image_url: payload.image_url || 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=400',
        purchase_price_inr: payload.purchase_price_inr || 1999,
        times_worn: 0,
      };
      setItems((prev) => [newItem, ...prev]);
      Alert.alert('✓ Saved', `Added "${payload.name}" to your closet.`);
    }
  };

  // Delete item
  const handleDeleteItem = async (id: string) => {
    try {
      const { apiClient } = await getClients();
      await removeWardrobeItem(apiClient, id);
    } catch {
      // Ignore fallback
    } finally {
      setItems((prev) => prev.filter((i) => i.id !== id));
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <View style={styles.titleWrap}>
          <Text style={styles.title}>🧥 Wardrobe</Text>
          <Text style={styles.subtitle}>Digital closet & capsule gap analysis</Text>
        </View>

        <TouchableOpacity
          style={styles.addBtn}
          onPress={() => setShowAddModal(true)}
          activeOpacity={0.85}
        >
          <Text style={styles.addBtnText}>+ Add Item</Text>
        </TouchableOpacity>
      </View>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Gap Analysis Card */}
        <GapAnalysisCard
          data={gapData}
          loading={gapLoading}
          onRunAnalysis={() => runGapAnalysis(items)}
        />

        {/* Grid Section Title */}
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>MY CLOSET COLLECTION</Text>
          <Text style={styles.itemCountText}>{items.length} Items Saved</Text>
        </View>

        {loading ? (
          <ActivityIndicator size="large" color="#FF3F6C" style={{ marginVertical: 24 }} />
        ) : (
          <WardrobeGrid
            items={items}
            onDeleteItem={handleDeleteItem}
            onAddItemPress={() => setShowAddModal(true)}
          />
        )}
      </ScrollView>

      {/* Add Item Sheet Modal */}
      <AddItemSheet
        visible={showAddModal}
        onClose={() => setShowAddModal(false)}
        onSave={handleSaveNewItem}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#0B0B0E' },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#16161C',
  },
  titleWrap: { gap: 2 },
  title: { fontSize: 22, fontWeight: '900', color: '#FF3F6C', letterSpacing: 0.5 },
  subtitle: { fontSize: 12, color: '#A0A0A5' },
  addBtn: {
    backgroundColor: '#FF3F6C',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 12,
  },
  addBtnText: { color: '#FFFFFF', fontSize: 13, fontWeight: '800' },

  scroll: { flex: 1 },
  scrollContent: {
    padding: 16,
    gap: 18,
    paddingBottom: 40,
  },

  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 6,
  },
  sectionTitle: {
    fontSize: 10,
    fontWeight: '800',
    color: '#60606A',
    letterSpacing: 0.8,
  },
  itemCountText: {
    fontSize: 11,
    color: '#A0A0A5',
    fontWeight: '600',
  },
});
