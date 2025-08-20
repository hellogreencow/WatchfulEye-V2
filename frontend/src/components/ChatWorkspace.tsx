import React, { useState, useEffect, useRef } from 'react';
import { AnimatePresence, motion, LayoutGroup } from 'framer-motion';
import axios from 'axios';
import { format } from 'date-fns';
import { 
  MessageSquare, Plus, Search, Pin, Archive, MoreVertical, 
  Send, User, Bot, Clock, ChevronLeft, ChevronRight,
  TrendingUp, Shield, Cpu, X, Edit2, Trash2, Copy
} from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Badge } from './ui/badge';
import { cn } from '../lib/utils';
import FormattedMessage from './FormattedMessage';
import { SourcesHoverChip } from './ArticleCard';
import RAGAnimation from './RAGAnimation';

interface Message {
  id: number;
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at: string;
  metadata?: {
    sources?: any[];
    angle?: string;
    horizon?: string;
  };
}

interface Conversation {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
  last_message_at: string;
  archived: boolean;
  message_count: number;
  last_message?: string;
  metadata?: {
    angle?: string;
    horizon?: string;
  };
}

interface ChatWorkspaceProps {
  isOpen: boolean;
  onClose?: () => void;
  initialQuery?: string;
  apiBaseUrl: string;
  className?: string;
  layout?: 'inline' | 'split';
  onFirstMessage?: () => void;
}

