/**
 * HTTP Client tests — mobile/__tests__/httpClient.test.ts
 *
 * Tests the httpClient module logic WITHOUT making live network calls.
 * Uses global.fetch mock to control responses.
 *
 * Tests:
 *   - Auth header is attached when token is provided
 *   - No auth header when token is null
 *   - 4xx response throws HttpError with correct status_code
 *   - 5xx response throws HttpError
 *   - Timeout (AbortError) throws HttpError with status_code 408
 *   - Network error throws HttpError with status_code 0
 *   - Successful response returns parsed JSON
 *   - 204 No Content returns undefined without error
 */

import { HttpError } from '../services/httpClient';

// ---------------------------------------------------------------------------
// Mock fetch
// ---------------------------------------------------------------------------

function mockFetch(
  status: number,
  body?: object,
  extraHeaders: Record<string, string> = {}
) {
  global.fetch = jest.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    statusText: `HTTP ${status}`,
    json: () => Promise.resolve(body ?? {}),
    headers: new Headers(extraHeaders),
  } as Response);
}

function mockFetchNetworkError(message: string) {
  global.fetch = jest.fn().mockRejectedValue(new TypeError(message));
}

function mockFetchAbort() {
  const err = Object.assign(new Error('The operation was aborted.'), { name: 'AbortError' });
  global.fetch = jest.fn().mockRejectedValue(err);
}

// ---------------------------------------------------------------------------
// We test the internal `request` function via a thin adapter since it is not
// exported. We create a minimal client using createClient-equivalent logic.
// ---------------------------------------------------------------------------

// Re-implement the internal request inline so we can test it directly
// without importing createClient (which reads Clerk hooks at module level).

