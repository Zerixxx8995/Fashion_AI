/**
 * Scan Screen — mobile/app/(tabs)/scan.tsx
 *
 * Responsibility: CV scan — user uploads product photo for confidence scoring.
 * Placeholder screen — full implementation in Build Order 20.
 */

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

export default function ScanScreen() {
  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.container}>
        <Text style={styles.title}>⊙ Scan</Text>
        <Text style={styles.subtitle}>CV confidence scoring engine</Text>
        <Text style={styles.coming}>Coming in Build Order 20</Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#0B0B0E' },
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  title: {
    fontSize: 28,
    fontWeight: '900',
    color: '#FF3F6C',
    marginBottom: 8,
    letterSpacing: 1,
  },
  subtitle: {
    fontSize: 15,
    color: '#A0A0A5',
    marginBottom: 24,
  },
  coming: {
    fontSize: 13,
    color: '#505058',
    backgroundColor: '#16161C',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#24242E',
  },
});
