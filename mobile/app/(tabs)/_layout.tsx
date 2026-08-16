/**
 * Tabs Layout — mobile/app/(tabs)/_layout.tsx
 *
 * Responsibility: Define the bottom tab navigator for all main app screens.
 * Expo Router requires this file to exist for the (tabs) group to work.
 *
 * Safe area handling:
 *   - useSafeAreaInsets() reads actual device insets (status bar, notch, gesture bar)
 *   - We add extra bottom padding so the tab bar sits above Android's gesture nav bar
 *
 * Tabs (in order):
 *   1. index     — Trends feed (home)
 *   2. discover  — Style recommendations
 *   3. scan      — CV scan / upload
 *   4. wardrobe  — Wardrobe builder
 *   5. alerts    — Price drop alerts
 */

import React from 'react';
import { Tabs } from 'expo-router';
import { Platform } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

export default function TabsLayout() {
  const insets = useSafeAreaInsets();

  // Bottom inset accounts for Android gesture nav bar and iOS home indicator
  const tabBarHeight = 52 + insets.bottom;

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: '#0B0B0E',
          borderTopColor: '#16161C',
          borderTopWidth: 1,
          height: tabBarHeight,
          paddingBottom: insets.bottom > 0 ? insets.bottom : 8,
          paddingTop: 8,
          // Ensure tab bar is above Android gesture/button bar
          elevation: 8,
        },
        tabBarActiveTintColor: '#FF3F6C',
        tabBarInactiveTintColor: '#505058',
        tabBarLabelStyle: {
          fontSize: 11,
          fontWeight: '600',
          letterSpacing: 0.3,
          marginBottom: 2,
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Trends',
          tabBarLabel: 'Trends',
        }}
      />
      <Tabs.Screen
        name="discover"
        options={{
          title: 'Discover',
          tabBarLabel: 'Discover',
        }}
      />
      <Tabs.Screen
        name="scan"
        options={{
          title: 'Scan',
          tabBarLabel: 'Scan',
        }}
      />
      <Tabs.Screen
        name="wardrobe"
        options={{
          title: 'Wardrobe',
          tabBarLabel: 'Wardrobe',
        }}
      />
      <Tabs.Screen
        name="alerts"
        options={{
          title: 'Alerts',
          tabBarLabel: 'Alerts',
        }}
      />
    </Tabs>
  );
}
