export type AlertEventRow = {
  id: number | string;
  rule_id: string;
  rule_name?: string;
  rule_type?: string;
  event_type: string;
  payload: unknown;
  created_at: string;
  delivered_at?: string | null;
  delivery_error?: string | null;
};

export type ListAlertEventsResponse =
  | { success: true; data: AlertEventRow[]; count: number }
  | { success: false; error: string };


