/**
 * useReviewExplanation — mobile/hooks/useReviewExplanation.ts
 *
 * Responsibility: Lazy-fetch review authenticity explanation.
 * Fetch is triggered ONLY when enabled=true (i.e. after first user tap).
 * Mirrors the useExplanation hook pattern from Feature 1.
 *
 * Usage:
 *   const { explanation, loading, error, retry } = useReviewExplanation({
 *     reviewId: 'uuid...',
 *     enabled: hasTapped,
 *   });
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { useHttpClients } from '../services/httpClient';
import {
  getReviewExplanation,
  type ReviewAuthenticityExplanation,
} from '../services/reviewExplainService';

interface UseReviewExplanationOptions {
  /** UUID of the flagged review to explain. */
  reviewId: string;
  /**
   * When false (default), no fetch is made.
   * Set to true on first user tap to trigger the lazy fetch.
   */
  enabled: boolean;
}

interface UseReviewExplanationReturn {
  explanation: ReviewAuthenticityExplanation | null;
  loading: boolean;
  error: string | null;
  /** Re-trigger the fetch (called on error tap). */
  retry: () => void;
}

export function useReviewExplanation({
  reviewId,
  enabled,
}: UseReviewExplanationOptions): UseReviewExplanationReturn {
  const { getClients } = useHttpClients();

  const [explanation, setExplanation] = useState<ReviewAuthenticityExplanation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  const isFetchingRef = useRef(false);

  useEffect(() => {
    if (!reviewId || !enabled) return;
    if (explanation !== null) return;
    if (isFetchingRef.current) return;

    let isMounted = true;
    isFetchingRef.current = true;
    setLoading(true);
    setError(null);

    (async () => {
      try {
        const { mlClient } = await getClients();
        const data = await getReviewExplanation(mlClient, reviewId);
        if (isMounted) {
          setExplanation(data);
          setError(null);
        }
      } catch (err: unknown) {
        if (isMounted) {
          const message =
            err instanceof Error ? err.message : 'Failed to load explanation';
          setError(message);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
        isFetchingRef.current = false;
      }
    })();

    return () => {
      isMounted = false;
    };
  }, [reviewId, enabled, retryCount]);

  const retry = useCallback(() => {
    setExplanation(null);
    setError(null);
    setRetryCount((n) => n + 1);
  }, []);

  return { explanation, loading, error, retry };
}
