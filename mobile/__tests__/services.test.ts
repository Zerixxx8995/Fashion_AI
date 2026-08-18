/**
 * Service Layer Tests — mobile/__tests__/services.test.ts
 *
 * Tests for all service files:
 *   - cvService: submitCVScore, getCVJobStatus, getCVScoreResult,
 *                pollCVScore (poll loop), findSimilarProducts
 *   - trendsService: getTrends (with/without params), recalculateTrends
 *   - alertService: createAlert, getUserAlerts, deleteAlert
 *   - wardrobeService: addWardrobeItem, getWardrobeItems,
 *                      removeWardrobeItem, getGapAnalysis
 *
 * All tests use mock client objects — no live network calls.
 */

// ---------------------------------------------------------------------------
// cvService tests
// ---------------------------------------------------------------------------

import {
  submitCVScore,
  getCVJobStatus,
  getCVScoreResult,
  pollCVScore,
  findSimilarProducts,
  type MlClient as CvMlClient,
} from '../services/cvService';

import {
  getTrends,
  recalculateTrends,
  type MlClient as TrendsMlClient,
} from '../services/trendsService';

import {
  createAlert,
  getUserAlerts,
  deleteAlert,
  type ApiClient as AlertApiClient,
} from '../services/alertService';

import {
  addWardrobeItem,
  getWardrobeItems,
  removeWardrobeItem,
  getGapAnalysis,
  type ApiClient as WardrobeApiClient,
  type MlClient as WardrobeMlClient,
} from '../services/wardrobeService';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeMlClient(overrides: Partial<CvMlClient> = {}): CvMlClient {
  return {
    get: jest.fn().mockResolvedValue({}),
    post: jest.fn().mockResolvedValue({}),
    uploadForm: jest.fn().mockResolvedValue({}),
    ...overrides,
  };
}

