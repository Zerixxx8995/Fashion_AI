/**
 * Scan Screen — mobile/app/(tabs)/scan.tsx
 *
 * Responsibility: CV scan tab — supports both:
 *   1. Single Product Scan: upload 1 product photo → get confidence score & cheaper alternatives.
 *   2. Direct 2-Image Comparison: upload Photo 1 (Received) + Photo 2 (Ad/Ref) → compute exact similarity score.
 *
 * UX enhancements:
 *   - Pull-to-refresh (`RefreshControl`) to easily rescan anytime.
 *   - Prominent Rescan / Reset buttons on completed result cards.
 *   - Mode toggle switch in header ("Single Scan" vs "2-Image Match").
 */

import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Animated,
  Easing,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useUser } from '@clerk/expo';
import { useCVScore } from '../../hooks/useCVScore';
import ImageUploader from '../../components/cv/ImageUploader';
import CompareUploader from '../../components/cv/CompareUploader';
import ConfidenceScoreCard from '../../components/cv/ConfidenceScoreCard';
import SimilarProductsCarousel from '../../components/cv/SimilarProductsCarousel';
import { useHttpClients } from '../../services/httpClient';
import { findSimilarProducts } from '../../services/cvService';
import type { SimilarProduct } from '../../types';

export type ScanMode = 'single' | 'compare';

// ---------------------------------------------------------------------------
// Phase label helper
// ---------------------------------------------------------------------------

