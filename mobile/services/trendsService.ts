/**
 * Trends Service — mobile/services/trendsService.ts
 *
 * Responsibility: Fetch trending fashion items from the ml-backend.
 *
 * Endpoints consumed (FastAPI ml-backend, prefix: /api/v1):
 *   GET  /trends           — Fetch trending items feed (optional category + limit)
 *   POST /trends/recalculate — Trigger server-side trend recalculation (admin)
 */

import type { TrendsResponse } from '../types';

export type MlClient = {
  get<T>(path: string, opts?: object): Promise<T>;
  post<T>(path: string, opts?: object): Promise<T>;
};

// ---------------------------------------------------------------------------
// Get trends
// ---------------------------------------------------------------------------

export interface GetTrendsParams {
  /** Optional category filter (e.g. 'tops', 'jeans'). Omit for all categories. */
  category?: string;
  /** Number of trend items to return. 1–50. Default: 10 */
  limit?: number;
}

/**
 * Fetch the current trending items feed.
 * Items include lifecycle_stage ('emerging' | 'peaking' | 'dying') and trend_score.
 */
export async function getTrends(
  mlClient: MlClient,
  params: GetTrendsParams = {}
): Promise<TrendsResponse> {
  const qs = new URLSearchParams();
  if (params.category) qs.set('category', params.category);
  if (params.limit !== undefined) qs.set('limit', String(params.limit));

  const query = qs.toString() ? `?${qs.toString()}` : '';
  return mlClient.get<TrendsResponse>(`/trends${query}`);
}

// ---------------------------------------------------------------------------
// Trigger recalculation (admin / background job)
// ---------------------------------------------------------------------------

/**
 * Trigger a server-side trend signal recalculation.
 * Not normally called from the mobile app — used for admin tooling.
 */
export async function recalculateTrends(
  mlClient: MlClient
): Promise<{ message: string }> {
  return mlClient.post<{ message: string }>('/trends/recalculate');
}
