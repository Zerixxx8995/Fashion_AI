/**
 * Jest mock for @clerk/clerk-expo
 * Prevents native module errors when testing httpClient.ts
 */
export const useAuth = () => ({
  getToken: jest.fn().mockResolvedValue('mock-clerk-token'),
  isSignedIn: true,
});

export const useUser = () => ({
  user: { id: 'mock-user-id', emailAddresses: [] },
  isLoaded: true,
});

export const ClerkProvider = ({ children }: { children: React.ReactNode }) => children;