function getPhaseLabel(phase: string): string {
  switch (phase) {
    case 'picking':    return 'Opening picker…';
    case 'uploading':  return 'Preparing image…';
    case 'submitted':  return 'Job submitted — starting analysis…';
    case 'polling':    return 'Running CLIP similarity analysis…';
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

  // Mode state
  const [mode, setMode] = useState<ScanMode>('single');
  const [refreshing, setRefreshing] = useState(false);

  // Compare mode local image state
  const [compareUriA, setCompareUriA] = useState<string | null>(null);
  const [compareUriB, setCompareUriB] = useState<string | null>(null);

  const {
    state,
    pickFromGallery,
    takePhoto,
    pickImageFromSource,
    submitDirectComparison,
    reset,
  } = useCVScore({
    userId,
    productId: mode === 'compare' ? 'comparison' : 'unknown',
    stockImageUrls: [],
  });

  // Similar products state (for single scan mode)
  const [similarProducts, setSimilarProducts] = useState<SimilarProduct[]>([]);
  const [similarLoading, setSimilarLoading] = useState(false);
  const { getClients } = useHttpClients();

  // Fetch similar products once CV scan completes (only in single mode)
  useEffect(() => {
    if (state.phase !== 'complete' || !state.imageUri || mode === 'compare') return;

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
        setSimilarProducts([]);
      } finally {
        setSimilarLoading(false);
      }
    };

    fetchSimilar();
  }, [state.phase, state.imageUri, mode, getClients]);

  const handleReset = useCallback(() => {
    setSimilarProducts([]);
    setCompareUriA(null);
    setCompareUriB(null);
    reset();
  }, [reset]);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    handleReset();
    setTimeout(() => setRefreshing(false), 300);
  }, [handleReset]);

  // Pick helper for comparison mode
  const handlePickCompareA = async (source: 'gallery' | 'camera') => {
    const uri = await pickImageFromSource(source);
    if (uri) setCompareUriA(uri);
  };

  const handlePickCompareB = async (source: 'gallery' | 'camera') => {
    const uri = await pickImageFromSource(source);
    if (uri) setCompareUriB(uri);
  };

  const handleRunComparison = () => {
    if (compareUriA && compareUriB) {
      submitDirectComparison(compareUriA, compareUriB);
    }
  };

  const isBusy =
    state.phase === 'uploading' ||
    state.phase === 'submitted' ||
    state.phase === 'polling';

  const showProgress = isBusy && state.progress > 0;

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      {/* ── Header & Mode Switcher ───────────────────────────────────────── */}
      <View style={styles.header}>
        <View style={styles.headerTopRow}>
          <View>
            <Text style={styles.headerTitle}>CV Scan</Text>
            <Text style={styles.headerSub}>
              {mode === 'single'
                ? 'Upload product photo · get confidence score'
                : 'Directly compare 2 images side-by-side'}
            </Text>
          </View>

          {state.phase === 'complete' && (
            <TouchableOpacity style={styles.headerRescanBtn} onPress={handleReset} activeOpacity={0.8}>
              <Text style={styles.headerRescanText}>↺ Rescan</Text>
            </TouchableOpacity>
          )}
        </View>

        {/* Mode Selector Tabs */}
        <View style={styles.modeTabs}>
          <TouchableOpacity
            style={[styles.modeTab, mode === 'single' && styles.modeTabActive]}
            onPress={() => {
              if (mode !== 'single') {
                setMode('single');
                handleReset();
              }
            }}
            activeOpacity={0.8}
            disabled={isBusy}
          >
            <Text style={[styles.modeTabText, mode === 'single' && styles.modeTabTextActive]}>
              📱 Single Product Scan
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.modeTab, mode === 'compare' && styles.modeTabActive]}
            onPress={() => {
              if (mode !== 'compare') {
                setMode('compare');
                handleReset();
              }
            }}
            activeOpacity={0.8}
            disabled={isBusy}
          >
            <Text style={[styles.modeTabText, mode === 'compare' && styles.modeTabTextActive]}>
              ⚡ 2-Image Match
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      <ScrollView
        style={styles.scroll}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor="#FF3F6C"
            colors={['#FF3F6C']}
          />
        }
      >
        {/* ── MODE 1: Single Scan Uploader ──────────────────────────────── */}
        {mode === 'single' && (
          <ImageUploader
            imageUri={state.imageUri}
            phase={state.phase}
            onGallery={pickFromGallery}
            onCamera={takePhoto}
            onReset={handleReset}
          />
        )}

        {/* ── MODE 2: Direct 2-Image Compare Uploader ───────────────────── */}
        {mode === 'compare' && (
          <CompareUploader
            imageUriA={compareUriA}
            imageUriB={compareUriB}
            isBusy={isBusy}
            onPickImageA={handlePickCompareA}
            onPickImageB={handlePickCompareB}
            onCompare={handleRunComparison}
            onReset={handleReset}
          />
        )}

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
              <TouchableOpacity
                style={styles.retryBtn}
                onPress={handleReset}
                activeOpacity={0.8}
              >
                <Text style={styles.retryBtnText}>↺ Try Again</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}

        {/* ── Result card ────────────────────────────────────────────── */}
        {state.phase === 'complete' && state.result && (
          <>
            <ConfidenceScoreCard result={state.result} />

            {/* Rescan / Start New Test Action */}
            <TouchableOpacity style={styles.bottomRescanBtn} onPress={handleReset} activeOpacity={0.85}>
              <Text style={styles.bottomRescanText}>
                {mode === 'single' ? '📷 Scan Another Product Photo' : '⚡ Compare Two New Photos'}
              </Text>
            </TouchableOpacity>

            {/* Similar products (Single mode only) */}
            {mode === 'single' && (
              <View style={styles.similarSection}>
                <SimilarProductsCarousel
                  products={similarProducts}
                  loading={similarLoading}
                />
              </View>
            )}
          </>
        )}

        {/* ── Explainer (only shown in idle state) ───────────────────── */}
        {state.phase === 'idle' && (
          <View style={styles.explainerSection}>
            <Text style={styles.explainerTitle}>
              {mode === 'single' ? 'How Confidence Scoring Works' : 'How 2-Image Comparison Works'}
            </Text>

            {mode === 'single' ? (
              <>
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
                      Our CLIP engine embeds your photo and compares it to stock listings
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
                      See how closely what you received matches what was advertised
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
              </>
            ) : (
              <>
                <View style={styles.stepRow}>
                  <View style={styles.stepBadge}>
                    <Text style={styles.stepNum}>1</Text>
                  </View>
                  <View style={styles.stepText}>
                    <Text style={styles.stepTitle}>Select Photo 1 (Received)</Text>
                    <Text style={styles.stepDesc}>
                      Upload the physical item photo you want to verify
                    </Text>
                  </View>
                </View>

                <View style={styles.stepRow}>
                  <View style={styles.stepBadge}>
                    <Text style={styles.stepNum}>2</Text>
                  </View>
                  <View style={styles.stepText}>
                    <Text style={styles.stepTitle}>Select Photo 2 (Ad / Reference)</Text>
                    <Text style={styles.stepDesc}>
                      Upload the online listing photo or ad screenshot
                    </Text>
                  </View>
                </View>

                <View style={styles.stepRow}>
                  <View style={styles.stepBadge}>
                    <Text style={styles.stepNum}>3</Text>
                  </View>
                  <View style={styles.stepText}>
                    <Text style={styles.stepTitle}>Direct CLIP Vector Comparison</Text>
                    <Text style={styles.stepDesc}>
                      The AI generates normalized 512-dim embeddings for both images and computes cosine similarity
                    </Text>
                  </View>
                </View>
              </>
            )}
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
    paddingBottom: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#16161C',
    gap: 12,
  },
  headerTopRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  headerTitle: {
    fontSize: 26,
    fontWeight: '900',
    color: '#FF3F6C',
    letterSpacing: 0.3,
  },
  headerSub: {
    fontSize: 12,
    color: '#60606A',
    marginTop: 2,
  },
  headerRescanBtn: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    backgroundColor: 'rgba(255,63,108,0.15)',
    borderWidth: 1,
    borderColor: '#FF3F6C',
  },
  headerRescanText: {
    color: '#FF3F6C',
    fontSize: 12,
    fontWeight: '700',
  },

  // Mode Tabs
  modeTabs: {
    flexDirection: 'row',
    backgroundColor: '#16161C',
    borderRadius: 12,
    padding: 3,
    gap: 4,
  },
  modeTab: {
    flex: 1,
    paddingVertical: 8,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 10,
  },
  modeTabActive: {
    backgroundColor: '#24242E',
  },
  modeTabText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#70707A',
  },
  modeTabTextActive: {
    color: '#E8E8F0',
    fontWeight: '700',
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
  retryBtn: {
    alignSelf: 'flex-start',
    marginTop: 10,
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: '#FF3F6C',
  },
  retryBtnText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '700',
  },

  // Rescan CTA at bottom
  bottomRescanBtn: {
    width: '100%',
    paddingVertical: 14,
    borderRadius: 14,
    backgroundColor: 'rgba(255,63,108,0.12)',
    borderWidth: 1,
    borderColor: '#FF3F6C',
    alignItems: 'center',
    justifyContent: 'center',
  },
  bottomRescanText: {
    color: '#FF3F6C',
    fontSize: 14,
    fontWeight: '800',
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
