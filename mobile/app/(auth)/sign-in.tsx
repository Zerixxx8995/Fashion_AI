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
import { useAuth, useClerk, useSignIn } from '@clerk/expo';
import { useRouter, Link } from 'expo-router';
import { useHttpClients } from '../../services/httpClient';
import { useAuthStore } from '../../store/authStore';

export default function SignInScreen() {
  const { signIn } = useSignIn();
  const { setActive } = useClerk();
  const { isLoaded } = useAuth();
  const { getClients } = useHttpClients();
  const syncUserWithBackend = useAuthStore((state) => state.syncUserWithBackend);
  const router = useRouter();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [infoMsg, setInfoMsg] = useState<string | null>(null);

  // Password reset state
  const [resetStep, setResetStep] = useState<'none' | 'email' | 'code'>('none');
  const [resetCode, setResetCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');

  const handleSignIn = async () => {
    if (!isLoaded || !signIn) return;
    if (!email || !password) {
      setErrorMsg('Please fill in all fields.');
      return;
    }

    setLoading(true);
    setErrorMsg(null);
    setInfoMsg(null);

    try {
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

      router.replace('/(tabs)');
    } catch (err: any) {
      const msg = err?.errors?.[0]?.message ?? err?.message ?? 'Authentication failed.';
      setErrorMsg(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleSendResetCode = async () => {
    if (!isLoaded || !signIn) return;
    if (!email) {
      setErrorMsg('Please enter your email address.');
      return;
    }

    setLoading(true);
    setErrorMsg(null);
    setInfoMsg(null);

    try {
      if (typeof (signIn as any).create === 'function') {
        await (signIn as any).create({
          strategy: 'reset_password_email_code',
          identifier: email,
        });
      } else if (typeof (signIn as any).resetPassword === 'function') {
        const { error } = await (signIn as any).resetPassword({ identifier: email });
        if (error) {
          setErrorMsg(error.message ?? 'Failed to send reset code.');
          return;
        }
      }

      setInfoMsg('Reset code sent! Check your inbox.');
      setResetStep('code');
    } catch (err: any) {
      setErrorMsg(err?.errors?.[0]?.message ?? err?.message ?? 'Failed to send reset code.');
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async () => {
    if (!isLoaded || !signIn) return;
    if (!resetCode || !newPassword || !confirmNewPassword) {
      setErrorMsg('Please fill in all fields.');
      return;
    }
    if (newPassword !== confirmNewPassword) {
      setErrorMsg('Passwords do not match.');
      return;
    }

    setLoading(true);
    setErrorMsg(null);
    setInfoMsg(null);

    try {
      let createdSessionId: string | undefined;

      if (typeof (signIn as any).attemptFirstFactor === 'function') {
        const result = await (signIn as any).attemptFirstFactor({
          strategy: 'reset_password_email_code',
          code: resetCode,
          password: newPassword,
        });
        if (result.status === 'complete') {
          createdSessionId = result.createdSessionId ?? undefined;
        } else {
          setErrorMsg('Password reset incomplete. Please check the verification code.');
          return;
        }
      } else if (typeof (signIn as any).resetPassword === 'function') {
        const res = await (signIn as any).resetPassword({
          code: resetCode,
          password: newPassword,
        });
        if (res?.error) {
          setErrorMsg(res.error.message ?? 'Password reset failed.');
          return;
        }
        createdSessionId = res?.createdSessionId;
      }

      if (createdSessionId && setActive) {
        await setActive({ session: createdSessionId });
      }

      router.replace('/(tabs)');
    } catch (err: any) {
      setErrorMsg(err?.errors?.[0]?.message ?? err?.message ?? 'Password reset failed.');
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
          {resetStep === 'none' && (
            <>
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
                <View style={styles.labelRow}>
                  <Text style={styles.label}>Password</Text>
                  <TouchableOpacity
                    onPress={() => {
                      setResetStep('email');
                      setErrorMsg(null);
                      setInfoMsg(null);
                    }}
                  >
                    <Text style={styles.forgotLink}>Forgot Password?</Text>
                  </TouchableOpacity>
                </View>
                <View style={styles.passwordContainer}>
                  <TextInput
                    style={styles.passwordInput}
                    placeholder="Enter your password"
                    placeholderTextColor="#555"
                    secureTextEntry={!showPassword}
                    autoCapitalize="none"
                    value={password}
                    onChangeText={setPassword}
                  />
                  <TouchableOpacity
                    style={styles.toggleButton}
                    onPress={() => setShowPassword(!showPassword)}
                    accessibilityLabel={showPassword ? 'Hide password' : 'Show password'}
                  >
                    <Text style={styles.toggleText}>{showPassword ? 'Hide' : 'Show'}</Text>
                  </TouchableOpacity>
                </View>
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
            </>
          )}

          {resetStep === 'email' && (
            <>
              <Text style={styles.cardTitle}>Reset Password</Text>
              <Text style={styles.cardDesc}>
                Enter your account email to receive a password reset code.
              </Text>

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

              <TouchableOpacity
                style={styles.button}
                onPress={handleSendResetCode}
                disabled={loading}
              >
                {loading ? (
                  <ActivityIndicator color="#FFF" />
                ) : (
                  <Text style={styles.buttonText}>Send Reset Code</Text>
                )}
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.backButton}
                onPress={() => {
                  setResetStep('none');
                  setErrorMsg(null);
                  setInfoMsg(null);
                }}
              >
                <Text style={styles.backButtonText}>← Back to Sign In</Text>
              </TouchableOpacity>
            </>
          )}

          {resetStep === 'code' && (
            <>
              <Text style={styles.cardTitle}>Set New Password</Text>
              <Text style={styles.cardDesc}>
                Enter the code sent to {email} and your new password.
              </Text>

              {infoMsg && (
                <View style={styles.infoContainer}>
                  <Text style={styles.infoText}>{infoMsg}</Text>
                </View>
              )}

              {errorMsg && (
                <View style={styles.errorContainer}>
                  <Text style={styles.errorText}>{errorMsg}</Text>
                </View>
              )}

              <View style={styles.inputGroup}>
                <Text style={styles.label}>Reset Code</Text>
                <TextInput
                  style={styles.input}
                  placeholder="Enter 6-digit code"
                  placeholderTextColor="#555"
                  keyboardType="number-pad"
                  value={resetCode}
                  onChangeText={setResetCode}
                />
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.label}>New Password</Text>
                <View style={styles.passwordContainer}>
                  <TextInput
                    style={styles.passwordInput}
                    placeholder="Enter new password"
                    placeholderTextColor="#555"
                    secureTextEntry={!showPassword}
                    autoCapitalize="none"
                    value={newPassword}
                    onChangeText={setNewPassword}
                  />
                  <TouchableOpacity
                    style={styles.toggleButton}
                    onPress={() => setShowPassword(!showPassword)}
                  >
                    <Text style={styles.toggleText}>{showPassword ? 'Hide' : 'Show'}</Text>
                  </TouchableOpacity>
                </View>
              </View>

              <View style={styles.inputGroup}>
                <Text style={styles.label}>Confirm New Password</Text>
                <View style={styles.passwordContainer}>
                  <TextInput
                    style={styles.passwordInput}
                    placeholder="Re-enter new password"
                    placeholderTextColor="#555"
                    secureTextEntry={!showConfirmPassword}
                    autoCapitalize="none"
                    value={confirmNewPassword}
                    onChangeText={setConfirmNewPassword}
                  />
                  <TouchableOpacity
                    style={styles.toggleButton}
                    onPress={() => setShowConfirmPassword(!showConfirmPassword)}
                  >
                    <Text style={styles.toggleText}>{showConfirmPassword ? 'Hide' : 'Show'}</Text>
                  </TouchableOpacity>
                </View>
              </View>

              <TouchableOpacity
                style={styles.button}
                onPress={handleResetPassword}
                disabled={loading}
              >
                {loading ? (
                  <ActivityIndicator color="#FFF" />
                ) : (
                  <Text style={styles.buttonText}>Reset & Sign In</Text>
                )}
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.backButton}
                onPress={() => {
                  setResetStep('none');
                  setErrorMsg(null);
                  setInfoMsg(null);
                }}
              >
                <Text style={styles.backButtonText}>← Back to Sign In</Text>
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
  infoContainer: {
    backgroundColor: '#3FFF6C20',
    borderWidth: 1,
    borderColor: '#3FFF6C80',
    padding: 12,
    borderRadius: 8,
    marginBottom: 16,
  },
  infoText: { color: '#3FFF6C', fontSize: 13 },
  inputGroup: { marginBottom: 20 },
  labelRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  label: { fontSize: 13, fontWeight: '600', color: '#A0A0A5', marginBottom: 8 },
  forgotLink: { color: '#FF3F6C', fontSize: 13, fontWeight: '600', marginBottom: 8 },
  input: {
    backgroundColor: '#0B0B0E',
    borderWidth: 1,
    borderColor: '#24242E',
    borderRadius: 8,
    padding: 14,
    color: '#FFF',
    fontSize: 15,
  },
  passwordContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#0B0B0E',
    borderWidth: 1,
    borderColor: '#24242E',
    borderRadius: 8,
  },
  passwordInput: {
    flex: 1,
    padding: 14,
    color: '#FFF',
    fontSize: 15,
  },
  toggleButton: {
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  toggleText: {
    color: '#FF3F6C',
    fontSize: 13,
    fontWeight: '600',
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
