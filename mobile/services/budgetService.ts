/**
 * Budget Service — mobile/services/budgetService.ts
 *
 * Responsibility: Outfit budget optimisation API calls.
 *
 * Endpoints consumed (FastAPI ml-backend, prefix: /api/v1):
 *   POST /budget/optimize — Compute proportional outfit budget allocations
 */

import type {
  BudgetOptimizeRequest,
  BudgetOptimizeResponse,
} from '../types';

export type MlClient = {
  post<T>(path: string, opts?: object): Promise<T>;
};

/**
 * Submit a total outfit budget and occasion type.
 * Returns proportional allocations across clothing categories (tops, bottoms,
 * footwear, accessories, etc.) with tailored shopping tips.
 *
 * The allocations always sum exactly to budget_inr.
 */
export async function optimizeBudget(
  mlClient: MlClient,
  request: BudgetOptimizeRequest
): Promise<BudgetOptimizeResponse> {
  return mlClient.post<BudgetOptimizeResponse>('/budget/optimize', {
    body: request,
  });
}
