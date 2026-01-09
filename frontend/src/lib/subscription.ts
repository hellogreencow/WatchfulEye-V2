// Subscription-related utilities
//
// NOTE: Billing/subscription endpoints are not implemented yet.
// These helpers are shaped for UI consumption and return safe defaults so the app
// can lint/typecheck/test/build without pretending billing is real.

export interface SubscriptionPackage {
  id: string;
  name: string;
  price: number;
  amount: number;
  bonus: number;
  features: string[];
}

export const EP_PACKAGES: SubscriptionPackage[] = [
  {
    id: 'starter',
    name: 'Starter Pack',
    price: 9.99,
    amount: 5000,
    bonus: 0,
    features: ['Instant delivery', 'No expiration'],
  },
  {
    id: 'pro',
    name: 'Pro Pack',
    price: 24.99,
    amount: 15000,
    bonus: 3000,
    features: ['Instant delivery', 'No expiration', 'Best value'],
  },
  {
    id: 'elite',
    name: 'Elite Pack',
    price: 74.99,
    amount: 50000,
    bonus: 15000,
    features: ['Instant delivery', 'No expiration', 'Maximum value'],
  },
];

export type SubscriptionTier = 'free' | 'war-room';

export interface SubscriptionState {
  tier: SubscriptionTier;
  package: string;
  active: boolean;
}

export function getSubscription(): SubscriptionState {
  return { tier: 'free', package: 'free', active: false };
}

export function upgradeToWarRoom(): { success: boolean; error?: string } {
  return { success: false, error: 'Not implemented' };
}


