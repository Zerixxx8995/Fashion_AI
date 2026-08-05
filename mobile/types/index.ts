/**
 * Shared TypeScript interfaces — mobile/types/index.ts
 *
 * Single source of truth for all domain types used across the mobile app.
 * These mirror the backend Pydantic/Sequelize models exactly.
 * Never import from individual service files — always use this file.
 */

// ---------------------------------------------------------------------------
// Platform
// ---------------------------------------------------------------------------

/** All supported Indian fashion e-commerce platforms. */
export type Platform = 'myntra' | 'amazon' | 'flipkart' | 'meesho' | 'ajio';

// ---------------------------------------------------------------------------
// Product
// ---------------------------------------------------------------------------

/** Mirrors the Product DB model (products table). */
export interface Product {
  id: string;
  platform: Platform;
  platform_id: string;
  name: string;
  brand: string | null;
  price_inr: number | null;
  stock_image_urls: string[];
  category: string | null;
  url: string;
  seller_id: string | null;
  scraped_at: string; // ISO 8601
}

// ---------------------------------------------------------------------------
// Confidence Score (CV Engine)
// ---------------------------------------------------------------------------

/** Job status values returned by /cv/score/{job_id}/status */
export type CVJobStatus = 'pending' | 'running' | 'complete' | 'failed';

/** Response from POST /cv/score — immediate job acceptance */
export interface CVJobSubmitResponse {
  job_id: string;
  status: CVJobStatus;
  message: string;
}

/** Response from GET /cv/score/{job_id}/status */
export interface CVJobStatusResponse {
  job_id: string;
  status: CVJobStatus;
}

/** Full confidence scoring result from GET /cv/score/{job_id}/result */
export interface CVScoreResult {
  job_id: string;
  status: CVJobStatus;
  product_id: string;
  user_id: string;
  confidence_score: number;       // 0.0 – 1.0
  fake_review_flag: boolean;
  matching_stock_url: string | null;
  computed_at: string;            // ISO 8601
}

/** Request body for POST /cv/similar */
export interface SimilarProductsRequest {
  image_url?: string;
  text_query?: string;
  max_price_inr?: number;
  category?: string;
  top_k?: number;
}

/** Single item in similar products results */
export interface SimilarProduct {
  product_id: string;
  platform: Platform;
  name: string;
  price_inr: number;
  url: string;
  similarity_score: number;       // 0.0 – 1.0
  stock_image_url: string | null;
}

/** Response from POST /cv/similar */
export interface SimilarProductsResponse {
  results: SimilarProduct[];
  total: number;
}

// ---------------------------------------------------------------------------
// Trends
// ---------------------------------------------------------------------------

export type LifecycleStage = 'emerging' | 'peaking' | 'dying';

/** Single trend item from GET /trends */
export interface TrendItem {
  category: string;
  lifecycle_stage: LifecycleStage;
  trend_score: number;            // 0.0 – 1.0
  product_count: number;
  representative_image_url: string | null;
  platforms: Platform[];
}

/** Response from GET /trends */
export interface TrendsResponse {
  trends: TrendItem[];
  total: number;
  computed_at: string;            // ISO 8601
}

// ---------------------------------------------------------------------------
// Wardrobe
// ---------------------------------------------------------------------------

/** Wardrobe item stored for a user (Sequelize WardrobeItem) */
export interface WardrobeItem {
  id: string;
  userId: string;
  productId: string;
  product?: Product;
  addedAt: string;                // ISO 8601
}

/** Request body for POST /api/v1/wardrobe/gap-analysis */
export interface GapAnalysisRequest {
  user_id: string;
  categories: string[];
}

/** Single gap item in gap analysis response */
export interface GapItem {
  missing_category: string;
  priority: 'high' | 'medium' | 'low';
  suggested_budget_inr: number | null;
  reason: string;
}

/** Response from POST /api/v1/wardrobe/gap-analysis */
export interface GapAnalysisResponse {
  user_id: string;
  coverage_score: number;         // 0.0 – 1.0
  gaps: GapItem[];
  total_gaps: number;
}

// ---------------------------------------------------------------------------
// Budget Optimizer
// ---------------------------------------------------------------------------

export type BudgetOccasion =
  | 'casual'
  | 'office'
  | 'party'
  | 'wedding'
  | 'sport'
  | 'festive';

/** Request body for POST /api/v1/budget/optimize */
export interface BudgetOptimizeRequest {
  budget_inr: number;
  occasion: BudgetOccasion;
}

/** Single category allocation from budget optimizer */
export interface CategoryAllocation {
  category: string;
  label: string;
  amount_inr: number;
  percentage: number;
}

/** Response from POST /api/v1/budget/optimize */
export interface BudgetOptimizeResponse {
  budget_inr: number;
  occasion: string;
  allocations: CategoryAllocation[];
  tips: string[];
}

// ---------------------------------------------------------------------------
// Alerts
// ---------------------------------------------------------------------------

export type AlertType = 'price_drop' | 'restock';

/** Alert object from the api-backend (Sequelize Alert) */
export interface Alert {
  id: string;
  userId: string;
  productId: string;
  product?: Product;
  type: AlertType;
  target_price_inr: number | null;
  triggered: boolean;
  createdAt: string;              // ISO 8601
  updatedAt: string;              // ISO 8601
}

/** Request body for POST /alerts */
export interface CreateAlertRequest {
  productId: string;
  type: AlertType;
  target_price_inr?: number;
}

// ---------------------------------------------------------------------------
// Auth / User
// ---------------------------------------------------------------------------

/** User profile from GET /users/:id */
export interface UserProfile {
  id: string;
  clerk_id: string;
  email: string;
  name: string | null;
  body_type: string | null;
  taste_preferences: string[];
  createdAt: string;              // ISO 8601
}

// ---------------------------------------------------------------------------
// API error shape (consistent across both backends)
// ---------------------------------------------------------------------------

/** Both backends return this shape on error. */
export interface ApiError {
  error: string;
  detail: string;
  status_code: number;
}

// ---------------------------------------------------------------------------
// HTTP client types
// ---------------------------------------------------------------------------

/** Options accepted by the httpClient request methods. */
export interface RequestOptions {
  /** Override the auth token (defaults to Clerk session token). */
  token?: string;
  /** Extra headers merged into every request. */
  headers?: Record<string, string>;
  /** Request body — will be JSON serialised for non-multipart requests. */
  body?: unknown;
  /** Milliseconds before the request is aborted. Default: 15000 */
  timeoutMs?: number;
}
