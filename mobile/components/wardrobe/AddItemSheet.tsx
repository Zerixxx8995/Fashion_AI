/**
 * AddItemSheet — mobile/components/wardrobe/AddItemSheet.tsx
 *
 * Responsibility: Modal form allowing users to add custom clothes
 * into their digital wardrobe.
 */

import React, { useState } from 'react';
import {
  Modal,
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';

export interface NewWardrobeItemPayload {
  name: string;
  category: string;
  color?: string;
  purchase_price_inr?: number;
  image_url?: string;
}

interface AddItemSheetProps {
  visible: boolean;
  onClose: () => void;
  onSave: (payload: NewWardrobeItemPayload) => Promise<void>;
}

const CATEGORIES = ['Tops', 'Bottoms', 'Outerwear', 'Footwear', 'Ethnic', 'Formals', 'Accessories'];

export default function AddItemSheet({
  visible,
  onClose,
  onSave,
}: AddItemSheetProps) {
  const [name, setName] = useState('');
  const [category, setCategory] = useState('Tops');
  const [color, setColor] = useState('');
  const [price, setPrice] = useState('');
  const [imageUrl, setImageUrl] = useState('');
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      await onSave({
        name: name.trim(),
        category,
        color: color.trim() || undefined,
        purchase_price_inr: price ? parseInt(price, 10) : undefined,
        image_url: imageUrl.trim() || undefined,
      });
      // Reset form
      setName('');
      setColor('');
      setPrice('');
      setImageUrl('');
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal visible={visible} animationType="slide" transparent>
      <View style={styles.overlay}>
        <View style={styles.sheet}>
          <View style={styles.header}>
            <Text style={styles.title}>+ Add Wardrobe Item</Text>
            <TouchableOpacity onPress={onClose} style={styles.closeBtn}>
              <Text style={styles.closeText}>✕</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.form}>
            <Text style={styles.label}>ITEM NAME *</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. Vintage Wash Denim Jacket"
              placeholderTextColor="#505058"
              value={name}
              onChangeText={setName}
            />

            <Text style={styles.label}>CATEGORY</Text>
            <View style={styles.catRow}>
              {CATEGORIES.map((cat) => (
                <TouchableOpacity
                  key={cat}
                  style={[styles.catChip, category === cat && styles.catChipActive]}
                  onPress={() => setCategory(cat)}
                >
                  <Text style={[styles.catText, category === cat && styles.catTextActive]}>
                    {cat}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <View style={styles.row}>
              <View style={{ flex: 1, gap: 4 }}>
                <Text style={styles.label}>COLOR</Text>
                <TextInput
                  style={styles.input}
                  placeholder="e.g. Indigo Blue"
                  placeholderTextColor="#505058"
                  value={color}
                  onChangeText={setColor}
                />
              </View>

              <View style={{ flex: 1, gap: 4 }}>
                <Text style={styles.label}>PRICE (₹)</Text>
                <TextInput
                  style={styles.input}
                  placeholder="e.g. 2499"
                  placeholderTextColor="#505058"
                  keyboardType="numeric"
                  value={price}
                  onChangeText={setPrice}
                />
              </View>
            </View>

            <Text style={styles.label}>IMAGE URL (OPTIONAL)</Text>
            <TextInput
              style={styles.input}
              placeholder="https://images.unsplash.com/..."
              placeholderTextColor="#505058"
              value={imageUrl}
              onChangeText={setImageUrl}
            />

            <TouchableOpacity
              style={[styles.saveBtn, !name.trim() && styles.saveBtnDisabled]}
              onPress={handleSave}
              disabled={!name.trim() || saving}
              activeOpacity={0.85}
            >
              {saving ? (
                <ActivityIndicator color="#FFFFFF" size="small" />
              ) : (
                <Text style={styles.saveBtnText}>Save to Wardrobe</Text>
              )}
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: '#16161C',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: 20,
    gap: 16,
    borderWidth: 1,
    borderColor: '#24242E',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  title: { fontSize: 18, fontWeight: '900', color: '#FF3F6C' },
  closeBtn: { padding: 4 },
  closeText: { fontSize: 16, color: '#A0A0A5', fontWeight: '800' },

  form: { gap: 12 },
  label: { fontSize: 10, fontWeight: '800', color: '#60606A', letterSpacing: 0.8 },
  input: {
    backgroundColor: '#0B0B0E',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#24242E',
    paddingHorizontal: 14,
    paddingVertical: 10,
    color: '#E8E8F0',
    fontSize: 13,
  },
  catRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  catChip: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 8,
    backgroundColor: '#0B0B0E',
    borderWidth: 1,
    borderColor: '#24242E',
  },
  catChipActive: { backgroundColor: 'rgba(255,63,108,0.15)', borderColor: '#FF3F6C' },
  catText: { fontSize: 11, color: '#A0A0A5', fontWeight: '600' },
  catTextActive: { color: '#FF3F6C', fontWeight: '800' },

  row: { flexDirection: 'row', gap: 12 },
  saveBtn: {
    backgroundColor: '#FF3F6C',
    height: 48,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 8,
  },
  saveBtnDisabled: { opacity: 0.5 },
  saveBtnText: { color: '#FFFFFF', fontSize: 14, fontWeight: '800' },
});
