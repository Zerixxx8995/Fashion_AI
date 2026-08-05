/**
 * Platform Constants — mobile/constants/platforms.ts
 *
 * Centralises all platform-specific configuration for the 5 supported
 * Indian fashion e-commerce platforms.
 *
 * Used by:
 *   - Product detail screen (deep link / open product URL)
 *   - Trends feed (platform badge colours)
 *   - CV scan (attribution labels)
 */

import type { Platform } from '../types';

export interface PlatformConfig {
  /** Canonical platform identifier (matches Product.platform DB field) */
  id: Platform;
  /** Human-readable display name */
  displayName: string;
  /** Brand colour (hex) for platform badges and UI accents */
  color: string;
  /** URL hostname — used to detect which platform a URL belongs to */
  hostname: string;
  /** Deep-link scheme prefix (if available) */
  appScheme?: string;
}

export const PLATFORMS: Record<Platform, PlatformConfig> = {
  myntra: {
    id: 'myntra',
    displayName: 'Myntra',
    color: '#FF3F6C',
    hostname: 'www.myntra.com',
    appScheme: 'myntra://',
  },
  amazon: {
    id: 'amazon',
    displayName: 'Amazon',
    color: '#FF9900',
    hostname: 'www.amazon.in',
  },
  flipkart: {
    id: 'flipkart',
    displayName: 'Flipkart',
    color: '#2874F0',
    hostname: 'www.flipkart.com',
  },
  meesho: {
    id: 'meesho',
    displayName: 'Meesho',
    color: '#F43397',
    hostname: 'www.meesho.com',
  },
  ajio: {
    id: 'ajio',
    displayName: 'AJIO',
    color: '#ED1C24',
    hostname: 'www.ajio.com',
  },
};

/** Ordered list of all platforms for rendering lists/pickers. */
export const ALL_PLATFORMS: PlatformConfig[] = Object.values(PLATFORMS);

/**
 * Detect which platform a product URL belongs to.
 * Returns null if no match found.
 */
export function detectPlatform(url: string): Platform | null {
  for (const config of ALL_PLATFORMS) {
    if (url.includes(config.hostname)) {
      return config.id;
    }
  }
  return null;
}
