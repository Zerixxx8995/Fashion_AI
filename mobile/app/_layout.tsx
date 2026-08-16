/**
 * Root Layout — mobile/app/_layout.tsx
 *
 * Responsibility: Mount ClerkProvider, SafeAreaProvider, and manage root-level routing.
 * Checks authentication status and redirects to sign-in or tabs.
 *
 * Uses @clerk/expo v3 tokenCache from the official package (not expo-secure-store directly).
 *
 * NOTE: Do NOT add explicit Stack.Screen declarations for route groups like "(auth)"
 * or "(tabs)" here. Expo Router auto-discovers them from their own _layout.tsx files.
 * Declaring them in the root Stack causes "No route named (auth)" warnings.
 */

import React, { useEffect } from 'react';
import { Slot, useRouter, useSegments } from 'expo-router';
import { ClerkProvider, useAuth } from '@clerk/expo';
import { tokenCache } from '@clerk/expo/token-cache';
import { ActivityIndicator, View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

const CLERK_PUBLISHABLE_KEY = process.env.EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY ?? '';

function InitialLayout() {
  const { isLoaded, isSignedIn } = useAuth();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    if (!isLoaded) return;

    const inAuthGroup = segments[0] === '(auth)';

    if (isSignedIn && inAuthGroup) {
      // Already signed in — push to main app
      router.replace('/(tabs)');
    } else if (!isSignedIn && !inAuthGroup) {
      // Not signed in — push to sign-in screen
      router.replace('/(auth)/sign-in');
    }
  }, [isSignedIn, isLoaded, segments]);

  if (!isLoaded) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#0B0B0E' }}>
        <ActivityIndicator size="large" color="#FF3F6C" />
      </View>
    );
  }

  // Slot renders whatever the current route's layout/screen is.
  // Expo Router handles group discovery automatically — no need to declare
  // Stack.Screen entries for "(auth)" or "(tabs)" here.
  return <Slot />;
}

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <ClerkProvider publishableKey={CLERK_PUBLISHABLE_KEY} tokenCache={tokenCache}>
        <InitialLayout />
      </ClerkProvider>
    </SafeAreaProvider>
  );
}
