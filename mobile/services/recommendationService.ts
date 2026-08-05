/**
 * Recommendation Service — mobile/services/recommendationService.ts
 *
 * Responsibility: Style recommendation and user profile-based suggestion calls.
 *
 * Note: As of Step 17, the recommendation routes are planned (Step 8 defined
 * the Pinecone + similarity backbone). This service wraps the /cv/similar endpoint
 * for product-based discovery and the ml-backend /recommendations endpoint
 * when it is wired up.
 *
 * Endpoints consumed (FastAPI ml-backend, prefix: /api/v1):
 *   POST /cv/similar — Find visually similar products (the core recommendation engine)
 *
 * Future endpoint (wired in Step 8 but exposed via this service):
 *   GET  /recommendations/:user_id — Get personalised recommendations
 */

import type { SimilarProductsRequest, SimilarProductsResponse } from '../types';

export type MlClient = {
  get<T>(path: string, opts?: object): Promise<T>;
  post<T>(path: string, opts?: object): Promise<T>;
};

// ---------------------------------------------------------------------------
// Find similar / cheaper products (recommendation core)
// ---------------------------------------------------------------------------

/**
 * Find visually similar products, optionally filtered by max price.
 * This is the primary recommendation surface — it powers both:
 *   - "Find Similar But Cheaper" (when max_price_inr is set)
 *   - "You Might Also Like" discovery carousel
 */
export async function getSimilarProducts(
  mlClient: MlClient,
  request: SimilarProductsRequest
): Promise<SimilarProductsResponse> {
  return mlClient.post<SimilarProductsResponse>('/cv/similar', { body: request });
}

// ---------------------------------------------------------------------------
// Personalised recommendations (future endpoint)
// ---------------------------------------------------------------------------

/**
 * Get personalised recommendations for a user based on body type + taste profile.
 * Returns a SimilarProductsResponse-compatible shape.
 *
 * NOTE: Will return 404 until the recommendations router is mounted in ml-backend.
 * Safe to call — catches 404 and returns empty results.
 */
export async function getPersonalisedRecommendations(
  mlClient: MlClient,
  userId: string,
  limit = 10
): Promise<SimilarProductsResponse> {
  try {
    return await mlClient.get<SimilarProductsResponse>(
      `/recommendations/${userId}?limit=${limit}`
    );
  } catch {
    // Endpoint not yet live — return empty
    return { results: [], total: 0 };
  }
}
