export type MarketDirection = 'up' | 'down' | 'vol ↑' | 'uncertain';

export interface MarketItem {
  asset: string;
  direction: MarketDirection;
  magnitude?: string;
  rationale?: string;
  provenance?: 'article' | 'db' | 'both';
}

export interface Timeframes {
  near?: string;
  medium?: string;
  long?: string;
}

export interface Perspectives {
  democrat?: string[];
  republican?: string[];
  independent?: string[];
}

export interface AnalysisStructured {
  insights?: string[];
  geopolitics?: string[];
  market?: MarketItem[];
  playbook?: string[];
  risks?: string[];
  timeframes?: Timeframes;
  signals?: string[];
  commentary?: string;
  perspectives?: Perspectives;
}


