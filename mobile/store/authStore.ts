/**
 * Auth Zustand Store — mobile/store/authStore.ts
 *
 * Responsibility: Manage local user profile state, style profile,
 * and handle syncing/updating with api-backend.
 *
 * Design guidelines:
 *   - Simple state definitions (user, loading, error)
 *   - Actions to sync, fetch, and update profiles
 *   - Persists style profile values on the client
 */

import { create } from 'zustand';
import type { UserProfile } from '../types';

interface AuthState {
  user: UserProfile | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  setUser: (user: UserProfile | null) => void;
  syncUserWithBackend: (apiClient: any, email: string, name?: string) => Promise<UserProfile>;
  fetchUserProfile: (apiClient: any, userId: string) => Promise<UserProfile>;
  updateUserProfile: (
    apiClient: any,
    userId: string,
    updates: { body_type?: string | null; taste_preferences?: string[] }
  ) => Promise<UserProfile>;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isLoading: false,
  error: null,

  setUser: (user) => set({ user }),

  syncUserWithBackend: async (apiClient, email, name) => {
    set({ isLoading: true, error: null });
    try {
      const response = await apiClient.post<{ message: string; user: UserProfile }>('/auth/sync', {
        body: { email, name },
      });
      const syncedUser = response.user;
      set({ user: syncedUser, isLoading: false });
      return syncedUser;
    } catch (err: any) {
      const message = err?.apiError?.detail || err?.message || 'Failed to sync user';
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  fetchUserProfile: async (apiClient, userId) => {
    set({ isLoading: true, error: null });
    try {
      const response = await apiClient.get<{ user: UserProfile }>(`/users/${userId}/profile`);
      const profile = response.user;
      set({ user: profile, isLoading: false });
      return profile;
    } catch (err: any) {
      const message = err?.apiError?.detail || err?.message || 'Failed to fetch user profile';
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  updateUserProfile: async (apiClient, userId, updates) => {
    set({ isLoading: true, error: null });
    try {
      const response = await apiClient.put<{ user: UserProfile }>(`/users/${userId}/profile`, {
        body: updates,
      });
      const updatedProfile = response.user;
      set({ user: updatedProfile, isLoading: false });
      return updatedProfile;
    } catch (err: any) {
      const message = err?.apiError?.detail || err?.message || 'Failed to update profile';
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  logout: () => {
    set({ user: null, error: null, isLoading: false });
  },
}));
