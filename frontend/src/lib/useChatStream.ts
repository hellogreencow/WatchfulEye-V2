import { useCallback, useRef, useState, useEffect } from 'react';

export type ChatMessage = {
  id: number;
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at: string;
  metadata?: Record<string, any>;
};

type UseChatStreamOptions = {
  apiBaseUrl: string;
  angle?: 'neutral' | 'market' | 'policy' | 'tech';
  horizon?: 'near' | 'medium' | 'long';
  useRag?: boolean;
};

export function useChatStream({ apiBaseUrl, angle = 'neutral', horizon = 'medium', useRag = true }: UseChatStreamOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  // Safety net: Mark messages with sources as complete after 30 seconds
  // This prevents infinite typing animations if complete event is lost
  useEffect(() => {
    const interval = setInterval(() => {
      setMessages(prev => prev.map(m => {
        if (m.role === 'assistant' &&
            Array.isArray(m.metadata?.sources) &&
            (m.metadata?.sources as any[]).length > 0 &&
            !(m.metadata as any)?.complete &&
            m.created_at) {
          const age = Date.now() - new Date(m.created_at).getTime();
          if (age > 30000) { // 30 seconds
            return { ...m, metadata: { ...(m.metadata || {}), complete: true } };
          }
        }
        return m;
      }));
    }, 5000); // Check every 5 seconds

    return () => clearInterval(interval);
  }, []);

  const createConversation = useCallback(async (title: string) => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
    const res = await fetch(`${apiBaseUrl}/chat/conversations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      credentials: 'include',
      body: JSON.stringify({ title: title.substring(0, 50), metadata: { angle, horizon } }),
    });
    if (!res.ok) {
      const err: any = new Error('create_conversation_failed');
      err.status = res.status;
      throw err;
    }
    const data = await res.json();
    setConversationId(data.conversation_id);
    return data.conversation_id as number;
  }, [apiBaseUrl, angle, horizon]);

  const postPlainChat = useCallback(async (content: string) => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
    const res = await fetch(`${apiBaseUrl}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      credentials: 'include',
      body: JSON.stringify({ query: content, use_rag: true }),
    });
    if (!res.ok) throw new Error('plain_chat_failed');
    const data = await res.json();
    return { response: data.response as string, sources: (data.sources ?? []) as any[] };
  }, [apiBaseUrl]);

  const send = useCallback(async (
    content: string,
    options?: {
      useRag?: boolean;
      useSearch?: boolean;
      angleOverride?: 'neutral'|'market'|'policy'|'tech';
      horizonOverride?: 'near'|'medium'|'long';
      suppressUserBubble?: boolean;
      userMetadata?: Record<string, any>;
    }
  ) => {
    if (isLoading) return;
    setIsLoading(true);

    const nowIso = new Date().toISOString();
    const userMsg: ChatMessage = { id: Date.now(), role: 'user', content, created_at: nowIso, metadata: { angle, horizon, ...(options?.userMetadata || {}) } };
    const assistantTemp: ChatMessage = { id: Date.now() + 1, role: 'assistant', content: '', created_at: nowIso, metadata: { angle, horizon } };
    setMessages(prev => options?.suppressUserBubble ? [...prev, assistantTemp] : [...prev, userMsg, assistantTemp]);

    try {
      let convId = conversationId;
      if (!convId) {
        convId = await createConversation(content);
      }

      // abort previous
      try { controllerRef.current?.abort(); } catch {}
      const controller = new AbortController();
      controllerRef.current = controller;

      const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
      const init = await fetch(`${apiBaseUrl}/chat/conversations/${convId}/messages/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        credentials: 'include',
        body: JSON.stringify({ 
          content, 
          angle: options?.angleOverride ?? angle, 
          horizon: options?.horizonOverride ?? horizon, 
          use_rag: true,
          use_search: options?.useSearch ?? false,
          suppress_display: options?.suppressUserBubble === true,
          origin: options?.userMetadata?.origin
        }),
        signal: controller.signal,
      });
      if (!init.ok) throw new Error('stream init failed');

      const reader = init.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let full = '';
      if (reader) {
        // read SSE-like lines
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          buffer += chunk;
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          for (const raw of lines) {
            const line = raw.trim();
            if (!line.startsWith('data: ')) continue;
            const data = line.slice(6);
            if (data === '[DONE]') continue;
            try {
              const parsed = JSON.parse(data);
              if (parsed.type === 'chunk') {
                full += parsed.content;
                setMessages(prev => prev.map(m => m.id === assistantTemp.id ? { ...m, content: full } : m));
              } else if (parsed.type === 'sources') {
                const id = assistantTemp.id;
                setMessages(prev => prev.map(m => m.id === id ? { ...m, metadata: { ...(m.metadata || {}), sources: parsed.sources, as_of: parsed.as_of ?? (m.metadata as any)?.as_of, mode: parsed.mode ?? (m.metadata as any)?.mode } } : m));
              } else if (parsed.type === 'complete') {
                const id = assistantTemp.id;
                setMessages(prev => prev.map(m => {
                  if (m.id === id) {
                    // Only update message_id and mark complete, preserve existing content
                    return { 
                      ...m, 
                      id: parsed.message_id, 
                      metadata: { ...(m.metadata || {}), complete: true } 
                    };
                  }
                  return m;
                }));
              }
            } catch {}
          }
        }
      }
    } catch (err: any) {
      // fallback path: if unauthorized or conv endpoints fail, use plain /api/chat (no auth requirement)
      try {
        const result = await postPlainChat(content);
        setMessages(prev => {
          const withoutTemps: ChatMessage[] = options?.suppressUserBubble ? prev.slice(0, -1) as ChatMessage[] : prev.slice(0, -2) as ChatMessage[];
          const maybeUser: ChatMessage[] = options?.suppressUserBubble ? [] : [{ id: Date.now(), role: 'user', content, created_at: new Date().toISOString(), metadata: { angle, horizon, ...(options?.userMetadata || {}) } } as ChatMessage];
          const assistant: ChatMessage = { id: Date.now() + 1, role: 'assistant', content: result.response, created_at: new Date().toISOString(), metadata: { angle, horizon, sources: result.sources, complete: true } };
          return [
            ...withoutTemps,
            ...maybeUser,
            assistant,
          ];
        });
      } catch {
        // final cleanup on total failure
        setMessages(prev => options?.suppressUserBubble ? prev.slice(0, -1) : prev.slice(0, -2));
      }
    } finally {
      setIsLoading(false);
    }
  }, [apiBaseUrl, angle, horizon, useRag, isLoading, conversationId, createConversation, postPlainChat]);

  return { messages, isLoading, send, setMessages, setConversationId };
}


