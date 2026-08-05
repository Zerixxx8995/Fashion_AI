/**
 * Wardrobe Service — mobile/services/wardrobeService.ts
 *
 * Responsibility: All wardrobe API calls from the mobile app.
 *
 * Endpoints consumed:
 *   FastAPI ml-backend (/api/v1):
 *     POST /wardrobe/gap-analysis       — Capsule gap analysis
 *
 *   Node.js api-backend:
 *     POST   /wardrobe                  — Add item to wardrobe
 *     GET    /wardrobe/:userId          — Get all wardrobe items for user
 *     DELETE /wardrobe/:itemId          — Remove item from wardrobe
 */

import type {
  WardrobeItem,
  GapAnalysisRequest,
  GapAnalysisResponse,
} from '../types';

export type MlClient = {
  post<T>(path: string, opts?: object): Promise<T>;
};

export type ApiClient = {
  get<T>(path: string, opts?: object): Promise<T>;
  post<T>(path: string, opts?: object): Promise<T>;
  delete<T>(path: string, opts?: object): Promise<T>;
};

// ---------------------------------------------------------------------------
// Wardrobe CRUD (api-backend)
// ---------------------------------------------------------------------------

/** Add a product to the user's wardrobe. */
export async function addWardrobeItem(
  apiClient: ApiClient,
  productId: string
): Promise<WardrobeItem> {
  return apiClient.post<WardrobeItem>('/wardrobe', { body: { productId } });
}

/** Get all wardrobe items for a user. */
export async function getWardrobeItems(
  apiClient: ApiClient,
  userId: string
): Promise<WardrobeItem[]> {
  return apiClient.get<WardrobeItem[]>(`/wardrobe/${userId}`);
}

/** Remove an item from the wardrobe. */
export async function removeWardrobeItem(
  apiClient: ApiClient,
  itemId: string
): Promise<void> {
  return apiClient.delete<void>(`/wardrobe/${itemId}`);
}

// ---------------------------------------------------------------------------
// Gap analysis (ml-backend)
// ---------------------------------------------------------------------------

/**
 * Submit the user's wardrobe category list and receive a capsule gap analysis.
 * Returns missing categories, priority rankings, and budget recommendations.
 */
export async function getGapAnalysis(
  mlClient: MlClient,
  request: GapAnalysisRequest
): Promise<GapAnalysisResponse> {
  return mlClient.post<GapAnalysisResponse>('/wardrobe/gap-analysis', {
    body: request,
  });
}
