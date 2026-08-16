/**
 * Product Detail Screen — mobile/app/product/[id].tsx
 *
 * Responsibility: Full product detail with confidence score and platform links.
 * Placeholder screen — full implementation in Build Order 21.
 */

import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';

export default function ProductDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();

  return (
    <View style={styles.container}>
      <TouchableOpacity style={styles.backBtn} onPress={() => router.back()}>
        <Text style={styles.backText}>← Back</Text>
      </TouchableOpacity>
      <Text style={styles.title}>Product Detail</Text>
      <Text style={styles.id}>Product ID: {id}</Text>
      <Text style={styles.coming}>Full implementation in Build Order 21</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0B0B0E',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  backBtn: {
    position: 'absolute',
    top: 56,
    left: 16,
  },
  backText: {
    color: '#FF3F6C',
    fontSize: 16,
    fontWeight: '600',
  },
  title: {
    fontSize: 28,
    fontWeight: '900',
    color: '#FF3F6C',
    marginBottom: 8,
    letterSpacing: 1,
  },
  id: {
    fontSize: 14,
    color: '#A0A0A5',
    marginBottom: 24,
    fontFamily: 'monospace',
  },
  coming: {
    fontSize: 13,
    color: '#505058',
    backgroundColor: '#16161C',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#24242E',
  },
});