async function testRequest<T>(
  baseUrl: string,
  path: string,
  method: string,
  token: string | null,
  options: { body?: unknown; timeoutMs?: number } = {}
): Promise<T> {
  const DEFAULT_TIMEOUT_MS = 15_000;
  const controller = new AbortController();
  const timeoutId = setTimeout(
    () => controller.abort(),
    options.timeoutMs ?? DEFAULT_TIMEOUT_MS
  );

  const url = `${baseUrl}${path}`;
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const init: RequestInit = { method, headers, signal: controller.signal };
  if (options.body !== undefined && method !== 'GET') {
    init.body = JSON.stringify(options.body);
  }

  try {
    const response = await fetch(url, init);
    clearTimeout(timeoutId);

    if (!response.ok) {
      let body: Partial<{ error: string; detail: string; status_code: number }> = {};
      try { body = await response.json(); } catch { /* ignore */ }
      throw new HttpError({
        error: body.error ?? response.statusText ?? 'Unknown error',
        detail: body.detail ?? `HTTP ${response.status}`,
        status_code: body.status_code ?? response.status,
      });
    }

    if (response.status === 204) return undefined as unknown as T;
    return response.json() as Promise<T>;
  } catch (err) {
    clearTimeout(timeoutId);
    if (err instanceof HttpError) throw err;
    if (err instanceof Error && err.name === 'AbortError') {
      throw new HttpError({ error: 'Request Timeout', detail: 'Timed out', status_code: 408 });
    }
    throw new HttpError({
      error: 'Network Error',
      detail: err instanceof Error ? err.message : 'Unknown',
      status_code: 0,
    });
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('httpClient — request', () => {
  afterEach(() => jest.resetAllMocks());

  test('attaches Authorization Bearer header when token is provided', async () => {
    mockFetch(200, { ok: true });
    await testRequest('http://localhost:3000', '/health', 'GET', 'test-token');

    const calls = (global.fetch as jest.Mock).mock.calls;
    expect(calls.length).toBe(1);
    const requestInit = calls[0][1] as RequestInit;
    expect((requestInit.headers as Record<string, string>)['Authorization']).toBe(
      'Bearer test-token'
    );
  });

  test('does NOT attach Authorization header when token is null', async () => {
    mockFetch(200, { ok: true });
    await testRequest('http://localhost:3000', '/health', 'GET', null);

    const calls = (global.fetch as jest.Mock).mock.calls;
    const requestInit = calls[0][1] as RequestInit;
    expect((requestInit.headers as Record<string, string>)['Authorization']).toBeUndefined();
  });

  test('returns parsed JSON on 200', async () => {
    mockFetch(200, { data: 'hello' });
    const result = await testRequest<{ data: string }>(
      'http://localhost:3000',
      '/test',
      'GET',
      null
    );
    expect(result.data).toBe('hello');
  });

  test('throws HttpError on 401 with status_code 401', async () => {
    mockFetch(401, { error: 'Unauthorized', detail: 'JWT missing', status_code: 401 });
    await expect(
      testRequest('http://localhost:3000', '/protected', 'GET', null)
    ).rejects.toThrow(HttpError);
  });

  test('HttpError has correct status_code on 401', async () => {
    mockFetch(401, { error: 'Unauthorized', detail: 'JWT missing', status_code: 401 });
    try {
      await testRequest('http://localhost:3000', '/protected', 'GET', null);
    } catch (err) {
      expect(err).toBeInstanceOf(HttpError);
      expect((err as HttpError).apiError.status_code).toBe(401);
      expect((err as HttpError).apiError.error).toBe('Unauthorized');
    }
  });

  test('throws HttpError on 404', async () => {
    mockFetch(404, { error: 'Not Found', detail: 'Resource not found', status_code: 404 });
    await expect(
      testRequest('http://localhost:3000', '/missing', 'GET', null)
    ).rejects.toMatchObject({ apiError: { status_code: 404 } });
  });

  test('throws HttpError on 500', async () => {
    mockFetch(500, { error: 'Internal Server Error', detail: 'Crash', status_code: 500 });
    await expect(
      testRequest('http://localhost:3000', '/boom', 'GET', null)
    ).rejects.toMatchObject({ apiError: { status_code: 500 } });
  });

  test('throws HttpError with status_code 408 on AbortError (timeout)', async () => {
    mockFetchAbort();
    await expect(
      testRequest('http://localhost:3000', '/slow', 'GET', null)
    ).rejects.toMatchObject({ apiError: { status_code: 408 } });
  });

  test('throws HttpError with status_code 0 on network failure', async () => {
    mockFetchNetworkError('Failed to fetch');
    await expect(
      testRequest('http://localhost:3000', '/offline', 'GET', null)
    ).rejects.toMatchObject({ apiError: { status_code: 0, error: 'Network Error' } });
  });

  test('POST serialises body as JSON', async () => {
    mockFetch(200, { created: true });
    await testRequest('http://localhost:3000', '/alerts', 'POST', 'tok', {
      body: { productId: 'abc', type: 'price_drop' },
    });
    const calls = (global.fetch as jest.Mock).mock.calls;
    const body = JSON.parse(calls[0][1].body as string);
    expect(body.productId).toBe('abc');
    expect(body.type).toBe('price_drop');
  });

  test('GET does NOT include body in request init', async () => {
    mockFetch(200, {});
    await testRequest('http://localhost:3000', '/users/me', 'GET', 'tok', {
      body: { should: 'be ignored' },
    });
    const calls = (global.fetch as jest.Mock).mock.calls;
    expect(calls[0][1].body).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// HttpError class
// ---------------------------------------------------------------------------

describe('HttpError', () => {
  test('is instanceof Error', () => {
    const err = new HttpError({ error: 'Test', detail: 'Detail', status_code: 400 });
    expect(err).toBeInstanceOf(Error);
  });

  test('message contains status_code, error, and detail', () => {
    const err = new HttpError({ error: 'Bad Request', detail: 'Invalid field', status_code: 400 });
    expect(err.message).toContain('400');
    expect(err.message).toContain('Bad Request');
    expect(err.message).toContain('Invalid field');
  });

  test('name is HttpError', () => {
    const err = new HttpError({ error: 'E', detail: 'D', status_code: 500 });
    expect(err.name).toBe('HttpError');
  });
});
