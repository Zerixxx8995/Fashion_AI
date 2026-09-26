/**
 * useExplanation — mobile/hooks/useExplanation.ts
 *
 * Responsibility: Manage lazy fetch + loading/error state for LLM explanations.
 *
 * Architecture rules:
 *   - Lazy — only fetches when `enabled` is true (controlled by ExplanationAccordion)
 *   - Caches result in component state — re-tapping is instant (no second API call)
 *   - All network calls go through explanationService (never raw fetch here)
 *   - mlClient is obtained from useHttpClients() inside the hook
 */

import { useState, useEffect, useRef } from 'react';
import { useHttpClients } from '../services/httpClient';
import {
  getTrendExplanation,
  getRecommendationExplanation,
} from '../services/explanationService';

// ---------------------------------------------------------------------------
// Input params
// ---------------------------------------------------------------------------

export interface UseExplanationParams {
  /** trend_id or product_id */
  id: string;
  /** Determines which endpoint is called */
  type: 'trend' | 'recommendation';
  /** Required when type === "recommendation" */
  userId?: string;
  /**
   * When false (default), the hook does nothing.
   * Set to true to trigger the fetch (on first user tap).
   * The hook then fetches once and caches the result indefinitely.
   */
  enabled?: boolean;
}

// ---------------------------------------------------------------------------
// Return shape
// ---------------------------------------------------------------------------

export interface UseExplanationResult {
  explanation: string | null;
  loading: boolean;
  error: string | null;
  retry: () => void;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useExplanation({
  id,
  type,
  userId,
  enabled = false,
}: UseExplanationParams): UseExplanationResult {
  const [explanation, setExplanation] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  // Track whether we've already fetched — explanation is cached in state after first fetch
  const hasFetched = useRef(false);
  const isMounted = useRef(true);

  const { getClients } = useHttpClients();
  const getClientsRef = useRef(getClients);
  getClientsRef.current = getClients;

  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
    };
  }, []);

  const retry = () => {
    hasFetched.current = false;
    setError(null);
    setRetryCount((c) => c + 1);
  };

  useEffect(() => {
    // Only fetch once when enabled becomes true
    if (!enabled || hasFetched.current) return;

    hasFetched.current = true;

    const fetchExplanation = async () => {
      setLoading(true);
      setError(null);

      try {
        const { mlClient } = await getClientsRef.current();

        let text: string;

        if (type === 'trend') {
          const response = await getTrendExplanation(mlClient, id);
          text = response.explanation;
        } else {
          if (!userId) {
            throw new Error('userId is required for recommendation explanations');
          }
          const response = await getRecommendationExplanation(mlClient, id, userId);
          text = response.explanation;
        }

        if (isMounted.current) {
          setExplanation(text);
        }
      } catch (err) {
        if (isMounted.current) {
          const message =
            err instanceof Error ? err.message : 'Failed to load explanation';
          setError(message);
        }
      } finally {
        if (isMounted.current) {
          setLoading(false);
        }
      }
    };

    fetchExplanation();
  }, [enabled, id, type, userId, retryCount]);

  return { explanation, loading, error, retry };
}
