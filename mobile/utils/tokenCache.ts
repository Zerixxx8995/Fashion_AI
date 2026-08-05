/**
 * Token Cache Utility — mobile/utils/tokenCache.ts
 *
 * Responsibility: Secure token storage for Clerk authentication on Expo.
 * Utilises expo-secure-store to save and retrieve JWTs securely.
 */

import * as SecureStore from 'expo-secure-store';

export interface TokenCache {
  getToken: (key: string) => Promise<string | null>;
  saveToken: (key: string, token: string) => Promise<void>;
}

export const tokenCache: TokenCache = {
  async getToken(key: string) {
    try {
      const item = await SecureStore.getItemAsync(key);
      return item;
    } catch (error) {
      console.error('[tokenCache] Error reading secure store token:', error);
      return null;
    }
  },
  async saveToken(key: string, value: string) {
    try {
      await SecureStore.setItemAsync(key, value);
    } catch (error) {
      console.error('[tokenCache] Error writing secure store token:', error);
    }
  },
};
