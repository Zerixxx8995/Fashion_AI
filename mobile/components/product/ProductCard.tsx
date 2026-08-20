/**
 * ProductCard — mobile/components/product/ProductCard.tsx
 *
 * Responsibility: Reusable product card component for feeds and carousels.
 */

import React from 'react';
import {
  View,
  Text,
  Image,
  TouchableOpacity,
  StyleSheet,
} from 'react-native';
import { useRouter } from 'expo-router';
import type { Product } from '../../types';

interface ProductCardProps {
  product: Product;
  onPress?: () => void;
}

export default function ProductCard({ product, onPress }: ProductCardProps) {
  const router = useRouter();

  const handlePress = () => {
    if (onPress) {
      onPress();
    } else {
      router.push(`/product/${product.id}`);
    }
  };

  const imageUri =
    product.stock_image_urls?.[0] ||
    'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=400';

  return (
    <TouchableOpacity
      style={styles.card}
      onPress={handlePress}
      activeOpacity={0.85}
    >
      <View style={styles.imageWrap}>
        <Image source={{ uri: imageUri }} style={styles.image} resizeMode="cover" />
        <View style={styles.platformBadge}>
          <Text style={styles.platformText}>
            {(product.platform || 'Myntra').toUpperCase()}
          </Text>
        </View>
      </View>

      <View style={styles.content}>
        {product.brand && <Text style={styles.brand}>{product.brand}</Text>}
        <Text style={styles.name} numberOfLines={2}>
          {product.name}
        </Text>
        <Text style={styles.price}>₹{product.price_inr?.toLocaleString('en-IN')}</Text>
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    width: 170,
    backgroundColor: '#16161C',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#24242E',
    overflow: 'hidden',
  },
  imageWrap: {
    width: '100%',
    height: 180,
    position: 'relative',
    backgroundColor: '#0B0B0E',
  },
  image: {
    width: '100%',
    height: '100%',
  },
  platformBadge: {
    position: 'absolute',
    top: 8,
    left: 8,
    backgroundColor: 'rgba(11,11,14,0.75)',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  platformText: {
    fontSize: 9,
    fontWeight: '800',
    color: '#FF3F6C',
    letterSpacing: 0.5,
  },
  content: {
    padding: 12,
    gap: 4,
  },
  brand: {
    fontSize: 11,
    fontWeight: '700',
    color: '#70707A',
    textTransform: 'uppercase',
  },
  name: {
    fontSize: 13,
    fontWeight: '600',
    color: '#E8E8F0',
    lineHeight: 17,
  },
  price: {
    fontSize: 14,
    fontWeight: '900',
    color: '#FF3F6C',
    marginTop: 2,
  },
});
