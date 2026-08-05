/**
 * HTTP Client — mobile/services/httpClient.ts
 *
 * Responsibility: All network I/O lives here. Every service file calls this.
 *
 * Architecture rules:
 *   - Never make raw fetch() calls outside this file.
 *   - Injects Clerk session token as Bearer on every request automatically.
 *   - Normalises all errors into a consistent ApiError shape.
 *   - Supports timeout with AbortController.
 *   - Two base URLs: API_BASE (Node.js backend) and ML_BASE (FastAPI backend).
 *
 * Base URLs (from Expo env vars):
 *   EXPO_PUBLIC_API_BASE_URL  — Node.js api-backend  (e.g. http://localhost:3000)
 *   EXPO_PUBLIC_ML_BASE_URL   — FastAPI ml-backend   (e.g. http://localhost:8000/api/v1)
 *
 * Usage:
 *   import { apiClient, mlClient } from './httpClient';
 *   const data = await apiClient.get<UserProfile>('/users/me');
 *   const result = await mlClient.post<BudgetOptimizeResponse>('/budget/optimize', { body });
 */

import { useAuth } from '@clerk/expo';
import type { ApiError, RequestOptions } from '../types';

// ---------------------------------------------------------------------------
// Base URLs — read from Expo public env vars at build time
// ---------------------------------------------------------------------------

const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://localhost:3000';

const ML_BASE_URL =
  process.env.EXPO_PUBLIC_ML_BASE_URL ?? 'http://localhost:8000/api/v1';

// ---------------------------------------------------------------------------
// Default timeout
// ---------------------------------------------------------------------------

const DEFAULT_TIMEOUT_MS = 15_000;

// ---------------------------------------------------------------------------
// Error normalisation
// ---------------------------------------------------------------------------

/**
 * Normalise any error into an ApiError.
 * Both backends return `{ error, detail, status_code }`.
 */
async function normaliseError(response: Response): Promise<ApiError> {
  let body: Partial<ApiError> = {};
  try {
    body = await response.json();
  } catch {
    // Response body is not JSON — use status text
  }
  return {
    error: body.error ?? response.statusText ?? 'Unknown error',
    detail: body.detail ?? `HTTP ${response.status}`,
    status_code: body.status_code ?? response.status,
  };
}

/**
 * Thrown on any non-2xx response. Carries the normalised ApiError payload.
 */
export class HttpError extends Error {
  constructor(public readonly apiError: ApiError) {
    super(`[HttpError] ${apiError.status_code} — ${apiError.error}: ${apiError.detail}`);
    this.name = 'HttpError';
  }
}

// ---------------------------------------------------------------------------
// Core fetch wrapper
// ---------------------------------------------------------------------------

async function request<T>(
  baseUrl: string,
  path: string,
  method: string,
  token: string | null,
  options: RequestOptions = {}
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(
    () => controller.abort(),
    options.timeoutMs ?? DEFAULT_TIMEOUT_MS
  );

  const url = `${baseUrl}${path}`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    ...options.headers,
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const init: RequestInit = {
    method,
    headers,
    signal: controller.signal,
  };

  if (options.body !== undefined && method !== 'GET' && method !== 'HEAD') {
    init.body = JSON.stringify(options.body);
  }

  try {
    const response = await fetch(url, init);
    clearTimeout(timeout);

    if (!response.ok) {
      const err = await normaliseError(response);
      throw new HttpError(err);
    }

    // 204 No Content
    if (response.status === 204) {
      return undefined as unknown as T;
    }

    return response.json() as Promise<T>;
  } catch (err) {
    clearTimeout(timeout);

    if (err instanceof HttpError) throw err;

    // AbortError = timeout
    if (err instanceof Error && err.name === 'AbortError') {
      throw new HttpError({
        error: 'Request Timeout',
        detail: `Request to ${url} timed out after ${options.timeoutMs ?? DEFAULT_TIMEOUT_MS}ms`,
        status_code: 408,
      });
    }

    // Network error
    throw new HttpError({
      error: 'Network Error',
      detail: err instanceof Error ? err.message : 'Unknown network error',
      status_code: 0,
    });
  }
}

