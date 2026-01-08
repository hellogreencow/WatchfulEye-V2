// Subscription management for War Room access

export type SubscriptionTier = 'free' | 'war-room';

export interface Subscription {
  tier: SubscriptionTier;
  eyePoints: number;
  hasUnlimitedEP: boolean;
  activatedDate?: string;
  expiresDate?: string;
}

const SUBSCRIPTION_KEY = 'watchfuleye_subscription';

export function getSubscription(): Subscription {
  if (typeof window === 'undefined') return getDefaultSubscription();
  
  const stored = localStorage.getItem(SUBSCRIPTION_KEY);
  if (!stored) {
    const defaultSub = getDefaultSubscription();
    saveSubscription(defaultSub);
    return defaultSub;
  }
  
  try {
    return JSON.parse(stored);
  } catch {
    return getDefaultSubscription();
  }
}

function getDefaultSubscription(): Subscription {
  return {
    tier: 'free',
    eyePoints: 1000, // Starting points
    hasUnlimitedEP: false,
  };
}

export function saveSubscription(sub: Subscription): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(SUBSCRIPTION_KEY, JSON.stringify(sub));
}

// Check if user has War Room access
export function hasWarRoomAccess(): boolean {
  const sub = getSubscription();
  return sub.tier === 'war-room';
}

// Spend EyePoints
export function spendEyePoints(amount: number): boolean {
  const sub = getSubscription();
  
  // War Room users have unlimited EP
  if (sub.hasUnlimitedEP) return true;
  
  if (sub.eyePoints >= amount) {
    sub.eyePoints -= amount;
    saveSubscription(sub);
    return true;
  }
  
  return false;
}

// Add EyePoints (from wins or purchases)
export function addEyePoints(amount: number): void {
  const sub = getSubscription();
  sub.eyePoints += amount;
  saveSubscription(sub);
}

// Purchase EyePoints
export interface EPPackage {
  id: string;
  amount: number;
  price: number;
  bonus: number;
  popular?: boolean;
}

export const EP_PACKAGES: EPPackage[] = [
  {
    id: 'starter',
    amount: 5000,
    price: 9.99,
    bonus: 0,
  },
  {
    id: 'pro',
    amount: 15000,
    price: 24.99,
    bonus: 3000,
    popular: true,
  },
  {
    id: 'elite',
    amount: 50000,
    price: 74.99,
    bonus: 15000,
  },
];

// EyePoint costs for various actions
export const EP_COSTS = {
  INTEL_DEEP_DIVE: 100,        // Unlock full article analysis with AI breakdown
  DAILY_5_EXTRA_PLAY: 250,     // Play Daily 5 again after your free daily attempt
  HISTORICAL_REPORT: 200,       // Access historical intel reports (30+ days old)
  CUSTOM_ALERT: 50,            // Set up a custom market alert
  AI_ANALYSIS: 150,            // Request AI analysis on specific ticker
  REPLAY_SCENARIO: 300,        // Replay past Daily 5 scenarios for practice
};

// Upgrade to War Room
export function upgradeToWarRoom(): void {
  const sub = getSubscription();
  sub.tier = 'war-room';
  sub.hasUnlimitedEP = true;
  sub.activatedDate = new Date().toISOString();
  // Set expiry to 30 days from now (in production, handle via backend)
  const expiry = new Date();
  expiry.setDate(expiry.getDate() + 30);
  sub.expiresDate = expiry.toISOString();
  saveSubscription(sub);
}

// Get subscription features
export interface SubscriptionFeatures {
  dailyFiveAccess: boolean;
  chimera: boolean;
  realtimeAlerts: boolean;
  premiumAI: boolean;
}

export function getSubscriptionFeatures(tier: SubscriptionTier): SubscriptionFeatures {
  if (tier === 'war-room') {
    return {
      dailyFiveAccess: true,
      chimera: true,
      realtimeAlerts: true,
      premiumAI: true,
    };
  }
  
  // Free tier
  return {
    dailyFiveAccess: true,
    chimera: false,
    realtimeAlerts: false,
    premiumAI: false,
  };
}