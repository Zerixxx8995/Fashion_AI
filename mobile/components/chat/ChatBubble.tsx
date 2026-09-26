/**
 * ChatBubble — mobile/components/chat/ChatBubble.tsx
 *
 * Responsibility: Render a single chat message bubble.
 * User messages are right-aligned (accent color).
 * Assistant messages are left-aligned (dark surface) with optional inline product cards.
 *
 * Architecture rules:
 *   - Pure display component — no state, no network calls
 *   - Products are rendered as compact inline cards if provided
 *   - Timestamps are rendered in 12h format
 */

import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Linking,
} from 'react-native';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ProductCited {
  name: string;
  price_inr: number;
  platform: string;
  url: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  products_cited?: ProductCited[];
  tools_called?: string[];
  timestamp?: number;
}

interface ChatBubbleProps {
  message: ChatMessage;
}

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function formatTime(ts?: number): string {
  if (!ts) return '';
  const d = new Date(ts);
  return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true });
}

function formatPrice(price: number): string {
  return `₹${price.toLocaleString('en-IN')}`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ChatBubble({ message }: ChatBubbleProps) {
  const isUser = message.role === 'user';

  return (
    <View style={[styles.row, isUser ? styles.rowRight : styles.rowLeft]}>
      {/* Assistant avatar dot */}
      {!isUser && <View style={styles.avatarDot} />}

      <View style={styles.bubbleWrapper}>
        {/* Main bubble */}
        <View style={[styles.bubble, isUser ? styles.userBubble : styles.assistantBubble]}>
          <Text style={[styles.messageText, isUser ? styles.userText : styles.assistantText]}>
            {message.content}
          </Text>
        </View>

        {/* Inline product cards — only for assistant messages */}
        {!isUser && message.products_cited && message.products_cited.length > 0 && (
          <View style={styles.productsContainer}>
            {message.products_cited.map((product, idx) => (
              <ProductCard key={`${product.url}-${idx}`} product={product} />
            ))}
          </View>
        )}

        {/* Timestamp */}
        {message.timestamp && (
          <Text style={[styles.timestamp, isUser ? styles.timestampRight : styles.timestampLeft]}>
            {formatTime(message.timestamp)}
          </Text>
        )}
      </View>
    </View>
  );
}

// ---------------------------------------------------------------------------
// Inline ProductCard — shown below assistant bubble
// ---------------------------------------------------------------------------

function ProductCard({ product }: { product: ProductCited }) {
  const handlePress = () => {
    if (product.url) {
      Linking.openURL(product.url).catch(() => {});
    }
  };

  const platformColor = PLATFORM_COLORS[product.platform.toLowerCase()] ?? '#505058';

  return (
    <TouchableOpacity
      style={styles.productCard}
      onPress={handlePress}
      activeOpacity={0.8}
      accessibilityRole="link"
      accessibilityLabel={`${product.name} on ${product.platform} for ${product.price_inr} rupees`}
    >
      <View style={styles.productCardContent}>
        <View style={[styles.platformBadge, { backgroundColor: platformColor + '22' }]}>
          <Text style={[styles.platformText, { color: platformColor }]}>
            {product.platform.toUpperCase()}
          </Text>
        </View>
        <Text style={styles.productName} numberOfLines={2}>
          {product.name}
        </Text>
        <Text style={styles.productPrice}>{formatPrice(product.price_inr)}</Text>
      </View>
      <Text style={styles.productArrow}>→</Text>
    </TouchableOpacity>
  );
}

const PLATFORM_COLORS: Record<string, string> = {
  myntra: '#FF3F6C',
  amazon: '#FF9900',
  flipkart: '#2874F0',
  meesho: '#9C27B0',
  ajio: '#00A896',
};

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    marginVertical: 4,
    paddingHorizontal: 16,
    alignItems: 'flex-end',
  },
  rowLeft: {
    justifyContent: 'flex-start',
  },
  rowRight: {
    justifyContent: 'flex-end',
  },
  avatarDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#FF3F6C',
    marginRight: 8,
    marginBottom: 6,
  },
  bubbleWrapper: {
    maxWidth: '80%',
  },
  bubble: {
    borderRadius: 16,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  userBubble: {
    backgroundColor: '#FF3F6C',
    borderBottomRightRadius: 4,
  },
  assistantBubble: {
    backgroundColor: '#1C1C26',
    borderBottomLeftRadius: 4,
    borderWidth: 1,
    borderColor: '#24242E',
  },
  messageText: {
    fontSize: 14,
    lineHeight: 20,
  },
  userText: {
    color: '#FFFFFF',
    fontWeight: '500',
  },
  assistantText: {
    color: '#E0E0EC',
  },
  timestamp: {
    fontSize: 10,
    color: '#505058',
    marginTop: 4,
  },
  timestampRight: {
    textAlign: 'right',
  },
  timestampLeft: {
    textAlign: 'left',
    marginLeft: 2,
  },
  // Product cards
  productsContainer: {
    marginTop: 6,
    gap: 6,
  },
  productCard: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: '#13131A',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#24242E',
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  productCardContent: {
    flex: 1,
    gap: 4,
  },
  platformBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  platformText: {
    fontSize: 9,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  productName: {
    fontSize: 12,
    color: '#C8C8D4',
    fontWeight: '500',
    lineHeight: 16,
  },
  productPrice: {
    fontSize: 13,
    color: '#FF3F6C',
    fontWeight: '700',
  },
  productArrow: {
    fontSize: 16,
    color: '#505058',
    marginLeft: 8,
  },
});
