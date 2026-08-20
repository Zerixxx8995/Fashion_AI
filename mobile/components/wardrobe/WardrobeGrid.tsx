/**
 * WardrobeGrid — mobile/components/wardrobe/WardrobeGrid.tsx
 *
 * Responsibility: Render categorized grid of user's saved wardrobe items
 * with category filtering, image previews, and item deletion.
 */

import React, { useState } from 'react';
import {
  View,
  Text,
  Image,
  TouchableOpacity,
  FlatList,
  StyleSheet,
  Alert,
} from 'react-native';

export interface DisplayWardrobeItem {
  id: string;
  name: string;
  category?: string | null;
  color?: string | null;
  image_url?: string | null;
  purchase_price_inr?: number | null;
  times_worn?: number;
}

interface WardrobeGridProps {
  items: DisplayWardrobeItem[];
  onDeleteItem: (id: string) => void;
  onAddItemPress: () => void;
}

const CATEGORY_TABS = ['All', 'Tops', 'Bottoms', 'Outerwear', 'Footwear', 'Ethnic', 'Formals'];

export default function WardrobeGrid({
  items,
  onDeleteItem,
  onAddItemPress,
}: WardrobeGridProps) {
  const [selectedCat, setSelectedCat] = useState('All');

  const filteredItems = items.filter((item) => {
    if (selectedCat === 'All') return true;
    const cat = (item.category || '').toLowerCase();
    const tab = selectedCat.toLowerCase();
    return cat.includes(tab) || tab.includes(cat);
  });

  const confirmDelete = (item: DisplayWardrobeItem) => {
    Alert.alert(
      'Remove Item',
      `Are you sure you want to remove "${item.name}" from your wardrobe?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Remove',
          style: 'destructive',
          onPress: () => onDeleteItem(item.id),
        },
      ]
    );
  };

  return (
    <View style={styles.container}>
      {/* Category Tabs Header */}
      <FlatList
        horizontal
        data={CATEGORY_TABS}
        keyExtractor={(item) => item}
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.tabRow}
        renderItem={({ item }) => {
          const isActive = selectedCat === item;
          return (
            <TouchableOpacity
              style={[styles.tabChip, isActive && styles.tabChipActive]}
              onPress={() => setSelectedCat(item)}
              activeOpacity={0.8}
            >
              <Text style={[styles.tabText, isActive && styles.tabTextActive]}>
                {item}
              </Text>
            </TouchableOpacity>
          );
        }}
      />

      {/* Grid List */}
      {filteredItems.length === 0 ? (
        <View style={styles.emptyWrap}>
          <Text style={styles.emptyIcon}>🧥</Text>
          <Text style={styles.emptyTitle}>No items in {selectedCat}</Text>
          <Text style={styles.emptySub}>
            Add items to build your digital capsule wardrobe.
          </Text>
          <TouchableOpacity style={styles.addBtn} onPress={onAddItemPress} activeOpacity={0.85}>
            <Text style={styles.addBtnText}>+ Add First Item</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <View style={styles.gridContainer}>
          {filteredItems.map((item) => {
            const imgUri =
              item.image_url ||
              'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=400';

            return (
              <View key={item.id} style={styles.card}>
                <View style={styles.imageWrap}>
                  <Image source={{ uri: imgUri }} style={styles.image} resizeMode="cover" />
                  <TouchableOpacity
                    style={styles.deleteBadge}
                    onPress={() => confirmDelete(item)}
                    activeOpacity={0.8}
                  >
                    <Text style={styles.deleteIcon}>✕</Text>
                  </TouchableOpacity>
                </View>

                <View style={styles.cardBody}>
                  <Text style={styles.itemName} numberOfLines={1}>
                    {item.name}
                  </Text>
                  <Text style={styles.itemMeta}>
                    {item.category || 'Essential'} • {item.color || 'Multi'}
                  </Text>
                  <View style={styles.cardFooter}>
                    {item.purchase_price_inr ? (
                      <Text style={styles.priceText}>
                        ₹{item.purchase_price_inr.toLocaleString('en-IN')}
                      </Text>
                    ) : (
                      <Text style={styles.priceText}>Saved</Text>
                    )}
                    <Text style={styles.wornCount}>
                      {item.times_worn || 0}× worn
                    </Text>
                  </View>
                </View>
              </View>
            );
          })}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { gap: 14 },
  tabRow: { gap: 8, paddingRight: 16 },
  tabChip: {
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: 20,
    backgroundColor: '#16161C',
    borderWidth: 1,
    borderColor: '#24242E',
  },
  tabChipActive: {
    backgroundColor: 'rgba(255,63,108,0.15)',
    borderColor: '#FF3F6C',
  },
  tabText: { fontSize: 12, color: '#A0A0A5', fontWeight: '600' },
  tabTextActive: { color: '#FF3F6C', fontWeight: '800' },

  emptyWrap: {
    padding: 32,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#16161C',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#24242E',
    gap: 8,
  },
  emptyIcon: { fontSize: 36 },
  emptyTitle: { fontSize: 16, fontWeight: '800', color: '#E8E8F0' },
  emptySub: { fontSize: 12, color: '#70707A', textAlign: 'center', marginBottom: 6 },
  addBtn: {
    backgroundColor: '#FF3F6C',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 12,
  },
  addBtnText: { color: '#FFFFFF', fontSize: 13, fontWeight: '800' },

  gridContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  card: {
    width: '48%',
    backgroundColor: '#16161C',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#24242E',
    overflow: 'hidden',
  },
  imageWrap: {
    width: '100%',
    height: 160,
    position: 'relative',
    backgroundColor: '#0B0B0E',
  },
  image: { width: '100%', height: '100%' },
  deleteBadge: {
    position: 'absolute',
    top: 8,
    right: 8,
    backgroundColor: 'rgba(11,11,14,0.8)',
    width: 24,
    height: 24,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  deleteIcon: { color: '#FF3F6C', fontSize: 12, fontWeight: '900' },
  cardBody: { padding: 10, gap: 3 },
  itemName: { fontSize: 13, fontWeight: '700', color: '#E8E8F0' },
  itemMeta: { fontSize: 10, color: '#70707A' },
  cardFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 4,
  },
  priceText: { fontSize: 12, fontWeight: '800', color: '#FF3F6C' },
  wornCount: { fontSize: 10, color: '#A0A0A5' },
});
