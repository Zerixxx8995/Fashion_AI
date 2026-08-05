/**
 * Alert Service — mobile/services/alertService.ts
 *
 * Responsibility: All price drop and restock alert API calls.
 *
 * Endpoints consumed (Node.js api-backend):
 *   POST   /alerts            — Create a new price drop or restock alert
 *   GET    /alerts/:userId    — Get all alerts for a user
 *   DELETE /alerts/:id        — Delete an alert
 */

import type { Alert, CreateAlertRequest } from '../types';

export type ApiClient = {
  get<T>(path: string, opts?: object): Promise<T>;
  post<T>(path: string, opts?: object): Promise<T>;
  delete<T>(path: string, opts?: object): Promise<T>;
};

// ---------------------------------------------------------------------------
// Create alert
// ---------------------------------------------------------------------------

/**
 * Create a price drop or restock alert for a product.
 * The authenticated user is determined server-side from the JWT.
 */
export async function createAlert(
  apiClient: ApiClient,
  request: CreateAlertRequest
): Promise<Alert> {
  return apiClient.post<Alert>('/alerts', { body: request });
}

// ---------------------------------------------------------------------------
// Get user alerts
// ---------------------------------------------------------------------------

/**
 * Fetch all alerts for a specific user.
 * Returns both triggered and untriggered alerts.
 */
export async function getUserAlerts(
  apiClient: ApiClient,
  userId: string
): Promise<Alert[]> {
  return apiClient.get<Alert[]>(`/alerts/${userId}`);
}

// ---------------------------------------------------------------------------
// Delete alert
// ---------------------------------------------------------------------------

/**
 * Delete a specific alert by its ID.
 * Only the owning user may delete their alert (enforced server-side).
 */
export async function deleteAlert(
  apiClient: ApiClient,
  alertId: string
): Promise<void> {
  return apiClient.delete<void>(`/alerts/${alertId}`);
}
