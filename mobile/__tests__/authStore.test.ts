/**
 * Auth Store Tests — mobile/__tests__/authStore.test.ts
 *
 * Tests the Zustand authStore actions and state updates using mock apiClients.
 */

import { useAuthStore } from '../store/authStore';
import type { UserProfile } from '../types';

const mockUser: UserProfile = {
  id: 'user-uuid-123',
  clerk_id: 'clerk-id-123',
  email: 'rahul@example.com',
  name: 'Rahul Kumar',
  body_type: 'athletic',
  taste_preferences: ['casual', 'ethnic'],
  createdAt: '2024-01-01T12:00:00Z',
};

describe('authStore', () => {
  beforeEach(() => {
    // Reset state before each test
    useAuthStore.getState().logout();
  });

  test('initial state has user as null, loading false, error null', () => {
    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.isLoading).toBe(false);
    expect(state.error).toBeNull();
  });

  test('setUser sets the user profile', () => {
    useAuthStore.getState().setUser(mockUser);
    expect(useAuthStore.getState().user).toEqual(mockUser);
  });

  test('syncUserWithBackend calls backend sync and updates state', async () => {
    const mockApiClient = {
      post: jest.fn().mockResolvedValue({
        message: 'User synced.',
        user: mockUser,
      }),
    };

    const synced = await useAuthStore.getState().syncUserWithBackend(
      mockApiClient,
      'rahul@example.com',
      'Rahul Kumar'
    );

    expect(mockApiClient.post).toHaveBeenCalledWith('/auth/sync', {
      body: { email: 'rahul@example.com', name: 'Rahul Kumar' },
    });
    expect(synced).toEqual(mockUser);
    expect(useAuthStore.getState().user).toEqual(mockUser);
    expect(useAuthStore.getState().isLoading).toBe(false);
  });

  test('syncUserWithBackend handles error response and updates error state', async () => {
    const mockApiClient = {
      post: jest.fn().mockRejectedValue({
        apiError: { detail: 'Invalid parameters', status_code: 400 },
      }),
    };

    await expect(
      useAuthStore.getState().syncUserWithBackend(mockApiClient, 'bad-email', 'Name')
    ).rejects.toBeDefined();

    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().error).toBe('Invalid parameters');
    expect(useAuthStore.getState().isLoading).toBe(false);
  });

  test('fetchUserProfile calls backend get profile and updates state', async () => {
    const mockApiClient = {
      get: jest.fn().mockResolvedValue({
        user: mockUser,
      }),
    };

    const profile = await useAuthStore.getState().fetchUserProfile(mockApiClient, 'user-uuid-123');

    expect(mockApiClient.get).toHaveBeenCalledWith('/users/user-uuid-123/profile');
    expect(profile).toEqual(mockUser);
    expect(useAuthStore.getState().user).toEqual(mockUser);
  });

  test('updateUserProfile calls backend update profile and updates state', async () => {
    const updatedUser = {
      ...mockUser,
      body_type: 'slim',
      taste_preferences: ['wedding'],
    };

    const mockApiClient = {
      put: jest.fn().mockResolvedValue({
        user: updatedUser,
      }),
    };

    const result = await useAuthStore.getState().updateUserProfile(
      mockApiClient,
      'user-uuid-123',
      { body_type: 'slim', taste_preferences: ['wedding'] }
    );

    expect(mockApiClient.put).toHaveBeenCalledWith('/users/user-uuid-123/profile', {
      body: { body_type: 'slim', taste_preferences: ['wedding'] },
    });
    expect(result).toEqual(updatedUser);
    expect(useAuthStore.getState().user).toEqual(updatedUser);
  });

  test('logout clears user profile, loading and error states', () => {
    useAuthStore.setState({
      user: mockUser,
      error: 'Some error',
      isLoading: true,
    });

    useAuthStore.getState().logout();

    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.error).toBeNull();
    expect(state.isLoading).toBe(false);
  });
});