// ---------------------------------------------------------------------------
// Multipart / FormData upload (used by CV scan)
// ---------------------------------------------------------------------------

async function uploadFormData<T>(
  baseUrl: string,
  path: string,
  formData: FormData,
  token: string | null,
  options: RequestOptions = {}
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(
    () => controller.abort(),
    options.timeoutMs ?? 30_000  // uploads get 30s
  );

  const url = `${baseUrl}${path}`;
  const headers: Record<string, string> = { ...options.headers };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  // Do NOT set Content-Type — browser sets it with correct boundary for multipart

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: formData,
      signal: controller.signal,
    });
    clearTimeout(timeout);

    if (!response.ok) {
      const err = await normaliseError(response);
      throw new HttpError(err);
    }

    return response.json() as Promise<T>;
  } catch (err) {
    clearTimeout(timeout);
    if (err instanceof HttpError) throw err;
    throw new HttpError({
      error: 'Upload Error',
      detail: err instanceof Error ? err.message : 'Unknown upload error',
      status_code: 0,
    });
  }
}

// ---------------------------------------------------------------------------
// Client factory
// ---------------------------------------------------------------------------

/**
 * Build a typed client that is bound to a specific base URL.
 * Call this inside React components / hooks where you have a Clerk token.
 *
 * @param baseUrl - API_BASE_URL or ML_BASE_URL
 * @param token   - Clerk session JWT (or null for unauthenticated requests)
 */
function createClient(baseUrl: string, token: string | null) {
  return {
    get<T>(path: string, opts?: RequestOptions): Promise<T> {
      return request<T>(baseUrl, path, 'GET', token, opts);
    },
    post<T>(path: string, opts?: RequestOptions): Promise<T> {
      return request<T>(baseUrl, path, 'POST', token, opts);
    },
    put<T>(path: string, opts?: RequestOptions): Promise<T> {
      return request<T>(baseUrl, path, 'PUT', token, opts);
    },
    patch<T>(path: string, opts?: RequestOptions): Promise<T> {
      return request<T>(baseUrl, path, 'PATCH', token, opts);
    },
    delete<T>(path: string, opts?: RequestOptions): Promise<T> {
      return request<T>(baseUrl, path, 'DELETE', token, opts);
    },
    uploadForm<T>(path: string, form: FormData, opts?: RequestOptions): Promise<T> {
      return uploadFormData<T>(baseUrl, path, form, token, opts);
    },
  };
}

export type ApiClient = ReturnType<typeof createClient>;



// ---------------------------------------------------------------------------
// Hook — useHttpClients
// ---------------------------------------------------------------------------

/**
 * React hook that returns both API clients pre-loaded with the current Clerk
 * session token. Use this inside any component or custom hook.
 *
 * @example
 *   const { apiClient, mlClient } = useHttpClients();
 *   const profile = await apiClient.get<UserProfile>('/users/me');
 */
export function useHttpClients() {
  const { getToken } = useAuth();

  const getClients = async () => {
    const token = await getToken();
    return {
      /** Calls the Node.js api-backend (auth, users, alerts, wardrobe) */
      apiClient: createClient(API_BASE_URL, token),
      /** Calls the FastAPI ml-backend (CV, trends, budget, similarity) */
      mlClient: createClient(ML_BASE_URL, token),
    };
  };

  return { getClients };
}

// ---------------------------------------------------------------------------
// Unauthenticated client (for public endpoints like /health)
// ---------------------------------------------------------------------------

export const publicApiClient = createClient(API_BASE_URL, null);
export const publicMlClient = createClient(ML_BASE_URL, null);

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

export { API_BASE_URL, ML_BASE_URL };
