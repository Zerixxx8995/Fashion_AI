/**
 * Sign Up Screen — mobile/app/(auth)/sign-up.tsx
 *
 * Responsibility: Email + password sign-up using @clerk/expo v4 JS-Only flow.
 * Compatible with Expo Go (no dev build required).
 *
 * API pattern (v4):
 *   const { signUp } = useSignUp();
 *   const { error } = await signUp.password({ emailAddress, password });
 *   const { error } = await signUp.verifications.sendEmailCode();
 *   const { error } = await signUp.verifications.verifyEmailCode({ code });
 *   const { error } = await signUp.finalize();
 *
 * After finalize(), useAuth() automatically updates with the signed-in state.
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
import { useAuth, useSignUp } from '@clerk/expo';
import { useRouter, Link } from 'expo-router';
import { useHttpClients } from '../../services/httpClient';
import { useAuthStore } from '../../store/authStore';

export default function SignUpScreen() {
  const { signUp } = useSignUp();
  const { isLoaded } = useAuth();
  const { getClients } = useHttpClients();
  const syncUserWithBackend = useAuthStore((state) => state.syncUserWithBackend);
  const router = useRouter();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [pendingVerification, setPendingVerification] = useState(false);
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSignUp = async () => {
    if (!isLoaded || !signUp) return;
    if (!name || !email || !password) {
      setErrorMsg('Please fill in all fields.');
      return;
    }

    setLoading(true);
    setErrorMsg(null);

    try {
      // Step 1: Create sign-up session with password strategy
      const { error: signUpError } = await signUp.password({
        emailAddress: email,
        password,
        firstName: name,
      });
      if (signUpError) {
        setErrorMsg(signUpError.message ?? 'Registration failed.');
        return;
      }

      // Step 2: Send email verification code
      const { error: sendError } = await signUp.verifications.sendEmailCode();
      if (sendError) {
        setErrorMsg(sendError.message ?? 'Failed to send verification code.');
        return;
      }

      setPendingVerification(true);
    } catch (err: any) {
      setErrorMsg(err?.errors?.[0]?.message ?? err?.message ?? 'Registration failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async () => {
    if (!isLoaded || !signUp) return;
    if (!code) {
      setErrorMsg('Please enter the verification code.');
      return;
    }

    setLoading(true);
    setErrorMsg(null);

    try {
      // Step 3: Verify the email code
      const { error: verifyError } = await signUp.verifications.verifyEmailCode({ code });
      if (verifyError) {
        setErrorMsg(verifyError.message ?? 'Verification failed.');
        return;
      }

      // Step 4: Finalize — converts to an active session
      const { error: finalizeError } = await signUp.finalize();
      if (finalizeError) {
        setErrorMsg(finalizeError.message ?? 'Could not complete sign-up.');
        return;
      }

      // Sync user profile with postgres backend
      try {
        const { apiClient } = await getClients();
        await syncUserWithBackend(apiClient, email, name);
      } catch (syncErr: any) {
        console.warn('[SignUp] Backend sync warning:', syncErr?.message);
      }

      router.replace('/(tabs)');
    } catch (err: any) {
      setErrorMsg(err?.errors?.[0]?.message ?? err?.message ?? 'Verification failed.');
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
          {!pendingVerification ? (
            <>
              <Text style={styles.cardTitle}>Create Account</Text>
              <Text style={styles.cardDesc}>
                Sign up to scan review authenticity & compare prices.
              </Text>

              {errorMsg && (
                <View style={styles.errorContainer}>
                  <Text style={styles.errorText}>{errorMsg}</Text>
                </View>
              )}

              <View style={styles.inputGroup}>
                <Text style={styles.label}>Your Name</Text>
                <TextInput
                  style={styles.input}
                  placeholder="Rahul Kumar"
                  placeholderTextColor="#555"
                  value={name}
                  onChangeText={setName}
                />
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.label}>Email Address</Text>
                <TextInput
                  style={styles.input}
                  placeholder="rahul@example.com"
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
                  placeholder="Create a strong password"
                  placeholderTextColor="#555"
                  secureTextEntry
                  autoCapitalize="none"
                  value={password}
                  onChangeText={setPassword}
                />
              </View>

              {/* Required mount point for Clerk bot protection (web). Skipped on iOS/Android. */}
              <View nativeID="clerk-captcha" />

              <TouchableOpacity
                style={styles.button}
                onPress={handleSignUp}
                disabled={loading || !isLoaded}
              >
                {loading ? (
                  <ActivityIndicator color="#FFF" />
                ) : (
                  <Text style={styles.buttonText}>Sign Up</Text>
                )}
              </TouchableOpacity>

              <View style={styles.footerLink}>
                <Text style={styles.footerText}>Already have an account? </Text>
                <Link href="/(auth)/sign-in" asChild>
                  <TouchableOpacity>
                    <Text style={styles.accentLink}>Sign In</Text>
                  </TouchableOpacity>
                </Link>
              </View>
            </>
          ) : (
            <>
              <Text style={styles.cardTitle}>Verify Your Email</Text>
              <Text style={styles.cardDesc}>We sent a 6-digit code to {email}.</Text>

              {errorMsg && (
                <View style={styles.errorContainer}>
                  <Text style={styles.errorText}>{errorMsg}</Text>
                </View>
              )}

              <View style={styles.inputGroup}>
                <Text style={styles.label}>Verification Code</Text>
                <TextInput
                  style={styles.input}
                  placeholder="Enter 6-digit code"
                  placeholderTextColor="#555"
                  keyboardType="number-pad"
                  value={code}
                  onChangeText={setCode}
                />
              </View>

              <TouchableOpacity
                style={styles.button}
                onPress={handleVerify}
                disabled={loading}
              >
                {loading ? (
                  <ActivityIndicator color="#FFF" />
                ) : (
                  <Text style={styles.buttonText}>Verify & Continue</Text>
                )}
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.backButton}
                onPress={() => { setPendingVerification(false); setErrorMsg(null); }}
                disabled={loading}
              >
                <Text style={styles.backButtonText}>← Back to Sign Up</Text>
              </TouchableOpacity>
            </>
          )}
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
  backButton: { alignItems: 'center', marginTop: 16, padding: 12 },
  backButtonText: { color: '#A0A0A5', fontSize: 14, fontWeight: '500' },
  footerLink: { flexDirection: 'row', justifyContent: 'center', marginTop: 20 },
  footerText: { color: '#707075', fontSize: 14 },
  accentLink: { color: '#FF3F6C', fontSize: 14, fontWeight: 'bold' },
});
