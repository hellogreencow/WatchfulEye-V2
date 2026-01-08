// Subscription-related utilities
export interface SubscriptionPackage {
  id: string;
  name: string;
  price: number;
  amount: number;
  bonus?: number;
  features: string[];
}

export const EP_PACKAGES: SubscriptionPackage[] = [
  {
    id: 'basic',
    name: 'Basic',
    price: 0,
    amount: 0,
    bonus: 0,
    features: [],
  },
];

export type SubscriptionTier = 'free' | 'war-room';

export interface SubscriptionState {
  tier: SubscriptionTier;
  package: string;
  active: boolean;
}

// NOTE: Subscription endpoints are not implemented yet. These helpers are shaped for UI consumption
// and return safe defaults so the app can typecheck/build without pretending billing is real.
export async function upgradeToWarRoom(_userId?: string): Promise<{ success: boolean; error?: string }> {
  return { success: false, error: 'Not implemented' };
}

export async function getSubscription(_userId?: string): Promise<SubscriptionState> {
  return { tier: 'free', package: 'free', active: false };
}

