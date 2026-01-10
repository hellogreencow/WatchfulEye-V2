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

export type AlertsInboxResponse =
  | {
      success: true;
      data: AlertEventRow[];
      count: number;
      unread_count: number;
      last_seen_event_id: number;
      newest_event_id: number;
    }
  | { success: false; error: string };


