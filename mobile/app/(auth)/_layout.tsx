/**
 * Auth Layout — mobile/app/(auth)/_layout.tsx
 *
 * Responsibility: Stack navigator for the authentication flow.
 * Expo Router requires this file to register the (auth) group.
 *
 * Screens in this group:
 *   - sign-in.tsx
 *   - sign-up.tsx
 */

import React from 'react';
import { Stack } from 'expo-router';

export default function AuthLayout() {
  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: '#0B0B0E' },
        animation: 'fade',
      }}
    >
      <Stack.Screen name="sign-in" options={{ headerShown: false }} />
      <Stack.Screen name="sign-up" options={{ headerShown: false }} />
    </Stack>
  );
}
