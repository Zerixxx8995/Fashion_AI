/**
 * CV Service — mobile/services/cvService.ts
 *
 * Responsibility: All Computer Vision API calls from the mobile app.
 *
 * Endpoints consumed (FastAPI ml-backend, prefix: /api/v1):
 *   POST /cv/score                   — Submit image for confidence scoring (202)
 *   GET  /cv/score/{job_id}/status   — Poll job status
 *   GET  /cv/score/{job_id}/result   — Retrieve completed result
 *   POST /cv/similar                 — Find visually similar cheaper products
 *
 * Consumers call useHttpClients() to obtain mlClient, then pass it in.
 * This keeps the service layer pure (no React hooks inside service files).
 */

import type {
  CVJobSubmitResponse,
  CVJobStatusResponse,
  CVScoreResult,
  SimilarProductsRequest,
  SimilarProductsResponse,
} from '../types';

/** Opaque type alias for the mlClient returned by useHttpClients().getClients() */
export type MlClient = {
  get<T>(path: string, opts?: object): Promise<T>;
  post<T>(path: string, opts?: object): Promise<T>;
  uploadForm<T>(path: string, form: FormData, opts?: object): Promise<T>;
};

/** CV polling interval in ms */
const POLL_INTERVAL_MS = 2_000;
/** Max polls before timing out (60s total) */
const MAX_POLLS = 30;

// ---------------------------------------------------------------------------
// Submit CV score job
// ---------------------------------------------------------------------------

/**
 * Submit a product image for CV confidence scoring.
 * Uses FormData — the image URLs are passed as form fields.
 * Returns a job envelope with a job_id immediately (HTTP 202).
 */
export async function submitCVScore(
  mlClient: MlClient,
  params: {
    product_id: string;
    user_id: string;
    uploaded_image_url: string;
    stock_image_urls: string[];
  }
): Promise<CVJobSubmitResponse> {
  const form = new FormData();
  form.append('product_id', params.product_id);
  form.append('user_id', params.user_id);

  if (
    params.uploaded_image_url.startsWith('file://') ||
    params.uploaded_image_url.startsWith('content://') ||
    params.uploaded_image_url.startsWith('ph://')
  ) {
    const rawUri = params.uploaded_image_url;
    const filename = rawUri.split('/').pop() || 'photo.jpg';
    const cleanFilename = filename.includes('.') ? filename : `${filename}.jpg`;

    form.append('file', {
      uri: rawUri,
      name: cleanFilename,
      type: 'image/jpeg',
    } as any);
  } else {
    form.append('uploaded_image_url', params.uploaded_image_url);
  }

  if (params.stock_image_urls && params.stock_image_urls.length > 0) {
    params.stock_image_urls.forEach((url, idx) => {
      if (
        url.startsWith('file://') ||
        url.startsWith('content://') ||
        url.startsWith('ph://')
      ) {
        const filename = url.split('/').pop() || `stock_${idx}.jpg`;
        const cleanFilename = filename.includes('.') ? filename : `${filename}.jpg`;
        form.append('stock_files', {
          uri: url,
          name: cleanFilename,
          type: 'image/jpeg',
        } as any);
      } else {
        form.append('stock_image_urls', url);
      }
    });
  }

  return mlClient.uploadForm<CVJobSubmitResponse>('/cv/score', form);
}

// ---------------------------------------------------------------------------
// Poll job status
// ---------------------------------------------------------------------------

/** Get the current status of a CV scoring job. */
export async function getCVJobStatus(
  mlClient: MlClient,
  jobId: string
): Promise<CVJobStatusResponse> {
  return mlClient.get<CVJobStatusResponse>(`/cv/score/${jobId}/status`);
}

// ---------------------------------------------------------------------------
// Get completed result
// ---------------------------------------------------------------------------

/** Fetch the full confidence scoring result for a completed job. */
export async function getCVScoreResult(
  mlClient: MlClient,
  jobId: string
): Promise<CVScoreResult> {
  return mlClient.get<CVScoreResult>(`/cv/score/${jobId}/result`);
}

// ---------------------------------------------------------------------------
// Polling helper
// ---------------------------------------------------------------------------

/**
 * Submit a CV score job and poll until complete or failed.
 *
 * @param mlClient       - mlClient from useHttpClients().getClients()
 * @param params         - same as submitCVScore params
 * @param onStatusUpdate - optional callback on each poll (e.g. to update UI)
 * @returns The completed CVScoreResult
 * @throws  Error if job fails or exceeds MAX_POLLS × POLL_INTERVAL_MS timeout
 */
export async function pollCVScore(
  mlClient: MlClient,
  params: Parameters<typeof submitCVScore>[1],
  onStatusUpdate?: (status: CVJobStatusResponse) => void
): Promise<CVScoreResult> {
  const submission = await submitCVScore(mlClient, params);
  const { job_id } = submission;

  for (let attempt = 0; attempt < MAX_POLLS; attempt++) {
    await delay(POLL_INTERVAL_MS);

    const statusResponse = await getCVJobStatus(mlClient, job_id);
    onStatusUpdate?.(statusResponse);

    if (statusResponse.status === 'complete') {
      return getCVScoreResult(mlClient, job_id);
    }

    if (statusResponse.status === 'failed') {
      throw new Error(`CV scoring job ${job_id} failed.`);
    }
    // status is 'pending' or 'running' — keep polling
  }

  throw new Error(
    `CV scoring job ${job_id} timed out after ${(MAX_POLLS * POLL_INTERVAL_MS) / 1000}s`
  );
}

// ---------------------------------------------------------------------------
// Similar products
// ---------------------------------------------------------------------------

/**
 * Find visually similar (and optionally cheaper) products.
 * Either image_url or text_query must be provided.
 */
export async function findSimilarProducts(
  mlClient: MlClient,
  request: SimilarProductsRequest
): Promise<SimilarProductsResponse> {
  return mlClient.post<SimilarProductsResponse>('/cv/similar', { body: request });
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
