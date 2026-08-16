/**
 * Scan Screen — mobile/app/(tabs)/scan.tsx
 *
 * Responsibility: CV scan tab — lets the user upload a product photo,
 * polls the FastAPI async job, and renders the confidence scoring result.
 *
 * Flow:
 *   1. User picks image (gallery) or takes photo (camera)
 *   2. Image URI passed to useCVScore hook
 *   3. Hook submits POST /cv/score → receives job_id
 *   4. Hook polls GET /cv/score/{job_id}/status every 2s
 *   5. On complete → GET /cv/score/{job_id}/result → ConfidenceScoreCard renders
 *   6. POST /cv/similar fires to populate SimilarProductsCarousel
 *
 * Architecture:
 *   - No business logic here — all in useCVScore hook + cvService
 *   - Screen is purely presentational: maps state → UI
 */

import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  Animated,
  Easing,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useUser } from '@clerk/expo';
import { useCVScore } from '../../hooks/useCVScore';
import ImageUploader from '../../components/cv/ImageUploader';
import ConfidenceScoreCard from '../../components/cv/ConfidenceScoreCard';
import SimilarProductsCarousel from '../../components/cv/SimilarProductsCarousel';
import { useHttpClients } from '../../services/httpClient';
import { findSimilarProducts } from '../../services/cvService';
import type { SimilarProduct } from '../../types';

// ---------------------------------------------------------------------------
// Phase label helper
// ---------------------------------------------------------------------------

function getPhaseLabel(phase: string): string {
  switch (phase) {
    case 'picking':    return 'Opening picker…';
    case 'uploading':  return 'Preparing image…';
    case 'submitted':  return 'Job submitted — starting analysis…';
    case 'polling':    return 'Running CV analysis…';
    case 'complete':   return 'Analysis complete!';
    case 'error':      return 'Something went wrong';
    default:           return '';
  }
}

// ---------------------------------------------------------------------------
// Animated progress bar
// ---------------------------------------------------------------------------

function ProgressBar({ progress }: { progress: number }) {
  const anim = React.useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(anim, {
      toValue: progress,
      duration: 400,
      easing: Easing.out(Easing.quad),
      useNativeDriver: false,
    }).start();
  }, [progress, anim]);

  const width = anim.interpolate({
    inputRange: [0, 1],
    outputRange: ['0%', '100%'],
  });

  return (
    <View style={styles.progressTrack}>
      <Animated.View style={[styles.progressFill, { width }]} />
    </View>
  );
}

// ---------------------------------------------------------------------------
// Main screen
// ---------------------------------------------------------------------------

