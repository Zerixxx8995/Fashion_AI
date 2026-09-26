/**
 * reviewExplainService — mobile/services/reviewExplainService.ts
 *
 * Responsibility: Call GET /api/v1/reviews/{review_id}/explain on the ML backend.
 *
 * Architecture:
 *   - Uses the same mlClient httpClient pattern as other ML services.
 *   - Returns ReviewAuthenticityExplanation matching the Pydantic schema.
 *   - Never caches here — caching is Redis-side (48h TTL).
 */

import type { AxiosInstance } from 'axios';

// ---------------------------------------------------------------------------
// Response type — mirrors ReviewAuthenticityExplanation Pydantic schema
// ---------------------------------------------------------------------------

export interface ReviewAuthenticityExplanation {
  review_id: string;
  overall_verdict: 'Likely fake' | 'Possibly fake' | 'Inconclusive';
  confidence_score: number;           // 0.0 – 1.0
  suspicious_phrases: string[];
  image_mismatch_summary: string;
  pattern_matches: string[];
  recommendation: string;
  cached: boolean;
}

// ---------------------------------------------------------------------------
// Service call
// ---------------------------------------------------------------------------

/**
 * Fetch the authenticity explanation for a flagged review.
 *
 * @param mlClient  Authenticated ML backend Axios instance.
 * @param reviewId  UUID of the flagged Review.
 * @returns         ReviewAuthenticityExplanation or throws on error.
 */
export async function getReviewExplanation(
  mlClient: AxiosInstance,
  reviewId: string,
): Promise<ReviewAuthenticityExplanation> {
  const response = await mlClient.get<ReviewAuthenticityExplanation>(
    `/reviews/${encodeURIComponent(reviewId)}/explain`,
  );
  return response.data;
}
