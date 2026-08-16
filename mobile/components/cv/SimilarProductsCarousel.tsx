/**
 * SimilarProductsCarousel — mobile/components/cv/SimilarProductsCarousel.tsx
 *
 * Responsibility: Horizontal scroll list of visually similar cheaper products.
 * Each card shows platform badge, price, similarity score, and a deep-link button.
 *
 * Props:
 *   products  — array of SimilarProduct from POST /cv/similar
 *   loading   — whether the similar products request is in-flight
 */

import React from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  Image,
  Linking,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import type { SimilarProduct, Platform } from '../../types';

// ---------------------------------------------------------------------------
// Platform colour palette (mirrors constants/platforms.ts intent)
// ---------------------------------------------------------------------------

const PLATFORM_COLORS: Record<Platform, { bg: string; text: string; label: string }> = {
  myntra:   { bg: '#FF3F6C22', text: '#FF3F6C', label: 'Myntra' },
  amazon:   { bg: '#FF990022', text: '#FF9900', label: 'Amazon' },
  flipkart: { bg: '#2874F022', text: '#2874F0', label: 'Flipkart' },
  meesho:   { bg: '#9B2D8F22', text: '#9B2D8F', label: 'Meesho' },
  ajio:     { bg: '#D3232322', text: '#D32323', label: 'Ajio' },
};

// ---------------------------------------------------------------------------
// Single product card
// ---------------------------------------------------------------------------

function SimilarProductCard({ product }: { product: SimilarProduct }) {
  const platformStyle = PLATFORM_COLORS[product.platform] ?? {
    bg: '#24242E',
    text: '#A0A0A5',
    label: product.platform,
  };

  const similarityPct = Math.round(product.similarity_score * 100);

  const openLink = () => {
    if (product.url) {
      Linking.openURL(product.url).catch(() => {
        // silently fail — nothing critical
      });
    }
  };

  return (
    <View style={styles.card}>
      {/* Thumbnail */}
      {product.stock_image_url ? (
        <Image
          source={{ uri: product.stock_image_url }}
          style={styles.thumbnail}
          resizeMode="cover"
        />
      ) : (
        <View style={[styles.thumbnail, styles.thumbnailPlaceholder]}>
          <Text style={styles.thumbnailPlaceholderIcon}>👗</Text>
        </View>
      )}

      {/* Platform badge */}
      <View style={[styles.platformBadge, { backgroundColor: platformStyle.bg }]}>
        <Text style={[styles.platformLabel, { color: platformStyle.text }]}>
          {platformStyle.label}
        </Text>
      </View>

      {/* Product name */}
      <Text style={styles.productName} numberOfLines={2}>
        {product.name}
      </Text>

      {/* Price */}
      <Text style={styles.price}>
        ₹{product.price_inr?.toLocaleString('en-IN') ?? 'N/A'}
      </Text>

      {/* Similarity */}
      <View style={styles.similarityRow}>
        <View
          style={[
            styles.similarityBar,
            {
              width: `${similarityPct}%`,
              backgroundColor: similarityPct >= 70 ? '#22C55E' : '#F59E0B',
            },
          ]}
        />
        <Text style={styles.similarityText}>{similarityPct}% similar</Text>
      </View>

      {/* View button */}
      <TouchableOpacity style={styles.viewBtn} onPress={openLink} activeOpacity={0.8}>
        <Text style={styles.viewBtnText}>View on {platformStyle.label} →</Text>
      </TouchableOpacity>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Carousel
// ---------------------------------------------------------------------------

interface SimilarProductsCarouselProps {
  products: SimilarProduct[];
  loading?: boolean;
}

export default function SimilarProductsCarousel({
  products,
  loading = false,
}: SimilarProductsCarouselProps) {
  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator color="#FF3F6C" />
        <Text style={styles.loadingText}>Finding similar products…</Text>
      </View>
    );
  }

  if (!products || products.length === 0) {
    return (
      <View style={styles.emptyContainer}>
        <Text style={styles.emptyIcon}>🔍</Text>
        <Text style={styles.emptyTitle}>No Similar Products Found</Text>
        <Text style={styles.emptyText}>
          We couldn't find cheaper alternatives right now. Try again after the CV scan.
        </Text>
      </View>
    );
  }

  return (
    <View>
      <Text style={styles.sectionTitle}>Similar Products  ·  {products.length} found</Text>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.scrollContent}
      >
        {products.map((p) => (
          <SimilarProductCard key={p.product_id} product={p} />
        ))}
      </ScrollView>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  // Section title
  sectionTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#A0A0A5',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 12,
  },

  // Scroll
  scrollContent: {
    paddingRight: 8,
    gap: 12,
  },

  // Card
  card: {
    width: 180,
    backgroundColor: '#16161C',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#24242E',
    padding: 12,
    gap: 8,
  },
  thumbnail: {
    width: '100%',
    height: 140,
    borderRadius: 10,
    backgroundColor: '#0B0B0E',
  },
  thumbnailPlaceholder: {
    justifyContent: 'center',
    alignItems: 'center',
  },
  thumbnailPlaceholderIcon: {
    fontSize: 36,
  },

  // Platform badge
  platformBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  platformLabel: {
    fontSize: 10,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },

  // Text
  productName: {
    fontSize: 12,
    color: '#C8C8D0',
    lineHeight: 16,
  },
  price: {
    fontSize: 16,
    fontWeight: '800',
    color: '#E8E8F0',
  },

  // Similarity bar
  similarityRow: {
    gap: 4,
  },
  similarityBar: {
    height: 3,
    borderRadius: 2,
    backgroundColor: '#22C55E',
    maxWidth: '100%',
  },
  similarityText: {
    fontSize: 10,
    color: '#505058',
  },

  // View button
  viewBtn: {
    paddingVertical: 8,
    borderRadius: 10,
    backgroundColor: 'rgba(255,63,108,0.1)',
    borderWidth: 1,
    borderColor: 'rgba(255,63,108,0.25)',
    alignItems: 'center',
  },
  viewBtnText: {
    fontSize: 11,
    fontWeight: '700',
    color: '#FF3F6C',
  },

  // Loading / Empty states
  loadingContainer: {
    alignItems: 'center',
    padding: 24,
    gap: 10,
  },
  loadingText: {
    color: '#60606A',
    fontSize: 13,
  },
  emptyContainer: {
    alignItems: 'center',
    padding: 24,
    gap: 8,
    backgroundColor: '#16161C',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#24242E',
  },
  emptyIcon: {
    fontSize: 32,
  },
  emptyTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#E8E8F0',
  },
  emptyText: {
    fontSize: 12,
    color: '#505058',
    textAlign: 'center',
    lineHeight: 18,
  },
});