export function ChatWorkspace({ 
  isOpen, 
  onClose, 
  initialQuery = '', 
  apiBaseUrl,
  className,
  layout = 'split',
  onFirstMessage
}: ChatWorkspaceProps) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [angle, setAngle] = useState<'neutral' | 'market' | 'policy' | 'tech'>('neutral');
  const [horizon, setHorizon] = useState<'near' | 'medium' | 'long'>('medium');
  const [useRag, setUseRag] = useState(true); // retrieval toggle
  const [useSearch, setUseSearch] = useState(false); // web-search backed model toggle
  const [streamingCompleteMessageIds, setStreamingCompleteMessageIds] = useState<Set<number>>(new Set());

  // Ensure Search is off on initial load/mount
  useEffect(() => {
    setUseSearch(false);
  }, []);
  const [railCollapsed, setRailCollapsed] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const streamControllerRef = useRef<AbortController | null>(null);
  const isMountedRef = useRef(true);

  // Load conversations on mount
  useEffect(() => {
    if (isOpen) {
      loadConversations();
    }
    return () => {
      // Mark unmounted and abort any in-flight stream
      isMountedRef.current = false;
      try { streamControllerRef.current?.abort(); } catch {}
    };
  }, [isOpen]);

  // Handle initial query
  useEffect(() => {
    if (initialQuery && isOpen && !activeConversation) {
      // Create new conversation with initial query
      handleNewConversation(initialQuery);
    }
  }, [initialQuery, isOpen]);

  // Auto-scroll only inside the chat scroll area; do not scroll the whole page
  useEffect(() => {
    try {
      const anchor = messagesEndRef.current;
      if (!anchor) return;
      const scroller = anchor.parentElement;
      if (scroller && scroller.scrollTo) {
        scroller.scrollTo({ top: scroller.scrollHeight, behavior: 'smooth' });
      } else {
        anchor.scrollIntoView({ behavior: 'smooth', block: 'end' });
      }
    } catch {}
  }, [messages]);

  const loadConversations = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const response = await axios.get(`${apiBaseUrl}/chat/conversations`, { 
        headers,
        withCredentials: true 
      });
      setConversations(response.data.conversations || []);
    } catch (error: any) {
      console.error('Failed to load conversations:', error);
      // Guest mode fallback: keep UI usable
      setConversations([]);
    }
  };

  const loadConversation = async (conversationId: number) => {
    try {
      const token = localStorage.getItem('auth_token');
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const response = await axios.get(`${apiBaseUrl}/chat/conversations/${conversationId}`, { 
        headers,
        withCredentials: true 
      });
      const loaded = response.data.messages || [];
      setMessages(loaded);
      const convFromResponse = (response.data && response.data.conversation) || null;
      const convFromState = conversations.find(c => c.id === conversationId) || null;
      const conv = convFromResponse || convFromState;
      if (conv) {
        setActiveConversation(conv);
        if (conv.metadata?.angle) setAngle(conv.metadata.angle as any);
        if (conv.metadata?.horizon) setHorizon(conv.metadata.horizon as any);
      } else {
        // Fallback minimal object to keep UI consistent
        const now = new Date().toISOString();
        setActiveConversation({
          id: conversationId,
          title: `Conversation ${conversationId}`,
          created_at: now,
          updated_at: now,
          last_message_at: now,
          archived: false,
          message_count: (response.data.messages || []).length,
          metadata: { angle, horizon }
        });
      }

      // Mark all loaded assistant messages as completed for purposes of showing sources chip
      try {
        const completedIds = new Set<number>(streamingCompleteMessageIds);
        for (const m of loaded as Message[]) {
          if (m.role === 'assistant') {
            completedIds.add(m.id);
          }
        }
        setStreamingCompleteMessageIds(completedIds);
      } catch {}
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  };

  const handleNewConversation = async (initialMessage?: string) => {
    try {
      const token = localStorage.getItem('auth_token');
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const response = await axios.post(`${apiBaseUrl}/chat/conversations`, {
        title: initialMessage ? initialMessage.substring(0, 50) : 'New Conversation',
        metadata: { angle, horizon }
      }, { headers, withCredentials: true });
      
      const newConvId = response.data.conversation_id;
      // Optimistically set active conversation immediately
      const now = new Date().toISOString();
      setActiveConversation({
        id: newConvId,
        title: response.data.title || (initialMessage ? initialMessage.substring(0, 50) : 'New Conversation'),
        created_at: now,
        updated_at: now,
        last_message_at: now,
        archived: false,
        message_count: 0,
        metadata: { angle, horizon }
      });
      setMessages([]);
      // Refresh list and hydrate conversation data in background
      loadConversations();
      
      // If there's an initial message, send it
      if (initialMessage) {
        await sendMessage(newConvId, initialMessage);
      }
    } catch (error) {
      console.error('Failed to create conversation:', error);
      // Guest fallback: create a temporary local conversation so the user can keep typing
      const now = new Date().toISOString();
      const tempId = Date.now();
      setActiveConversation({
        id: tempId,
        title: (initialMessage ? initialMessage.substring(0, 50) : 'New Conversation'),
        created_at: now,
        updated_at: now,
        last_message_at: now,
        archived: false,
        message_count: 0,
        metadata: { angle, horizon }
      });
      setMessages([]);
      if (initialMessage) {
        // Still try streaming POST; backend may allow messages without listing conversations
        await sendMessage(tempId, initialMessage);
      }
    }
  };

  const sendMessage = async (conversationId?: number, messageContent?: string) => {
    const convId = conversationId || activeConversation?.id;
    const content = messageContent || inputValue.trim();
    
    if (!convId || !content) return;
    if (isLoading) return;
    
    // Notify parent on first user message in inline mode
    if (layout === 'inline' && messages.length === 0) {
      try { onFirstMessage && onFirstMessage(); } catch {}
    }
    
    setIsLoading(true);
    setInputValue('');
    
    // Add optimistic user message
    const tempUserMessage: Message = {
      id: Date.now(),
      role: 'user',
      content: content,
      created_at: new Date().toISOString(),
      metadata: { angle, horizon }
    };
    setMessages(prev => [...prev, tempUserMessage]);
    
    // Create temporary assistant message for streaming
    const tempAssistantMessage: Message = {
      id: Date.now() + 1,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
      metadata: { angle, horizon }
    };
    setMessages(prev => [...prev, tempAssistantMessage]);
    
    try {
      // Abort any previous in-flight stream
      try { streamControllerRef.current?.abort(); } catch {}
      const controller = new AbortController();
      streamControllerRef.current = controller;
      
      // Start streaming via POST
      const token = localStorage.getItem('auth_token');
      const headers: HeadersInit = { 'Content-Type': 'application/json' };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      
      const initResponse = await fetch(`${apiBaseUrl}/chat/conversations/${convId}/messages/stream`, {
        method: 'POST',
        headers,
        credentials: 'include',
        body: JSON.stringify({
          content,
          angle,
          horizon,
          use_rag: useRag,
          use_search: useSearch
        }),
        signal: controller.signal
      });
      
      if (!initResponse.ok) {
        throw new Error('Failed to start streaming');
      }
      
      const reader = initResponse.body?.getReader();
      const decoder = new TextDecoder();
      let fullResponse = '';
      let sources: any[] = [];
      let buffer = '';
      
      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          const chunk = decoder.decode(value, { stream: true });
          buffer += chunk;
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          for (const rawLine of lines) {
            const line = rawLine.trim();
            if (line.startsWith('data: ')) {
              const data = line.slice(6);
              if (data === '[DONE]') continue;
              
              try {
                const parsed = JSON.parse(data);
                
                if (parsed.type === 'chunk') {
                  fullResponse += parsed.content;
                  // Update the assistant message with streaming content
                  setMessages(prev => prev.map(m => 
                    m.id === tempAssistantMessage.id 
                      ? { ...m, content: fullResponse }
                      : m
                  ));
                } else if (parsed.type === 'sources') {
                  sources = parsed.sources;
                  const asOf = parsed.as_of || null;
                  const mode = parsed.mode || null;
                  // Update metadata with sources + freshness + mode
                  setMessages(prev => prev.map(m => 
                    m.id === tempAssistantMessage.id 
                      ? { ...m, metadata: { ...m.metadata, sources, as_of: asOf, mode } }
                      : m
                  ));
                } else if (parsed.type === 'complete') {
                  // Update with final message ID
                  setMessages(prev => prev.map(m => 
                    m.id === tempAssistantMessage.id 
                      ? { ...m, id: parsed.message_id, content: parsed.full_response }
                      : m
                  ));
                  setStreamingCompleteMessageIds(prev => new Set(prev).add(parsed.message_id));
                } else if (parsed.type === 'error') {
                  console.error('Streaming error:', parsed.message);
                  throw new Error(parsed.message);
                }
              } catch (e) {
                console.error('Failed to parse SSE data:', e);
              }
            }
          }
        }
        // Handle any trailing buffer content
        if (buffer.startsWith('data: ')) {
          try {
            const parsed = JSON.parse(buffer.slice(6));
            if (parsed.type === 'complete') {
              setMessages(prev => prev.map(m => m.id === tempAssistantMessage.id 
                ? { ...m, id: parsed.message_id, content: parsed.full_response }
                : m));
              setStreamingCompleteMessageIds(prev => new Set(prev).add(parsed.message_id));
            }
          } catch {}
        }
      }
      
      // Reload conversations to update last message
      await loadConversations();
    } catch (error) {
      if ((error as any)?.name === 'AbortError') {
        console.warn('Streaming aborted');
        return;
      }
      console.error('Failed to send message:', error);
      // Remove both messages on error
      setMessages(prev => prev.filter(m => 
        m.id !== tempUserMessage.id && m.id !== tempAssistantMessage.id
      ));
      
      // Fallback to non-streaming
      try {
        const response = await axios.post(`${apiBaseUrl}/chat/conversations/${convId}/messages`, {
          content,
          angle,
          horizon,
          use_rag: useRag
        }, { withCredentials: true });
        
        // Re-add user message with correct ID
        setMessages(prev => [
          ...prev.filter(m => m.id !== tempUserMessage.id),
          { ...tempUserMessage, id: response.data.user_message_id }
        ]);
        
        // Add assistant response
        const assistantMessage: Message = {
          id: response.data.assistant_message_id,
          role: 'assistant',
          content: response.data.response,
          created_at: new Date().toISOString(),
          metadata: {
            sources: response.data.sources,
            angle: response.data.angle,
            horizon: response.data.horizon
          }
        };
        
        setMessages(prev => [...prev, assistantMessage]);
        // Non-streaming path is complete by definition
        setStreamingCompleteMessageIds(prev => {
          const next = new Set(prev);
          next.add(assistantMessage.id);
          return next;
        });
        await loadConversations();
      } catch (fallbackError) {
        console.error('Fallback also failed:', fallbackError);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = async (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      
      // In inline mode, automatically create a conversation if none exists
      if (isInline && !activeConversation && inputValue.trim()) {
        await handleNewConversation(inputValue.trim());
      } else {
        sendMessage();
      }
    }
  };

  const deleteConversation = async (id: number) => {
    try {
      await axios.delete(`${apiBaseUrl}/chat/conversations/${id}`, { withCredentials: true });
      await loadConversations();
      if (activeConversation?.id === id) {
        setActiveConversation(null);
        setMessages([]);
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error);
    }
  };

  const archiveConversation = async (id: number) => {
    try {
      await axios.patch(`${apiBaseUrl}/chat/conversations/${id}`, {
        archived: true
      }, { withCredentials: true });
      await loadConversations();
    } catch (error) {
      console.error('Failed to archive conversation:', error);
    }
  };

  const renameConversation = async (id: number, newTitle: string) => {
    try {
      await axios.patch(`${apiBaseUrl}/chat/conversations/${id}`, {
        title: newTitle
      }, { withCredentials: true });
      await loadConversations();
    } catch (error) {
      console.error('Failed to rename conversation:', error);
    }
  };

  const angleIcons = {
    neutral: <MessageSquare className="w-4 h-4" />,
    market: <TrendingUp className="w-4 h-4" />,
    policy: <Shield className="w-4 h-4" />,
    tech: <Cpu className="w-4 h-4" />
  };

  const filteredConversations = conversations.filter(c => 
    !searchQuery || c.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const isInline = layout === 'inline';
  const hasMessages = messages.length > 0;
  
  return (
    <LayoutGroup>
      <motion.div 
        className={cn(
          isInline ? "relative w-full" : "relative h-full",
          isOpen && !isInline ? "md:grid md:grid-cols-[auto_1fr] gap-3" : "",
          className
        )}
        layout
        transition={{ type: 'spring', stiffness: 320, damping: 28 }}
      >
        {/* Left Rail - Conversations List */}
        <AnimatePresence mode="wait">
          {isOpen && !isInline && (
            <motion.aside
              key="rail"
              className={cn(
                "hidden md:flex flex-col bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden",
                railCollapsed ? "w-16" : "w-72"
              )}
              initial={{ width: 0, x: -24, opacity: 0 }}
              animate={{ width: railCollapsed ? 64 : 288, x: 0, opacity: 1 }}
              exit={{ width: 0, x: -24, opacity: 0 }}
              transition={{ duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
            >
              {/* Rail Header */}
              <div className="flex items-center justify-between p-3 border-b border-gray-200 dark:border-gray-700">
                {!railCollapsed && (
                  <h3 className="font-semibold text-sm">Conversations</h3>
                )}
                <div className="flex items-center gap-1">
                  {!railCollapsed && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => handleNewConversation()}
                    >
                      <Plus className="w-4 h-4" />
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => setRailCollapsed(!railCollapsed)}
                  >
                    {railCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
                  </Button>
                </div>
              </div>

              {/* Search */}
              {!railCollapsed && (
                <div className="p-3 border-b border-gray-200 dark:border-gray-700">
                  <div className="relative">
                    <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <Input
                      placeholder="Search conversations..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="pl-8 h-8 text-sm"
                    />
                  </div>
                </div>
              )}

              {/* Conversations List */}
              <div className="flex-1 overflow-y-auto">
                {filteredConversations.map(conv => (
                  <motion.div
                    key={conv.id}
                    className={cn(
                      "group cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors",
                      activeConversation?.id === conv.id && "bg-gray-100 dark:bg-gray-700"
                    )}
                    onClick={() => loadConversation(conv.id)}
                    whileHover={{ x: railCollapsed ? 0 : 2 }}
                  >
                    <div className={cn("p-3", railCollapsed && "px-2")}>
                      {railCollapsed ? (
                        <div className="flex justify-center">
                          <MessageSquare className="w-5 h-5" />
                        </div>
                      ) : (
                        <>
                          <div className="flex items-start justify-between">
                            <h4 className="font-medium text-sm truncate flex-1">
                              {conv.title}
                            </h4>
                            <div className="opacity-0 group-hover:opacity-100 transition-opacity">
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-6 w-6"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  // Show context menu or options
                                }}
                              >
                                <MoreVertical className="w-3 h-3" />
                              </Button>
                            </div>
                          </div>
                          <p className="text-xs text-gray-500 dark:text-gray-400 truncate mt-1">
                            {conv.last_message || 'No messages yet'}
                          </p>
                          <div className="flex items-center gap-2 mt-2">
                            <span className="text-xs text-gray-400">
                              {format(new Date(conv.last_message_at), 'MMM d')}
                            </span>
                            {conv.message_count > 0 && (
                              <Badge variant="secondary" className="text-xs px-1 py-0">
                                {conv.message_count}
                              </Badge>
                            )}
                          </div>
                        </>
                      )}
                    </div>
                  </motion.div>
                ))}
              </div>
            </motion.aside>
          )}
        </AnimatePresence>

        {/* Main Thread Area */}
        <motion.section
          key="thread"
          className={cn(
            "flex flex-col bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700",
            isInline ? "shadow-sm" : "overflow-hidden"
          )}
          layout
          animate={isInline && hasMessages ? { 
            paddingLeft: "1.5rem",
            paddingRight: "1.5rem",
            marginLeft: "1rem",
            marginRight: "1rem"
          } : {}}
          transition={{ duration: 0.3, ease: "easeInOut" }}
        >
          {activeConversation || isInline ? (
            <>
              {/* Thread Header */}
              {activeConversation && (
                <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
                <div className="flex items-center gap-3">
                  <h2 className="font-semibold">{activeConversation.title}</h2>
                  <Badge variant="outline" className="text-xs">
                    {angleIcons[angle]} {angle}
                  </Badge>
                  <Badge variant="outline" className="text-xs">
                    {horizon}-term
                  </Badge>
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="ghost" size="icon" onClick={() => {
                    const newTitle = prompt('Rename conversation:', activeConversation.title);
                    if (newTitle) renameConversation(activeConversation.id, newTitle);
                  }}>
                    <Edit2 className="w-4 h-4" />
                  </Button>
                  <Button variant="ghost" size="icon" onClick={() => archiveConversation(activeConversation.id)}>
                    <Archive className="w-4 h-4" />
                  </Button>
                  <Button variant="ghost" size="icon" onClick={() => deleteConversation(activeConversation.id)}>
                    <Trash2 className="w-4 h-4" />
                  </Button>
                  {onClose && (
                    <Button variant="ghost" size="icon" onClick={onClose}>
                      <X className="w-4 h-4" />
                    </Button>
                  )}
                </div>
              </div>
              )}

              {/* Messages Area */}
              <div className={cn(
                isInline ? "p-4 space-y-4 max-h-[70vh] overflow-y-auto" : "flex-1 overflow-y-auto p-4 space-y-4"
              )}>
                {isLoading && useRag ? (
                  <div className="px-3 sm:px-4 md:px-6 pt-2">
                    <RAGAnimation />
                  </div>
                ) : null}
                {messages.map((message) => {
                  const sourcesList = (((message.metadata as any)?.sources) ?? []) as any[];
                  const asOf = (message.metadata as any)?.as_of;
                  const mode = (message.metadata as any)?.mode;
                  const showSourcesChip = message.role === 'assistant' && sourcesList.length > 0 && streamingCompleteMessageIds.has(message.id);

                  return (
                  <motion.div
                    key={message.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={cn(
                      "flex gap-3",
                      message.role === 'user' ? "justify-end" : "justify-start"
                    )}
                  >
                    {message.role === 'assistant' && (
                      <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center flex-shrink-0">
                        <Bot className="w-4 h-4 text-white" />
                      </div>
                    )}
                    <div className={cn(
                      "max-w-[70%] rounded-lg p-3",
                      message.role === 'user' 
                        ? "bg-blue-500 text-white" 
                        : "bg-gray-100 dark:bg-gray-700"
                    )}>
                      {message.role === 'assistant' && (!message.content || message.content === '') ? (
                        <div className="we-typing" aria-label="Analyzing">
                          <span className="dot" />
                          <span className="dot" />
                          <span className="dot" />
                        </div>
                      ) : (
                        <div className={cn("text-sm", message.role === 'assistant' && message.content ? 'we-text-fade' : '')}>
                          <FormattedMessage text={message.content || ''} />
                        </div>
                      )}
                        {showSourcesChip && (
                          <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-600">
                            <SourcesHoverChip
                              sources={sourcesList}
                              asOf={asOf}
                              mode={mode}
                            />
                          </div>
                        )}
                      <div className="flex items-center gap-2 mt-2">
                        <span className="text-xs opacity-60">
                          {format(new Date(message.created_at), 'HH:mm')}
                        </span>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-5 w-5 opacity-0 hover:opacity-100"
                          onClick={() => navigator.clipboard.writeText(message.content)}
                        >
                          <Copy className="w-3 h-3" />
                        </Button>
                      </div>
                    </div>
                    {message.role === 'user' && (
                      <div className="w-8 h-8 rounded-full bg-gray-200 dark:bg-gray-600 flex items-center justify-center flex-shrink-0">
                        <User className="w-4 h-4" />
                      </div>
                    )}
                  </motion.div>
                  );
                })}

                <div ref={messagesEndRef} />
              </div>

              {/* Input Area */}
              <div className="border-t border-gray-200 dark:border-gray-700 p-4">
                {/* Angle and Horizon Controls */}
                <div className="flex items-center gap-2 mb-3">
                  <div className="flex gap-1">
                    {(['neutral', 'market', 'policy', 'tech'] as const).map(a => (
                      <Button
                        key={a}
                        variant={angle === a ? 'default' : 'outline'}
                        size="sm"
                        className="h-7 px-2 text-xs"
                        onClick={() => setAngle(a)}
                      >
                        {angleIcons[a]}
                        <span className="ml-1">{a}</span>
                      </Button>
                    ))}
                  </div>
                  <div className="flex gap-1 ml-2">
                    {(['near', 'medium', 'long'] as const).map(h => (
                      <Button
                        key={h}
                        variant={horizon === h ? 'default' : 'outline'}
                        size="sm"
                        className="h-7 px-2 text-xs"
                        onClick={() => setHorizon(h)}
                      >
                        {h}
                      </Button>
                    ))}
                  </div>
                  <div className="ml-auto flex gap-2">
                    <Button
                      variant={useRag ? 'default' : 'outline'}
                      size="sm"
                      className="h-7 px-2 text-xs"
                      onClick={() => setUseRag(!useRag)}
                    >
                      {useRag ? 'RAG On' : 'RAG Off'}
                    </Button>
                    <Button
                      variant={useSearch ? 'default' : 'outline'}
                      size="sm"
                      className="h-7 px-2 text-xs"
                      onClick={() => setUseSearch(!useSearch)}
                      title="Use web-search backed model (Perplexity Sonar)"
                    >
                      {useSearch ? 'Search On' : 'Search Off'}
                    </Button>
                  </div>
                </div>

                {/* Message Input */}
                <div className="flex gap-2">
                  <Textarea
                    ref={inputRef}
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Type your message..."
                    className="flex-1 min-h-[60px] max-h-[120px] resize-none"
                    disabled={isLoading}
                  />
                  <Button
                    onClick={() => sendMessage()}
                    disabled={!inputValue.trim() || isLoading}
                    className="self-end"
                  >
                    <Send className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </>
          ) : (
            <div className={cn(
              "flex flex-col items-center justify-center text-center",
              isInline ? "p-6" : "flex-1 p-8"
            )}>
              <MessageSquare className={cn(
                "text-gray-400 mb-4",
                isInline ? "w-8 h-8" : "w-12 h-12"
              )} />
              <h3 className={cn(
                "font-semibold mb-2",
                isInline ? "text-base" : "text-lg"
              )}>Start a Conversation</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                {isInline ? "Type a message below to start" : "Select a conversation from the list or start a new one"}
              </p>
              {!isInline && (
                <Button onClick={() => handleNewConversation()}>
                  <Plus className="w-4 h-4 mr-2" />
                  New Conversation
                </Button>
              )}
            </div>
          )}
        </motion.section>
      </motion.div>
    </LayoutGroup>
  );
}
