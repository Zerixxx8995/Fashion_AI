/**
 * Sign In Screen — mobile/app/(auth)/sign-in.tsx
 *
 * Responsibility: Render Sign-in form and execute login via Clerk.
 * Automatically synchronises the user profile with the api-backend on success.
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
import { useSignIn } from '@clerk/clerk-expo';
import { useRouter, Link } from 'expo-router';
import { useHttpClients } from '../../services/httpClient';
import { useAuthStore } from '../../store/authStore';

export default function SignInScreen() {
  const { signIn, setActive, isLoaded } = useSignIn();
  const { getClients } = useHttpClients();
  const syncUserWithBackend = useAuthStore((state) => state.syncUserWithBackend);
  const router = useRouter();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSignIn = async () => {
    if (!isLoaded) return;
    if (!email || !password) {
      setErrorMsg('Please fill in all fields.');
      return;
    }

    setLoading(true);
    setErrorMsg(null);

    try {
      // 1. Sign in via Clerk
      const result = await signIn.create({
        identifier: email,
        password,
      });

      if (result.status === 'complete') {
        // Set the active session in Clerk
        await setActive({ session: result.createdSessionId });

        // 2. Sync user profile with postgres backend
        try {
          const { apiClient } = await getClients();
          await syncUserWithBackend(apiClient, email, email.split('@')[0]);
        } catch (syncErr: any) {
          console.error('[SignIn] Backend sync warning:', syncErr);
          // Don't block navigation on sync failure, but log it
        }

        router.replace('/(tabs)');
      } else {
        setErrorMsg('Sign-in status incomplete. Check verification steps.');
      }
    } catch (err: any) {
      setErrorMsg(err.errors?.[0]?.message || err.message || 'Authentication failed.');
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
            disabled={loading}
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
  container: {
    flex: 1,
    backgroundColor: '#0B0B0E',
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: 24,
  },
  header: {
    alignItems: 'center',
    marginBottom: 40,
  },
  title: {
    fontSize: 36,
    fontWeight: 'bold',
    color: '#FF3F6C',
    letterSpacing: 4,
  },
  subtitle: {
    fontSize: 14,
    color: '#A0A0A5',
    marginTop: 8,
    textAlign: 'center',
  },
  card: {
    backgroundColor: '#16161C',
    borderRadius: 16,
    padding: 24,
    borderWidth: 1,
    borderColor: '#24242E',
  },
  cardTitle: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#FFF',
  },
  cardDesc: {
    fontSize: 14,
    color: '#707075',
    marginTop: 6,
    marginBottom: 24,
  },
  errorContainer: {
    backgroundColor: '#FF3F3F20',
    borderWidth: 1,
    borderColor: '#FF3F3F80',
    padding: 12,
    borderRadius: 8,
    marginBottom: 16,
  },
  errorText: {
    color: '#FF3F3F',
    fontSize: 13,
  },
  inputGroup: {
    marginBottom: 20,
  },
  label: {
    fontSize: 13,
    fontWeight: '600',
    color: '#A0A0A5',
    marginBottom: 8,
  },
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
  buttonText: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: 'bold',
  },
  footerLink: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: 20,
  },
  footerText: {
    color: '#707075',
    fontSize: 14,
  },
  accentLink: {
    color: '#FF3F6C',
    fontSize: 14,
    fontWeight: 'bold',
  },
});