export default function ScanScreen() {
  const { user } = useUser();
  const userId = user?.id ?? 'anonymous';

  const { state, pickFromGallery, takePhoto, reset } = useCVScore({
    userId,
    productId: 'unknown', // will be linked to a real product in Build Order 21
    stockImageUrls: [],    // populated when navigating from a product page
  });

  // Similar products state — fetched after scan completes
  const [similarProducts, setSimilarProducts] = useState<SimilarProduct[]>([]);
  const [similarLoading, setSimilarLoading] = useState(false);
  const { getClients } = useHttpClients();

  // Fetch similar products once CV scan is complete
  useEffect(() => {
    if (state.phase !== 'complete' || !state.imageUri) return;

    const fetchSimilar = async () => {
      setSimilarLoading(true);
      try {
        const { mlClient } = await getClients();
        const response = await findSimilarProducts(mlClient, {
          image_url: state.imageUri ?? undefined,
          top_k: 6,
        });
        setSimilarProducts(response.results ?? []);
      } catch {
        // Non-critical — similar products section just stays empty
        setSimilarProducts([]);
      } finally {
        setSimilarLoading(false);
      }
    };

    fetchSimilar();
  }, [state.phase, state.imageUri, getClients]);

  const handleReset = useCallback(() => {
    setSimilarProducts([]);
    reset();
  }, [reset]);

  const isBusy =
    state.phase === 'uploading' ||
    state.phase === 'submitted' ||
    state.phase === 'polling';

  const showProgress = isBusy && state.progress > 0;

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>CV Scan</Text>
        <Text style={styles.headerSub}>Upload a product photo · get a confidence score</Text>
      </View>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        {/* ── Image uploader ─────────────────────────────────────────── */}
        <ImageUploader
          imageUri={state.imageUri}
          phase={state.phase}
          onGallery={pickFromGallery}
          onCamera={takePhoto}
          onReset={handleReset}
        />

        {/* ── Progress bar + phase label ─────────────────────────────── */}
        {showProgress && (
          <View style={styles.progressSection}>
            <ProgressBar progress={state.progress} />
            <View style={styles.progressLabelRow}>
              <ActivityIndicator size="small" color="#FF3F6C" />
              <Text style={styles.progressLabel}>
                {getPhaseLabel(state.phase)}
              </Text>
            </View>
          </View>
        )}

        {/* ── Submitted / polling state label (no bar yet) ──────────── */}
        {state.phase === 'submitted' && !showProgress && (
          <View style={styles.progressSection}>
            <View style={styles.progressLabelRow}>
              <ActivityIndicator size="small" color="#FF3F6C" />
              <Text style={styles.progressLabel}>
                {getPhaseLabel(state.phase)}
              </Text>
            </View>
          </View>
        )}

        {/* ── Error state ────────────────────────────────────────────── */}
        {state.phase === 'error' && state.errorMessage && (
          <View style={styles.errorBox}>
            <Text style={styles.errorIcon}>⚠️</Text>
            <View style={styles.errorTextWrap}>
              <Text style={styles.errorTitle}>Scan Failed</Text>
              <Text style={styles.errorDetail}>{state.errorMessage}</Text>
            </View>
          </View>
        )}

        {/* ── Result card ────────────────────────────────────────────── */}
        {state.phase === 'complete' && state.result && (
          <>
            <ConfidenceScoreCard result={state.result} />

            {/* ── Similar products ─────────────────────────────────── */}
            <View style={styles.similarSection}>
              <SimilarProductsCarousel
                products={similarProducts}
                loading={similarLoading}
              />
            </View>
          </>
        )}

        {/* ── Explainer (only shown in idle state) ───────────────────── */}
        {state.phase === 'idle' && (
          <View style={styles.explainerSection}>
            <Text style={styles.explainerTitle}>How It Works</Text>

            <View style={styles.stepRow}>
              <View style={styles.stepBadge}>
                <Text style={styles.stepNum}>1</Text>
              </View>
              <View style={styles.stepText}>
                <Text style={styles.stepTitle}>Upload Product Photo</Text>
                <Text style={styles.stepDesc}>
                  Take or select a photo of the product you received
                </Text>
              </View>
            </View>

            <View style={styles.stepRow}>
              <View style={styles.stepBadge}>
                <Text style={styles.stepNum}>2</Text>
              </View>
              <View style={styles.stepText}>
                <Text style={styles.stepTitle}>CV Analysis Runs</Text>
                <Text style={styles.stepDesc}>
                  Our CLIP engine embeds your photo and compares it to the stock image
                </Text>
              </View>
            </View>

            <View style={styles.stepRow}>
              <View style={styles.stepBadge}>
                <Text style={styles.stepNum}>3</Text>
              </View>
              <View style={styles.stepText}>
                <Text style={styles.stepTitle}>Get Confidence Score</Text>
                <Text style={styles.stepDesc}>
                  See exactly how closely what you received matches what was advertised
                </Text>
              </View>
            </View>

            <View style={styles.stepRow}>
              <View style={styles.stepBadge}>
                <Text style={styles.stepNum}>4</Text>
              </View>
              <View style={styles.stepText}>
                <Text style={styles.stepTitle}>Find Cheaper Alternatives</Text>
                <Text style={styles.stepDesc}>
                  We surface visually similar products at a lower price across platforms
                </Text>
              </View>
            </View>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: '#0B0B0E',
  },

  // Header
  header: {
    paddingHorizontal: 20,
    paddingTop: 8,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#16161C',
  },
  headerTitle: {
    fontSize: 26,
    fontWeight: '900',
    color: '#FF3F6C',
    letterSpacing: 0.3,
  },
  headerSub: {
    fontSize: 13,
    color: '#505058',
    marginTop: 2,
  },

  // Scroll
  scroll: { flex: 1 },
  scrollContent: {
    padding: 20,
    gap: 20,
    paddingBottom: 40,
  },

  // Progress
  progressSection: {
    gap: 8,
  },
  progressTrack: {
    height: 4,
    backgroundColor: '#24242E',
    borderRadius: 2,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: 2,
    backgroundColor: '#FF3F6C',
  },
  progressLabelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  progressLabel: {
    fontSize: 13,
    color: '#A0A0A5',
  },

  // Error
  errorBox: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 12,
    backgroundColor: 'rgba(239,68,68,0.08)',
    borderRadius: 14,
    borderWidth: 1,
    borderColor: 'rgba(239,68,68,0.25)',
    padding: 16,
  },
  errorIcon: {
    fontSize: 20,
    marginTop: 1,
  },
  errorTextWrap: {
    flex: 1,
  },
  errorTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#FCA5A5',
    marginBottom: 4,
  },
  errorDetail: {
    fontSize: 12,
    color: '#A05050',
    lineHeight: 18,
  },

  // Similar products
  similarSection: {
    gap: 4,
  },

  // Explainer
  explainerSection: {
    gap: 16,
    backgroundColor: '#16161C',
    borderRadius: 20,
    borderWidth: 1,
    borderColor: '#24242E',
    padding: 20,
  },
  explainerTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: '#E8E8F0',
    marginBottom: 4,
  },
  stepRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 14,
  },
  stepBadge: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: 'rgba(255,63,108,0.15)',
    borderWidth: 1,
    borderColor: '#FF3F6C',
    justifyContent: 'center',
    alignItems: 'center',
    flexShrink: 0,
  },
  stepNum: {
    fontSize: 13,
    fontWeight: '800',
    color: '#FF3F6C',
  },
  stepText: {
    flex: 1,
    gap: 2,
  },
  stepTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#E8E8F0',
  },
  stepDesc: {
    fontSize: 12,
    color: '#60606A',
    lineHeight: 18,
  },
});
