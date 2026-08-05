/**
 * Product Service — mobile/services/productService.ts
 *
 * Responsibility: Product listing and detail fetches from the api-backend.
 *
 * Endpoints consumed (Node.js api-backend):
 *   GET /products/:id           — Fetch a single product by ID
 *   GET /products?platform=...  — Fetch product listing with optional filters
 */

import type { Product } from '../types';

export type ApiClient = {
  get<T>(path: string, opts?: object): Promise<T>;
};

export interface ProductListParams {
  platform?: string;
  category?: string;
  limit?: number;
  offset?: number;
}

// ---------------------------------------------------------------------------
// Get product by ID
// ---------------------------------------------------------------------------

/**
 * Fetch a single product by its UUID.
 */
export async function getProduct(
  apiClient: ApiClient,
  productId: string
): Promise<Product> {
  return apiClient.get<Product>(`/products/${productId}`);
}

// ---------------------------------------------------------------------------
// List products
// ---------------------------------------------------------------------------

/**
 * Fetch a paginated list of products with optional platform/category filters.
 */
export async function listProducts(
  apiClient: ApiClient,
  params: ProductListParams = {}
): Promise<{ products: Product[]; total: number }> {
  const qs = new URLSearchParams();
  if (params.platform) qs.set('platform', params.platform);
  if (params.category) qs.set('category', params.category);
  if (params.limit !== undefined) qs.set('limit', String(params.limit));
  if (params.offset !== undefined) qs.set('offset', String(params.offset));

  const query = qs.toString() ? `?${qs.toString()}` : '';
  return apiClient.get<{ products: Product[]; total: number }>(`/products${query}`);
}