function makeApiClient(overrides: Partial<AlertApiClient> = {}): AlertApiClient {
  return {
    get: jest.fn().mockResolvedValue({}),
    post: jest.fn().mockResolvedValue({}),
    delete: jest.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// cvService
// ---------------------------------------------------------------------------

describe('cvService — submitCVScore', () => {
  test('calls mlClient.uploadForm with /cv/score path', async () => {
    const uploadForm = jest.fn().mockResolvedValue({ job_id: 'job-001', status: 'pending' });
    const mlClient = makeMlClient({ uploadForm });

    const result = await submitCVScore(mlClient, {
      product_id: 'prod-1',
      user_id: 'user-1',
      uploaded_image_url: 'https://example.com/photo.jpg',
      stock_image_urls: ['https://example.com/stock.jpg'],
    });

    expect(uploadForm).toHaveBeenCalledWith('/cv/score', expect.any(FormData));
    expect(result.job_id).toBe('job-001');
  });

  test('appends file field for local file:// URI', async () => {
    const uploadForm = jest.fn().mockResolvedValue({ job_id: 'job-002', status: 'pending' });
    const mlClient = makeMlClient({ uploadForm });

    await submitCVScore(mlClient, {
      product_id: 'prod-2',
      user_id: 'user-2',
      uploaded_image_url: 'file:///data/user/0/photo.jpg',
      stock_image_urls: [],
    });

    expect(uploadForm).toHaveBeenCalledTimes(1);
    const formArg = uploadForm.mock.calls[0][1] as FormData;
    // FormData should include the file field (native RN blob object)
    expect(formArg.get('file') || formArg.get('uploaded_image_url')).toBeTruthy();
  });

  test('appends uploaded_image_url field for https:// URI', async () => {
    const uploadForm = jest.fn().mockResolvedValue({ job_id: 'job-003', status: 'pending' });
    const mlClient = makeMlClient({ uploadForm });

    await submitCVScore(mlClient, {
      product_id: 'prod-3',
      user_id: 'user-3',
      uploaded_image_url: 'https://cdn.example.com/image.jpg',
      stock_image_urls: ['https://cdn.example.com/stock.jpg'],
    });

    const formArg = uploadForm.mock.calls[0][1] as FormData;
    expect(formArg.get('uploaded_image_url')).toBe('https://cdn.example.com/image.jpg');
  });
});

describe('cvService — getCVJobStatus', () => {
  test('calls mlClient.get with correct status path', async () => {
    const get = jest.fn().mockResolvedValue({ job_id: 'j1', status: 'running', progress: 50 });
    const mlClient = makeMlClient({ get });

    const result = await getCVJobStatus(mlClient, 'j1');

    expect(get).toHaveBeenCalledWith('/cv/score/j1/status');
    expect(result.status).toBe('running');
  });
});

describe('cvService — getCVScoreResult', () => {
  test('calls mlClient.get with correct result path', async () => {
    const mockResult = {
      job_id: 'j2',
      status: 'complete',
      product_id: 'prod-1',
      user_id: 'user-1',
      confidence_score: 0.87,
      fake_review_flag: false,
      matching_stock_url: 'https://example.com/stock.jpg',
      computed_at: '2026-01-01T00:00:00Z',
    };
    const get = jest.fn().mockResolvedValue(mockResult);
    const mlClient = makeMlClient({ get });

    const result = await getCVScoreResult(mlClient, 'j2');

    expect(get).toHaveBeenCalledWith('/cv/score/j2/result');
    expect(result.confidence_score).toBe(0.87);
    expect(result.fake_review_flag).toBe(false);
  });
});

describe('cvService — pollCVScore', () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  test('polls until status is complete and returns result', async () => {
    const mockResult = {
      job_id: 'j3',
      status: 'complete',
      product_id: 'prod-1',
      user_id: 'u1',
      confidence_score: 0.91,
      fake_review_flag: false,
      matching_stock_url: null,
      computed_at: '2026-01-01T00:00:00Z',
    };

    const uploadForm = jest.fn().mockResolvedValue({ job_id: 'j3', status: 'pending' });
    // First poll: running, second poll: complete
    const get = jest.fn()
      .mockResolvedValueOnce({ job_id: 'j3', status: 'running', progress: 50 })
      .mockResolvedValueOnce({ job_id: 'j3', status: 'complete', progress: 100 })
      .mockResolvedValueOnce(mockResult); // getCVScoreResult call

    const mlClient = makeMlClient({ get, uploadForm });
    const onStatusUpdate = jest.fn();

    const resultPromise = pollCVScore(
      mlClient,
      {
        product_id: 'p1',
        user_id: 'u1',
        uploaded_image_url: 'https://example.com/img.jpg',
        stock_image_urls: [],
      },
      onStatusUpdate
    );

    // Advance timers to simulate polling delays
    await jest.runAllTimersAsync();

    const result = await resultPromise;
    expect(result.confidence_score).toBe(0.91);
    expect(onStatusUpdate).toHaveBeenCalledTimes(2);
  });

  test('throws when job status is failed', async () => {
    const uploadForm = jest.fn().mockResolvedValue({ job_id: 'j4', status: 'pending' });
    const get = jest.fn().mockResolvedValue({ job_id: 'j4', status: 'failed' });
    const mlClient = makeMlClient({ get, uploadForm });

    // Start the poll — do NOT await yet
    const resultPromise = pollCVScore(mlClient, {
      product_id: 'p2',
      user_id: 'u2',
      uploaded_image_url: 'https://example.com/img.jpg',
      stock_image_urls: [],
    });

    // Attach rejection handler BEFORE advancing timers to prevent unhandled rejection
    const rejection = expect(resultPromise).rejects.toThrow('failed');
    await jest.runAllTimersAsync();
    await rejection;
  });
});

describe('cvService — findSimilarProducts', () => {
  test('calls mlClient.post with /cv/similar and request body', async () => {
    const mockResponse = {
      results: [{ product_id: 'prod-x', platform: 'myntra', name: 'Top', price_inr: 500, url: 'https://myntra.com/p/1', similarity_score: 0.95, stock_image_url: null }],
      total: 1,
    };
    const post = jest.fn().mockResolvedValue(mockResponse);
    const mlClient = makeMlClient({ post });

    const result = await findSimilarProducts(mlClient, {
      image_url: 'https://example.com/photo.jpg',
      top_k: 10,
      max_price_inr: 2000,
    });

    expect(post).toHaveBeenCalledWith('/cv/similar', {
      body: { image_url: 'https://example.com/photo.jpg', top_k: 10, max_price_inr: 2000 },
    });
    expect(result.results[0].platform).toBe('myntra');
  });
});

// ---------------------------------------------------------------------------
// trendsService
// ---------------------------------------------------------------------------

describe('trendsService — getTrends', () => {
  test('calls mlClient.get /trends with no params when none provided', async () => {
    const get = jest.fn().mockResolvedValue({ items: [] });
    const mlClient: TrendsMlClient = { get, post: jest.fn() };

    await getTrends(mlClient);

    expect(get).toHaveBeenCalledWith('/trends');
  });

  test('appends category query param when provided', async () => {
    const get = jest.fn().mockResolvedValue({ items: [] });
    const mlClient: TrendsMlClient = { get, post: jest.fn() };

    await getTrends(mlClient, { category: 'tops' });

    expect(get).toHaveBeenCalledWith('/trends?category=tops');
  });

  test('appends limit query param when provided', async () => {
    const get = jest.fn().mockResolvedValue({ items: [] });
    const mlClient: TrendsMlClient = { get, post: jest.fn() };

    await getTrends(mlClient, { limit: 20 });

    expect(get).toHaveBeenCalledWith('/trends?limit=20');
  });

  test('appends both category and limit when both provided', async () => {
    const get = jest.fn().mockResolvedValue({ items: [] });
    const mlClient: TrendsMlClient = { get, post: jest.fn() };

    await getTrends(mlClient, { category: 'jeans', limit: 5 });

    const call = (get as jest.Mock).mock.calls[0][0] as string;
    expect(call).toContain('category=jeans');
    expect(call).toContain('limit=5');
  });

  test('returns trend items from mlClient response', async () => {
    const mockTrends = {
      trends: [
        {
          category: 'tops',
          lifecycle_stage: 'peaking',
          trend_score: 0.93,
          product_count: 42,
          representative_image_url: null,
          platforms: ['myntra'],
        },
      ],
      total: 1,
      computed_at: '2026-01-01T00:00:00Z',
    };
    const get = jest.fn().mockResolvedValue(mockTrends);
    const mlClient: TrendsMlClient = { get, post: jest.fn() };

    const result = await getTrends(mlClient, { category: 'tops', limit: 1 });

    expect(result.trends[0].lifecycle_stage).toBe('peaking');
    expect(result.trends[0].trend_score).toBe(0.93);
  });
});

describe('trendsService — recalculateTrends', () => {
  test('calls mlClient.post with /trends/recalculate', async () => {
    const post = jest.fn().mockResolvedValue({ message: 'Recalculation triggered' });
    const mlClient: TrendsMlClient = { get: jest.fn(), post };

    const result = await recalculateTrends(mlClient);

    expect(post).toHaveBeenCalledWith('/trends/recalculate');
    expect(result.message).toBe('Recalculation triggered');
  });
});

// ---------------------------------------------------------------------------
// alertService
// ---------------------------------------------------------------------------

describe('alertService — createAlert', () => {
  test('calls apiClient.post /alerts with alert body', async () => {
    const mockAlert = {
      id: 'alert-1',
      userId: 'user-1',
      productId: 'prod-1',
      type: 'price_drop' as const,
      target_price_inr: 500,
      triggered: false,
      createdAt: '2026-01-01T00:00:00Z',
      updatedAt: '2026-01-01T00:00:00Z',
    };
    const post = jest.fn().mockResolvedValue(mockAlert);
    const apiClient: AlertApiClient = { get: jest.fn(), post, delete: jest.fn() };

    const result = await createAlert(apiClient, {
      productId: 'prod-1',
      type: 'price_drop',
      target_price_inr: 500,
    });

    expect(post).toHaveBeenCalledWith('/alerts', {
      body: { productId: 'prod-1', type: 'price_drop', target_price_inr: 500 },
    });
    expect(result.type).toBe('price_drop');
    expect(result.target_price_inr).toBe(500);
  });
});

describe('alertService — getUserAlerts', () => {
  test('calls apiClient.get /alerts/:userId', async () => {
    const mockAlerts = [
      { id: 'a1', userId: 'u1', productId: 'p1', type: 'restock' as const, target_price_inr: null, triggered: false, createdAt: '', updatedAt: '' },
      { id: 'a2', userId: 'u1', productId: 'p2', type: 'price_drop' as const, target_price_inr: 300, triggered: true, createdAt: '', updatedAt: '' },
    ];
    const get = jest.fn().mockResolvedValue(mockAlerts);
    const apiClient: AlertApiClient = { get, post: jest.fn(), delete: jest.fn() };

    const result = await getUserAlerts(apiClient, 'u1');

    expect(get).toHaveBeenCalledWith('/alerts/u1');
    expect(result).toHaveLength(2);
    expect(result[1].type).toBe('price_drop');
  });
});

describe('alertService — deleteAlert', () => {
  test('calls apiClient.delete /alerts/:id', async () => {
    const deleteFn = jest.fn().mockResolvedValue(undefined);
    const apiClient: AlertApiClient = { get: jest.fn(), post: jest.fn(), delete: deleteFn };

    await deleteAlert(apiClient, 'alert-99');

    expect(deleteFn).toHaveBeenCalledWith('/alerts/alert-99');
  });
});

// ---------------------------------------------------------------------------
// wardrobeService
// ---------------------------------------------------------------------------

describe('wardrobeService — addWardrobeItem', () => {
  test('calls apiClient.post /wardrobe with productId body', async () => {
    const mockItem = { id: 'wi-1', productId: 'prod-5', category: 'tops' };
    const post = jest.fn().mockResolvedValue(mockItem);
    const apiClient: WardrobeApiClient = { get: jest.fn(), post, delete: jest.fn() };

    const result = await addWardrobeItem(apiClient, 'prod-5');

    expect(post).toHaveBeenCalledWith('/wardrobe', { body: { productId: 'prod-5' } });
    expect(result.productId).toBe('prod-5');
  });
});

describe('wardrobeService — getWardrobeItems', () => {
  test('calls apiClient.get /wardrobe/:userId', async () => {
    const mockItems = [
      { id: 'wi-1', userId: 'user-5', productId: 'p1', addedAt: '2026-01-01T00:00:00Z' },
      { id: 'wi-2', userId: 'user-5', productId: 'p2', addedAt: '2026-01-02T00:00:00Z' },
    ];
    const get = jest.fn().mockResolvedValue(mockItems);
    const apiClient: WardrobeApiClient = { get, post: jest.fn(), delete: jest.fn() };

    const result = await getWardrobeItems(apiClient, 'user-5');

    expect(get).toHaveBeenCalledWith('/wardrobe/user-5');
    expect(result).toHaveLength(2);
    expect(result[0].productId).toBe('p1');
  });
});

describe('wardrobeService — removeWardrobeItem', () => {
  test('calls apiClient.delete /wardrobe/:itemId', async () => {
    const deleteFn = jest.fn().mockResolvedValue(undefined);
    const apiClient: WardrobeApiClient = { get: jest.fn(), post: jest.fn(), delete: deleteFn };

    await removeWardrobeItem(apiClient, 'wi-77');

    expect(deleteFn).toHaveBeenCalledWith('/wardrobe/wi-77');
  });
});

describe('wardrobeService — getGapAnalysis', () => {
  test('calls mlClient.post /wardrobe/gap-analysis with correct body', async () => {
    const mockGap = {
      user_id: 'user-5',
      coverage_score: 0.6,
      gaps: [
        { missing_category: 'dresses', priority: 'high' as const, suggested_budget_inr: 1500, reason: 'No dresses in wardrobe' },
        { missing_category: 'footwear', priority: 'medium' as const, suggested_budget_inr: 2000, reason: 'Only 1 pair' },
      ],
      total_gaps: 2,
    };
    const post = jest.fn().mockResolvedValue(mockGap);
    const mlClient: WardrobeMlClient = { post };

    const result = await getGapAnalysis(mlClient, {
      user_id: 'user-5',
      categories: ['tops', 'jeans'],
    });

    expect(post).toHaveBeenCalledWith('/wardrobe/gap-analysis', {
      body: { user_id: 'user-5', categories: ['tops', 'jeans'] },
    });
    expect(result.gaps[0].missing_category).toBe('dresses');
    expect(result.gaps[1].missing_category).toBe('footwear');
  });
});
