import { useState, useCallback } from 'react';

interface UseChatStreamOptions {
  apiBaseUrl: string;
}

interface ChatStreamReturn {
  send: (message: string, options?: {
    useRag?: boolean;
    useSearch?: boolean;
    suppressUserBubble?: boolean;
    userMetadata?: Record<string, any>;
  }) => Promise<void>;
  messages: any[];
  setMessages: (messages: any[] | ((prev: any[]) => any[])) => void;
  setConversationId: (id: number | null) => void;
  isLoading: boolean;
  error: string | null;
}

export function useChatStream({ apiBaseUrl }: UseChatStreamOptions): ChatStreamReturn {
  const [messages, setMessagesState] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conversationId, setConversationIdState] = useState<number | null>(null);

  const send = useCallback(async (message: string, options?: {
    useRag?: boolean;
    useSearch?: boolean;
    suppressUserBubble?: boolean;
    userMetadata?: Record<string, any>;
  }) => {
    setIsLoading(true);
    setError(null);
    // Minimal implementation - Dashboard will handle actual streaming
    try {
      // Stub implementation
      await new Promise(resolve => setTimeout(resolve, 100));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const updateMessages = useCallback((newMessages: any[] | ((prev: any[]) => any[])) => {
    if (typeof newMessages === 'function') {
      setMessagesState(newMessages);
    } else {
      setMessagesState(newMessages);
    }
  }, []);

  const setConversationId = useCallback((id: number | null) => {
    setConversationIdState(id);
  }, []);

  return { send, messages, setMessages: updateMessages, setConversationId, isLoading, error };
}

