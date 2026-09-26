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

export type MlClient = {
  get<T>(path: string, opts?: object): Promise<T>;
};

export interface ReviewAuthenticityExplanation {
  review_id: string;
  overall_verdict: string;
  confidence_score: number;
  suspicious_phrases: string[];
  image_mismatch_summary: string;
  pattern_matches: string[];
  recommendation: string;
  cached: boolean;
}

export async function getReviewExplanation(
  mlClient: MlClient,
  reviewId: string,
): Promise<ReviewAuthenticityExplanation> {
  return mlClient.get<ReviewAuthenticityExplanation>(
    `/reviews/${encodeURIComponent(reviewId)}/explain`,
  );
}
