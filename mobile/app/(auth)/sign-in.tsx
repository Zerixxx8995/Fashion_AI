/**
 * Sign In Screen — mobile/app/(auth)/sign-in.tsx
 *
 * Responsibility: Email + password sign-in using @clerk/expo v4 JS-Only flow.
 * Compatible with Expo Go (no dev build required).
 *
 * API pattern (v4):
 *   const { signIn } = useSignIn();
 *   const { error } = await signIn.password({ identifier, password });
 *   const { error: finalizeError } = await signIn.finalize();
 *
 * Syncs the signed-in user with the api-backend on success.
 */

import React, { useState } from 'react';
import {
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from 'react-native';
import { useAuth, useSignIn } from '@clerk/expo';
import { useRouter, Link } from 'expo-router';
import { useHttpClients } from '../../services/httpClient';
import { useAuthStore } from '../../store/authStore';

export default function SignInScreen() {
  const { signIn } = useSignIn();
  const { isLoaded } = useAuth();
  const { getClients } = useHttpClients();
  const syncUserWithBackend = useAuthStore((state) => state.syncUserWithBackend);
  const router = useRouter();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSignIn = async () => {
    if (!isLoaded || !signIn) return;
    if (!email || !password) {
      setErrorMsg('Please fill in all fields.');
      return;
    }

    setLoading(true);
    setErrorMsg(null);

    try {
      // v4 method-based API: returns { error } instead of throwing
      const { error: signInError } = await signIn.password({ identifier: email, password });
      if (signInError) {
        setErrorMsg(signInError.message ?? 'Authentication failed.');
        return;
      }

      const { error: finalizeError } = await signIn.finalize();
      if (finalizeError) {
        setErrorMsg(finalizeError.message ?? 'Sign-in could not be completed.');
        return;
      }

      // Sync user profile with postgres backend
      try {
        const { apiClient } = await getClients();
        await syncUserWithBackend(apiClient, email, email.split('@')[0]);
      } catch (syncErr: any) {
        console.warn('[SignIn] Backend sync warning:', syncErr?.message);
      }

      router.replace('/(tabs)');
    } catch (err: any) {
      // Fallback for unexpected errors
      const msg = err?.errors?.[0]?.message ?? err?.message ?? 'Authentication failed.';
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      style={styles.container}
    >
      <ScrollView contentContainerStyle={styles.scrollContent} keyboardShouldPersistTaps="handled">
        <View style={styles.header}>
          <Text style={styles.title}>ZEST</Text>
          <Text style={styles.subtitle}>Curated Indian Fashion & Trust Engine</Text>
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>Welcome Back</Text>
          <Text style={styles.cardDesc}>Sign in to scan and discover authentic trends.</Text>

          {errorMsg && (
            <View style={styles.errorContainer}>
              <Text style={styles.errorText}>{errorMsg}</Text>
            </View>
          )}

          <View style={styles.inputGroup}>
            <Text style={styles.label}>Email Address</Text>
            <TextInput
              style={styles.input}
              placeholder="name@example.com"
              placeholderTextColor="#555"
              autoCapitalize="none"
              keyboardType="email-address"
              value={email}
              onChangeText={setEmail}
            />
          </View>

          <View style={styles.inputGroup}>
            <Text style={styles.label}>Password</Text>
            <TextInput
              style={styles.input}
              placeholder="Enter your password"
              placeholderTextColor="#555"
              secureTextEntry
              autoCapitalize="none"
              value={password}
              onChangeText={setPassword}
            />
          </View>

          <TouchableOpacity
            style={styles.button}
            onPress={handleSignIn}
            disabled={loading || !isLoaded}
          >
            {loading ? (
              <ActivityIndicator color="#FFF" />
            ) : (
              <Text style={styles.buttonText}>Sign In</Text>
            )}
          </TouchableOpacity>

          <View style={styles.footerLink}>
            <Text style={styles.footerText}>Don't have an account? </Text>
            <Link href="/(auth)/sign-up" asChild>
              <TouchableOpacity>
                <Text style={styles.accentLink}>Sign Up</Text>
              </TouchableOpacity>
            </Link>
          </View>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0B0B0E' },
  scrollContent: { flexGrow: 1, justifyContent: 'center', padding: 24 },
  header: { alignItems: 'center', marginBottom: 40 },
  title: { fontSize: 36, fontWeight: 'bold', color: '#FF3F6C', letterSpacing: 4 },
  subtitle: { fontSize: 14, color: '#A0A0A5', marginTop: 8, textAlign: 'center' },
  card: {
    backgroundColor: '#16161C',
    borderRadius: 16,
    padding: 24,
    borderWidth: 1,
    borderColor: '#24242E',
  },
  cardTitle: { fontSize: 22, fontWeight: 'bold', color: '#FFF' },
  cardDesc: { fontSize: 14, color: '#707075', marginTop: 6, marginBottom: 24 },
  errorContainer: {
    backgroundColor: '#FF3F3F20',
    borderWidth: 1,
    borderColor: '#FF3F3F80',
    padding: 12,
    borderRadius: 8,
    marginBottom: 16,
  },
  errorText: { color: '#FF3F3F', fontSize: 13 },
  inputGroup: { marginBottom: 20 },
  label: { fontSize: 13, fontWeight: '600', color: '#A0A0A5', marginBottom: 8 },
  input: {
    backgroundColor: '#0B0B0E',
    borderWidth: 1,
    borderColor: '#24242E',
    borderRadius: 8,
    padding: 14,
    color: '#FFF',
    fontSize: 15,
  },
  button: {
    backgroundColor: '#FF3F6C',
    borderRadius: 8,
    padding: 16,
    alignItems: 'center',
    marginTop: 8,
  },
  buttonText: { color: '#FFF', fontSize: 16, fontWeight: 'bold' },
  footerLink: { flexDirection: 'row', justifyContent: 'center', marginTop: 20 },
  footerText: { color: '#707075', fontSize: 14 },
  accentLink: { color: '#FF3F6C', fontSize: 14, fontWeight: 'bold' },
});
