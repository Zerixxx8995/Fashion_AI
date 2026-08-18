/**
 * useCVScore — mobile/hooks/useCVScore.ts
 *
 * Responsibility: Orchestrate the full CV confidence-scoring flow:
 *   1. Pick image from gallery or camera
 *   2. Upload to Backblaze B2 (placeholder: use a local file URI or image URL)
 *   3. Submit job to POST /cv/score
 *   4. Poll GET /cv/score/{job_id}/status every 2s
 *   5. Fetch result from GET /cv/score/{job_id}/result
 *
 * Architecture notes:
 *   - This hook is the ONLY place the polling timer lives.
 *   - All network calls go through cvService (never raw fetch here).
 *   - mlClient is obtained from useHttpClients() inside the hook.
 */

import { useState, useCallback, useRef } from 'react';
import * as ImagePicker from 'expo-image-picker';
import { useHttpClients } from '../services/httpClient';
import {
  submitCVScore,
  getCVJobStatus,
  getCVScoreResult,
} from '../services/cvService';
import type { CVJobStatus, CVScoreResult } from '../types';

// ---------------------------------------------------------------------------
// State shape exposed to consumers
// ---------------------------------------------------------------------------

export type CVScanPhase =
  | 'idle'
  | 'picking'
  | 'uploading'
  | 'submitted'
  | 'polling'
  | 'complete'
  | 'error';

export interface CVScanState {
  phase: CVScanPhase;
  imageUri: string | null;      // local URI of the picked image
  jobId: string | null;
  jobStatus: CVJobStatus | null;
  result: CVScoreResult | null;
  errorMessage: string | null;
  /** 0–1 rough progress for the UI progress bar */
  progress: number;
}

const INITIAL_STATE: CVScanState = {
  phase: 'idle',
  imageUri: null,
  jobId: null,
  jobStatus: null,
  result: null,
  errorMessage: null,
  progress: 0,
};

const POLL_INTERVAL_MS = 2_000;
const MAX_POLLS = 30; // 60 s total

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useCVScore(params: {
  /** Product ID this scan is associated with. Falls back to 'unknown'. */
  productId?: string;
  /** Clerk user ID injected from auth context. Required by the CV endpoint. */
  userId: string;
  /** Stock image URLs to compare against. Can be empty — backend handles it. */
  stockImageUrls?: string[];
}) {
  const { productId = 'unknown', userId, stockImageUrls = [] } = params;
  const { getClients } = useHttpClients();
  const [state, setState] = useState<CVScanState>(INITIAL_STATE);
  const pollCountRef = useRef(0);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // --------------------------------------------------------------------------
  // Helpers
  // --------------------------------------------------------------------------

  const patch = useCallback((partial: Partial<CVScanState>) => {
    setState((prev) => ({ ...prev, ...partial }));
  }, []);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const reset = useCallback(() => {
    stopPolling();
    pollCountRef.current = 0;
    setState(INITIAL_STATE);
  }, [stopPolling]);

  // --------------------------------------------------------------------------
  // Polling loop
  // --------------------------------------------------------------------------

  const poll = useCallback(
    async (jobId: string) => {
      if (pollCountRef.current >= MAX_POLLS) {
        stopPolling();
        patch({
          phase: 'error',
          errorMessage: 'CV scoring timed out after 60 seconds. Please try again.',
        });
        return;
      }

      try {
        const { mlClient } = await getClients();
        const statusResponse = await getCVJobStatus(mlClient, jobId);

        const attempt = pollCountRef.current + 1;
        const progressVal = Math.min(0.9, 0.2 + (attempt / MAX_POLLS) * 0.7);
        patch({
          jobStatus: statusResponse.status,
          phase: 'polling',
          progress: progressVal,
        });

        if (statusResponse.status === 'complete') {
          stopPolling();
          const result = await getCVScoreResult(mlClient, jobId);
          patch({ phase: 'complete', result, progress: 1 });
          return;
        }

        if (statusResponse.status === 'failed') {
          stopPolling();
          patch({ phase: 'error', errorMessage: `Job ${jobId} failed on the server.` });
          return;
        }

        // Still pending/running — schedule next poll
        pollCountRef.current += 1;
        pollTimerRef.current = setTimeout(() => poll(jobId), POLL_INTERVAL_MS);
      } catch (err) {
        stopPolling();
        patch({
          phase: 'error',
          errorMessage: err instanceof Error ? err.message : 'Polling error.',
        });
      }
    },
    [getClients, patch, stopPolling]
  );

  // --------------------------------------------------------------------------
  // Pick image from gallery
  // --------------------------------------------------------------------------

  const pickFromGallery = useCallback(async () => {
    patch({ phase: 'picking' });

    const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (status !== 'granted') {
      patch({
        phase: 'error',
        errorMessage: 'Gallery permission denied. Please enable it in Settings.',
      });
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsEditing: false,
      quality: 0.8,
    });

    if (result.canceled || !result.assets?.[0]) {
      patch({ phase: 'idle' });
      return;
    }

    const imageUri = result.assets[0].uri;
    patch({ imageUri, phase: 'uploading', progress: 0.05 });
    await submitJob(imageUri);
  }, [patch]);

  // --------------------------------------------------------------------------
  // Take photo with camera
  // --------------------------------------------------------------------------

  const takePhoto = useCallback(async () => {
    patch({ phase: 'picking' });

    const { status } = await ImagePicker.requestCameraPermissionsAsync();
    if (status !== 'granted') {
      patch({
        phase: 'error',
        errorMessage: 'Camera permission denied. Please enable it in Settings.',
      });
      return;
    }

    const result = await ImagePicker.launchCameraAsync({
      allowsEditing: false,
      quality: 0.8,
    });

    if (result.canceled || !result.assets?.[0]) {
      patch({ phase: 'idle' });
      return;
    }

    const imageUri = result.assets[0].uri;
    patch({ imageUri, phase: 'uploading', progress: 0.1 });
    await submitJob(imageUri);
  }, [patch]);

  // --------------------------------------------------------------------------
  // Submit the CV job
  // --------------------------------------------------------------------------

  /**
   * For MVP: we pass the local URI as the uploaded_image_url directly.
   * The backend handles downloading if it's a public URL.
   * In production this would be: upload to B2 first → get public URL → submit.
   */
  const submitJob = useCallback(
    async (imageUri: string) => {
      try {
        const { mlClient } = await getClients();
        patch({ phase: 'uploading', progress: 0.15 });

        const submission = await submitCVScore(mlClient, {
          product_id: productId,
          user_id: userId,
          uploaded_image_url: imageUri,
          stock_image_urls: stockImageUrls,
        });

        pollCountRef.current = 0;
        patch({
          jobId: submission.job_id,
          jobStatus: submission.status,
          phase: 'submitted',
          progress: 0.2,
        });

        // Begin polling
        pollTimerRef.current = setTimeout(
          () => poll(submission.job_id),
          POLL_INTERVAL_MS
        );
      } catch (err) {
        patch({
          phase: 'error',
          errorMessage: err instanceof Error ? err.message : 'Failed to submit CV job.',
        });
      }
    },
    [getClients, patch, poll, productId, userId, stockImageUrls]
  );

  return {
    state,
    pickFromGallery,
    takePhoto,
    reset,
  };
}
