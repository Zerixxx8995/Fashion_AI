/**
 * Alert Store — mobile/store/alertStore.ts
 *
 * Responsibility: Zustand state management for price drop & restock alerts,
 * unread notification count, and real-time Socket.io updates.
 */

import { create } from 'zustand';
import type { Alert as AlertType } from '../types';

export interface DisplayAlertItem {
  id: string;
  productId: string;
  productName: string;
  brand: string;
  platform: string;
  image_url: string;
  type: 'price_drop' | 'restock';
  target_price_inr: number;
  current_price_inr: number;
  triggered: boolean;
  createdAt: string;
}

interface AlertState {
  alerts: DisplayAlertItem[];
  unreadCount: number;
  isLoading: boolean;
  setAlerts: (alerts: DisplayAlertItem[]) => void;
  addAlert: (alert: DisplayAlertItem) => void;
  removeAlert: (id: string) => void;
  markAllAsRead: () => void;
  setLoading: (loading: boolean) => void;
}

const SEED_ALERTS: DisplayAlertItem[] = [
  {
    id: 'alert-01',
    productId: 'sneaker-01',
    productName: 'Retro Chunky Leather Sneakers',
    brand: 'Roadster',
    platform: 'myntra',
    image_url: 'https://images.unsplash.com/photo-1552346154-21d32810aba3?w=500',
    type: 'price_drop',
    target_price_inr: 2200,
    current_price_inr: 1899,
    triggered: true,
    createdAt: new Date(Date.now() - 3600000 * 4).toISOString(),
  },
  {
    id: 'alert-02',
    productId: 'denim-02',
    productName: 'Tactical Wide-Leg Parachute Cargo Pants',
    brand: 'Zara',
    platform: 'amazon',
    image_url: 'https://images.unsplash.com/photo-1517445312882-bc9910d016b7?w=500',
    type: 'price_drop',
    target_price_inr: 2500,
    current_price_inr: 2990,
    triggered: false,
    createdAt: new Date(Date.now() - 3600000 * 24).toISOString(),
  },
  {
    id: 'alert-03',
    productId: 'dress-03',
    productName: 'Boho Floral Print Tiered Maxi Dress',
    brand: 'Biba',
    platform: 'meesho',
    image_url: 'https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=500',
    type: 'restock',
    target_price_inr: 3499,
    current_price_inr: 3499,
    triggered: true,
    createdAt: new Date(Date.now() - 3600000 * 48).toISOString(),
  },
];

export const useAlertStore = create<AlertState>((set) => ({
  alerts: SEED_ALERTS,
  unreadCount: 2,
  isLoading: false,

  setAlerts: (alerts) =>
    set({
      alerts,
      unreadCount: alerts.filter((a) => a.triggered).length,
    }),

  addAlert: (alert) =>
    set((state) => ({
      alerts: [alert, ...state.alerts],
      unreadCount: alert.triggered ? state.unreadCount + 1 : state.unreadCount,
    })),

  removeAlert: (id) =>
    set((state) => {
      const filtered = state.alerts.filter((a) => a.id !== id);
      return {
        alerts: filtered,
        unreadCount: filtered.filter((a) => a.triggered).length,
      };
    }),

  markAllAsRead: () => set({ unreadCount: 0 }),
  setLoading: (isLoading) => set({ isLoading }),
}));
