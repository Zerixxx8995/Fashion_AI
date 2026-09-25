/**
 * Explanation Service — mobile/services/explanationService.ts
 *
 * Responsibility: Calls explanation endpoints on the ml-backend.
 *
 * Endpoints consumed (FastAPI ml-backend, prefix: /api/v1):
 *   GET /explanations/trend/{trend_id}
 *   GET /explanations/recommendation/{product_id}?user_id=...
 *
 * Architecture rules:
 *   - Only HTTP calls live here — no component state, no caching logic
 *   - All caching is component-level via useExplanation hook
 */

export type MlClient = {
  get<T>(path: string, opts?: object): Promise<T>;
};

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

export interface TrendExplanationResponse {
  trend_id: string;
  trend_name: string;
  explanation: string;
  cached: boolean;
  generated_at: string;
}

export interface RecommendationExplanationResponse {
  product_id: string;
  product_name: string;
  explanation: string;
  cached: boolean;
  generated_at: string;
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

/**
 * Fetch a natural-language explanation for why a trend is popular.
 * Called lazily — only when the user taps to expand.
 *
 * @param mlClient  Configured axios-based HTTP client (from httpClient.ts)
 * @param trendId   UUID of the TrendItem
 */
export async function getTrendExplanation(
  mlClient: MlClient,
  trendId: string
): Promise<TrendExplanationResponse> {
  return mlClient.get<TrendExplanationResponse>(
    `/explanations/trend/${trendId}`
  );
}

/**
 * Fetch a personalised explanation for why a product suits a specific user.
 * Called lazily — only when the user taps to expand.
 *
 * @param mlClient  Configured axios-based HTTP client
 * @param productId UUID of the Product
 * @param userId    User's UUID or Clerk ID (for personalisation)
 */
export async function getRecommendationExplanation(
  mlClient: MlClient,
  productId: string,
  userId: string
): Promise<RecommendationExplanationResponse> {
  return mlClient.get<RecommendationExplanationResponse>(
    `/explanations/recommendation/${productId}?user_id=${encodeURIComponent(userId)}`
  );
}
