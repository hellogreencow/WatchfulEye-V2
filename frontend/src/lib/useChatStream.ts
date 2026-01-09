import { useRef, useState, useCallback } from 'react';

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
  const streamAbortRef = useRef<AbortController | null>(null);

  const send = useCallback(async (message: string, options?: {
    useRag?: boolean;
    useSearch?: boolean;
    suppressUserBubble?: boolean;
    userMetadata?: Record<string, any>;
  }) => {
    setIsLoading(true);
    setError(null);

    try {
      const content = (message || '').trim();
      if (!content) return;

      const suppressUserBubble = options?.suppressUserBubble === true;
      const useRag = options?.useRag !== false;
      const useSearch = options?.useSearch === true;

      const nowIso = new Date().toISOString();
      const tempUserId = Date.now();
      const tempAssistantId = tempUserId + 1;

      if (!suppressUserBubble) {
        setMessagesState(prev => [
          ...prev,
          {
            id: tempUserId,
            role: 'user',
            content,
            created_at: nowIso,
            metadata: options?.userMetadata || {},
          },
        ]);
      }

      // Add an assistant placeholder immediately so UI shows “typing”
      setMessagesState(prev => [
        ...prev,
        {
          id: tempAssistantId,
          role: 'assistant',
          content: '',
          created_at: nowIso,
          metadata: { ...(options?.userMetadata || {}), complete: false },
        },
      ]);

      // Abort previous stream if any
      try { streamAbortRef.current?.abort(); } catch {}
      const controller = new AbortController();
      streamAbortRef.current = controller;

      const token = localStorage.getItem('auth_token');
      const headers: HeadersInit = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      // Preferred: conversation-backed streaming (requires login/session)
      let convId = conversationId;
      if (!convId) {
        try {
          const createRes = await fetch(`${apiBaseUrl}/chat/conversations`, {
            method: 'POST',
            headers,
            credentials: 'include',
            body: JSON.stringify({
              title: null,
              metadata: { created_via: 'inline_chat' },
            }),
            signal: controller.signal,
          });
          if (createRes.ok) {
            const j = await createRes.json();
            convId = Number(j.conversation_id);
            if (Number.isFinite(convId)) setConversationIdState(convId);
          }
        } catch {
          // ignore and fall back
        }
      }

      // If we have a conversationId, use SSE stream; otherwise fall back to stateless /chat
      if (convId && Number.isFinite(convId)) {
        const res = await fetch(`${apiBaseUrl}/chat/conversations/${convId}/messages/stream`, {
          method: 'POST',
          headers,
          credentials: 'include',
          body: JSON.stringify({
            content,
            use_rag: useRag,
            use_search: useSearch,
          }),
          signal: controller.signal,
        });

        if (!res.ok) {
          // If not logged in, fall back to stateless /chat (which does not require login)
          if (res.status === 401) {
            throw new Error('AUTH_REQUIRED');
          }
          const text = await res.text().catch(() => '');
          throw new Error(`Chat stream failed (${res.status}): ${text || res.statusText}`);
        }

        const reader = res.body?.getReader();
        if (!reader) throw new Error('No response body (streaming unavailable)');

        const decoder = new TextDecoder();
        let buffer = '';
        let full = '';
        let sources: any[] = [];

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const rawLine of lines) {
            const line = rawLine.trim();
            if (!line.startsWith('data: ')) continue;
            const payload = line.slice(6);
            if (!payload || payload === '[DONE]') continue;

            try {
              const evt = JSON.parse(payload);
              if (evt.type === 'chunk') {
                const nextFull = full + String(evt.content || '');
                full = nextFull;
                setMessagesState(prev => prev.map(m => (m.id === tempAssistantId ? { ...m, content: nextFull } : m)));
              } else if (evt.type === 'sources') {
                const nextSources = evt.sources || [];
                sources = nextSources;
                setMessagesState(prev =>
                  prev.map(m => (m.id === tempAssistantId ? { ...m, metadata: { ...(m.metadata || {}), sources: nextSources } } : m))
                );
              } else if (evt.type === 'complete') {
                const finalText = String(evt.full_response || full || '');
                const finalSources = sources;
                setMessagesState(prev =>
                  prev.map(m =>
                    m.id === tempAssistantId
                      ? {
                          ...m,
                          id: evt.message_id || m.id,
                          content: finalText,
                          metadata: { ...(m.metadata || {}), sources: finalSources, complete: true },
                        }
                      : m
                  )
                );
              } else if (evt.type === 'error') {
                throw new Error(String(evt.message || 'Chat stream error'));
              }
            } catch (e) {
              // eslint-disable-next-line no-console
              console.warn('Failed to parse chat SSE event', e);
            }
          }
        }
        return;
      }

      // Stateless fallback: /api/chat (works without login; no persistence)
      const fallback = await fetch(`${apiBaseUrl}/chat`, {
        method: 'POST',
        headers,
        credentials: 'include',
        body: JSON.stringify({
          query: content,
          use_rag: useRag,
          use_search: useSearch,
        }),
        signal: controller.signal,
      });
      if (!fallback.ok) {
        const text = await fallback.text().catch(() => '');
        throw new Error(`Chat failed (${fallback.status}): ${text || fallback.statusText}`);
      }
      const j = await fallback.json();
      const resp = String(j.response || '');
      setMessagesState(prev =>
        prev.map(m => (m.id === tempAssistantId ? { ...m, content: resp, metadata: { ...(m.metadata || {}), sources: j.sources || [], complete: true } } : m))
      );
    } catch (err) {
      if ((err as any)?.name === 'AbortError') return;

      // Special-case auth required: show a crisp message (still keeps UI responsive)
      const msg = err instanceof Error ? err.message : 'Failed to send message';
      setError(msg);
      setMessagesState(prev =>
        prev.map(m =>
          m.role === 'assistant' && (m.metadata as any)?.complete === false
            ? { ...m, content: msg === 'AUTH_REQUIRED' ? 'Please sign in to use saved conversations. (AI is available, but persistence requires auth.)' : `Error: ${msg}`, metadata: { ...(m.metadata || {}), complete: true } }
            : m
        )
      );
    } finally {
      setIsLoading(false);
    }
  }, [apiBaseUrl, conversationId]);

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

