export type ExamineRequest = {
  q: string;
};

export interface ExamineEvidenceItem {
  url?: string;
  title?: string;
  snippet?: string;
  source?: string;
  published_at?: string;
  [key: string]: unknown;
}

// `content` can be null or an object; keep this flexible and contract-shaped.
export type ExamineReportContent =
  | null
  | {
      bullets?: string[];
      evidence?: Array<string | ExamineEvidenceItem>;
      predictions?: string[];
      dissent?: string[];
      [key: string]: unknown;
    };

export interface ExamineReport {
  title?: string | null;
  summary?: string | null;
  content?: ExamineReportContent;
}

export interface ExamineResponse {
  investigation_id?: string;
  report_id?: string;
  status?: string;
  trace_id?: string;
  report?: ExamineReport | null;
}


