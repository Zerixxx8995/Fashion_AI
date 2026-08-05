/**
 * Sign Up Screen — mobile/app/(auth)/sign-up.tsx
 *
 * Responsibility: Render Sign-up form, execute sign-up, and verification via Clerk.
 * Syncs the newly created user profile with the postgres backend.
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
import { useSignUp } from '@clerk/clerk-expo';
import { useRouter, Link } from 'expo-router';
import { useHttpClients } from '../../services/httpClient';
import { useAuthStore } from '../../store/authStore';

export default function SignUpScreen() {
  const { signUp, setActive, isLoaded } = useSignUp();
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
    if (!isLoaded) return;
    if (!name || !email || !password) {
      setErrorMsg('Please fill in all fields.');
      return;
    }

    setLoading(true);
    setErrorMsg(null);

    try {
      // 1. Create Clerk user sign-up record
      await signUp.create({
        firstName: name,
        emailAddress: email,
        password,
      });

      // 2. Send email verification code
      await signUp.prepareEmailAddressVerification({ strategy: 'email_code' });
      setPendingVerification(true);
    } catch (err: any) {
      setErrorMsg(err.errors?.[0]?.message || err.message || 'Registration failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async () => {
    if (!isLoaded) return;
    if (!code) {
      setErrorMsg('Please enter the verification code.');
      return;
    }

    setLoading(true);
    setErrorMsg(null);

    try {
      // 3. Verify code
      const result = await signUp.attemptEmailAddressVerification({ code });

      if (result.status === 'complete') {
        // Set the session active
        await setActive({ session: result.createdSessionId });

        // 4. Sync user profile with postgres backend
        try {
          const { apiClient } = await getClients();
          await syncUserWithBackend(apiClient, email, name);
        } catch (syncErr: any) {
          console.error('[SignUp] Backend sync warning:', syncErr);
        }

        router.replace('/(tabs)');
      } else {
        setErrorMsg('Sign-up status incomplete. Verify your input.');
      }
    } catch (err: any) {
      setErrorMsg(err.errors?.[0]?.message || err.message || 'Verification failed.');
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
              <Text style={styles.cardDesc}>Sign up to scan review authenticity & compare prices.</Text>

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

              <TouchableOpacity
                style={styles.button}
                onPress={handleSignUp}
                disabled={loading}
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
              <Text style={styles.cardTitle}>Verify Email</Text>
              <Text style={styles.cardDesc}>We sent a verification code to {email}.</Text>

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
                  <Text style={styles.buttonText}>Verify & Sync</Text>
                )}
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.backButton}
                onPress={() => setPendingVerification(false)}
                disabled={loading}
              >
                <Text style={styles.backButtonText}>Back to Sign Up</Text>
              </TouchableOpacity>
            </>
          )}
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
  backButton: {
    alignItems: 'center',
    marginTop: 16,
    padding: 12,
  },
  backButtonText: {
    color: '#A0A0A5',
    fontSize: 14,
    fontWeight: '500',
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
