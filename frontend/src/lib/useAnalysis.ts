import { useCallback, useState } from 'react';
import { AnalysisStructured } from './analysisTypes';

type UseAnalysisOptions = { apiBaseUrl: string };

export function useAnalysis({ apiBaseUrl }: UseAnalysisOptions) {
  const [data, setData] = useState<AnalysisStructured | null>(null);
  const [raw, setRaw] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const analyze = useCallback(async (article: { title: string; description: string; source?: string; category?: string; sentiment_score?: number; }) => {
    console.log('🔧 useAnalysis.analyze() called with:', article);
    console.log('🌐 API Base URL:', apiBaseUrl);
    
    setIsLoading(true);
    setError(null);
    setData(null);
    setRaw(null);
    
    try {
      const url = `${apiBaseUrl}/ollama-analysis`;
      console.log('📡 Making fetch request to:', url);
      
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(article),
      });
      
      console.log('📨 Response received:', { 
        status: res.status, 
        statusText: res.statusText, 
        ok: res.ok,
        hasBody: !!res.body 
      });
      
      if (!res.ok || !res.body) {
        const errorMsg = `Analysis failed (${res.status})`;
        console.log('❌ Request failed:', errorMsg);
        setError(errorMsg);
        return;
      }
      
      // Check if this is a streaming response (SSE) or regular JSON
      const contentType = res.headers.get('content-type') || '';
      console.log('📨 Content-Type:', contentType);
      
      if (contentType.includes('text/event-stream')) {
        console.log('🔄 Reading streaming response...');
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let collected = '';
        let chunkCount = 0;
        
        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            console.log('✅ Stream reading completed. Total chunks:', chunkCount);
            break;
          }
          
          chunkCount++;
          const chunk = decoder.decode(value, { stream: true });
          console.log(`📦 Chunk ${chunkCount}:`, chunk.substring(0, 100) + (chunk.length > 100 ? '...' : ''));
          
          buffer += chunk;
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          
          for (const rawLine of lines) {
            const line = rawLine.trim();
            if (!line.startsWith('data: ')) continue;
            const dataStr = line.slice(6);
            if (dataStr === '[DONE]') {
              console.log('🏁 Received [DONE] signal');
              continue;
            }
            
            try {
              const evt = JSON.parse(dataStr);
              console.log('📋 Parsed event:', evt);
              
              if (evt.type === 'chunk' && typeof evt.content === 'string') {
                collected += evt.content;
                console.log('📝 Collected content length:', collected.length);
              } else if (evt.type === 'complete') {
                console.log('🎉 Analysis complete event received');
                if (evt.structured) {
                  console.log('📊 Setting structured data:', evt.structured);
                  setData(evt.structured as AnalysisStructured);
                } else if (evt.raw) {
                  console.log('📄 Setting raw data:', evt.raw);
                  setRaw(String(evt.raw));
                }
              } else if (evt.type === 'error') {
                console.log('🚨 Error event received:', evt.message);
                setError(evt.message || 'Analysis error');
              }
            } catch (parseError) {
              console.log('⚠️ Failed to parse event data:', dataStr, parseError);
            }
          }
        }
      } else {
        console.log('📄 Reading regular JSON response...');
        const jsonResponse = await res.json();
        console.log('📊 JSON Response received:', jsonResponse);
        
        if (jsonResponse.success && jsonResponse.analysis) {
          console.log('✅ Converting analysis to structured format');
          // Convert the simple analysis format to structured format
          const structuredData: AnalysisStructured = {
            insights: [jsonResponse.analysis.substring(0, 200) + '...'],
            market: [],
            geopolitics: [],
            playbook: [],
            risks: [],
            timeframes: { near: "", medium: "", long: "" },
            signals: [],
            commentary: jsonResponse.analysis
          };
          console.log('📊 Setting converted structured data:', structuredData);
          setData(structuredData);
        } else if (jsonResponse.error) {
          console.log('❌ API returned error:', jsonResponse.error);
          setError(jsonResponse.error);
        } else {
          console.log('⚠️ Unexpected response format:', jsonResponse);
          setError('Unexpected response format');
        }
      }
    } catch (e: any) {
      console.log('💥 Exception in analyze():', e);
      setError(e?.message || 'Analysis error');
    } finally {
      console.log('🏁 Analysis request completed, setting isLoading to false');
      setIsLoading(false);
    }
  }, [apiBaseUrl]);

  return { analyze, data, raw, error, isLoading };
}


