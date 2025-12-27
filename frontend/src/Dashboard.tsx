"use client";

import React, { useState, useEffect, useRef, createContext, useContext, useCallback } from 'react';
import axios from 'axios';
import { AnimatePresence, motion } from 'framer-motion';
import { Search, TrendingUp, TrendingDown, BarChart3, Globe, Paperclip, Send, BookmarkIcon, X, MessageSquare, Eye, Copy, Menu, Bell, Settings, User, LogIn, Save, Filter, Calendar, ExternalLink, Zap, Brain, Star, RefreshCw, Loader2, LogOut, Database, Activity, Sparkles, FileText, Plus, ChevronDown, Clock } from "lucide-react";
import { BullHeadIcon, BearHeadIcon } from './components/BullBearIcons';
import { Card, CardContent, CardHeader, CardTitle } from "./components/ui/card";
import { Button } from "./components/ui/button";
import { Input } from "./components/ui/input";
import { Textarea } from "./components/ui/textarea";
import { Popover, PopoverContent, PopoverTrigger } from "./components/ui/popover";
import { Badge } from "./components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./components/ui/tabs";
import { cn } from "./lib/utils";
import { useChatStream } from "./lib/useChatStream";
import { InlineCitationCard, ExpandedArticleCard, RelatedArticlesGrid, SourcesHoverChip } from './components/ArticleCard';
import FormattedMessage from './components/FormattedMessage';
import { useAnalysis } from './lib/useAnalysis';
import type { AnalysisStructured } from './lib/analysisTypes';
import { MessageActions, SmartSuggestions, InsightBadge, exportConversation } from './components/ChatEnhancements';
import RAGAnimation from './components/RAGAnimation';

// API Base URL resolution
// - Default: relative `/api` (nginx reverse proxy in production)
// - Dev override: set REACT_APP_API_URL (e.g., http://localhost:5002/api)
function resolveApiBaseUrl(): string {
  const fallback = '/api';
  const raw = (process.env.REACT_APP_API_URL || '').trim();
  if (!raw) return fallback;

  const isBrowser = typeof window !== 'undefined';
  const pageHost = isBrowser ? window.location.hostname : '';
  const isLocalPage = pageHost === 'localhost' || pageHost === '127.0.0.1';

  // If someone accidentally bakes a localhost URL into a production build,
  // browsers will try to call the user's own machine and axios will throw "Network Error".
  // Protect prod by ignoring localhost targets unless the page itself is localhost.
  let candidate = raw;

  try {
    if (/^https?:\/\//i.test(candidate)) {
      const u = new URL(candidate);
      const isLocalTarget = u.hostname === 'localhost' || u.hostname === '127.0.0.1';
      if (isLocalTarget && !isLocalPage) return fallback;

      // If env is just an origin (no path), assume backend is mounted at /api
      if (!u.pathname || u.pathname === '/') {
        u.pathname = '/api';
      }
      candidate = u.toString();
    }
  } catch {
    // If parsing fails, fall back to the raw string
  }

  candidate = candidate.replace(/\/$/, '');
  if (!candidate.startsWith('http') && !candidate.startsWith('/')) {
    candidate = `/${candidate}`;
  }
  return candidate;
}

const API_BASE_URL = resolveApiBaseUrl();

// Configure axios to send credentials for CSRF token support
axios.defaults.withCredentials = true;

// Also ensure individual requests have withCredentials
axios.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';

// Real Data Interfaces
interface Article {
  id: string;
  title: string;
  source: string;
  created_at: string;
  sentiment_score: number;
  sentiment_confidence: number;
  sentiment_analysis_text?: string;
  category: string;
  description: string;
  url?: string;
  category_confidence?: number;
  saved_at?: string;
  notes?: string;
}

type NewsRequest = {
  limit: number;
  search: string;
  category: string;
  sentiment: string;
  timeframe: string;
};

interface Analysis {
  id: string;
  created_at: string;
  sentiment_summary?: any;
  category_breakdown?: any;
  quality_score?: number;
  raw_response_json?: string;
  content_preview?: string;
  article_count?: number;
}

interface StatsData {
  articles_by_category: { [key: string]: number };
  articles_by_sentiment: { 
    positive: number;
    negative: number;
    neutral: number;
  };
  total_articles: number;
  daily_counts: Array<{
    date: string;
    count: number;
    sentiment_positive: number;
    sentiment_negative: number;
    sentiment_neutral: number;
  }>;
  total_analyses: number;
  recent_articles_count: number;
  recent_analyses: any[];
}

// User Authentication Context
interface User {
  id: string;
  username: string;
  email: string;
  full_name?: string;
  role: string;
  saved_articles: string[];
  profile_picture?: string;
}

interface AuthContextType {
  user: User | null;
  login: (username: string, password: string) => Promise<boolean>;
  register: (username: string, email: string, password: string, full_name?: string) => Promise<boolean>;
  logout: () => void;
  saveArticle: (articleId: string, notes?: string) => Promise<boolean>;
  unsaveArticle: (articleId: string) => Promise<boolean>;
  updateProfile: (data: {username?: string; full_name?: string; email?: string}) => Promise<boolean>;
  updateProfilePicture: (file: File) => Promise<boolean>;
  checkUsernameAvailability: (username: string) => Promise<boolean>;
  loading: boolean;
  error: string | null;
}

const AuthContext = React.createContext<AuthContextType | null>(null);

function useAuth() {
  const context = React.useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

// Auth API Functions
const authAPI = {
  async login(username: string, password: string) {
    try {
      // Get CSRF token first
      const csrfResponse = await axios.get(`${API_BASE_URL}/auth/csrf-token`, {
        withCredentials: true
      });
      const csrfToken = csrfResponse.data.csrf_token;

      // The API_BASE_URL is now '/api', so we shouldn't add another '/api' prefix
      const loginEndpoint = `${API_BASE_URL}/auth/login`;
      console.log('Attempting login to:', loginEndpoint, 'with username:', username);

      // Check if the API endpoint is reachable
      console.log('Checking if API is accessible...');
      try {
        await fetch(`${API_BASE_URL}/health`);
        console.log('API health check successful');
      } catch (err) {
        console.error('API health check failed:', err);
      }

      const response = await axios.post(loginEndpoint, {
        username,
        password
      }, {
        headers: {
          'X-CSRF-Token': csrfToken
        },
        withCredentials: true
      });
      
      console.log('Login response status:', response.status);
      console.log('Login response data:', response.data);
      
      if (response.data.success) {
        console.log('Login successful, token stored in httpOnly cookie');
        // Token is now automatically handled by httpOnly cookie
        // No need to manually store in localStorage
        return response.data.user;
      }
      throw new Error(response.data.error || 'Login failed');
    } catch (error: any) {
      console.error('Login error details:', error);
      console.error('Response status:', error.response?.status);
      console.error('Response data:', error.response?.data);
      console.error('Network error:', error.request ? 'Yes' : 'No');
      
      let errorMessage = 'Login failed: ';
      if (error.response?.data?.message) {
        errorMessage += error.response.data.message;
      } else if (error.message) {
        errorMessage += error.message;
      } else {
        errorMessage += 'Unknown error';
      }
      
      console.error(errorMessage);
      alert(errorMessage);
      return null;
    }
  },

  async register(username: string, email: string, password: string, full_name?: string) {
    try {
      const response = await axios.post(`${API_BASE_URL}/auth/register`, {
        username,
        email,
        password,
        full_name
      });
      if (response.data.success) {
        localStorage.setItem('auth_token', response.data.session_token);
        axios.defaults.headers.common['Authorization'] = `Bearer ${response.data.session_token}`;
        return response.data.user;
      }
      throw new Error(response.data.error || 'Registration failed');
    } catch (error: any) {
      console.error('Registration error:', error);
      let errorMessage = 'Registration failed: ';
      
      if (error.response?.data?.error) {
        // Check for specific error messages from the backend
        const backendError = error.response.data.error;
        if (backendError.includes('Password must be')) {
          errorMessage = backendError;
        } else if (backendError.includes('Username')) {
          errorMessage = 'Username already exists, please choose another one';
        } else if (backendError.includes('Email')) {
          errorMessage = 'Email already exists, please use another email';
        } else {
          errorMessage += backendError;
        }
      } else if (error.message) {
        errorMessage += error.message;
      }
      
      throw new Error(errorMessage);
    }
  },

  async logout() {
    try {
      // Get CSRF token first
      const csrfResponse = await axios.get(`${API_BASE_URL}/auth/csrf-token`, {
        withCredentials: true
      });
      const csrfToken = csrfResponse.data.csrf_token;

      await axios.post(`${API_BASE_URL}/auth/logout`, {}, {
        headers: {
          'X-CSRF-Token': csrfToken
        },
        withCredentials: true
      });
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      // Token is now handled by httpOnly cookie, no need to manually clear
      delete axios.defaults.headers.common['Authorization'];
    }
  },

  async getCurrentUser() {
    try {
      // Token is now handled by httpOnly cookie, no need to manually set headers
      const response = await axios.get(`${API_BASE_URL}/auth/me`);
      return response.data.success ? response.data.user : null;
    } catch (error) {
      // Token is handled by httpOnly cookie, no need to manually clear
      delete axios.defaults.headers.common['Authorization'];
      return null;
    }
  },

  async saveArticle(articleId: string, notes?: string) {
    const response = await axios.post(`${API_BASE_URL}/profile/save-article`, {
      article_id: articleId,
      notes
    });
    return response.data.success;
  },

  async unsaveArticle(articleId: string) {
    const response = await axios.post(`${API_BASE_URL}/profile/unsave-article`, {
      article_id: articleId
    });
    return response.data.success;
  },

  async getSavedArticles() {
    const response = await axios.get(`${API_BASE_URL}/profile/saved-articles`);
    return response.data.success ? response.data.data : [];
  },

  async updateProfile(data: {username?: string; full_name?: string; email?: string}) {
    try {
      // Try PUT first, then POST if it fails with 405
      let response;
      try {
        response = await axios.put(`${API_BASE_URL}/profile/update`, data);
      } catch (putError: any) {
        if (putError.response?.status === 405) {
          // If PUT fails with 405, try POST
          response = await axios.post(`${API_BASE_URL}/profile/update`, data);
        } else {
          throw putError;
        }
      }
      
      if (response.data.success) {
        return response.data;
      }
      return response.data;
    } catch (error: any) {
      // Handle specific error messages from server
      if (error.response?.data?.error) {
        const errorMsg = error.response.data.error;
        // Check for username duplicate error
        if (errorMsg.toLowerCase().includes('username') && errorMsg.toLowerCase().includes('exists')) {
          throw new Error('Username already exists, please choose another one');
        }
        throw new Error(errorMsg);
      }
      if (error.response?.data?.message) {
        throw new Error(error.response.data.message);
      }
      throw error;
    }
  },

  async updateProfilePicture(file: File) {
    try {
      // First, validate the file
      if (!file.type.startsWith('image/')) {
        throw new Error('File must be an image');
      }
      
      if (file.size > 5 * 1024 * 1024) { // 5MB limit
        throw new Error('Image size must be less than 5MB');
      }
      
      // Create a local URL for immediate display
      const localUrl = URL.createObjectURL(file);
      
      // Create a FormData object for the file upload
      const formData = new FormData();
      formData.append('profile_picture', file);
      
      // Try multiple endpoints and methods to ensure robustness
      let response;
      let lastError;
      
      // Try the dedicated endpoint with PUT first
      try {
        response = await axios.put(`${API_BASE_URL}/profile/update-picture`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        if (response.data.success) {
          return {
            success: true,
            profile_picture_url: response.data.profile_picture_url || localUrl
          };
        }
      } catch (err: any) {
        lastError = err;
        console.log('PUT to /profile/update-picture failed:', err.response?.status);
      }
      
      // Try the dedicated endpoint with POST
      try {
        response = await axios.post(`${API_BASE_URL}/profile/update-picture`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        });
        if (response.data.success) {
          return {
            success: true,
            profile_picture_url: response.data.profile_picture_url || localUrl
          };
        }
      } catch (err: any) {
        lastError = err;
        console.log('POST to /profile/update-picture failed:', err.response?.status);
      }
      
      // Try the general update endpoint with base64 encoding
      try {
        // Convert file to base64
        const base64Data = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(reader.result as string);
          reader.onerror = () => reject(new Error('Failed to read file'));
          reader.readAsDataURL(file);
        });
        
        // Send the base64 data
        response = await axios.post(`${API_BASE_URL}/profile/update`, {
          profile_picture_data: base64Data
        });
        
        if (response.data.success) {
          return {
            success: true,
            profile_picture_url: response.data.profile_picture_url || base64Data
          };
        }
      } catch (err: any) {
        lastError = err;
        console.log('Base64 upload failed:', err.response?.status);
      }
      
      // If all API attempts fail, just use the local URL and save to localStorage
      console.log('All API attempts failed, using local storage fallback');
      return {
        success: true,
        profile_picture_url: localUrl
      };
    } catch (error: any) {
      console.error('Error updating profile picture:', error);
      if (error.response?.data?.error) {
        throw new Error(error.response.data.error);
      }
      throw error;
    }
  },

  async checkUsernameAvailability(username: string) {
    try {
      console.log('Checking username availability for:', username);
      
      // Try the server endpoint first
      try {
        const response = await axios.get(`${API_BASE_URL}/auth/check-username?username=${encodeURIComponent(username)}`);
        console.log('Username check response:', response.data);
        
        // Check if response is HTML (means endpoint doesn't exist)
        if (typeof response.data === 'string' && response.data.includes('<!doctype html>')) {
          console.log('Username check endpoint returned HTML, endpoint not implemented, assuming available');
          return true;
        }
        
        // Handle different response formats
        if (response.data.available !== undefined) {
          return response.data.available === true;
        }
        if (response.data.success !== undefined) {
          return response.data.success === true;
        }
        // If no clear indicator, assume available
        return true;
      } catch (apiError: any) {
        // If 404, endpoint doesn't exist, assume available
        if (apiError.response?.status === 404) {
          console.log('Username check endpoint not found, assuming available');
          return true;
        }
        // For other errors, re-throw
        throw apiError;
      }
    } catch (error) {
      console.error('Error checking username availability:', error);
      // Default to available=true to allow users to proceed
      return true;
    }
  }
};

// Custom hook for auto-resizing textarea
const useAutoResizeTextarea = ({ minHeight = 48, maxHeight = 164 }) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const adjustHeight = (reset = false) => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    if (reset) {
      textarea.style.height = `${minHeight}px`;
      return;
    }

    textarea.style.height = 'auto';
    const scrollHeight = textarea.scrollHeight;
    const newHeight = Math.min(Math.max(scrollHeight, minHeight), maxHeight);
    textarea.style.height = `${newHeight}px`;
  };

  return { textareaRef, adjustHeight };
};

// HyperText component for animated text
interface HyperTextProps {
  text: string;
  className?: string;
  duration?: number;
  animateOnLoad?: boolean;
}

function HyperText({ text, className, duration = 800, animateOnLoad = true }: HyperTextProps) {
  const [displayText, setDisplayText] = useState(animateOnLoad ? "" : text);
  const [isAnimating, setIsAnimating] = useState(false);
  const isLoginPage = useRef(false);
  const hasSetupRecurring = useRef(false);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const recurringIntervalRef = useRef<NodeJS.Timeout | null>(null);
  
  // Simple animation function - no useCallback to avoid closure issues
  function runAnimation() {
    if (isAnimating) return;
    
    setIsAnimating(true);
    const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
    let iteration = 0;

    intervalRef.current = setInterval(() => {
      setDisplayText(
        text
          .split("")
          .map((char, index) => {
            if (index < iteration) {
              return text[index];
            }
            return chars[Math.floor(Math.random() * chars.length)];
          })
          .join("")
      );

      if (iteration >= text.length) {
        clearInterval(intervalRef.current!);
        setIsAnimating(false);
        intervalRef.current = null;
      }

      iteration += 1 / 3;
    }, duration / text.length / 3);
  }

  // Initial load - check if login page and run first animation
  useEffect(() => {
    // Detect if on login page
    isLoginPage.current = !!document.querySelector('.bg-gradient-to-br');
    
    // Run initial animation
    if (animateOnLoad) {
      runAnimation();
    }
    
    // For dashboard only, set up recurring animation after a delay
    if (!isLoginPage.current && !hasSetupRecurring.current) {
      hasSetupRecurring.current = true;
      
      // Wait 5 seconds, then set up the recurring animation
      const initialDelayTimer = setTimeout(() => {
        recurringIntervalRef.current = setInterval(() => {
          if (!isAnimating) {
            runAnimation();
          }
        }, 5000);
      }, 5000);
      
      return () => {
        clearTimeout(initialDelayTimer);
      };
    }
  }, [animateOnLoad, duration, text]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
      if (recurringIntervalRef.current) {
        clearInterval(recurringIntervalRef.current);
      }
    };
  }, []);

  return <span className={className}>{displayText}</span>;
}

// AI Input Component
interface AIInputWithSearchProps {
  id?: string;
  placeholder?: string;
  minHeight?: number;
  maxHeight?: number;
  onSubmit?: (value: string, withSearch: boolean) => void;
  onFileSelect?: (file: File) => void;
  className?: string;
  children?: React.ReactNode;
  contentAbove?: React.ReactNode; // content area that appears above the input (e.g., conversation)
  fullWidth?: boolean; // when true, container is not capped at max-w-xl
  autoScrollBottom?: boolean;
  scrollAnchorKey?: number;
}

function AIInputWithSearch({
  id = "ai-input-with-search",
  placeholder = "Search the web...",
  minHeight = 48,
  maxHeight = 164,
  onSubmit,
  onFileSelect,
  className,
  children,
  contentAbove,
  fullWidth = false,
  autoScrollBottom = true,
  scrollAnchorKey,
}: AIInputWithSearchProps) {
  const [value, setValue] = useState("");
  const { textareaRef, adjustHeight } = useAutoResizeTextarea({
    minHeight,
    maxHeight,
  });
  const [showSearch, setShowSearch] = useState(true);
  const conversationRef = useRef<HTMLDivElement | null>(null);

  const handleSubmit = () => {
    if (value.trim()) {
      onSubmit?.(value, showSearch);
      setValue("");
      adjustHeight(true);
    }
  };

  // Auto-stick to bottom inside the chat box only
  useEffect(() => {
    if (!autoScrollBottom) return;
    const el = conversationRef.current;
    if (!el) return;
    try {
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
    } catch {}
  }, [contentAbove, autoScrollBottom, scrollAnchorKey]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      onFileSelect?.(file);
    }
  };

  return (
    <div className={cn("w-full py-4", className)}>
      <div className={cn("relative w-full mx-auto", fullWidth ? "max-w-none" : "max-w-xl") }>
        <div className="relative flex flex-col bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl shadow-sm hover:shadow-md transition-shadow duration-200">
          {/* Conversation area - inside the rounded container */}
          {contentAbove && (
            <motion.div 
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              transition={{ duration: 0.3, ease: 'easeOut' }}
              className="max-h-[400px] overflow-y-auto"
              ref={conversationRef}
            >
              <div className="p-4 space-y-3">
                {contentAbove}
              </div>
              <div className="h-px bg-gradient-to-r from-transparent via-slate-200 dark:via-slate-700 to-transparent" />
            </motion.div>
          )}
          {/* Input area */}
          <div
            className="overflow-y-auto"
            style={{ maxHeight: `${maxHeight}px` }}
          >
            <Textarea
              id={id}
              value={value}
              placeholder={placeholder}
              className="w-full rounded-none px-4 py-3 bg-transparent border-none text-slate-900 dark:text-white placeholder:text-slate-500 dark:placeholder:text-slate-400 resize-none focus-visible:ring-0 focus:outline-none text-[15px] leading-relaxed"
              ref={textareaRef}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit();
                }
              }}
              onChange={(e) => {
                setValue(e.target.value);
                adjustHeight();
              }}
            />
          </div>

          {/* Smart Suggestions */}
          {!value && (
            <SmartSuggestions 
              onSelect={(suggestion) => {
                setValue(suggestion);
                adjustHeight();
                textareaRef.current?.focus();
              }}
              context={{
                lastTopic: contentAbove ? 'current analysis' : undefined
              }}
            />
          )}

          <div className="h-14 bg-slate-50 dark:bg-slate-900/50 rounded-b-xl relative flex items-center px-3">
            <div className="flex items-center gap-2 flex-1">
              <label className="cursor-pointer rounded-lg p-2 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors">
                <input 
                  type="file" 
                  className="hidden" 
                  onChange={handleFileChange}
                />
                <Paperclip className="w-4 h-4 text-black/40 dark:text-white/40 hover:text-black dark:hover:text-white transition-colors" />
              </label>
              <button
                type="button"
                onClick={() => setShowSearch(!showSearch)}
        className={cn(
                  "rounded-full transition-all flex items-center gap-2 px-1.5 py-1 border h-8",
                  showSearch
                    ? "bg-sky-500/15 dark:bg-sky-900/30 border-sky-400 dark:border-sky-600 text-sky-500 dark:text-sky-400"
                    : "bg-black/5 dark:bg-white/5 border-transparent text-black/40 dark:text-white/40 hover:text-black dark:hover:text-white"
                )}
              >
                <div className="w-4 h-4 flex items-center justify-center flex-shrink-0">
                  <motion.div
                    animate={{
                      rotate: showSearch ? 180 : 0,
                      scale: showSearch ? 1.1 : 1,
                    }}
                    whileHover={{
                      rotate: showSearch ? 180 : 15,
                      scale: 1.1,
                      transition: {
                        type: "spring",
                        stiffness: 300,
                        damping: 10,
                      },
                    }}
                    transition={{
                      type: "spring",
                      stiffness: 260,
                      damping: 25,
                    }}
                  >
                    <Globe
                      className={cn(
                        "w-4 h-4",
                        showSearch
                          ? "text-sky-500 dark:text-sky-400"
                          : "text-inherit"
                      )}
                    />
                  </motion.div>
      </div>
                <AnimatePresence>
                  {showSearch && (
                    <motion.span
                      initial={{ width: 0, opacity: 0 }}
                      animate={{
                        width: "auto",
                        opacity: 1,
                      }}
                      exit={{ width: 0, opacity: 0 }}
                      transition={{ duration: 0.2 }}
                      className="text-sm overflow-hidden whitespace-nowrap text-sky-500 dark:text-sky-400 flex-shrink-0"
                    >
                      Search
                    </motion.span>
                  )}
                </AnimatePresence>
              </button>
            </div>
            <button
              type="button"
              onClick={handleSubmit}
              className={cn(
                "rounded-lg p-2.5 transition-all duration-200 ml-auto",
                value
                  ? "bg-blue-500 dark:bg-blue-600 text-white hover:bg-blue-600 dark:hover:bg-blue-700 shadow-sm"
                  : "bg-slate-200 dark:bg-slate-700 text-slate-400 dark:text-slate-500 cursor-not-allowed"
              )}
              disabled={!value.trim()}
            >
              <Send className="w-4 h-4" />
            </button>
            {children && (
              <div className="pt-12 px-3 pb-3">
                <div className="mt-2 border-t border-black/10 dark:border-white/10 pt-3">
                  {children}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// API Functions
const fetchStats = async (retry = 0): Promise<StatsData> => {
  try {
    const response = await axios.get(`${API_BASE_URL}/stats`);
    return response.data.data;
  } catch (error: any) {
    console.error('Failed to fetch stats:', error);
    // If we get a 429 rate limit error and haven't tried too many times, retry after a delay
    if (error.response?.status === 429 && retry < 3) {
      console.log(`Rate limited, retrying in ${(retry + 1) * 2} seconds...`);
      await new Promise(resolve => setTimeout(resolve, (retry + 1) * 2000));
      return fetchStats(retry + 1);
    }
    throw error;
  }
};

const fetchMarketIntelligence = async () => {
  try {
    const response = await axios.get(`${API_BASE_URL}/market-intelligence`);
    return response.data.data;
  } catch (error: any) {
    console.error('Failed to fetch market intelligence:', error);
    return null;
  }
};

const fetchSentimentDistribution = async () => {
  try {
    const response = await axios.get(`${API_BASE_URL}/sentiment-distribution`);
    return response.data.data;
  } catch (error: any) {
    console.error('Failed to fetch sentiment distribution:', error);
    return null;
  }
};

const fetchArticles = async (
  limit = 50,
  search = '',
  category = '',
  sentiment = '',
  timeframe = ''
): Promise<Article[]> => {
  try {
    // For search results
    if (search.trim()) {
      const params = new URLSearchParams();
      params.append('q', search);
      if (limit) params.append('limit', limit.toString());
      if (category) params.append('category', category);
      if (sentiment) params.append('sentiment', sentiment);
      if (timeframe) params.append('timeframe', timeframe);
      const response = await axios.get(`${API_BASE_URL}/search?${params}`);
      return response.data.data;
    }
    
    // For filtered articles
    const params = new URLSearchParams();
    if (limit) params.append('limit', limit.toString());
    if (category) params.append('category', category);
    if (sentiment) params.append('sentiment', sentiment);
    if (timeframe) params.append('timeframe', timeframe);
    
    const response = await axios.get(`${API_BASE_URL}/articles?${params}`);
    return response.data.data;
  } catch (error) {
    console.error("Failed to fetch articles:", error);
    throw error;
  }
};

const fetchAnalyses = async (limit = 10): Promise<Analysis[]> => {
  try {
    const response = await axios.get(`${API_BASE_URL}/analyses?limit=${limit}`);
    return response.data.data;
  } catch (error) {
    console.error("Failed to fetch analyses:", error);
    throw error;
  }
};

// Utility Functions
const getSentimentLabel = (score: number | undefined | null): string => {
  // If score is null or undefined, return 'neutral'
  if (score === null || score === undefined) return 'neutral';
  
  // Otherwise, evaluate the score
  if (score > 0.1) return 'positive';
  if (score < -0.1) return 'negative';
  return 'neutral';
};

const calculateTimeAgo = (dateString: string): string => {
  const date = new Date(dateString);
  const now = new Date();
  const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);
  
  if (diffInSeconds < 60) return 'just now';
  if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)} minutes ago`;
  if (diffInSeconds < 86400) return `${Math.floor(diffInSeconds / 3600)} hours ago`;
  return `${Math.floor(diffInSeconds / 86400)} days ago`;
};

const calculateSentimentPercentages = (stats: StatsData | null) => {
  // Handle missing or incomplete data
  if (!stats) {
    return { positive: 0, negative: 0, neutral: 0 };
  }
  
  // Ensure articles_by_sentiment exists and has expected properties
  const sentimentData = stats.articles_by_sentiment || { positive: 0, negative: 0, neutral: 0 };
  
  // Use safe values with fallbacks for each property
  const positive = sentimentData.positive || 0;
  const negative = sentimentData.negative || 0;
  const neutral = sentimentData.neutral || 0;
  
  const total = positive + negative + neutral;
  
  // Avoid division by zero
  if (total === 0) {
    return { positive: 0, negative: 0, neutral: 0 };
  }
  
  // Calculate percentages and round to integers
  return {
    positive: Math.round((positive / total) * 100),
    negative: Math.round((negative / total) * 100),
    neutral: Math.round((neutral / total) * 100)
  };
};

// Helper function to extract final_intel summary from raw_response_json
const extractIntelSummary = (raw_response_json: any): string | null => {
  try {
    if (!raw_response_json) return null;
    
    let rawData;
    if (typeof raw_response_json === 'string') {
      rawData = JSON.parse(raw_response_json);
    } else if (typeof raw_response_json === 'object') {
      rawData = raw_response_json;
    } else {
      return null;
    }
    
    // Try to extract the final_intel.summary field
    if (rawData.final_intel && rawData.final_intel.summary) {
      return rawData.final_intel.summary;
    }
    
    return null;
  } catch (error) {
    console.error('Error extracting intel summary:', error);
    return null;
  }
};

// Helper function to extract the entire final_intel object from raw_response_json
const extractFinalIntel = (raw_response_json: any): any => {
  try {
    if (!raw_response_json) return null;
    
    let rawData;
    if (typeof raw_response_json === 'string') {
      rawData = JSON.parse(raw_response_json);
    } else if (typeof raw_response_json === 'object') {
      rawData = raw_response_json;
    } else {
      return null;
    }
    
    // Extract the entire final_intel object
    if (rawData.final_intel) {
      return rawData.final_intel;
    }
    
    return null;
  } catch (error) {
    console.error('Error extracting final intel:', error);
    return null;
  }
};

// Helper function to clean content preview (remove prompt)
const getCleanContentPreview = (content: string | undefined): string | null => {
  if (!content) return null;
  
  // Try to identify and remove prompt sections
  const lines = content.split('\n');
  
  // Look for common patterns in prompts
  const promptEndIndex = lines.findIndex(line => 
    line.includes('FINAL ANALYSIS:') || 
    line.includes('INTELLIGENCE REPORT:') ||
    line.includes('===') ||
    line.includes('---')
  );
  
  if (promptEndIndex > 0) {
    // Return content after the prompt
    return lines.slice(promptEndIndex + 1).join('\n').trim();
  }
  
  return content;
};

// Login Component
function LoginPage({ onLogin }: { onLogin: () => void }) {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isRegistering, setIsRegistering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const auth = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      let success = false;
      
      if (isRegistering) {
        success = await auth.register(username, email, password, fullName);
      } else {
        success = await auth.login(username, password);
      }

      if (success) {
        onLogin();
      } else {
        setError(auth.error || 'Authentication failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setIsLoading(false);
    }
  };

  const switchMode = () => {
    setIsRegistering(!isRegistering);
    setError(null);
    setUsername("");
    setEmail("");
    setPassword("");
    setFullName("");
  };

  return (
    <div className="h-screen overflow-hidden flex flex-col items-center justify-center bg-gradient-to-br from-blue-50 to-white dark:from-slate-900 dark:to-slate-800">
      {/* Simple clean background */}
      <div className="absolute inset-0 bg-gradient-to-br from-blue-100/30 via-white to-blue-50/50 dark:from-slate-900/50 dark:via-slate-800 dark:to-slate-900/50"></div>
      
      <div className="relative z-10 w-full max-w-5xl px-6">
        {/* Welcome section */}
        <motion.div 
          initial={{ opacity: 0, y: 10 }} 
          animate={{ opacity: 1, y: 0 }} 
          transition={{ duration: 0.6 }}
          className="text-center mb-8 text-slate-900 dark:text-white"
        >
          <motion.h1 
            className="text-4xl font-extrabold mb-4 text-slate-900 dark:text-white drop-shadow-lg"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2, duration: 0.8 }}
          >
            <HyperText text="WatchfulEye" duration={1000} />
          </motion.h1>
          <motion.p 
            className="text-lg text-slate-800 dark:text-white/95 font-medium mb-4 max-w-2xl mx-auto"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.5, duration: 0.8 }}
          >
            <HyperText text="AI-Powered Intelligence Platform for Financial Markets & Geopolitical Analysis" duration={1200} />
          </motion.p>
          <motion.p 
            className="text-sm text-slate-700 dark:text-white/90 mb-6 max-w-xl mx-auto"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 3.0, duration: 0.8 }}
          >
            <HyperText text="Real-time insights for institutional investors, analysts, and decision-makers. Track breaking events, analyze market impacts, and model scenarios with cutting-edge AI synthesis." duration={1500} />
          </motion.p>
        </motion.div>
        
        {/* Centered login card */}
        <div className="max-w-md mx-auto">
        <motion.div 
          initial={{ opacity: 0, y: 30 }} 
          animate={{ opacity: 1, y: 0 }} 
          transition={{ duration: 0.6 }} 
          className="w-full"
        >
          <Card className="bg-white dark:bg-slate-800 border border-blue-200 dark:border-slate-700 shadow-xl">
            <CardContent className="p-8">
              {/* Simple header */}
              <div className="text-center mb-8">
                <div className="w-12 h-12 bg-gradient-to-r from-blue-500 to-blue-600 rounded-xl flex items-center justify-center mx-auto mb-4">
                  <Globe className="w-6 h-6 text-white" />
                </div>
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                  WatchfulEye
                </h2>
                <p className="text-gray-600 dark:text-gray-300 text-sm">
                  {isRegistering ? 'Create your account' : 'Sign in to your account'}
                </p>
              </div>

              {/* Simple mode toggle */}
              <div className="flex bg-blue-50 dark:bg-gray-700 rounded-lg p-1 mb-6">
                <button 
                  onClick={() => setIsRegistering(false)}
                  className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-all ${
                    !isRegistering
                      ? 'bg-white dark:bg-gray-600 text-blue-600 shadow-sm'
                      : 'text-gray-600 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400'
                  }`}
                >
                  Sign In
                </button>
                <button 
                  onClick={() => setIsRegistering(true)}
                  className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-all ${
                    isRegistering
                      ? 'bg-white dark:bg-gray-600 text-blue-600 shadow-sm'
                      : 'text-gray-600 dark:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400'
                  }`}
                >
                  Sign Up
                </button>
              </div>

              {error && (
                <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                  <p className="text-red-700 dark:text-red-400 text-sm">{error}</p>
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Username Field */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-2">
                    Username
                  </label>
                  <Input 
                    type="text" 
                    placeholder="Enter your username" 
                    value={username} 
                    onChange={(e) => setUsername(e.target.value)} 
                    required 
                    autoComplete="username"
                    className="h-11 border-blue-200 focus:border-blue-500 focus:ring-blue-500"
                  />
                </div>

                {isRegistering && (
                  <>
                    {/* Email Field */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-2">
                        Email
                      </label>
                      <Input 
                        type="email" 
                        value={email} 
                        onChange={(e) => setEmail(e.target.value)} 
                        placeholder="you@example.com" 
                        required 
                        className="h-11 border-blue-200 focus:border-blue-500 focus:ring-blue-500"
                      />
                    </div>

                    {/* Full Name Field */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-2">
                        Full Name
                      </label>
                      <Input 
                        type="text" 
                        value={fullName} 
                        onChange={(e) => setFullName(e.target.value)} 
                        placeholder="Your name" 
                        className="h-11 border-blue-200 focus:border-blue-500 focus:ring-blue-500"
                      />
                    </div>
                  </>
                )}

                {/* Password Field */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-2">
                    Password
                  </label>
                  <Input 
                    type="password" 
                    placeholder="Enter your password" 
                    value={password} 
                    onChange={(e) => setPassword(e.target.value)} 
                    required 
                    autoComplete={isRegistering ? "new-password" : "current-password"}
                    className="h-11 border-blue-200 focus:border-blue-500 focus:ring-blue-500"
                  />
                </div>

                {/* Submit Button */}
                <Button 
                  type="submit" 
                  className="w-full h-11 bg-blue-600 hover:bg-blue-700 text-white font-medium transition-colors" 
                  disabled={isLoading}
                >
                  {isLoading ? (
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      {isRegistering ? 'Creating account...' : 'Signing in...'}
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <LogIn className="w-4 h-4" />
                      {isRegistering ? 'Create Account' : 'Sign In'}
                    </div>
                  )}
                </Button>
              </form>
              <div className="mt-6 text-center space-y-3">
                <button 
                  onClick={switchMode} 
                  className="text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 hover:underline text-sm transition-colors block w-full" 
                  disabled={isLoading}
                >
                  {isRegistering ? 'Already have an account? Sign in' : "Don't have an account? Register"}
                </button>
                
                <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
                  <p className="text-xs text-gray-600 dark:text-gray-400 mb-2">Stay updated with intelligence reports</p>
                  <Button 
                    variant="outline"
                    size="sm"
                    className="w-full bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-700 text-blue-700 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900/40"
                    onClick={() => window.open('https://t.me/watchfuleye41', '_blank')}
                  >
                    <svg className="w-4 h-4 mr-2" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221l-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.446 1.394c-.14.18-.357.295-.6.295-.002 0-.003 0-.005 0l.213-3.054 5.56-5.022c.24-.213-.054-.334-.373-.121l-6.869 4.326-2.96-.924c-.64-.203-.658-.64.135-.954l11.566-4.458c.538-.196 1.006.128.832.941z"/>
                    </svg>
                    Join Telegram Channel
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>
        </div>
      </div>
    </div>
  );
}

// AI Analysis Modal
function AIAnalysisModal({ article, isOpen, onClose, onSendToChat }: { 
  article: Article | null; 
  isOpen: boolean; 
  onClose: () => void; 
  onSendToChat?: (article: Article, seedText?: string) => void;
}) {
  const [analysisStep, setAnalysisStep] = useState(0);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'compact' | 'detailed'>("detailed");
  const [structuredAnalysis, setStructuredAnalysis] = useState<AnalysisStructured | null>(null);
  const { analyze, data, raw, error: analysisError, isLoading } = useAnalysis({ apiBaseUrl: API_BASE_URL });
  const [perspLoading, setPerspLoading] = useState<string | null>(null);

  const [perspError, setPerspError] = useState<string | null>(null);
  const [showPersp, setShowPersp] = useState<{democrat:boolean; republican:boolean; independent:boolean}>({democrat:false, republican:false, independent:false});
  // Sonar toggle removed; we default to the primary model path on backend




  useEffect(() => {
    console.log('🔍 AIAnalysisModal useEffect triggered:', { isOpen, article: article?.title });
    if (isOpen && article) {
      console.log('🚀 Starting AI analysis for article:', article.title);
      setIsAnalyzing(true);
      setAnalysisStep(0);
      setError(null);
      setStructuredAnalysis(null);
      // Ensure perspectives do not preload from previous sessions
      setShowPersp({democrat:false,republican:false,independent:false});
      setPerspError(null);
      
      console.log('📡 Calling analyze() with data:', {
        title: article.title,
        description: article.description?.substring(0, 100) + '...',
        source: article.source,
        category: article.category,
        sentiment_score: article.sentiment_score,
      });
      
      // Start analysis via dedicated hook
      analyze({
        title: article.title,
        description: article.description,
        source: article.source,
        category: article.category,
        sentiment_score: article.sentiment_score,
      });
      
      const steps = [
        "Analyzing sentiment patterns...",
        "Extracting key entities...",
        "Identifying market implications...",
        "Generating insights..."
      ];

      console.log('⏱️ Setting up analysis steps timer');
      steps.forEach((step, index) => {
        setTimeout(() => {
          console.log(`📊 Analysis step ${index + 1}: ${step}`);
          setAnalysisStep(index + 1);
          if (index === steps.length - 1) {
            console.log('✅ Analysis steps completed, setting isAnalyzing to false');
            setIsAnalyzing(false);
            
            // Check if sentiment data is available
            if (article.sentiment_score === undefined || article.sentiment_confidence === undefined) {
              console.log('⚠️ Missing sentiment data');
              setError("Sentiment analysis data is not available for this article.");
            }
          }
        }, (index + 1) * 800);
      });
    }
  }, [isOpen, article]);
  
  // Bridge analysis hook state into modal local state
  useEffect(() => {
    console.log('📊 Analysis data received:', data);
    if (data) {
      console.log('✅ Setting structured analysis data:', data);
      setStructuredAnalysis(data);
    }
  }, [data]);
  useEffect(() => {
    console.log('❌ Analysis error received:', analysisError);
    if (analysisError) {
      console.log('🚨 Setting analysis error:', analysisError);
      setError(analysisError);
    }
  }, [analysisError]);

  const fetchPerspectives = async (targets: Array<'democrat'|'republican'|'independent'>) => {
    if (!article || !targets || targets.length === 0) return;
    setPerspError(null);

    const streamSingle = async (t: 'democrat'|'republican'|'independent') => {
      try {
        setPerspLoading(t);
        setShowPersp(prev => ({ ...prev, [t]: true }));
        const res = await fetch(`${API_BASE_URL}/perspectives/stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: article.title,
            description: article.description,
            source: article.source,
            category: article.category,
            targets: [t],
          })
        });
        if (!res.ok || !res.body) {
          setPerspError('Failed to start perspectives stream');
          return;
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          buffer += chunk;
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          for (const rawLine of lines) {
            const line = rawLine.trim();
            if (!line.startsWith('data: ')) continue;
            const data = line.slice(6);
            if (data === '[DONE]') continue;
            try {
              const evt = JSON.parse(data);
              if (evt.type === 'complete') {
                const pers = evt.perspectives || {};
                setStructuredAnalysis((prev:any)=>{
                  const next = prev ? { ...prev } : ({ perspectives: {} } as any);
                  next.perspectives = { ...(next.perspectives || {}), ...pers };
                  return next;
                });
              } else if (evt.type === 'error') {
                setPerspError(evt.message || 'Perspectives error');
              }
            } catch {}
          }
        }
      } catch (e:any) {
        setPerspError(e?.message || 'Perspectives stream failed');
      } finally {
        setPerspLoading(null);
      }
    };

    // Only handle single target now (no bulk generation)
    await streamSingle(targets[0]);
  };



  if (!article) return null;

  // Ensure sentiment values are properly defined with fallbacks
  const sentimentScore = article.sentiment_score !== undefined && article.sentiment_score !== null 
    ? article.sentiment_score 
    : 0;
  const sentimentConfidence = article.sentiment_confidence !== undefined && article.sentiment_confidence !== null 
    ? article.sentiment_confidence 
    : 0.5;
  const sentimentLabel = getSentimentLabel(sentimentScore);

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[9999]"
          onClick={onClose}
        >
          {/* Fullscreen dim + blur layer */}
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" />

          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            className="absolute inset-0 flex items-center justify-center p-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="bg-white dark:bg-gray-800 rounded-xl w-full max-w-4xl max-h-[95vh] flex flex-col shadow-xl relative overflow-hidden" role="dialog" aria-modal="true" aria-label="AI Analysis">
              <div className="px-4 sm:px-6 py-3 bg-white dark:bg-gray-800 border-b border-slate-200 dark:border-slate-700 rounded-t-xl">
                <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 sm:gap-3">
                  <div className="w-8 h-8 sm:w-10 sm:h-10 bg-gradient-to-r from-purple-500 to-pink-500 rounded-lg flex items-center justify-center">
                    <Brain className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
                  </div>
                  <div>
                    <h2 className="text-lg sm:text-xl font-bold text-gray-900 dark:text-gray-100">AI Analysis</h2>
                    <p className="text-xs sm:text-sm text-gray-600 dark:text-gray-400">Deep insights powered by OpenRouter</p>
                  </div>
                </div>
                  <div className="flex items-center gap-2">
                    <Tabs value={viewMode} onValueChange={(v) => setViewMode(v as 'compact' | 'detailed')}>
                      <TabsList className="h-8">
                        <TabsTrigger value="compact" className="text-xs text-gray-700 dark:text-gray-300">Compact</TabsTrigger>
                        <TabsTrigger value="detailed" className="text-xs text-gray-700 dark:text-gray-300">Detailed</TabsTrigger>
                      </TabsList>
                    </Tabs>
                    <Button aria-label="Close analysis modal" variant="ghost" size="icon" onClick={onClose} className="h-8 w-8 text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100">
                      <X className="w-4 h-4 sm:w-5 sm:h-5" />
                    </Button>
                  </div>
                </div>
              </div>

              {error && (
                <div className="mb-4 p-3 bg-amber-100 dark:bg-amber-900/20 border border-amber-300 dark:border-amber-600 rounded-lg">
                  <p className="text-amber-700 dark:text-amber-400 text-xs sm:text-sm">{error}</p>
                </div>
              )}

              <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-4">
              {isAnalyzing ? (
                <div className="space-y-4">
                  {["Analyzing sentiment patterns...", "Extracting key entities...", "Identifying market implications...", "Generating insights..."].map((step, index) => (
                    <motion.div
                      key={index}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ 
                        opacity: analysisStep > index ? 1 : 0.5,
                        x: 0 
                      }}
                      className="flex items-center gap-3"
                    >
                      {analysisStep > index ? (
                        <div className="w-5 h-5 bg-green-500 rounded-full flex items-center justify-center">
                          <div className="w-2 h-2 bg-white rounded-full" />
                        </div>
                      ) : analysisStep === index ? (
                        <div className="w-5 h-5 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
                      ) : (
                        <div className="w-5 h-5 border-2 border-gray-300 rounded-full" />
                      )}
                      <span className="text-xs sm:text-sm text-gray-700 dark:text-gray-300">{step}</span>
                    </motion.div>
                  ))}

                  {/* Skeletons */}
                  <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-700">
                      <div className="h-4 w-24 bg-slate-200 dark:bg-slate-700 rounded animate-pulse mb-2" />
                      <div className="h-2 w-full bg-slate-200 dark:bg-slate-700 rounded animate-pulse" />
                    </div>
                    <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-700">
                      <div className="h-4 w-28 bg-slate-200 dark:bg-slate-700 rounded animate-pulse mb-2" />
                      <div className="h-2 w-full bg-slate-200 dark:bg-slate-700 rounded animate-pulse" />
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-4 sm:space-y-6">
                  <div>
                    <h3 className="text-[13px] sm:text-sm font-semibold tracking-wide text-slate-600 dark:text-slate-300 uppercase mb-2">Article Summary</h3>
                    <div className="bg-slate-50 dark:bg-slate-700/40 rounded-lg p-3 sm:p-4 border border-slate-200 dark:border-slate-600">
                      <p className="text-slate-800 dark:text-slate-200 text-xs sm:text-sm leading-relaxed">{article.description}</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                    <div className="rounded-lg p-3 sm:p-4 border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 shadow-sm">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="text-xs sm:text-sm font-medium text-slate-800 dark:text-slate-100">Sentiment</h4>
                        <div className={`w-2.5 h-2.5 rounded-full ${sentimentLabel === 'positive' ? 'bg-green-500' : sentimentLabel === 'negative' ? 'bg-red-500' : 'bg-gray-400'}`} />
                      </div>
                      <div className="flex items-center justify-between text-xs text-slate-600 dark:text-slate-400 mb-1">
                        <span className="capitalize">{sentimentLabel}</span>
                        <span>{Math.round(sentimentConfidence * 100)}%</span>
                        </div>
                      <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2 overflow-hidden">
                        <div className="h-2 rounded-full bg-blue-500 transition-all duration-1000" style={{ width: `${sentimentConfidence * 100}%` }} />
                        </div>
                      </div>
                    <div className="rounded-lg p-3 sm:p-4 border border-slate-200 dark:border-slate-600 bg-white dark:bg-slate-800 shadow-sm">
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="text-xs sm:text-sm font-medium text-slate-800 dark:text-slate-100">Category</h4>
                        <Badge variant="secondary" className="text-[10px] sm:text-xs">{article.category || 'Uncategorized'}</Badge>
                    </div>
                      {article.category_confidence !== undefined && (
                        <>
                          <div className="flex items-center justify-between text-xs text-slate-600 dark:text-slate-400 mb-1">
                            <span>Confidence</span>
                            <span>{Math.round((article.category_confidence || 0) * 100)}%</span>
                          </div>
                          <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-2 overflow-hidden">
                            <div className="h-2 rounded-full bg-purple-500 transition-all duration-1000" style={{ width: `${(article.category_confidence || 0) * 100}%` }} />
                          </div>
                        </>
                      )}
                    </div>
                  </div>

                  <div>
                    <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-2 text-sm sm:text-base">
                      AI Analysis
                      {isLoading && (
                        <span className="ml-2 text-xs font-normal text-blue-500 dark:text-blue-400">
                          <span className="inline-block w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mr-1 align-middle" />
                          Loading...
                        </span>
                      )}
                    </h3>
                    
                    {/* Analysis Section with Skeleton Loading */}
                    {viewMode === 'detailed' && (isLoading || structuredAnalysis) && (
                      <motion.div className="space-y-3" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
                        <motion.div className="rounded-xl p-3 sm:p-4 border border-blue-200 dark:border-blue-800 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/10 shadow-sm overflow-visible" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.25 }}>
                          <div className="text-[11px] text-blue-700 dark:text-blue-300 mb-2 flex items-center font-medium">
                            <Zap className="w-3 h-3 mr-1" /> Powered by OpenRouter
                        </div>
                        <div className="text-[10px] text-amber-600 dark:text-amber-400 mb-2 px-2 py-1 bg-amber-50 dark:bg-amber-900/20 rounded border border-amber-200 dark:border-amber-800">
                          ⚠️ Analysis based on AI model with knowledge cutoff - may not reflect most recent events or market conditions
                        </div>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            {/* Key Insights - Show skeleton while loading, content when ready */}
                            {(isLoading && !structuredAnalysis?.insights) ? (
                              <div className="rounded-lg bg-white/60 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700 p-3">
                                <div className="text-xs font-semibold text-slate-700 dark:text-slate-200 mb-1">Key Insights</div>
                                <div className="space-y-2">
                                  {[1,2,3].map(i => (
                                    <div key={`skel-insight-${i}`} className="flex items-start gap-2">
                                      <div className="w-1 h-1 bg-slate-300 dark:bg-slate-600 rounded-full mt-1.5 animate-pulse"></div>
                                      <div className="flex-1 h-3 bg-slate-200 dark:bg-slate-600 rounded animate-pulse" style={{width: `${85 - i*10}%`}}></div>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            ) : structuredAnalysis?.insights && (
                              <motion.div className="rounded-lg bg-white/60 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700 p-3" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
                                <div className="text-xs font-semibold text-slate-700 dark:text-slate-200 mb-1">Key Insights</div>
                                <ul className="list-disc list-inside text-xs sm:text-sm text-slate-800 dark:text-slate-200 space-y-1">
                                  {structuredAnalysis.insights.map((it: string, i: number) => (<li key={i}>{it}</li>))}
                                </ul>
                              </motion.div>
                            )}
                            
                            {/* Geopolitics - Show skeleton while loading, content when ready */}
                            {(isLoading && !structuredAnalysis?.geopolitics) ? (
                              <div className="rounded-lg bg-white/60 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700 p-3">
                                <div className="text-xs font-semibold text-slate-700 dark:text-slate-200 mb-1">Geopolitics</div>
                                <div className="space-y-2">
                                  {[1,2].map(i => (
                                    <div key={`skel-geo-${i}`} className="flex items-start gap-2">
                                      <div className="w-1 h-1 bg-slate-300 dark:bg-slate-600 rounded-full mt-1.5 animate-pulse"></div>
                                      <div className="flex-1 h-3 bg-slate-200 dark:bg-slate-600 rounded animate-pulse" style={{width: `${75 - i*15}%`}}></div>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            ) : structuredAnalysis?.geopolitics && (
                              <motion.div className="rounded-lg bg-white/60 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700 p-3" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25, delay: 0.03 }}>
                                <div className="text-xs font-semibold text-slate-700 dark:text-slate-200 mb-1">Geopolitics</div>
                                <ul className="list-disc list-inside text-xs sm:text-sm text-slate-800 dark:text-slate-200 space-y-1">
                                  {structuredAnalysis.geopolitics.map((it: string, i: number) => (<li key={i}>{it}</li>))}
                                </ul>
                              </motion.div>
                            )}
                          </div>
                          
                          {/* Market - Show skeleton while loading, content when ready */}
                          {(isLoading && !structuredAnalysis?.market) ? (
                            <div className="mt-2">
                              <div className="text-xs font-semibold text-slate-700 dark:text-slate-200 mb-1">Market</div>
                              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                {[1,2].map(i => (
                                  <div key={`skel-market-${i}`} className="rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 p-3 animate-pulse">
                                    <div className="flex items-center justify-between mb-2">
                                      <div className="h-3 bg-slate-200 dark:bg-slate-600 rounded w-1/3"></div>
                                      <div className="h-5 bg-slate-200 dark:bg-slate-600 rounded-full w-16"></div>
                                    </div>
                                    <div className="h-2 bg-slate-200 dark:bg-slate-600 rounded w-3/4"></div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ) : structuredAnalysis?.market && (
                            <div className="mt-2">
                              <div className="text-xs font-semibold text-slate-700 dark:text-slate-200 mb-1">Market</div>
                              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                {structuredAnalysis.market.map((m: any, i: number) => (
                                  <motion.div key={i} className="rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 p-3" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2, delay: i * 0.03 }}>
                                    <div className="flex items-center justify-between">
                                      <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">{m.asset}</div>
                                      <div className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${m.direction==='up'?'bg-green-200 dark:bg-green-700/70 text-green-800 dark:text-green-200':m.direction==='down'?'bg-red-200 dark:bg-red-700/70 text-red-800 dark:text-red-200':m.direction==='volatile'?'bg-amber-200 dark:bg-amber-700/70 text-amber-800 dark:text-amber-200':'bg-gray-200 dark:bg-gray-600 text-gray-800 dark:text-gray-200'}`}>
                                        {m.direction}
                                        {/* show magnitude only if provenance present */}
                                        {m.magnitude && (m.provenance === 'article' || m.provenance === 'db' || m.provenance === 'both') ? ` ${m.magnitude}` : ''}
                                      </div>
                                    </div>
                                    {m.rationale && <div className="mt-1 text-[11px] text-slate-700 dark:text-slate-300">{m.rationale}</div>}
                                  </motion.div>
                                ))}
                              </div>
                            </div>
                          )}
                          {structuredAnalysis?.playbook && (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-2">
                              <motion.div className="rounded-lg bg-white/60 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700 p-3" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
                                <div className="text-xs font-semibold text-slate-700 dark:text-slate-200 mb-1">Playbook</div>
                                <ul className="list-disc list-inside text-xs sm:text-sm text-slate-800 dark:text-slate-200 space-y-1">
                                  {structuredAnalysis.playbook.map((it: string, i: number) => (<li key={i}>{it}</li>))}
                                </ul>
                              </motion.div>
                               {structuredAnalysis?.risks && (
                                <motion.div className="rounded-lg bg-white/60 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700 p-3" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25, delay: 0.03 }}>
                                  <div className="text-xs font-semibold text-slate-700 dark:text-slate-200 mb-1">Risks</div>
                                  <ul className="list-disc list-inside text-xs sm:text-sm text-slate-800 dark:text-slate-200 space-y-1">
                                    {structuredAnalysis.risks.map((it: string, i: number) => (<li key={i}>{it}</li>))}
                                  </ul>
                                </motion.div>
                              )}
                            </div>
                          )}
                           {structuredAnalysis?.timeframes && (
                            <div className="rounded-lg bg-white/60 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700 p-3">
                              <div className="text-xs font-semibold text-slate-700 dark:text-slate-200 mb-2">⏰ Timeframes</div>
                              <div className="flex flex-wrap gap-2 text-[11px] sm:text-xs">
                                <span className="px-2 py-1 rounded bg-blue-200 dark:bg-blue-700/70 text-blue-800 dark:text-blue-200 border border-blue-300 dark:border-blue-600 font-medium"><strong>Near:</strong> {structuredAnalysis.timeframes.near}</span>
                                <span className="px-2 py-1 rounded bg-amber-200 dark:bg-amber-700/70 text-amber-800 dark:text-amber-200 border border-amber-300 dark:border-amber-600 font-medium"><strong>Medium:</strong> {structuredAnalysis.timeframes.medium}</span>
                                <span className="px-2 py-1 rounded bg-purple-200 dark:bg-purple-700/70 text-purple-800 dark:text-purple-200 border border-purple-300 dark:border-purple-600 font-medium"><strong>Long:</strong> {structuredAnalysis.timeframes.long}</span>
                              </div>
                            </div>
                          )}
                           {structuredAnalysis?.signals && (
                            <div className="rounded-lg bg-white/60 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700 p-3">
                              <div className="text-xs font-semibold text-slate-700 dark:text-slate-200 mb-2">📊 Key Signals to Watch</div>
                              <div className="space-y-1">
                                {structuredAnalysis.signals.map((s: string, i: number) => (
                                  <motion.div key={i} className="text-[11px] sm:text-xs text-slate-600 dark:text-slate-300 flex items-start gap-2" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2, delay: i * 0.02 }}>
                                    <span className="text-slate-400 dark:text-slate-500 mt-0.5">•</span>
                                    <span>{s}</span>
                                  </motion.div>
                                ))}
                              </div>
                            </div>
                          )}
                           {structuredAnalysis?.commentary && (
                            <div className="mt-3 rounded-lg bg-white/60 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700 p-3">
                              <div className="text-xs sm:text-sm text-slate-800 dark:text-slate-200 leading-relaxed">{structuredAnalysis.commentary}</div>
                            </div>
                          )}
                          <div className="mt-3">
                            <div className="flex items-center justify-between mb-2">
                              <div className="flex flex-wrap gap-2">
                                <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
                                  <Button variant="outline" size="sm" className="border-red-300 dark:border-red-600 text-red-700 dark:text-red-300 hover:bg-red-50 dark:hover:bg-red-900/20" onClick={()=>fetchPerspectives(['democrat'])} disabled={perspLoading==='democrat'} aria-label="Generate Democratic talking points">
                                    {perspLoading==='democrat' ? 'Generating…' : 'Democratic Talking Points'}
                                  </Button>
                                </motion.div>
                                <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.03 }}>
                                  <Button variant="outline" size="sm" className="border-blue-300 dark:border-blue-600 text-blue-700 dark:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/20" onClick={()=>fetchPerspectives(['republican'])} disabled={perspLoading==='republican'} aria-label="Generate Republican talking points">
                                    {perspLoading==='republican' ? 'Generating…' : 'Republican Talking Points'}
                                  </Button>
                                </motion.div>
                                <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.06 }}>
                                  <Button variant="outline" size="sm" className="border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-900/20" onClick={()=>fetchPerspectives(['independent'])} disabled={perspLoading==='independent'} aria-label="Generate Independent talking points">
                                    {perspLoading==='independent' ? 'Generating…' : 'Independent Talking Points'}
                                  </Button>
                                </motion.div>

                              </div>
                              {/* Sonar toggle removed per product decision */}
                              {perspError && (
                                <div className="mt-2 rounded border border-red-300 dark:border-red-700 bg-red-50 dark:bg-red-900/20 p-2 text-xs text-red-700 dark:text-red-300">
                                  {perspError}
                                </div>
                              )}
                            </div>

                            {structuredAnalysis?.perspectives && (
                              <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                                {showPersp.democrat && (
                                  <motion.div className="rounded-lg border border-red-400 bg-red-100 p-3 dark:bg-red-800/50 dark:border-red-600" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
                                    <div className="text-xs font-semibold text-red-800 dark:text-red-200 mb-1">Democratic Talking Points</div>
                                    {Array.isArray(structuredAnalysis.perspectives?.democrat) && structuredAnalysis.perspectives.democrat.length > 0 ? (
                                      <ul className="list-disc list-inside text-[11px] sm:text-xs text-red-900 dark:text-red-200 space-y-1">
                                        {structuredAnalysis.perspectives.democrat.map((it: string, i: number) => (<li key={i}>{it}</li>))}
                                      </ul>
                                    ) : (
                                      <div className="space-y-1">
                                        {Array.from({ length: 3 }).map((_, i) => (
                                          <div key={i} className="h-3 rounded bg-red-100/60 dark:bg-red-900/40 animate-pulse" />
                                        ))}
                                      </div>
                                    )}
                                  </motion.div>
                                )}
                                {showPersp.republican && (
                                  <motion.div className="rounded-lg border border-blue-400 bg-blue-100 p-3 dark:bg-blue-800/50 dark:border-blue-600" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
                                    <div className="text-xs font-semibold text-blue-800 dark:text-blue-200 mb-1">Republican Talking Points</div>
                                    {Array.isArray(structuredAnalysis.perspectives?.republican) && structuredAnalysis.perspectives.republican.length > 0 ? (
                                      <ul className="list-disc list-inside text-[11px] sm:text-xs text-blue-900 dark:text-blue-200 space-y-1">
                                        {structuredAnalysis.perspectives.republican.map((it: string, i: number) => (<li key={i}>{it}</li>))}
                                      </ul>
                                    ) : (
                                      <div className="space-y-1">
                                        {Array.from({ length: 3 }).map((_, i) => (
                                          <div key={i} className="h-3 rounded bg-blue-100/60 dark:bg-blue-900/40 animate-pulse" />
                                        ))}
                                      </div>
                                    )}
                                  </motion.div>
                                )}
                                {showPersp.independent && (
                                  <motion.div className="rounded-lg border border-slate-300 bg-white p-3 dark:bg-slate-800 dark:border-slate-600" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
                                    <div className="text-xs font-semibold text-slate-700 dark:text-slate-200 mb-1">Independent</div>
                                    {Array.isArray(structuredAnalysis.perspectives?.independent) && structuredAnalysis.perspectives.independent.length > 0 ? (
                                      <ul className="list-disc list-inside text-[11px] sm:text-xs text-slate-800 dark:text-slate-200 space-y-1">
                                        {structuredAnalysis.perspectives.independent.map((it: string, i: number) => (<li key={i}>{it}</li>))}
                                      </ul>
                                    ) : (
                                      <div className="space-y-1">
                                        {Array.from({ length: 3 }).map((_, i) => (
                                          <div key={i} className="h-3 rounded bg-slate-100 dark:bg-slate-700 animate-pulse" />
                                        ))}
                                      </div>
                                    )}
                                  </motion.div>
                                )}
                              </div>
                            )}
                          </div>
                        </motion.div>
                      </motion.div>
                    )}
                    {viewMode === 'detailed' && !structuredAnalysis && (raw ? (
                      <div className="rounded-lg p-3 sm:p-4 border border-blue-200 dark:border-blue-800 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/10 shadow-sm overflow-visible">
                        <div className="text-[11px] text-blue-700 dark:text-blue-300 mb-2 flex items-center font-medium">
                          <Zap className="w-3 h-3 mr-1" /> Powered by OpenRouter
                        </div>
                        <div className="text-[10px] text-amber-600 dark:text-amber-400 mb-2 px-2 py-1 bg-amber-50 dark:bg-amber-900/20 rounded border border-amber-200 dark:border-amber-800">
                          ⚠️ Analysis based on AI model with knowledge cutoff - may not reflect most recent events or market conditions
                        </div>
                        <div className="text-xs sm:text-sm text-slate-800 dark:text-slate-200 whitespace-pre-wrap break-words leading-relaxed font-mono">{raw}</div>
                      </div>
                    ) : error ? (
                      <div className="rounded-lg p-3 sm:p-4 border border-red-300 dark:border-red-700 bg-red-50 dark:bg-red-900/20 shadow-sm">
                        <div className="text-[11px] text-red-700 dark:text-red-300 mb-1 font-medium">Analysis Error</div>
                        <p className="text-xs sm:text-sm text-slate-800 dark:text-slate-200">{error}</p>
                      </div>
                    ) : null)}
                    
                    {/* Original Analysis Section */}
                    {viewMode === 'detailed' && article.sentiment_analysis_text ? (
                      <div className="mt-3 rounded-lg p-3 sm:p-4 border border-purple-200 dark:border-purple-800 bg-gradient-to-br from-purple-50 to-pink-50 dark:from-purple-900/20 dark:to-pink-900/10 shadow-sm">
                        <p className="text-[11px] sm:text-xs text-purple-700 dark:text-purple-300 mb-1">Original Analysis</p>
                        <p className="text-xs sm:text-sm text-slate-800 dark:text-slate-200 italic leading-relaxed">{article.sentiment_analysis_text}</p>
                      </div>
                    ) : viewMode === 'detailed' && !structuredAnalysis && !isLoading && !error ? (
                      <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3 sm:p-4 text-center">
                        <p className="text-xs sm:text-sm text-gray-500 dark:text-gray-400">
                          No detailed analysis available for this article.
                        </p>
                      </div>
                    ) : null}
                  </div>

                </div>
              )}
              </div>
              
              {/* Footer Actions */}
              <div className="px-4 sm:px-6 py-3 bg-white dark:bg-gray-800 border-t border-slate-200 dark:border-slate-700 rounded-b-xl">
                <div className="flex flex-col sm:flex-row gap-2">
                        <Button 
                          variant="outline" 
                          className="flex-1 h-9 text-xs sm:text-sm"
                          onClick={() => {
                            const analysis = `
 Article: ${article.title}
 Source: ${article.source}
 Category: ${article.category || 'Uncategorized'} (${Math.round((article.category_confidence || 0) * 100)}% confidence)
 Sentiment: ${sentimentLabel} (${Math.round(sentimentConfidence * 100)}% confidence)
  ${structuredAnalysis ? `\nInsights: ${structuredAnalysis.insights?.join('; ') || ''}` : (raw ? `\nOpenRouter Analysis:\n${raw}` : '')}
 ${article.sentiment_analysis_text ? `\nOriginal Analysis: ${article.sentiment_analysis_text}` : ''}
                            `.trim();
                            navigator.clipboard.writeText(analysis);
                          }}
                          aria-label="Copy analysis"
                        >
                          <Copy className="w-3 h-3 sm:w-4 sm:h-4 mr-2" />
                          Copy Analysis
                        </Button>
                        {article.url && (
                          <Button variant="outline" className="flex-1 h-9 text-xs sm:text-sm" onClick={() => window.open(article.url as string, '_blank')} aria-label="Open full article">
                            <ExternalLink className="w-3 h-3 sm:w-4 sm:h-4 mr-2" />
                            Read Full Article
                          </Button>
                        )}
                        {onSendToChat && (structuredAnalysis || raw) && (
                          <Button 
                            className="flex-1 h-9 text-xs sm:text-sm"
                            onClick={() => {
                              const seed = structuredAnalysis ? JSON.stringify(structuredAnalysis) : (raw || article.sentiment_analysis_text || '');
                              onSendToChat(article, seed);
                            }}
                            aria-label="Ask in chat"
                          >
                            Ask in Chat (deeper analysis)
                          </Button>
                        )}
                      </div>
                    </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// Article Search Component
function ArticleSearch({
  onResults,
  onApply,
}: {
  onResults: (results: Article[]) => void;
  onApply?: (req: NewsRequest) => void;
}) {
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState({
    category: "all",
    sentiment: "all",
    timeRange: "24h"
  });
  const [availableCategories, setAvailableCategories] = useState<Array<{ name: string; display_name?: string; count?: number }>>([]);
  const [isSearching, setIsSearching] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await axios.get(`${API_BASE_URL}/categories`);
        const cats = (res.data?.categories || []) as Array<{ name: string; display_name?: string; count?: number }>;
        if (!cancelled) setAvailableCategories(cats);
      } catch {
        // Non-fatal: keep dropdown usable with "All" only
        if (!cancelled) setAvailableCategories([]);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const handleSearch = async () => {
    setIsSearching(true);
    try {
      const sentimentFilter = filters.sentiment === "positive" ? "positive" : 
                             filters.sentiment === "negative" ? "negative" :
                             filters.sentiment === "neutral" ? "neutral" : "";

      const req: NewsRequest = {
        limit: 50,
        search: query,
        category: filters.category === 'all' ? '' : filters.category,
        sentiment: sentimentFilter,
        timeframe: filters.timeRange || ''
      };

      onApply?.(req);
      
      const results = await fetchArticles(req.limit, req.search, req.category, req.sentiment, req.timeframe);
      onResults(results);
    } catch (error) {
      console.error('Search failed:', error);
      onResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <Card className="bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base sm:text-lg">
          <Search className="w-4 h-4 sm:w-5 sm:h-5" />
          Article Search
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <Input
            placeholder="Search articles..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="flex-1"
          />
          <Button onClick={handleSearch} disabled={isSearching}>
            {isSearching ? (
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <Search className="w-4 h-4" />
            )}
          </Button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          <div>
            <label className="text-xs text-gray-600 dark:text-gray-400 mb-1 block">Category</label>
            <select 
              value={filters.category}
              onChange={(e) => setFilters(prev => ({ ...prev, category: e.target.value }))}
              className="w-full text-xs sm:text-sm border rounded px-2 py-1 bg-background"
            >
              <option value="all">All</option>
              {availableCategories.map(cat => (
                <option key={cat.name} value={cat.name}>
                  {cat.display_name || cat.name}
                  {typeof cat.count === 'number' ? ` (${cat.count})` : ''}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-600 dark:text-gray-400 mb-1 block">Sentiment</label>
            <select 
              value={filters.sentiment}
              onChange={(e) => setFilters(prev => ({ ...prev, sentiment: e.target.value }))}
              className="w-full text-xs sm:text-sm border rounded px-2 py-1 bg-background"
            >
              <option value="all">All</option>
              <option value="positive">Positive</option>
              <option value="negative">Negative</option>
              <option value="neutral">Neutral</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-600 dark:text-gray-400 mb-1 block">Time</label>
            <select 
              value={filters.timeRange}
              onChange={(e) => setFilters(prev => ({ ...prev, timeRange: e.target.value }))}
              className="w-full text-xs sm:text-sm border rounded px-2 py-1 bg-background"
            >
              <option value="24h">24 Hours</option>
              <option value="7d">7 Days</option>
              <option value="30d">30 Days</option>
            </select>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// Analysis Report Modal
function AnalysisReportModal({ analysis, isOpen, onClose }: { 
  analysis: Analysis | null; 
  isOpen: boolean; 
  onClose: () => void; 
}) {
  if (!analysis || !isOpen) return null;

  // Get the entire final_intel object if available
  const finalIntel = extractFinalIntel(analysis.raw_response_json);

  // Safely parse raw structured data for comprehensive rendering
  const structuredData: any = (() => {
    try {
      if (!analysis?.raw_response_json) return null;
      return typeof analysis.raw_response_json === 'string'
        ? JSON.parse(analysis.raw_response_json)
        : analysis.raw_response_json;
    } catch {
      return null;
    }
  })();

  // Curated sections parsing
  const curated = (() => {
    const sections: { title: string; content: string | string[] }[] = [];
    const add = (title: string, value: any) => {
      if (!value) return;
      if (Array.isArray(value) && value.length === 0) return;
      sections.push({ title, content: value });
    };
    try {
      if (finalIntel) {
        add('Key Insights', finalIntel.key_insights || finalIntel.insights);
        add('Actions / Advice', finalIntel.actionable_advice || finalIntel.actions || finalIntel.recommendations);
        add('Risks', finalIntel.risks || finalIntel.threats);
        add('Opportunities', finalIntel.opportunities || finalIntel.upside);
        add('Signals to Watch', finalIntel.signals || finalIntel.indicators);
        add('Timeframes', finalIntel.timeframes || finalIntel.horizon);
        // Sources can be in final_intel or in raw_response_json
        const raw = typeof analysis.raw_response_json === 'string' ? JSON.parse(analysis.raw_response_json) : analysis.raw_response_json;
        const sources = (raw && (raw.sources || raw.context_sources)) || [];
        if (Array.isArray(sources) && sources.length > 0) add('Sources', sources.map((s: any) => s.title || s.url || 'Source'));
      }
    } catch {}
    return sections;
  })();

  return (
    <AnimatePresence>
      {isOpen && (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
          className="fixed inset-0 z-[9999]"
        onClick={onClose}
        >
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" />
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
            className="absolute inset-0 flex items-center justify-center p-4"
          onClick={(e) => e.stopPropagation()}
        >
            <div className="bg-white dark:bg-gray-800 rounded-xl w-full max-w-4xl max-h-[90vh] overflow-y-auto p-4 sm:p-6 shadow-xl">
            <div className="flex items-center justify-between mb-4 sm:mb-6">
              <div className="flex items-center gap-2 sm:gap-3">
                <div className="w-8 h-8 sm:w-10 sm:h-10 bg-gradient-to-r from-blue-500 to-purple-500 rounded-lg flex items-center justify-center">
                  <Brain className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
                </div>
                <div>
                  <h2 className="text-lg sm:text-xl font-bold text-gray-900 dark:text-gray-100 truncate">Intelligence Report #{analysis.id}</h2>
                  <p className="text-xs sm:text-sm text-gray-600 dark:text-gray-400">
                    Generated on {new Date(analysis.created_at).toLocaleString()} ({calculateTimeAgo(analysis.created_at)})
                  </p>
                </div>
              </div>
              <Button variant="ghost" size="icon" onClick={onClose} className="h-8 w-8 text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100">
                <X className="w-4 h-4 sm:w-5 sm:h-5" />
              </Button>
            </div>

            {/* Analysis Stats */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4 mb-4 sm:mb-6">
              <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3 sm:p-4 text-center">
                <div className="text-lg sm:text-2xl font-bold text-blue-600">{analysis.article_count || 'N/A'}</div>
                <div className="text-xs sm:text-sm text-gray-600 dark:text-gray-400">Articles Analyzed</div>
              </div>
              <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3 sm:p-4 text-center">
                <div className="text-lg sm:text-2xl font-bold text-green-600">
                  {(() => {
                    const q: any = (analysis as any).quality_score;
                    if (q === null || q === undefined) return 'N/A';
                    if (typeof q === 'number') {
                      if (q <= 1) return `${Math.round(q * 100)}%`;
                      if (q <= 10) return `${q}/10`;
                      return String(q);
                    }
                    return String(q);
                  })()}
                </div>
                <div className="text-xs sm:text-sm text-gray-600 dark:text-gray-400">Quality Score</div>
              </div>
              <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3 sm:p-4 text-center">
                <div className="text-lg sm:text-2xl font-bold text-purple-600">
                  {analysis.category_breakdown ? Object.keys(analysis.category_breakdown).length : 'N/A'}
                </div>
                <div className="text-xs sm:text-sm text-gray-600 dark:text-gray-400">Categories</div>
              </div>
            </div>

            {/* Report Content */}
            <div className="space-y-4 sm:space-y-6">
              {/* Analysis Summary - Prioritize final_intel.summary if available */}
                              <div>
                  <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-2 sm:mb-3 text-sm sm:text-base">Analysis Summary</h3>
                  <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3 sm:p-4">
                    <p className="text-xs sm:text-sm text-gray-700 dark:text-gray-300 whitespace-pre-line">
                      {finalIntel?.summary || getCleanContentPreview(analysis.content_preview) || "No summary available"}
                    </p>
                  </div>
                </div>
                
                {/* Curated sections if available */}
                {curated.length > 0 && (
                  <div>
                    <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-2 sm:mb-3 text-sm sm:text-base">Structured Insights</h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                      {curated.map((sec, idx) => (
                        <div key={idx} className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 rounded-lg p-3 sm:p-4 border-l-4 border-blue-500">
                          <h4 className="text-sm font-medium text-blue-700 dark:text-blue-300 mb-1">{sec.title}</h4>
                          {Array.isArray(sec.content) ? (
                            <ul className="list-disc list-inside text-xs sm:text-sm text-gray-700 dark:text-gray-300 space-y-1">
                              {sec.content.map((item, i) => (
                                <li key={i}>{item}</li>
                              ))}
                            </ul>
                          ) : (
                            <p className="text-xs sm:text-sm text-gray-700 dark:text-gray-300 whitespace-pre-line">{sec.content}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Structured sections from raw data */}
                {structuredData?.breaking_news && Array.isArray(structuredData.breaking_news) && (
                  <div>
                    <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-2 sm:mb-3 text-sm sm:text-base">Breaking News</h3>
                    <div className="space-y-2">
                      {structuredData.breaking_news.map((item: any, i: number) => (
                        <div key={i} className="bg-red-100 dark:bg-red-800/50 rounded-lg p-3 border border-red-200 dark:border-red-700">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs font-bold text-red-700 dark:text-red-300">TIER {item.tier ?? 1}</span>
                            <span className="text-xs text-slate-500 dark:text-slate-400">{item.timestamp_hint || item.time || ''}</span>
                          </div>
                          <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">{item.title || item.headline}</div>
                          <div className="text-xs text-slate-700 dark:text-slate-300 mt-1">{item.summary || item.details || item.description}</div>
                          {item.key_insight && (
                            <div className="text-xs mt-2 text-gray-700 dark:text-gray-300"><span className="font-semibold text-gray-900 dark:text-gray-100">Key Insight:</span> {item.key_insight}</div>
                          )}
                          {item.actionable_advice && (
                            <div className="text-xs mt-1 text-gray-700 dark:text-gray-300"><span className="font-semibold text-gray-900 dark:text-gray-100">Actionable:</span> {item.actionable_advice}</div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {structuredData?.key_numbers && Array.isArray(structuredData.key_numbers) && (
                  <div>
                    <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-2 sm:mb-3 text-sm sm:text-base">Key Numbers</h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {structuredData.key_numbers.map((item: any, i: number) => (
                        <div key={i} className="bg-emerald-100 dark:bg-emerald-800/50 rounded-lg p-3 border border-emerald-200 dark:border-emerald-700">
                          <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">{item.label || item.title}</div>
                          <div className="text-sm text-gray-700 dark:text-gray-300">{item.value || item.details}</div>
                          {(item.description || item.context) && (
                            <div className="text-xs text-slate-600 dark:text-slate-400">{item.description || item.context}</div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {structuredData?.market_pulse && Array.isArray(structuredData.market_pulse) && (
                  <div>
                    <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-2 sm:mb-3 text-sm sm:text-base">Market Pulse</h3>
                    <div className="space-y-2">
                      {structuredData.market_pulse.map((item: any, i: number) => (
                        <div key={i} className="bg-blue-100 dark:bg-blue-800/50 rounded-lg p-3 border border-blue-200 dark:border-blue-700">
                          <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">{item.asset_class || item.asset} {item.direction || '↔'}</div>
                          {(item.catalyst || item.reason) && (
                            <div className="text-xs mt-1 text-gray-700 dark:text-gray-300"><span className="font-semibold text-gray-900 dark:text-gray-100">Catalyst:</span> {item.catalyst || item.reason}</div>
                          )}
                          {item.context && (
                            <div className="text-xs mt-1 text-gray-700 dark:text-gray-300"><span className="font-semibold text-gray-900 dark:text-gray-100">Context:</span> {item.context}</div>
                          )}
                          {item.why_it_matters && (
                            <div className="text-xs mt-1 text-gray-700 dark:text-gray-300"><span className="font-semibold text-gray-900 dark:text-gray-100">Why it matters:</span> {item.why_it_matters}</div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {structuredData?.crypto_barometer && Array.isArray(structuredData.crypto_barometer) && (
                  <div>
                    <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-2 sm:mb-3 text-sm sm:text-base">Crypto Barometer</h3>
                    <div className="space-y-2">
                      {structuredData.crypto_barometer.map((item: any, i: number) => (
                        <div key={i} className="bg-amber-100 dark:bg-amber-800/50 rounded-lg p-3 border border-amber-200 dark:border-amber-700">
                          <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">{item.token_name || item.token} {item.direction || item.movement || '↔'}</div>
                          {(item.catalyst || item.catalyst_reason) && (
                            <div className="text-xs mt-1 text-gray-700 dark:text-gray-300"><span className="font-semibold text-gray-900 dark:text-gray-100">Catalyst:</span> {item.catalyst || item.catalyst_reason}</div>
                          )}
                          {item.details && (
                            <div className="text-xs mt-1 text-gray-700 dark:text-gray-300">{item.details}</div>
                          )}
                          {(item.quick_take || item.quick_take_themed) && (
                            <div className="text-xs mt-1 text-gray-700 dark:text-gray-300"><span className="font-semibold text-gray-900 dark:text-gray-100">Quick take:</span> {item.quick_take || item.quick_take_themed}</div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {structuredData?.tech_emergence && Array.isArray(structuredData.tech_emergence) && (
                  <div>
                    <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-2 sm:mb-3 text-sm sm:text-base">Tech Emergence</h3>
                    <div className="space-y-2">
                      {structuredData.tech_emergence.map((item: any, i: number) => (
                        <div key={i} className="bg-purple-100 dark:bg-purple-800/50 rounded-lg p-3 border border-purple-200 dark:border-purple-700">
                          <div className="text-xs text-gray-700 dark:text-gray-300">{item.description || item.potential_impact}</div>
                          {item.adoption_outlook && (
                            <div className="text-xs mt-1 text-gray-700 dark:text-gray-300"><span className="font-semibold text-gray-900 dark:text-gray-100">Adoption Outlook:</span> {item.adoption_outlook}</div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {structuredData?.idea_desk && Array.isArray(structuredData.idea_desk) && (
                  <div>
                    <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-2 sm:mb-3 text-sm sm:text-base">Idea Desk</h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {structuredData.idea_desk.map((item: any, i: number) => (
                        <div key={i} className="bg-green-100 dark:bg-green-800/50 rounded-lg p-3 border border-green-200 dark:border-green-700">
                          <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">{item.action || 'HOLD'} {item.asset_ticker_class || item.ticker || ''}</div>
                          {item.rationale && (
                            <div className="text-xs mt-1 text-gray-700 dark:text-gray-300">{item.rationale}</div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {structuredData?.risk_radar && Array.isArray(structuredData.risk_radar) && (
                  <div>
                    <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-2 sm:mb-3 text-sm sm:text-base">Risk Radar</h3>
                    <div className="space-y-2">
                      {structuredData.risk_radar.map((item: any, i: number) => (
                        <div key={i} className="bg-rose-100 dark:bg-rose-800/50 rounded-lg p-3 border border-rose-200 dark:border-rose-700">
                          <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">{item.risk_type || item.risk}</div>
                          {(item.percentage || item.probability) && (
                            <div className="text-xs text-gray-700 dark:text-gray-300"><span className="font-semibold text-gray-900 dark:text-gray-100">Likelihood:</span> {item.percentage || item.probability}</div>
                          )}
                          {(item.description || item.details) && (
                            <div className="text-xs mt-1">{item.description || item.details}</div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {structuredData?.executive_summary && (
                  <div>
                    <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-2 sm:mb-3 text-sm sm:text-base">Executive Summary</h3>
                    <div className="bg-slate-50 dark:bg-slate-900/20 rounded-lg p-3">
                      <div className="text-xs sm:text-sm whitespace-pre-line">{structuredData.executive_summary}</div>
                    </div>
                  </div>
                )}

                {(() => {
                  const sources = structuredData?.sources || structuredData?.context_sources;
                  if (!sources || !Array.isArray(sources) || sources.length === 0) return null;
                  return (
                    <div>
                      <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-2 sm:mb-3 text-sm sm:text-base">Sources</h3>
                      <div className="space-y-1">
                        {sources.map((s: any, i: number) => (
                          <div key={i} className="text-xs">
                            <span className="font-semibold">{s.title || s.headline || s.url || 'Source'}</span>
                            {s.url && (
                              <a href={s.url} target="_blank" rel="noreferrer" className="ml-2 text-blue-600 hover:underline">Open</a>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })()}

              {analysis.sentiment_summary && (
                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-2 sm:mb-3 text-sm sm:text-base">Sentiment Summary</h3>
                  <div className="bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-900/20 dark:to-purple-900/20 rounded-lg p-3 sm:p-4 border-l-4 border-blue-500">
                    <p className="text-xs sm:text-sm text-gray-700 dark:text-gray-300 break-words">
                      {(() => {
                        try {
                          // Handle string that needs parsing
                          if (typeof analysis.sentiment_summary === 'string') {
                            try {
                              // Try to parse and pretty print
                              const parsed = JSON.parse(analysis.sentiment_summary);
                              return JSON.stringify(parsed, null, 2);
                            } catch {
                              // If not valid JSON, return as is
                              return analysis.sentiment_summary;
                            }
                          } 
                          // Handle object that needs stringifying
                          else if (typeof analysis.sentiment_summary === 'object') {
                            return JSON.stringify(analysis.sentiment_summary, null, 2);
                          }
                          // Fallback
                          return String(analysis.sentiment_summary);
                        } catch (error) {
                          return "Unable to display sentiment summary due to data format issues";
                        }
                      })()}
                    </p>
                  </div>
                </div>
              )}

              {analysis.category_breakdown && (
                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-2 sm:mb-3 text-sm sm:text-base">Category Breakdown</h3>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 sm:gap-3">
                    {(() => {
                      let categoryData = {};
                      
                      try {
                        // Try to parse if it's a string
                        if (typeof analysis.category_breakdown === 'string') {
                          categoryData = JSON.parse(analysis.category_breakdown);
                        } 
                        // Use directly if it's already an object
                        else if (typeof analysis.category_breakdown === 'object') {
                          categoryData = analysis.category_breakdown;
                        }
                        
                        // Render the categories
                        return Object.entries(categoryData).map(([category, count]) => (
                          <div key={category} className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3 text-center">
                            <div className="text-lg font-bold text-gray-900 dark:text-gray-100">{count as number}</div>
                            <div className="text-sm text-gray-600 dark:text-gray-400 capitalize">{category}</div>
                          </div>
                        ));
                      } catch (error) {
                        // Fallback for malformed JSON
                        return (
                          <div className="col-span-3 bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
                            <div className="text-sm text-amber-600 dark:text-amber-400 mb-2">
                              There was an issue parsing the category data
                            </div>
                            <pre className="text-xs text-gray-600 dark:text-gray-400 overflow-auto max-h-40">
                              {String(analysis.category_breakdown)}
                            </pre>
                          </div>
                        );
                      }
                    })()}
                  </div>
                </div>
              )}

              {structuredData && (
                <details>
                  <summary className="cursor-pointer select-none text-sm text-slate-600 dark:text-slate-400">Show All Raw Data</summary>
                  <div className="bg-gray-900 dark:bg-gray-800 rounded-lg p-4 overflow-x-auto mt-2">
                    <pre className="text-xs sm:text-sm text-green-400 whitespace-pre-wrap">
                      {JSON.stringify(structuredData, null, 2)}
                    </pre>
                  </div>
                </details>
              )}
            </div>

            <div className="flex gap-2 mt-6">
              <Button variant="outline" className="flex-1">
                <Copy className="w-4 h-4 mr-2" />
                Copy Report
              </Button>
              <Button variant="outline" className="flex-1">
                <ExternalLink className="w-4 h-4 mr-2" />
                Export Report
              </Button>
            </div>
          </div>
        </motion.div>
      </motion.div>
      )}
    </AnimatePresence>
  );
}

// Auth Provider Component
function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Check for existing authentication on app load
  useEffect(() => {
    const checkAuth = async () => {
      try {
        // Get user from API
        const currentUser = await authAPI.getCurrentUser();
        
        // If we have a user, check for stored profile picture
        if (currentUser) {
          try {
            // Try to get saved profile picture from localStorage
            const userData = JSON.parse(localStorage.getItem('user_data') || '{}');
            if (userData.profile_picture) {
              // Always use the localStorage version if available as it's the most recent
              currentUser.profile_picture = userData.profile_picture;
            }
          } catch (storageError) {
            console.error('Error loading stored user data:', storageError);
          }
        }
        
        setUser(currentUser);
      } catch (e) {
        console.error('Auth check failed:', e);
      } finally {
        setLoading(false);
      }
    };
    
    checkAuth();
  }, []);

  const login = async (username: string, password: string) => {
    try {
      setError(null);
      const user = await authAPI.login(username, password);
      setUser(user);
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'An error occurred');
      return false;
    }
  };

  const register = async (username: string, email: string, password: string, full_name?: string) => {
    try {
      setError(null);
      const user = await authAPI.register(username, email, password, full_name);
      setUser(user);
      
      // Set flag to show welcome modal for new users
      localStorage.setItem('hasSeenWelcome', 'false');
      
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'An error occurred');
      return false;
    }
  };

  const logout = async () => {
    await authAPI.logout();
    setUser(null);
  };

  const saveArticle = async (articleId: string, notes?: string) => {
    try {
      const success = await authAPI.saveArticle(articleId, notes);
      if (success) {
        setUser(prev => ({
          ...prev!,
          saved_articles: [...prev!.saved_articles, articleId]
        }));
      }
      return success;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'An error occurred');
      return false;
    }
  };

  const unsaveArticle = async (articleId: string) => {
    try {
      const success = await authAPI.unsaveArticle(articleId);
      if (success) {
        setUser(prev => ({
          ...prev!,
          saved_articles: prev!.saved_articles.filter(id => id !== articleId)
        }));
      }
      return success;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'An error occurred');
      return false;
    }
  };

  const updateProfile = async (data: {username?: string; full_name?: string; email?: string}) => {
    try {
      const result = await authAPI.updateProfile(data);
      if (result && (result === true || result.success)) {
        setUser(prev => ({
          ...prev!,
          username: data.username || prev!.username,
          full_name: data.full_name || prev!.full_name,
          email: data.email || prev!.email
        }));
        return true;
      }
      return false;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'An error occurred');
      throw e; // Re-throw to let EditProfileModal handle it
    }
  };

  const updateProfilePicture = async (file: File) => {
    try {
      const response = await authAPI.updateProfilePicture(file) as { success: boolean; profile_picture_url: string };
      if (response && response.success) {
        // Get the picture URL from the response
        const pictureUrl = response.profile_picture_url;
        
        // Update the user state with the new profile picture
        setUser(prev => ({
          ...prev!,
          profile_picture: pictureUrl
        }));
        
        // Store the profile picture URL in localStorage to persist across page reloads
        const userData = JSON.parse(localStorage.getItem('user_data') || '{}');
        userData.profile_picture = pictureUrl;
        localStorage.setItem('user_data', JSON.stringify(userData));
        
        return true;
      }
      return false;
    } catch (e) {
      console.error('Error in updateProfilePicture:', e);
      setError(e instanceof Error ? e.message : 'An error occurred');
      return false;
    }
  };

  const checkUsernameAvailability = async (username: string) => {
    try {
      const success = await authAPI.checkUsernameAvailability(username);
      return success;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'An error occurred');
      return false;
    }
  };

  return (
    <AuthContext.Provider value={{ user, login, register, logout, saveArticle, unsaveArticle, updateProfile, updateProfilePicture, checkUsernameAvailability, loading, error }}>
      {children}
    </AuthContext.Provider>
  );
}

// Minimalist Dashboard
function MinimalistDashboard({ 
  onShowProfile,
  showWelcomeOnLoad,
  onWelcomeModalClose
}: { 
  onShowProfile?: () => void;
  showWelcomeOnLoad?: boolean;
  onWelcomeModalClose?: () => void;
}) {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedArticle, setSelectedArticle] = useState<Article | null>(null);
  const [showAnalysis, setShowAnalysis] = useState(false);
  const [selectedAnalysis, setSelectedAnalysis] = useState<Analysis | null>(null);
  const [showAnalysisReport, setShowAnalysisReport] = useState(false);
  const [articles, setArticles] = useState<Article[]>([]);
  const [searchResults, setSearchResults] = useState<Article[]>([]);
  const [newsRequest, setNewsRequest] = useState<NewsRequest>({ limit: 50, search: '', category: '', sentiment: '', timeframe: '' });
  const [draftNewsRequest, setDraftNewsRequest] = useState<NewsRequest>({ limit: 50, search: '', category: '', sentiment: '', timeframe: '' });
  const [newsCategories, setNewsCategories] = useState<Array<{ name: string; display_name?: string; count?: number }>>([]);
  const [showNewsFilters, setShowNewsFilters] = useState(false);
  const [showSearch, setShowSearch] = useState(false);
  const [showAnalytics, setShowAnalytics] = useState(false);
  const [showWelcomeHelp, setShowWelcomeHelp] = useState(false);
  const [showTelegramBlink, setShowTelegramBlink] = useState(true);
  const [stats, setStats] = useState<StatsData | null>(null);
  const [marketIntel, setMarketIntel] = useState<any>(null);
  const [sentimentDist, setSentimentDist] = useState<any>(null);
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  // Inline chat stays in existing box; no ChatWorkspace swapping
  const [chatInitialQuery, setChatInitialQuery] = useState('');
  const [reindexing, setReindexing] = useState(false);
  const [toast, setToast] = useState<{visible: boolean; text: string; variant: 'success'|'error'}>({visible: false, text: '', variant: 'success'});
  const [reindexLimit, setReindexLimit] = useState<number>(50);
  const [inlineChatExpanded, setInlineChatExpanded] = useState(false);
  const inlineChatRef = useRef<HTMLDivElement | null>(null);
  const chat = useChatStream({ apiBaseUrl: API_BASE_URL });
  const auth = useAuth();
  const [conversationHistory, setConversationHistory] = useState<any[]>([]);

  // Fetch conversation history
  const fetchConversationHistory = async () => {
    try {
      if (!auth.user?.id) return;
      const token = localStorage.getItem('auth_token');
      const response = await axios.get(`${API_BASE_URL}/chat/conversations`, {
        params: { user_id: auth.user.id },
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        withCredentials: true
      });
      console.log('[DEBUG] Conversation history response:', response.data);
      if (response.data.conversations) {
        setConversationHistory(response.data.conversations.slice(0, 10));
      }
    } catch (error) {
      console.error('Failed to fetch conversation history:', error);
    }
  };

  const loadConversation = async (conversationId: number) => {
    try {
      const response = await axios.get(`${API_BASE_URL}/chat/conversations/${conversationId}`, {
        withCredentials: true
      });
      if (response.data.messages) {
        chat.setMessages(response.data.messages);
        chat.setConversationId(conversationId); // Set active conversation
        setInlineChatExpanded(true);
      }
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  };

  // Fetch data function (stats + news + reports). Uses current `newsRequest` so filters/search persist across refresh.
  const fetchData = useCallback(async (showRefreshSpinner = false) => {
    try {
      if (showRefreshSpinner) setRefreshing(true);
      else setLoading(true);

      const [statsData, articlesData, analysesData, marketIntelData, sentimentDistData] = await Promise.all([
        fetchStats().catch(error => {
          console.error('Error fetching stats:', error);
          return null;
        }),
        fetchArticles(
          newsRequest.limit,
          newsRequest.search,
          newsRequest.category,
          newsRequest.sentiment,
          newsRequest.timeframe
        ).catch(error => {
          console.error('Error fetching articles:', error);
          return [];
        }),
        fetchAnalyses(10).catch(error => {
          console.error('Error fetching analyses:', error);
          return [];
        }),
        fetchMarketIntelligence().catch(error => {
          console.error('Error fetching market intelligence:', error);
          return null;
        }),
        fetchSentimentDistribution().catch(error => {
          console.error('Error fetching sentiment distribution:', error);
          return null;
        })
      ]);

      if (statsData) setStats(statsData);
      if (marketIntelData) setMarketIntel(marketIntelData);
      if (sentimentDistData) setSentimentDist(sentimentDistData);
      if (articlesData.length > 0) {
        setArticles(articlesData);
        setSearchResults(articlesData);
      }
      if (analysesData.length > 0) setAnalyses(analysesData);
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [newsRequest]);

  const applyDraftNewsRequest = useCallback(async () => {
    const req: NewsRequest = {
      limit: draftNewsRequest.limit || 50,
      search: draftNewsRequest.search || '',
      category: draftNewsRequest.category || '',
      sentiment: draftNewsRequest.sentiment || '',
      timeframe: draftNewsRequest.timeframe || '',
    };
    setNewsRequest(req);
    try {
      setRefreshing(true);
      const articlesData = await fetchArticles(req.limit, req.search, req.category, req.sentiment, req.timeframe);
      setArticles(articlesData);
      setSearchResults(articlesData);
    } catch (e) {
      console.error('Failed to apply news filters:', e);
    } finally {
      setRefreshing(false);
    }
  }, [draftNewsRequest]);

  const clearNewsRequest = useCallback(async () => {
    const req: NewsRequest = { limit: 50, search: '', category: '', sentiment: '', timeframe: '' };
    setDraftNewsRequest(req);
    setNewsRequest(req);
    try {
      setRefreshing(true);
      const articlesData = await fetchArticles(req.limit);
      setArticles(articlesData);
      setSearchResults(articlesData);
    } catch (e) {
      console.error('Failed to clear news filters:', e);
    } finally {
      setRefreshing(false);
    }
  }, []);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    fetchData();
    const interval = setInterval(() => fetchData(true), 300000); // 5 minutes
    return () => clearInterval(interval);
  }, [fetchData]);

  // Fetch conversation history when user logs in
  useEffect(() => {
    if (auth.user?.id) {
      fetchConversationHistory();
    }
  }, [auth.user?.id]);

  // Fetch categories once for Latest News filters
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await axios.get(`${API_BASE_URL}/categories`);
        const cats = (res.data?.categories || []) as Array<{ name: string; display_name?: string; count?: number }>;
        if (!cancelled) setNewsCategories(cats);
      } catch {
        if (!cancelled) setNewsCategories([]);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Keep draft in sync with the currently-applied request (so the filter UI reflects reality)
  useEffect(() => {
    setDraftNewsRequest(newsRequest);
  }, [newsRequest]);

  // Handle welcome modal from props
  useEffect(() => {
    if (showWelcomeOnLoad) {
      setShowWelcomeHelp(true);
      if (onWelcomeModalClose) {
        onWelcomeModalClose();
      }
    }
  }, [showWelcomeOnLoad, onWelcomeModalClose]);

  // Auto-hide help arrow after 10 seconds
  useEffect(() => {
    if (showTelegramBlink) {
      const timer = setTimeout(() => {
        setShowTelegramBlink(false);
      }, 10000); // Show blinking for 10 seconds
      return () => clearTimeout(timer);
    }
  }, [showTelegramBlink]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-900 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-blue-500" />
          <p className="text-slate-600 dark:text-slate-400">Loading dashboard...</p>
          </div>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-900 flex items-center justify-center">
        <div className="text-center">
          <p className="text-slate-600 dark:text-slate-400">Failed to load data</p>
          <Button onClick={() => fetchData()} className="mt-4">
            <RefreshCw className="w-4 h-4 mr-2" />
            Retry
          </Button>
        </div>
      </div>
    );
  }

  const sentimentPercentages = calculateSentimentPercentages(stats);

  // Show loading state while fetching initial data
  if (loading && !stats) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-900 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-blue-500" />
          <p className="text-slate-600 dark:text-slate-400">Loading dashboard...</p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900">
      <div className="w-full px-0 sm:px-4 lg:px-8 py-1 sm:py-2 md:py-4 lg:py-6 space-y-2 sm:space-y-3 md:space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between bg-white/50 dark:bg-slate-800/50 backdrop-blur p-1 sm:p-2 md:p-3 rounded-lg shadow-sm sticky top-0 z-10">
          <div className="flex items-center">
            <h1 className="text-xl sm:text-2xl md:text-3xl font-bold text-slate-900 dark:text-slate-100 mr-2" style={{width: '180px', minWidth: '180px', maxWidth: '180px'}}>
              <HyperText 
                text="WatchfulEye" 
                animateOnLoad={true}
                duration={800}
              />
            </h1>
            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 hidden sm:block">Intelligence Platform</p>
          </div>
          <div className="flex items-center gap-1 sm:gap-2 md:gap-4">
            {/* Mobile: Essential buttons only */}
            <div className="flex items-center gap-1 sm:hidden">
              <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-600 dark:text-slate-300" onClick={() => setShowSearch(!showSearch)}>
                <Search className="w-4 h-4" />
              </Button>
              <Button 
                variant="ghost" 
                size="icon" 
                className="h-8 w-8 text-slate-600 dark:text-slate-300"
                onClick={() => window.open('https://t.me/watchfuleye41', '_blank')} 
                title="Join Telegram"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221l-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.446 1.394c-.14.18-.357.295-.6.295-.002 0-.003 0-.005 0l.213-3.054 5.56-5.022c.24-.213-.054-.334-.373-.121l-6.869 4.326-2.96-.924c-.64-.203-.658-.64.135-.954l11.566-4.458c.538-.196 1.006.128.832.941z"/>
                </svg>
              </Button>
              {auth.user ? (
                <>
                  <Button variant="ghost" size="icon" className="h-8 w-8 p-0 overflow-hidden text-slate-600 dark:text-slate-300" onClick={onShowProfile}>
                    {auth.user.profile_picture ? (
                      <img 
                        src={auth.user.profile_picture} 
                        alt={auth.user.username} 
                        className="w-full h-full object-cover rounded-full"
                      />
                    ) : (
                      <User className="w-4 h-4" />
                    )}
                  </Button>
                  <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-600 dark:text-slate-300" onClick={auth.logout}>
                    <LogOut className="w-4 h-4" />
                  </Button>
                </>
              ) : (
                <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-600 dark:text-slate-300">
                  <User className="w-4 h-4" />
                </Button>
              )}
            </div>
            
            {/* Desktop: All buttons */}
            <div className="hidden sm:flex items-center gap-2 md:gap-4">
              <Button 
                variant="ghost" 
                size="icon" 
                className="h-8 w-8 text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white"
                onClick={() => fetchData(true)}
                disabled={refreshing}
              >
                <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
              </Button>
              {auth.user?.username === 'oli' && (
                <div className="flex items-center gap-2">
                  <select
                    className="h-8 text-xs border rounded px-2 bg-white dark:bg-slate-800 dark:border-slate-700 text-slate-900 dark:text-slate-200"
                    value={reindexLimit}
                    onChange={(e) => setReindexLimit(Number(e.target.value))}
                    title="Reindex count"
                  >
                    <option value={10}>10</option>
                    <option value={50}>50</option>
                    <option value={200}>200</option>
                  </select>
                <Button
                  variant="outline"
                  size="sm"
                  className="text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white"
                  onClick={async () => {
                    try {
                      setReindexing(true);
                      const res = await axios.post(`${API_BASE_URL}/admin/reindex-embeddings`, { limit: reindexLimit });
                      if (res.data?.success) {
                        setToast({visible: true, text: `Reindexed ${res.data.updated} articles`, variant: 'success'});
                      } else {
                        setToast({visible: true, text: res.data?.error || 'Reindex failed', variant: 'error'});
                      }
                    } catch (e) {
                      setToast({visible: true, text: 'Reindex failed', variant: 'error'});
                    } finally {
                      setReindexing(false);
                      setTimeout(() => setToast(prev => ({...prev, visible: false})), 3000);
                    }
                  }}
                  disabled={reindexing}
                >
                  {reindexing ? 'Reindexing…' : 'Reindex'}
                </Button>
                </div>
              )}
              <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white" onClick={() => setShowSearch(!showSearch)}>
                <Search className="w-4 h-4" />
              </Button>
              <Button 
                variant="ghost" 
                size="icon" 
                className={`h-8 w-8 text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white ${showTelegramBlink ? 'animate-pulse ring-2 ring-blue-500 ring-opacity-75' : ''}`}
                onClick={() => window.open('https://t.me/watchfuleye41', '_blank')} 
                title="Join our Telegram"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221l-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.446 1.394c-.14.18-.357.295-.6.295-.002 0-.003 0-.005 0l.213-3.054 5.56-5.022c.24-.213-.054-.334-.373-.121l-6.869 4.326-2.96-.924c-.64-.203-.658-.64.135-.954l11.566-4.458c.538-.196 1.006.128.832.941z"/>
                </svg>
              </Button>
              <div className="relative">
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="h-8 w-8 text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white"
                  onClick={() => setShowWelcomeHelp(true)}
                  title="Help & Information"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
                </Button>
              </div>
              {auth.user ? (
                <div className="flex items-center gap-1 sm:gap-2">
                  <span className="text-xs hidden sm:inline text-slate-600 dark:text-slate-400">{auth.user.username}</span>
                  <Button variant="ghost" size="icon" className="h-8 w-8 p-0 overflow-hidden text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white" onClick={onShowProfile}>
                    {auth.user.profile_picture ? (
                      <img 
                        src={auth.user.profile_picture} 
                        alt={auth.user.username} 
                        className="w-full h-full object-cover rounded-full"
                      />
                    ) : (
                      <User className="w-4 h-4" />
                    )}
                  </Button>
                  <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white" onClick={auth.logout}>
                    <LogOut className="w-4 h-4" />
                  </Button>
                </div>
              ) : (
                <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-600 dark:text-slate-300">
                  <User className="w-4 h-4" />
                </Button>
              )}
            </div>
          </div>
        </div>

        {/* Search */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="px-0"
        >
        <div className="relative w-full mx-auto px-0 sm:px-2 lg:px-4">
      <motion.div
        ref={inlineChatRef}
        initial={false}
        animate={{ 
          width: '100%',
          maxWidth: inlineChatExpanded ? '100%' : '36rem'
        }}
        transition={{ 
          type: 'spring', 
          stiffness: 120, 
          damping: 20,
          mass: 0.8
        }}
        className={cn('mx-auto w-full')}
        style={{ transformOrigin: 'center top' }}
      >
      <AIInputWithSearch
        placeholder="Ask WatchfulEye or search news..."
        minHeight={38}
        maxHeight={120}
        className="py-2"
        fullWidth={inlineChatExpanded}
        autoScrollBottom={true}
        scrollAnchorKey={chat.messages.length}
        onSubmit={async (value, showSearchFlag?: boolean) => {
          try {
            setSearchQuery(value);
            setChatInitialQuery(value);
            if (!inlineChatExpanded) setInlineChatExpanded(true);
            await chat.send(value, { useRag: true, useSearch: showSearchFlag === true });
            // Keep chat within its box; avoid page-level scroll jumps
            try {
              setTimeout(() => {
                const el = inlineChatRef.current;
                if (el && el.scrollTo) el.scrollTo({ top: 0 });
              }, 50);
            } catch {}
          } catch (err) {
            console.error('AI chat failed:', err);
          }
        }}
        contentAbove={
          <>
              {/* New Chat Button - Only show when expanded and has messages */}
              {inlineChatExpanded && chat.messages.length > 0 && (
                <div className="flex items-center justify-center py-2 sticky top-0 z-10">
                  <button
                    onClick={() => {
                      chat.setMessages([]);
                      chat.setConversationId(null);
                      setChatInitialQuery('');
                    }}
                    className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 hover:shadow-sm transition-all duration-200"
                  >
                    <Plus className="w-3.5 h-3.5 text-slate-600 dark:text-slate-300" />
                    <span className="text-xs font-medium text-slate-700 dark:text-slate-200">New Chat</span>
                    <span className="text-[11px] px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300">
                      {chat.messages.length}
                    </span>
                  </button>
                </div>
              )}
            {chat.messages.length > 0 && chat.messages.map(m => {
              // Check if this is an article context card
              if (m.metadata?.isArticleCard && m.metadata?.articleContext) {
                const article = m.metadata.articleContext;
                return (
                  <ExpandedArticleCard
                    key={m.id}
                    source={article}
                    onAnalyze={(source) => {
                      console.log('🎯 onAnalyze triggered for article:', source.title);
                      console.log('📝 Article data:', source);
                      setSelectedArticle(source as Article);
                      setShowAnalysis(true);
                      console.log('✅ Modal state updated: showAnalysis=true, selectedArticle set');
                    }}
                    onSave={(source) => {
                      const isSaved = auth.user?.saved_articles?.includes(source.id as string);
                      if (isSaved) {
                        auth.unsaveArticle(source.id as string);
                      } else {
                        auth.saveArticle(source.id as string);
                      }
                    }}
                    isSaved={auth.user?.saved_articles?.includes(article.id)}
                  />
                );
              }
              
              // Regular message rendering
              return (
                <motion.div 
                  key={m.id} 
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2 }}
                  className={cn(
                    'rounded-lg p-4 relative group',
                    m.role === 'user' 
                      ? 'bg-slate-50 dark:bg-slate-900/30 ml-8' 
                      : m.role === 'system'
                      ? 'bg-amber-50/50 dark:bg-amber-900/20'
                      : 'bg-blue-50/50 dark:bg-blue-900/20 mr-8'
                  )}
                >
                  <MessageActions 
                    content={m.content}
                    sources={m.metadata?.sources}
                    messageId={m.id}
                    onExport={(format) => exportConversation({ messages: [m], format })}
                  />
                  <div className="text-xs font-medium mb-1.5 text-slate-600 dark:text-slate-400">
                    {m.role === 'user' ? 'You' : m.role === 'system' ? 'Context' : 'WatchfulEye'}
                  </div>
                  <div className="text-[15px] leading-relaxed text-slate-800 dark:text-slate-200">
                    {m.role === 'assistant' && (!m.content || m.content.trim() === '') && !(m.metadata as any)?.complete ? (
                      <div className="we-typing" aria-label="Analyzing">
                        <span className="dot" />
                        <span className="dot" />
                        <span className="dot" />
                      </div>
                    ) : (
                      <FormattedMessage text={m.content || ''} />
                    )}
                  </div>
                  {Array.isArray(m.metadata?.sources) && (m.metadata!.sources as any[]).length > 0 && (
                    <div className="mt-3 pt-3 border-t border-slate-200 dark:border-slate-600">
                      <div style={{ ['--chip-top' as any]: '0px' }}>
                      <SourcesHoverChip 
                        sources={(m.metadata!.sources as any[])}
                        asOf={(m.metadata as any)?.as_of}
                        mode={(m.metadata as any)?.mode}
                      />
                      </div>
                    </div>
                  )}
                </motion.div>
              );
            })}
          </>
        }
      />
      </motion.div>
    </div>
        </motion.div>

    {/* Toast */}
    {toast.visible && (
      <div className={`fixed bottom-4 right-4 px-3 py-2 rounded shadow text-sm ${toast.variant === 'success' ? 'bg-green-600 text-white' : 'bg-red-600 text-white'}`}>
        {toast.text}
      </div>
    )}

        {/* Article Search */}
        <AnimatePresence>
          {showSearch && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.3 }}
            >
              <ArticleSearch onResults={setSearchResults} onApply={setNewsRequest} />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Stats Grid */}
        <motion.div 
          className="grid grid-cols-2 md:grid-cols-4 gap-2 sm:gap-4 lg:gap-6"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          {[
            { 
              title: "Intelligence Database", 
              value: stats?.total_articles?.toLocaleString() || "0", 
              subtitle: "Total Articles",
              icon: Database, 
              clickable: true,
              color: "text-blue-600 dark:text-blue-400"
            },
            { 
              title: "Market Intelligence", 
              value: marketIntel ? `${marketIntel.bullish_percentage}%` : `${sentimentPercentages.positive}%`, 
              subtitle: marketIntel ? `${marketIntel.label} ${marketIntel.momentum > 0 ? '↑' : marketIntel.momentum < 0 ? '↓' : '→'}` : (sentimentPercentages.positive > sentimentPercentages.negative ? "Bullish" : "Bearish"),
              icon: (marketIntel ? marketIntel.bullish_percentage > 50 : sentimentPercentages.positive > sentimentPercentages.negative) ? BullHeadIcon : BearHeadIcon,
              clickable: false,
              color: (marketIntel ? marketIntel.bullish_percentage > 50 : sentimentPercentages.positive > sentimentPercentages.negative) ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"
            },
            { 
              title: "Total Activity", 
              value: stats?.recent_articles_count?.toString() || "0", 
              subtitle: "Since Inception",
              icon: Activity, 
              clickable: false,
              color: "text-purple-600 dark:text-purple-400"
            },
            { 
              title: "AI Analyses", 
              value: stats?.total_analyses?.toString() || "0", 
              subtitle: "Deep insights",
              icon: Sparkles, 
              clickable: false,
              color: "text-amber-600 dark:text-amber-400"
            }
          ].map((stat, index) => (
            <Card 
              key={index} 
              className={`bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 ${
                stat.clickable ? 'cursor-pointer hover:shadow-lg hover:border-blue-300 dark:hover:border-blue-600 transition-all duration-200' : ''
              }`}
              onClick={stat.clickable ? () => setShowAnalytics(true) : undefined}
            >
              <CardContent className="p-2 sm:p-4 md:p-6">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <p className="text-xs sm:text-sm font-medium text-slate-600 dark:text-slate-400">{stat.title}</p>
                    <p className="text-lg sm:text-xl md:text-2xl font-bold text-slate-900 dark:text-slate-100">{stat.value}</p>
                    {stat.subtitle && (
                      <p className="text-xs text-slate-500 dark:text-slate-500 mt-0.5">{stat.subtitle}</p>
                    )}
                  </div>
                  {typeof stat.icon === 'function' ? (
                    <div className="text-2xl leading-none">{(stat.icon as any)()}</div>
                  ) : (
                    React.createElement(stat.icon as any, { className: cn("w-6 h-6 sm:w-7 sm:h-7 md:w-8 md:h-8", stat.color || "text-slate-400") })
                  )}
                </div>
        </CardContent>
      </Card>
          ))}
        </motion.div>

        {/* Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-2 sm:gap-4 md:gap-6">
          {/* Sentiment Chart */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            className="order-3 lg:order-1"
          >
            <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
              <CardHeader className="p-3 sm:p-4 md:p-6 pb-1 sm:pb-2 md:pb-3">
                <CardTitle className="text-base sm:text-lg text-slate-900 dark:text-slate-100">Sentiment Analysis</CardTitle>
                <div className="text-xs sm:text-sm text-slate-600 dark:text-slate-400">
                  Total: {(stats?.articles_by_sentiment?.positive || 0) + (stats?.articles_by_sentiment?.neutral || 0) + (stats?.articles_by_sentiment?.negative || 0)} articles
                </div>
              </CardHeader>
              <CardContent className="p-3 sm:p-4 md:p-6 pt-1 sm:pt-2 md:pt-3">
                <div className="space-y-2">
                  {sentimentDist && sentimentDist.distribution ? (
                    <>
                      {[
                        { key: 'very_bullish', label: 'Very Bullish', color: 'bg-green-600', textColor: 'text-green-600' },
                        { key: 'bullish', label: 'Bullish', color: 'bg-green-500', textColor: 'text-green-500' },
                        { key: 'slightly_bullish', label: 'Slightly Bullish', color: 'bg-green-400', textColor: 'text-green-400' },
                        { key: 'neutral', label: 'Neutral', color: 'bg-slate-400', textColor: 'text-slate-600' },
                        { key: 'slightly_bearish', label: 'Slightly Bearish', color: 'bg-red-400', textColor: 'text-red-400' },
                        { key: 'bearish', label: 'Bearish', color: 'bg-red-500', textColor: 'text-red-500' },
                        { key: 'very_bearish', label: 'Very Bearish', color: 'bg-red-600', textColor: 'text-red-600' }
                      ].map((bucket, idx) => {
                        const count = sentimentDist.distribution[bucket.key] || 0;
                        const total = sentimentDist.distribution.total || 1;
                        const pct = Math.round((count / total) * 100);
                        
                        if (count === 0) return null;
                        
                        return (
                          <div key={bucket.key}>
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-1 sm:gap-2">
                                <div className={`w-2 h-2 sm:w-3 sm:h-3 ${bucket.color} rounded-full`}></div>
                                <span className="text-xs text-slate-600 dark:text-slate-400">{bucket.label}</span>
                              </div>
                              <div className="text-right">
                                <div className={`text-xs font-bold ${bucket.textColor}`}>{count}</div>
                                <div className="text-xs text-slate-500">{pct}%</div>
                              </div>
                            </div>
                            <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-1.5">
                              <motion.div 
                                className={`${bucket.color} h-1.5 rounded-full`}
                                initial={{ width: 0 }}
                                animate={{ width: `${pct}%` }}
                                transition={{ duration: 0.8, delay: idx * 0.1 }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </>
                  ) : (
                    <div className="text-center text-slate-500 py-4">Loading sentiment data...</div>
                  )}
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* News Feed - Moved before Bot Analyses for mobile first ordering */}
          <motion.div
            className="lg:col-span-2 order-1 lg:order-3" 
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.4 }}
          >
            <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
              <CardHeader className="p-3 sm:p-4 md:p-6 pb-1 sm:pb-2 md:pb-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <CardTitle className="text-base sm:text-lg text-slate-900 dark:text-slate-100 truncate">Latest News</CardTitle>
                    <span className="text-[10px] sm:text-xs text-slate-500 dark:text-slate-400 whitespace-nowrap">
                      {searchResults.length} shown
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 sm:h-8 sm:w-8"
                      onClick={() => setShowNewsFilters(v => !v)}
                      aria-label="Toggle news filters"
                      title="Filters"
                    >
                      <Filter className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 sm:h-8 sm:w-8"
                      onClick={() => fetchData(true)}
                      aria-label="Refresh latest news"
                      title="Refresh"
                    >
                      <RefreshCw className={cn("w-3.5 h-3.5 sm:w-4 sm:h-4", refreshing ? "animate-spin" : "")} />
                    </Button>
                  </div>
                </div>

                {showNewsFilters && (
                  <div className="mt-2 grid grid-cols-1 sm:grid-cols-4 gap-2">
                    <div className="sm:col-span-2">
                      <Input
                        placeholder="Search within your corpus…"
                        value={draftNewsRequest.search}
                        onChange={(e) => setDraftNewsRequest(prev => ({ ...prev, search: e.target.value }))}
                        onKeyDown={(e) => e.key === 'Enter' && applyDraftNewsRequest()}
                        className="h-8 text-xs sm:text-sm"
                      />
                    </div>
                    <div>
                      <select
                        value={draftNewsRequest.category || 'all'}
                        onChange={(e) => setDraftNewsRequest(prev => ({ ...prev, category: e.target.value === 'all' ? '' : e.target.value }))}
                        className="w-full h-8 text-xs sm:text-sm border rounded px-2 bg-background"
                        aria-label="Category filter"
                      >
                        <option value="all">All categories</option>
                        {newsCategories.map(cat => (
                          <option key={cat.name} value={cat.name}>{cat.display_name || cat.name}</option>
                        ))}
                      </select>
                    </div>
                    <div className="flex gap-2">
                      <select
                        value={draftNewsRequest.sentiment || 'all'}
                        onChange={(e) => setDraftNewsRequest(prev => ({ ...prev, sentiment: e.target.value === 'all' ? '' : e.target.value }))}
                        className="w-full h-8 text-xs sm:text-sm border rounded px-2 bg-background"
                        aria-label="Sentiment filter"
                      >
                        <option value="all">All sentiment</option>
                        <option value="positive">Positive</option>
                        <option value="neutral">Neutral</option>
                        <option value="negative">Negative</option>
                      </select>
                      <select
                        value={draftNewsRequest.timeframe || 'all'}
                        onChange={(e) => setDraftNewsRequest(prev => ({ ...prev, timeframe: e.target.value === 'all' ? '' : e.target.value }))}
                        className="w-full h-8 text-xs sm:text-sm border rounded px-2 bg-background"
                        aria-label="Timeframe filter"
                      >
                        <option value="all">All time</option>
                        <option value="24h">24h</option>
                        <option value="7d">7d</option>
                        <option value="30d">30d</option>
                      </select>
                      <Button
                        className="h-8 text-xs sm:text-sm"
                        onClick={applyDraftNewsRequest}
                        disabled={refreshing}
                      >
                        Apply
                      </Button>
                      <Button
                        variant="outline"
                        className="h-8 text-xs sm:text-sm"
                        onClick={clearNewsRequest}
                        disabled={refreshing}
                      >
                        Clear
                      </Button>
                    </div>
                  </div>
                )}
              </CardHeader>
              <CardContent className="p-3 sm:p-4 md:p-6 pt-1 sm:pt-2 md:pt-3">
                <div className="max-h-[calc(100vh-280px)] overflow-y-auto space-y-2 sm:space-y-3 pr-1 sm:pr-2">
                  {searchResults.map((item, index) => (
                    <motion.div
                      key={item.id}
                      className="flex items-start gap-2 sm:gap-3 p-2 sm:p-3 rounded-lg bg-slate-50 dark:bg-slate-700/50 cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.3, delay: 0.6 + index * 0.1 }}
                      onClick={() => {
                        setSelectedArticle(item);
                        setShowAnalysis(true);
                      }}
                    >
                      <div className="flex-1 min-w-0">
                        <h4 className="font-medium text-slate-900 dark:text-slate-100 hover:text-blue-600 dark:hover:text-blue-400 transition-colors text-sm sm:text-base truncate">{item.title}</h4>
                        <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-400 mt-1 line-clamp-2">{item.description}</p>
                        <div className="flex flex-wrap items-center gap-1 sm:gap-2 mt-2">
                          <Badge variant="secondary" className="text-[10px] sm:text-xs">{item.category}</Badge>
                          <Badge 
                            variant={getSentimentLabel(item.sentiment_score) === 'positive' ? 'default' : getSentimentLabel(item.sentiment_score) === 'negative' ? 'destructive' : 'secondary'}
                            className="text-[10px] sm:text-xs"
                          >
                            {getSentimentLabel(item.sentiment_score)}
                          </Badge>
                          <span className="text-[10px] sm:text-xs text-slate-500">{calculateTimeAgo(item.created_at)}</span>
                          <span className="text-[10px] sm:text-xs text-slate-500 hidden sm:inline">•</span>
                          <span className="text-[10px] sm:text-xs text-slate-500 hidden sm:inline">{item.source}</span>
                          {item.saved_at && (
                            <>
                              <span className="text-[10px] sm:text-xs text-slate-500 hidden sm:inline">•</span>
                              <span className="text-[10px] sm:text-xs text-slate-500 hidden sm:inline">Saved {calculateTimeAgo(item.saved_at)}</span>
                            </>
                          )}
                        </div>
                        {item.notes && (
                          <div className="mt-2 p-1 sm:p-2 bg-blue-50 dark:bg-blue-900/20 rounded text-[10px] sm:text-xs text-slate-700 dark:text-slate-300">
                            <strong>Notes:</strong> {item.notes}
                          </div>
                        )}
                      </div>
                      <div className="flex flex-col gap-1 sm:gap-2">
                        {(() => {
                          const isSaved = !!auth.user?.saved_articles?.includes(item.id);
                          return (
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-6 w-6 sm:h-8 sm:w-8 hover:bg-amber-50 dark:hover:bg-amber-900/20"
                              onClick={(e) => {
                                e.stopPropagation();
                                if (isSaved) {
                                  auth.unsaveArticle(item.id);
                                } else {
                                  auth.saveArticle(item.id);
                                }
                              }}
                              aria-label={isSaved ? 'Unsave article' : 'Save article'}
                            >
                              <BookmarkIcon className={cn('w-3 h-3 sm:w-4 sm:h-4', isSaved ? 'text-amber-600' : 'text-slate-600')} />
                            </Button>
                          );
                        })()}
                        <Button 
                          variant="ghost" 
                          size="icon"
                          className="h-6 w-6 sm:h-8 sm:w-8 hover:bg-blue-50 dark:hover:bg-blue-900/20"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedArticle(item);
                            setShowAnalysis(true);
                          }}
                          aria-label="Analyze article"
                        >
                          <Brain className="w-3 h-3 sm:w-4 sm:h-4 we-animated-stroke" />
                        </Button>
                        {item.url && (
                          <Button 
                            variant="ghost" 
                            size="icon"
                            className="h-6 w-6 sm:h-8 sm:w-8"
                            onClick={(e) => {
                              e.stopPropagation();
                              window.open(item.url, '_blank');
                            }}
                            aria-label="Open full article"
                          >
                            <ExternalLink className="w-3 h-3 sm:w-4 sm:h-4" />
                          </Button>
                        )}
                      </div>
                    </motion.div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </motion.div>

          {/* Bot Analyses - Moved after News Feed for mobile first ordering */}
          <motion.div
            className="order-2 lg:order-2"
            initial={{ opacity: 0, x: 0 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.35 }}
          >
            <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
              <CardHeader className="p-3 sm:p-4 md:p-6 pb-1 sm:pb-2 md:pb-3">
                <CardTitle className="text-base sm:text-lg text-slate-900 dark:text-slate-100">Intelligence Reports</CardTitle>
                <div className="text-xs sm:text-sm text-slate-600 dark:text-slate-400">
                  Recent intelligence reports
                </div>
              </CardHeader>
              <CardContent className="p-3 sm:p-4 md:p-6 pt-1 sm:pt-2 md:pt-3">
                <div className="max-h-[calc(100vh-280px)] overflow-y-auto space-y-2 sm:space-y-3 pr-1 sm:pr-2">
                  {analyses?.length > 0 ? (
                    analyses.map((analysis, index) => (
                      <motion.div
                        key={analysis.id || index}
                        className="p-2 sm:p-3 rounded-lg bg-slate-50 dark:bg-slate-700/50 border border-slate-200 dark:border-slate-600 cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.3, delay: 0.1 * index }}
                        onClick={() => {
                          setSelectedAnalysis(analysis);
                          setShowAnalysisReport(true);
                        }}
                      >
                        <div className="flex items-start justify-between mb-1 sm:mb-2">
                          <div className="text-[10px] sm:text-xs text-slate-500">
                            {calculateTimeAgo(analysis.created_at)}
                          </div>
                          <Badge variant="secondary" className="text-[10px] sm:text-xs">
                            Report #{analyses.length - index}
                          </Badge>
                        </div>
                        <div className="text-xs sm:text-sm text-slate-700 dark:text-slate-300 line-clamp-3">
                          {(() => {
                            // Try to get the final_intel object first
                            const finalIntel = extractFinalIntel(analysis.raw_response_json);
                            if (finalIntel?.summary) return finalIntel.summary;
                            
                            // If no final intel, try to get cleaned content preview
                            const cleanPreview = getCleanContentPreview(analysis.content_preview);
                            if (cleanPreview) return cleanPreview;
                            
                            // Fallback to sentiment summary or default text
                            return (typeof analysis.sentiment_summary === 'string' ? analysis.sentiment_summary : 
                                   JSON.stringify(analysis.sentiment_summary)) || 
                                   "Intelligence analysis report generated";
                          })()}
                        </div>
                        <div className="flex flex-wrap items-center gap-1 sm:gap-2 mt-1 sm:mt-2 text-[10px] sm:text-xs text-slate-500">
                          <span>Articles: {analysis.article_count || 'N/A'}</span>
                          {analysis.quality_score && (
                            <>
                              <span>•</span>
                              <span>Quality: {analysis.quality_score > 1 
                                ? Math.round(analysis.quality_score) 
                                : Math.round(analysis.quality_score * 100)}%</span>
                            </>
                          )}
                          {analysis.category_breakdown && (
                            <>
                              <span>•</span>
                              <span>Categories: {Object.keys(analysis.category_breakdown).length}</span>
                            </>
                          )}
                        </div>
                      </motion.div>
                    ))
                  ) : (
                    <div className="text-center py-6 sm:py-8 text-slate-500 dark:text-slate-400">
                      <Brain className="w-8 h-8 sm:w-12 sm:h-12 mx-auto mb-2 sm:mb-3 opacity-50" />
                      <p className="text-xs sm:text-sm">No analyses available yet</p>
                      <p className="text-[10px] sm:text-xs mt-1">Run the bot to generate intelligence reports</p>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>

        {/* AI Analysis Modal */}
        <AIAnalysisModal 
          article={selectedArticle}
          isOpen={showAnalysis}
          onClose={() => {
            console.log('🚪 AIAnalysisModal onClose triggered');
            setShowAnalysis(false);
            console.log('✅ Modal closed: showAnalysis=false');
          }}
          onSendToChat={(article, seedText) => {
            // Add article as context card in chat
            const articleContext = {
              ...article,
              preview: article.description?.substring(0, 200)
            };
            
            // Create a cleaner prompt with clear structure
            const composed = `Analyze this article and provide: 1) Market implications 2) Geopolitical context 3) Decision-maker insights 4) 3-5 key takeaways with timeframes`;
            
            // Add article card to chat as a system message
            const articleMessage = {
              id: Date.now() - 1,
              role: 'system' as const,
              content: '',
              created_at: new Date().toISOString(),
              metadata: { 
                articleContext,
                isArticleCard: true 
              }
            };
            
            // Update messages with article card
            chat.setMessages(prev => [...prev, articleMessage]);
            
            // Trigger inline chat within existing box
            setChatInitialQuery(composed);
            if (!inlineChatExpanded) setInlineChatExpanded(true);
            
            // Build a richer context payload for the chat so the model has substance
            const contextSeed = (seedText || article.sentiment_analysis_text || article.description || '').toString();
            const MAX_SEED = 4000; // guardrail to keep request reasonable
            const trimmedSeed = contextSeed.length > MAX_SEED ? contextSeed.slice(0, MAX_SEED) + "\n…" : contextSeed;
            const fullQuery = `${composed}\n\nArticle: "${article.title}" from ${article.source}${article.category ? ` (${article.category})` : ''}\n\nContext:\n${trimmedSeed}`;
            try { chat.send(fullQuery, { useRag: true, useSearch: false, suppressUserBubble: true, userMetadata: { origin: 'analysis_modal' } }); } catch {}
            setShowAnalysis(false);
          }}
        />

        {/* Analytics Modal */}
        <AnalyticsModal 
          isOpen={showAnalytics}
          onClose={() => setShowAnalytics(false)}
          stats={stats}
          sentimentDist={sentimentDist}
          marketIntel={marketIntel}
        />

        {/* Analysis Report Modal */}
        <AnalysisReportModal 
          analysis={selectedAnalysis}
          isOpen={showAnalysisReport}
          onClose={() => setShowAnalysisReport(false)}
        />

        {/* Welcome Help Modal */}
        <WelcomeModal 
          isOpen={showWelcomeHelp}
          onClose={() => setShowWelcomeHelp(false)}
        />
      </div>
    </div>
  );
}

// Analytics Modal Component
function AnalyticsModal({ isOpen, onClose, stats, sentimentDist, marketIntel }: { isOpen: boolean; onClose: () => void; stats: StatsData | null; sentimentDist: any; marketIntel: any }) {
  if (!isOpen || !stats) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/50 backdrop-blur z-[9999] flex items-center justify-center p-4 overflow-hidden"
        onClick={onClose}
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          width: "100vw",
          height: '100vh'
        }}
      >
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
          className="bg-white dark:bg-gray-800 rounded-xl max-w-6xl w-full max-h-[90vh] overflow-y-auto"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="p-6">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Analytics Dashboard</h2>
                <p className="text-gray-600 dark:text-gray-400">Comprehensive Intelligence Metrics</p>
              </div>
              <Button variant="ghost" size="icon" onClick={onClose}>
                <X className="w-5 h-5" />
              </Button>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
              {[
                { 
                  title: "Articles Processed", 
                  value: stats?.total_articles?.toLocaleString() || "0", 
                  change: "+15.2%", 
                  trend: "up" 
                },
                { 
                  title: "Avg Sentiment Score", 
                  value: "0.74", 
                  change: "+0.08", 
                  trend: "up" 
                },
                { 
                  title: "Active Sources", 
                  value: Object.keys(stats?.articles_by_category || {}).length.toString(), 
                  change: "+23", 
                  trend: "up" 
                },
                { 
                  title: "Total Analyses", 
                  value: stats?.total_analyses?.toString() || "0", 
                  change: "-0.4s", 
                  trend: "up" 
                }
              ].map((metric, index) => (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.3, delay: index * 0.1 }}
                >
                  <Card className="bg-gray-50 dark:bg-gray-700 border-gray-200 dark:border-gray-600">
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-xs text-gray-600 dark:text-gray-400 uppercase tracking-wide">{metric.title}</p>
                          <p className="text-xl font-bold text-gray-900 dark:text-gray-100">{metric.value}</p>
                          <div className="flex items-center gap-1 mt-1">
                            {metric.trend === "up" ? (
                              <TrendingUp className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
                            ) : (
                              <TrendingDown className="w-3 h-3 text-red-600 dark:text-red-400" />
                            )}
                            <span className="text-xs text-emerald-600 dark:text-emerald-400">{metric.change}</span>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              ))}
            </div>

            {/* Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                              <Card className="bg-gray-50 dark:bg-gray-700 border-gray-200 dark:border-gray-600">
      <CardHeader>
                    <CardTitle className="text-gray-900 dark:text-gray-100">Market Intelligence</CardTitle>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      {marketIntel ? `${marketIntel.label} Market • ${Math.round(marketIntel.confidence * 100)}% Confidence` : 'Analyzing...'}
                    </p>
      </CardHeader>
      <CardContent>
                    <div className="space-y-3">
                      {sentimentDist && sentimentDist.distribution ? (
                        <>
                          {[
                            { key: 'very_bullish', label: 'Very Bullish', color: 'bg-green-600', textColor: 'text-green-600' },
                            { key: 'bullish', label: 'Bullish', color: 'bg-green-500', textColor: 'text-green-500' },
                            { key: 'slightly_bullish', label: 'Slightly Bullish', color: 'bg-green-400', textColor: 'text-green-400' },
                            { key: 'neutral', label: 'Neutral', color: 'bg-gray-500', textColor: 'text-gray-600' },
                            { key: 'slightly_bearish', label: 'Slightly Bearish', color: 'bg-red-400', textColor: 'text-red-400' },
                            { key: 'bearish', label: 'Bearish', color: 'bg-red-500', textColor: 'text-red-500' },
                            { key: 'very_bearish', label: 'Very Bearish', color: 'bg-red-600', textColor: 'text-red-600' }
                          ].map((bucket, idx) => {
                            const count = sentimentDist.distribution[bucket.key] || 0;
                            const total = sentimentDist.distribution.total || 1;
                            const pct = Math.round((count / total) * 100);
                            
                            if (count === 0) return null;
                            
                            return (
                              <div key={bucket.key}>
                                <div className="flex items-center justify-between mb-1">
                                  <div className="flex items-center gap-2">
                                    <div className={`w-3 h-3 ${bucket.color} rounded`}></div>
                                    <span className="text-sm text-gray-700 dark:text-gray-300">{bucket.label}</span>
                                  </div>
                                  <div className="text-right">
                                    <span className={`text-sm font-bold ${bucket.textColor} dark:${bucket.textColor}`}>
                                      {count} <span className="text-xs text-gray-500">({pct}%)</span>
                                    </span>
                                  </div>
                                </div>
                                <div className="w-full bg-gray-200 dark:bg-gray-600 rounded-full h-2">
                                  <motion.div 
                                    className={`${bucket.color} h-2 rounded-full`}
                                    initial={{ width: 0 }}
                                    animate={{ width: `${pct}%` }}
                                    transition={{ duration: 0.8, delay: idx * 0.08 }}
                                  />
                                </div>
                              </div>
                            );
                          })}
                          
                          <div className="pt-3 mt-3 border-t border-gray-300 dark:border-gray-600">
                            <div className="grid grid-cols-2 gap-2 text-xs">
                              <div>
                                <span className="text-gray-500 dark:text-gray-400">Avg Sentiment:</span>
                                <span className={`ml-1 font-bold ${sentimentDist.averages.sentiment > 0 ? 'text-green-600' : 'text-red-600'}`}>
                                  {sentimentDist.averages.sentiment > 0 ? '+' : ''}{sentimentDist.averages.sentiment.toFixed(3)}
                                </span>
                              </div>
                              <div>
                                <span className="text-gray-500 dark:text-gray-400">Avg Confidence:</span>
                                <span className="ml-1 font-bold text-blue-600">{Math.round(sentimentDist.averages.confidence * 100)}%</span>
                              </div>
                            </div>
                          </div>
                        </>
                      ) : (
                        <div className="text-center text-gray-500 py-8">Loading detailed sentiment data...</div>
                      )}
                    </div>
                  </CardContent>
                </Card>

                <Card className="bg-gray-50 dark:bg-gray-700 border-gray-200 dark:border-gray-600">
                  <CardHeader>
                    <CardTitle className="text-gray-900 dark:text-gray-100">Processing Volume</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="h-64 flex items-end justify-between gap-2">
                      {stats?.daily_counts?.slice(-7).map((item, index) => {
                        const maxCount = Math.max(...(stats?.daily_counts?.map(d => d.count) || [1]));
                        return (
                          <motion.div
                            key={index}
                            className="bg-emerald-500 rounded-t flex-1"
                            initial={{ height: 0 }}
                            animate={{ height: `${Math.min((item.count / maxCount) * 100, 100)}%` }}
                            transition={{ duration: 0.8, delay: 0.2 + index * 0.1 }}
                          />
                        );
                      }) || []}
        </div>
      </CardContent>
    </Card>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

// Welcome Modal Component
function WelcomeModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 bg-black/50 backdrop-blur z-[9999] flex items-center justify-center p-4 overflow-hidden"
          onClick={onClose}
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            width: "100vw",
            height: '100vh'
          }}
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            className="bg-white dark:bg-slate-800 rounded-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Welcome to WatchfulEye</h2>
                <Button variant="ghost" size="icon" onClick={onClose}>
                  <X className="w-5 h-5" />
                </Button>
              </div>
              
              <div className="space-y-4">
                <div className="bg-gradient-to-r from-blue-50 to-indigo-100 dark:from-blue-900/20 dark:to-indigo-900/20 text-gray-900 dark:text-gray-100 p-4 rounded-lg">
                  <h3 className="font-semibold text-lg mb-2">Geopolitical Intelligence Dashboard</h3>
                  <p className="text-gray-700 dark:text-gray-300">WatchfulEye helps you track and analyze global news with AI-powered sentiment analysis.</p>
                </div>
                
                <h4 className="text-xl font-semibold mt-6">Key Features</h4>
                
                <div className="grid sm:grid-cols-2 gap-4">
                  <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                    <div className="flex items-center mb-2">
                      <div className="bg-blue-500 p-2 rounded-full mr-2">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2v4m0 12v4M4.93 4.93l2.83 2.83m8.48 8.48 2.83 2.83M2 12h4m12 0h4M4.93 19.07l2.83-2.83m8.48-8.48 2.83-2.83"/></svg>
                      </div>
                      <span className="font-medium">Sentiment Analysis</span>
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">Track positive, negative, and neutral sentiment in news articles</p>
                  </div>
                  
                  <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                    <div className="flex items-center mb-2">
                      <div className="bg-purple-500 p-2 rounded-full mr-2">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>
                      </div>
                      <span className="font-medium">Article Categories</span>
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">Browse news by categories like technology, environment, science, and finance</p>
                  </div>
                  
                  <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                    <div className="flex items-center mb-2">
                      <div className="bg-emerald-500 p-2 rounded-full mr-2">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20.24 12.24a6 6 0 0 0-8.49-8.49L5 10.5V19h8.5l6.74-6.76z"></path><line x1="16" y1="8" x2="2" y2="22"></line><line x1="17.5" y1="15" x2="9" y2="15"></line></svg>
                      </div>
                      <span className="font-medium">AI Analysis</span>
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">Get AI-generated insights for individual articles</p>
                  </div>
                  
                  <div className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                    <div className="flex items-center mb-2">
                      <div className="bg-amber-700 p-2 rounded-full mr-2">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"></path></svg>
                      </div>
                      <span className="font-medium">Save Articles</span>
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">Bookmark important articles and add personal notes</p>
                  </div>
                </div>

                <div className="bg-blue-50 dark:bg-blue-900/20 border-l-4 border-blue-500 p-4 rounded-r-lg mt-6">
                  <h4 className="font-medium text-blue-700 dark:text-blue-300 flex items-center">
                    <svg className="w-4 h-4 mr-2" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221l-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.446 1.394c-.14.18-.357.295-.6.295-.002 0-.003 0-.005 0l.213-3.054 5.56-5.022c.24-.213-.054-.334-.373-.121l-6.869 4.326-2.96-.924c-.64-.203-.658-.64.135-.954l11.566-4.458c.538-.196 1.006.128.832.941z"/>
                    </svg>
                    Join our Telegram Channel
                  </h4>
                  <p className="text-sm text-gray-700 dark:text-gray-300 mt-2">
                    Get real-time updates and insights directly in Telegram. Note that AI reports are truncated in Telegram chats - visit the "Intelligence Reports" section on this dashboard to view full reports.
                  </p>
                  <Button 
                    className="mt-3 bg-blue-500 hover:bg-blue-600"
                    onClick={() => window.open('https://t.me/watchfuleye41', '_blank')}
                  >
                    <svg className="w-4 h-4 mr-2" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221l-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.446 1.394c-.14.18-.357.295-.6.295-.002 0-.003 0-.005 0l.213-3.054 5.56-5.022c.24-.213-.054-.334-.373-.121l-6.869 4.326-2.96-.924c-.64-.203-.658-.64.135-.954l11.566-4.458c.538-.196 1.006.128.832.941z"/>
                    </svg>
                    Join Telegram Channel
                  </Button>
                </div>
                
                <div className="mt-6 bg-gray-50 dark:bg-slate-700/50 p-4 rounded-lg">
                  <h4 className="font-medium mb-2">Getting Started</h4>
                  <ol className="list-decimal pl-5 space-y-2 text-sm">
                    <li>Browse the latest news articles in the main feed</li>
                    <li>Click on any article to view its AI analysis</li>
                    <li>Check the "Intelligence Reports" section for complete AI intelligence reports</li>
                    <li>Use the bookmark icon to save articles to your profile</li>
                    <li>Join our Telegram channel for mobile updates</li>
                  </ol>
                </div>
              </div>
              
              <div className="mt-6 flex justify-end">
                <Button 
                  onClick={onClose}
                  className="px-4 py-2"
                >
                  Get Started
                </Button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// Edit Profile Modal Component
function EditProfileModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const auth = useAuth();
  const [username, setUsername] = useState(auth.user?.username || '');
  const [fullName, setFullName] = useState(auth.user?.full_name || '');
  const [email, setEmail] = useState(auth.user?.email || '');
  const [profilePicture, setProfilePicture] = useState<File | null>(null);
  const [profilePicturePreview, setProfilePicturePreview] = useState(auth.user?.profile_picture || '');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [usernameAvailable, setUsernameAvailable] = useState(true);
  const [isCheckingUsername, setIsCheckingUsername] = useState(false);
  const usernameTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen && auth.user) {
      setUsername(auth.user.username || '');
      setFullName(auth.user.full_name || '');
      setEmail(auth.user.email || '');
      setProfilePicturePreview(auth.user.profile_picture || '');
      setProfilePicture(null);
      setError(null);
      setUsernameAvailable(true);
    }
  }, [isOpen, auth.user]);

  // Check username availability with debounce
  useEffect(() => {
    // If username is unchanged, it's available
    if (username === auth.user?.username) {
      setUsernameAvailable(true);
      return;
    }

    // Don't check if username is too short
    if (username.trim().length < 3) {
      return;
    }

    // Clear existing timeout
    if (usernameTimeoutRef.current) {
      clearTimeout(usernameTimeoutRef.current);
    }

    // Set checking state and create new timeout
    setIsCheckingUsername(true);
    usernameTimeoutRef.current = setTimeout(async () => {
      try {
        console.log('Checking username availability for:', username);
        const available = await auth.checkUsernameAvailability(username);
        console.log('Username availability result:', available);
        setUsernameAvailable(available);
      } catch (error) {
        console.error('Error checking username:', error);
        // Default to available to prevent blocking valid usernames on error
        setUsernameAvailable(true);
      } finally {
        setIsCheckingUsername(false);
      }
    }, 500);

    return () => {
      if (usernameTimeoutRef.current) {
        clearTimeout(usernameTimeoutRef.current);
      }
    };
  }, [username, auth]);

  const handleProfilePictureChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setProfilePicture(file);
      setProfilePicturePreview(URL.createObjectURL(file));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      // Validate username availability on client side first
      if (username !== auth.user?.username && !usernameAvailable) {
        setError('Username is already taken');
        setIsSubmitting(false);
        return;
      }

      // Update profile information
      const profileData = {
        username: username !== auth.user?.username ? username : undefined,
        full_name: fullName !== auth.user?.full_name ? fullName : undefined,
        email: email !== auth.user?.email ? email : undefined
      };

      // Only update if something changed
      if (Object.values(profileData).some(value => value !== undefined)) {
        try {
          await auth.updateProfile(profileData);
        } catch (updateError: any) {
          // Set the error from the server response
          setError(updateError.message || 'Failed to update profile');
          setIsSubmitting(false);
          return;
        }
      }

      // Upload profile picture if selected
      if (profilePicture) {
        const success = await auth.updateProfilePicture(profilePicture);
        if (!success) {
          setError('Failed to update profile picture');
          setIsSubmitting(false);
          return;
        }
      }

      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/50 backdrop-blur z-[9999] flex items-center justify-center p-4 overflow-hidden"
        onClick={onClose}
      >
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
          className="bg-white dark:bg-gray-800 rounded-xl w-full max-w-md max-h-[90vh] overflow-y-auto"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">Edit Profile</h2>
              <Button variant="ghost" size="icon" onClick={onClose} className="text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100">
                <X className="w-5 h-5" />
              </Button>
            </div>

            {error && (
              <div className="mb-4 p-3 bg-red-100 dark:bg-red-900/20 border border-red-300 dark:border-red-600 rounded-lg">
                <p className="text-red-700 dark:text-red-400 text-sm">{error}</p>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Profile Picture */}
              <div className="flex flex-col items-center">
                <div className="relative mb-4">
                  <div className="w-24 h-24 rounded-full overflow-hidden bg-gray-200 dark:bg-gray-700">
                    {profilePicturePreview ? (
                      <img 
                        src={profilePicturePreview} 
                        alt="Profile" 
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-gray-400">
                        <User className="w-12 h-12" />
                      </div>
                    )}
                  </div>
                  <label className="absolute bottom-0 right-0 bg-blue-500 hover:bg-blue-600 rounded-full p-1.5 cursor-pointer">
                    <input 
                      type="file" 
                      accept="image/*"
                      className="hidden" 
                      onChange={handleProfilePictureChange}
                    />
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"></path>
                      <circle cx="9" cy="7" r="4"></circle>
                      <line x1="17" y1="8" x2="22" y2="8"></line>
                      <line x1="19.5" y1="5.5" x2="19.5" y2="10.5"></line>
                    </svg>
                  </label>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  Click the icon to upload a new profile picture
                </p>
              </div>

              {/* Username */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Username
                </label>
                <div className="relative">
                  <Input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className={`${!usernameAvailable && username !== auth.user?.username ? 'border-red-500 focus:ring-red-500' : ''}`}
                    disabled={isSubmitting}
                  />
                  {isCheckingUsername && (
                    <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                      <Loader2 className="w-4 h-4 animate-spin text-gray-400" />
                    </div>
                  )}
                </div>
                {!usernameAvailable && username !== auth.user?.username && (
                  <p className="mt-1 text-xs text-red-500">Username is already taken</p>
                )}
              </div>

              {/* Full Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Full Name
                </label>
                <Input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  disabled={isSubmitting}
                />
              </div>

              {/* Email */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Email
                </label>
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={isSubmitting}
                />
              </div>

              <div className="flex gap-3 pt-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={onClose}
                  disabled={isSubmitting}
                  className="flex-1"
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={isSubmitting || (!usernameAvailable && username !== auth.user?.username)}
                  className="flex-1"
                >
                  {isSubmitting ? (
                    <div className="flex items-center gap-2">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Saving...
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <Save className="w-4 h-4" />
                      Save Changes
                    </div>
                  )}
                </Button>
              </div>
            </form>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

// Profile Page Component
function ProfilePage({ onBack }: { onBack: () => void }) {
  const [savedArticles, setSavedArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedArticle, setSelectedArticle] = useState<Article | null>(null);
  const [showAnalysis, setShowAnalysis] = useState(false);
  const [activeTab, setActiveTab] = useState('articles');
  const [showEditProfile, setShowEditProfile] = useState(false);
  const auth = useAuth();
  const isAdmin = auth.user?.role === 'admin';

  useEffect(() => {
    const fetchSavedArticles = async () => {
      try {
        const articles = await authAPI.getSavedArticles();
        setSavedArticles(articles);
      } catch (error) {
        console.error('Failed to fetch saved articles:', error);
    } finally {
      setLoading(false);
    }
  };

    fetchSavedArticles();
  }, []);

  const handleUnsaveArticle = async (articleId: string) => {
    const success = await auth.unsaveArticle(articleId);
    if (success) {
      setSavedArticles(prev => prev.filter(article => article.id !== articleId));
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-900 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-blue-500" />
          <p className="text-slate-600 dark:text-slate-400">Loading profile...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <motion.div 
          className="flex items-center justify-between"
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <div>
            <Button 
              variant="ghost" 
              onClick={onBack}
              className="mb-4"
            >
              ← Back to Dashboard
            </Button>
            <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-100">Profile</h1>
            <p className="text-slate-600 dark:text-slate-400">Manage your account and saved articles</p>
          </div>
        </motion.div>

        {/* User Info */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
        >
          <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-slate-900 dark:text-slate-100">Account Information</CardTitle>
              <Button 
                variant="outline" 
                size="sm"
                onClick={() => setShowEditProfile(true)}
                className="flex items-center gap-2"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17 3a2.85 2.85 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path>
                </svg>
                Edit Profile
              </Button>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col sm:flex-row gap-6 items-start">
                <div className="flex-shrink-0">
                  <div className="w-24 h-24 rounded-full overflow-hidden bg-gray-200 dark:bg-gray-700">
                    {auth.user?.profile_picture ? (
                      <img 
                        src={auth.user.profile_picture} 
                        alt="Profile" 
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-gray-400">
                        <User className="w-12 h-12" />
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex-grow grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm text-slate-600 dark:text-slate-400">Username</label>
                    <p className="font-medium text-slate-900 dark:text-slate-100">{auth.user?.username}</p>
                  </div>
                  <div>
                    <label className="text-sm text-slate-600 dark:text-slate-400">Email</label>
                    <p className="font-medium text-slate-900 dark:text-slate-100">{auth.user?.email}</p>
                  </div>
                  <div>
                    <label className="text-sm text-slate-600 dark:text-slate-400">Full Name</label>
                    <p className="font-medium text-slate-900 dark:text-slate-100">{auth.user?.full_name || 'Not set'}</p>
                  </div>
                  <div>
                    <label className="text-sm text-slate-600 dark:text-slate-400">Role</label>
                    <Badge variant={auth.user?.role === 'admin' ? 'default' : 'secondary'}>
                      {auth.user?.role}
                    </Badge>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Tabs for admin users */}
        {isAdmin && (
          <div className="flex border-b border-gray-200 dark:border-gray-700">
            <button
              className={`py-2 px-4 text-sm font-medium ${
                activeTab === 'articles' 
                  ? 'border-b-2 border-blue-500 text-blue-600 dark:text-blue-400' 
                  : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
              }`}
              onClick={() => setActiveTab('articles')}
            >
              Saved Articles
            </button>
            <button
              className={`py-2 px-4 text-sm font-medium ${
                activeTab === 'admin' 
                  ? 'border-b-2 border-blue-500 text-blue-600 dark:text-blue-400' 
                  : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
              }`}
              onClick={() => setActiveTab('admin')}
            >
              Admin Dashboard
            </button>
          </div>
        )}

        {/* Admin Dashboard for admin users */}
        {isAdmin && activeTab === 'admin' && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <AdminDashboard />
          </motion.div>
        )}

        {/* Saved Articles */}
        {(!isAdmin || activeTab === 'articles') && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
            <Card className="bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700">
              <CardHeader>
                <CardTitle className="text-slate-900 dark:text-slate-100">
                  Saved Articles ({savedArticles.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                {savedArticles.length === 0 ? (
                  <div className="text-center py-8 text-slate-500 dark:text-slate-400">
                    <BookmarkIcon className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p className="text-sm">No saved articles yet</p>
                    <p className="text-xs mt-1">Start saving articles from the dashboard</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {savedArticles.map((article, index) => (
                      <motion.div
                        key={article.id}
                        className="flex items-start gap-4 p-4 rounded-lg bg-slate-50 dark:bg-slate-700/50 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.3, delay: index * 0.1 }}
                      >
                        <div className="flex-1 cursor-pointer" onClick={() => {
                          setSelectedArticle(article);
                          setShowAnalysis(true);
                        }}>
                          <h4 className="font-medium text-slate-900 dark:text-slate-100 hover:text-blue-600 dark:hover:text-blue-400 transition-colors">{article.title}</h4>
                          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1 line-clamp-2">{article.description}</p>
                          <div className="flex items-center gap-2 mt-2">
                            <Badge variant="secondary" className="text-xs">{article.category}</Badge>
                            <Badge 
                              variant={getSentimentLabel(article.sentiment_score) === 'positive' ? 'default' : getSentimentLabel(article.sentiment_score) === 'negative' ? 'destructive' : 'secondary'}
                              className="text-xs"
                            >
                              {getSentimentLabel(article.sentiment_score)}
                            </Badge>
                            <span className="text-xs text-slate-500">{calculateTimeAgo(article.created_at)}</span>
                            <span className="text-xs text-slate-500">•</span>
                            <span className="text-xs text-slate-500">{article.source}</span>
                            {article.saved_at && (
                              <>
                                <span className="text-xs text-slate-500">•</span>
                                <span className="text-xs text-slate-500">Saved {calculateTimeAgo(article.saved_at)}</span>
                              </>
                            )}
                          </div>
                          {article.notes && (
                            <div className="mt-2 p-1 sm:p-2 bg-blue-50 dark:bg-blue-900/20 rounded text-[10px] sm:text-xs text-slate-700 dark:text-slate-300">
                              <strong>Notes:</strong> {article.notes}
                            </div>
                          )}
                        </div>
                        <div className="flex flex-col gap-2">
                          <Button 
                            variant="ghost" 
                            size="icon"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleUnsaveArticle(article.id);
                            }}
                            className="text-red-500 hover:text-red-700"
                          >
                            <X className="w-4 h-4" />
                          </Button>
                          <Button 
                            variant="ghost" 
                            size="icon"
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedArticle(article);
                              setShowAnalysis(true);
                            }}
                          >
                            <Brain className="w-4 h-4" />
                          </Button>
                          {article.url && (
                            <Button 
                              variant="ghost" 
                              size="icon"
                              onClick={(e) => {
                                e.stopPropagation();
                                window.open(article.url, '_blank');
                              }}
                            >
                              <ExternalLink className="w-4 h-4" />
                            </Button>
                          )}
                        </div>
                      </motion.div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* AI Analysis Modal */}
        <AIAnalysisModal 
          article={selectedArticle}
          isOpen={showAnalysis}
          onClose={() => setShowAnalysis(false)}
        />

        {/* Edit Profile Modal */}
        <EditProfileModal
          isOpen={showEditProfile}
          onClose={() => setShowEditProfile(false)}
        />
      </div>
    </div>
  );
}

// Admin Dashboard Component
function AdminDashboard() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('dashboard');

  useEffect(() => {
    const fetchAdminStats = async () => {
      try {
        setLoading(true);
        const response = await axios.get(`${API_BASE_URL}/admin/user-stats`);
        if (response.data.success) {
          setStats(response.data.data);
        } else {
          setError('Failed to load admin statistics');
        }
      } catch (err) {
        console.error('Error fetching admin stats:', err);
        setError(err instanceof Error ? err.message : 'Failed to load admin statistics');
      } finally {
        setLoading(false);
      }
    };

    fetchAdminStats();
  }, []);

  if (loading && !stats && activeTab === 'dashboard') {
    return (
      <div className="min-h-[300px] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  if (error && !stats && activeTab === 'dashboard') {
    return (
      <div className="min-h-[300px] flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-500 mb-2">{error}</p>
          <Button variant="outline" onClick={() => window.location.reload()}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Retry
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Admin tabs */}
      <div className="flex border-b border-gray-200 dark:border-gray-700">
        <button
          className={`py-2 px-4 text-sm font-medium ${
            activeTab === 'dashboard' 
              ? 'border-b-2 border-blue-500 text-blue-600 dark:text-blue-400' 
              : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
          }`}
          onClick={() => setActiveTab('dashboard')}
        >
          Dashboard
        </button>
        <button
          className={`py-2 px-4 text-sm font-medium ${
            activeTab === 'users' 
              ? 'border-b-2 border-blue-500 text-blue-600 dark:text-blue-400' 
              : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
          }`}
          onClick={() => setActiveTab('users')}
        >
          User Management
        </button>
      </div>

      {/* Admin dashboard content */}
      {activeTab === 'dashboard' && stats && (
        <>
          {/* Summary Stats */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <Card className="bg-white dark:bg-gray-800">
              <CardContent className="p-4 text-center">
                <p className="text-2xl font-bold text-blue-600">{stats.total_users}</p>
                <p className="text-sm text-gray-600 dark:text-gray-400">Total Users</p>
              </CardContent>
            </Card>
            <Card className="bg-white dark:bg-gray-800">
              <CardContent className="p-4 text-center">
                <p className="text-2xl font-bold text-green-600">{stats.active_users_7d}</p>
                <p className="text-sm text-gray-600 dark:text-gray-400">Active Users (7d)</p>
              </CardContent>
            </Card>
            <Card className="bg-white dark:bg-gray-800">
              <CardContent className="p-4 text-center">
                <p className="text-2xl font-bold text-purple-600">{stats.active_sessions}</p>
                <p className="text-sm text-gray-600 dark:text-gray-400">Active Sessions</p>
              </CardContent>
            </Card>
            <Card className="bg-white dark:bg-gray-800">
              <CardContent className="p-4 text-center">
                <p className="text-2xl font-bold text-amber-600">{stats.new_users_24h}</p>
                <p className="text-sm text-gray-600 dark:text-gray-400">New Users (24h)</p>
              </CardContent>
            </Card>
          </div>

          {/* New Signups Chart */}
          <Card className="bg-white dark:bg-gray-800">
            <CardHeader>
              <CardTitle>User Registrations (Last 30 Days)</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-64 flex items-end justify-between gap-1">
                {stats.daily_signups && stats.daily_signups.length > 0 ? (
                  stats.daily_signups.map((day: any, index: number) => {
                    const maxCount = Math.max(...stats.daily_signups.map((d: any) => d.count));
                    const height = Math.max((day.count / (maxCount || 1)) * 100, 5);
                    return (
                      <div key={index} className="flex flex-col items-center flex-1">
                        <div 
                          className="bg-blue-500 w-full rounded-t" 
                          style={{ height: `${height}%` }}
                          title={`${day.date}: ${day.count} users`}
                        />
                        {index % 5 === 0 && (
                          <span className="text-xs mt-1 text-gray-500 rotate-45 origin-left">
                            {day.date.split('-')[2]}
                          </span>
                        )}
                      </div>
                    );
                  })
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <p className="text-gray-500">No signup data available</p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* User Roles */}
          <Card className="bg-white dark:bg-gray-800">
            <CardHeader>
              <CardTitle>Users by Role</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {stats.users_by_role && Object.keys(stats.users_by_role).length > 0 ? (
                  Object.entries(stats.users_by_role).map(([role, count]: [string, any]) => (
                    <div key={role} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className={`w-3 h-3 rounded-full ${
                          role === 'admin' ? 'bg-red-500' : 
                          role === 'moderator' ? 'bg-yellow-500' : 
                          'bg-green-500'
                        }`} />
                        <span className="capitalize">{role}</span>
                      </div>
                      <span className="font-bold">{count}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-gray-500">No role data available</p>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Active Sessions */}
          <Card className="bg-white dark:bg-gray-800">
            <CardHeader>
              <CardTitle>Recent Active Sessions</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="max-h-[300px] overflow-y-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 dark:bg-gray-700">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Username</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Role</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Login Time</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">Expires</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-600">
                    {stats.recent_sessions && stats.recent_sessions.length > 0 ? (
                      stats.recent_sessions.map((session: any, index: number) => (
                        <tr key={index} className={index % 2 === 0 ? 'bg-white dark:bg-gray-800' : 'bg-gray-50 dark:bg-gray-700/50'}>
                          <td className="px-4 py-2 text-sm text-gray-900 dark:text-gray-100">{session.username}</td>
                          <td className="px-4 py-2 text-sm">
                            <Badge variant={session.role === 'admin' ? 'destructive' : 'default'}>
                              {session.role}
                            </Badge>
                          </td>
                          <td className="px-4 py-2 text-sm text-gray-500 dark:text-gray-400">{calculateTimeAgo(session.created_at)}</td>
                          <td className="px-4 py-2 text-sm text-gray-500 dark:text-gray-400">
                            {new Date(session.expires_at) > new Date() 
                              ? `Expires in ${calculateTimeAgo(session.expires_at)}`
                              : 'Expired'}
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={4} className="px-4 py-8 text-center text-gray-500">
                          No active sessions
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
          
          <div className="text-xs text-gray-500 text-center">
            Last updated: {new Date(stats.timestamp).toLocaleString()}
          </div>
        </>
      )}

      {/* User management content */}
      {activeTab === 'users' && (
        <UserManagement />
      )}
    </div>
  );
}

// User Management Component for Admin Dashboard
function UserManagement() {
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedUser, setSelectedUser] = useState<any>(null);
  const [showUserDetails, setShowUserDetails] = useState(false);

  useEffect(() => {
    const fetchUsers = async () => {
      try {
        setLoading(true);
        const response = await axios.get(`${API_BASE_URL}/admin/users`);
        if (response.data.success) {
          setUsers(response.data.data);
        } else {
          setError('Failed to load users');
        }
      } catch (err) {
        console.error('Error fetching users:', err);
        setError(err instanceof Error ? err.message : 'Failed to load users');
      } finally {
        setLoading(false);
      }
    };

    fetchUsers();
  }, []);

  const handleViewUser = async (userId: number) => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_BASE_URL}/admin/users/${userId}`);
      if (response.data.success) {
        setSelectedUser(response.data.data);
        setShowUserDetails(true);
      } else {
        setError('Failed to load user details');
      }
    } catch (err) {
      console.error('Error fetching user details:', err);
      setError(err instanceof Error ? err.message : 'Failed to load user details');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleUserStatus = async (userId: number, currentStatus: boolean) => {
    try {
      const response = await axios.post(`${API_BASE_URL}/admin/users/${userId}/status`, {
        is_active: !currentStatus
      });
      
      if (response.data.success) {
        // Update the users list with the new status
        setUsers(users.map(user => 
          user.id === userId ? { ...user, is_active: !currentStatus } : user
        ));
        
        // Update the selected user if viewing details
        if (selectedUser && selectedUser.id === userId) {
          setSelectedUser({ ...selectedUser, is_active: !currentStatus });
        }
      } else {
        setError('Failed to update user status');
      }
    } catch (err) {
      console.error('Error updating user status:', err);
      setError(err instanceof Error ? err.message : 'Failed to update user status');
    }
  };

  if (loading && users.length === 0) {
    return (
      <div className="min-h-[300px] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  if (error && users.length === 0) {
    return (
      <div className="min-h-[300px] flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-500 mb-2">{error}</p>
          <Button variant="outline" onClick={() => window.location.reload()}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Retry
          </Button>
        </div>
      </div>
    );
  }

  // User Details Modal
  const UserDetailsModal = () => {
    if (!selectedUser) return null;
    
    return (
      <AnimatePresence>
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 bg-black/50 backdrop-blur z-[9999] flex items-center justify-center p-4 overflow-hidden"
          onClick={() => setShowUserDetails(false)}
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            className="bg-white dark:bg-gray-800 rounded-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center text-white ${
                    selectedUser.role === 'admin' ? 'bg-red-500' : 'bg-blue-500'
                  }`}>
                    {selectedUser.username.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">{selectedUser.username}</h2>
                    <p className="text-sm text-gray-500 dark:text-gray-400">{selectedUser.email}</p>
                  </div>
                </div>
                <Button variant="ghost" size="icon" onClick={() => setShowUserDetails(false)} className="text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100">
                  <X className="w-5 h-5" />
                </Button>
              </div>

              <div className="grid grid-cols-2 gap-4 mb-6">
                <div>
                  <p className="text-sm text-gray-500">Full Name</p>
                  <p>{selectedUser.full_name || 'Not set'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Role</p>
                  <Badge variant={selectedUser.role === 'admin' ? 'destructive' : 'default'}>
                    {selectedUser.role}
                  </Badge>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Status</p>
                  <Badge variant={selectedUser.is_active ? 'default' : 'secondary'}>
                    {selectedUser.is_active ? 'Active' : 'Inactive'}
                  </Badge>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Created</p>
                  <p>{new Date(selectedUser.created_at).toLocaleString()}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Last Login</p>
                  <p>{selectedUser.last_login ? new Date(selectedUser.last_login).toLocaleString() : 'Never'}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Login Count</p>
                  <p>{selectedUser.login_count}</p>
                </div>
              </div>

              {/* User actions */}
              <div className="flex gap-3 mb-6">
                <Button 
                  variant={selectedUser.is_active ? 'destructive' : 'default'}
                  onClick={() => handleToggleUserStatus(selectedUser.id, selectedUser.is_active)}
                  disabled={selectedUser.role === 'admin'}
                >
                  {selectedUser.is_active ? 'Deactivate User' : 'Activate User'}
                </Button>
              </div>

              {/* User sessions */}
              <div className="mb-6">
                <h3 className="text-lg font-bold mb-3">Session History</h3>
                <div className="max-h-[200px] overflow-y-auto">
                  <table className="w-full">
                    <thead className="bg-gray-50 dark:bg-gray-700">
                      <tr>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300">Session ID</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300">Created</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300">Expires</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 dark:divide-gray-600">
                      {selectedUser.sessions && selectedUser.sessions.length > 0 ? (
                        selectedUser.sessions.map((session: any, index: number) => (
                          <tr key={index} className={index % 2 === 0 ? 'bg-white dark:bg-gray-800' : 'bg-gray-50 dark:bg-gray-700/50'}>
                            <td className="px-4 py-2 text-sm text-gray-900 dark:text-gray-100">{session.id}</td>
                            <td className="px-4 py-2 text-sm text-gray-500 dark:text-gray-400">
                              {new Date(session.created_at).toLocaleString()}
                            </td>
                            <td className="px-4 py-2 text-sm text-gray-500 dark:text-gray-400">
                              {new Date(session.expires_at).toLocaleString()}
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={3} className="px-4 py-8 text-center text-gray-500">
                            No session history
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Saved articles */}
              <div>
                <h3 className="text-lg font-bold mb-3">Saved Articles</h3>
                <div className="max-h-[200px] overflow-y-auto">
                  {selectedUser.saved_articles && selectedUser.saved_articles.length > 0 ? (
                    <div className="space-y-2">
                      {selectedUser.saved_articles.map((article: any, index: number) => (
                        <div key={index} className="p-2 rounded bg-gray-50 dark:bg-gray-700/50">
                          <p className="text-sm font-medium">{article.title}</p>
                          <p className="text-xs text-gray-500">
                            Saved on {new Date(article.saved_at).toLocaleString()}
                          </p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="py-8 text-center text-gray-500">
                      No saved articles
                    </div>
                  )}
                </div>
              </div>
            </div>
          </motion.div>
        </motion.div>
      </AnimatePresence>
    );
  };

  return (
    <div>
      <Card className="bg-white dark:bg-gray-800 mb-6">
        <CardHeader>
          <CardTitle>User Management</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="max-h-[500px] overflow-y-auto">
            <table className="w-full">
              <thead className="bg-gray-50 dark:bg-gray-700 sticky top-0">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300">Username</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300">Email</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300">Role</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300">Status</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300">Sessions</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-600">
                {users.map((user, index) => (
                  <tr key={user.id} className={index % 2 === 0 ? 'bg-white dark:bg-gray-800' : 'bg-gray-50 dark:bg-gray-700/50'}>
                    <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100">
                      <div className="flex items-center gap-2">
                        <div className={`w-6 h-6 rounded-full flex items-center justify-center text-white text-xs ${
                          user.role === 'admin' ? 'bg-red-500' : 'bg-blue-500'
                        }`}>
                          {user.username.charAt(0).toUpperCase()}
                        </div>
                        {user.username}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">{user.email}</td>
                    <td className="px-4 py-3 text-sm">
                      <Badge variant={user.role === 'admin' ? 'destructive' : 'default'}>
                        {user.role}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <Badge variant={user.is_active ? 'default' : 'secondary'}>
                        {user.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                      {user.active_sessions}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      <div className="flex gap-2">
                        <Button variant="ghost" size="sm" onClick={() => handleViewUser(user.id)}>
                          <Eye className="w-4 h-4 mr-1" />
                          View
                        </Button>
                        {user.role !== 'admin' && (
                          <Button 
                            variant={user.is_active ? 'destructive' : 'default'} 
                            size="sm"
                            onClick={() => handleToggleUserStatus(user.id, user.is_active)}
                          >
                            {user.is_active ? 'Deactivate' : 'Activate'}
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                      No users found
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* User details modal */}
      {showUserDetails && <UserDetailsModal />}
    </div>
  );
}

// Main Dashboard Component
function WatchfulEyeDashboard() {
  const [showProfile, setShowProfile] = useState(false);
  const [showWelcomeModal, setShowWelcomeModal] = useState(false);
  const auth = useAuth();

  // Check if user should see welcome modal on first login or after registration
  useEffect(() => {
    // Check for the flag set during registration
    const hasSeenWelcome = localStorage.getItem('hasSeenWelcome');
    
    // If user is authenticated and either hasSeenWelcome is 'false' (new registration) 
    // or null/undefined (first login), show the welcome modal
    if (auth.user && hasSeenWelcome !== 'true') {
      // Set a small delay to ensure the UI is fully rendered
      setTimeout(() => {
        setShowWelcomeModal(true);
        // Mark as seen after showing
        localStorage.setItem('hasSeenWelcome', 'true');
      }, 500);
    }
  }, [auth.user]);

  // Show loading state while checking authentication
  if (auth.loading) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-900 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-blue-500" />
          <p className="text-slate-600 dark:text-slate-400">Loading...</p>
        </div>
      </div>
    );
  }

  // Show login page if not authenticated
  if (!auth.user) {
    return <LoginPage onLogin={() => {}} />;
  }

  // Show profile page if requested
  if (showProfile) {
    return (
      <>
        <ProfilePage onBack={() => setShowProfile(false)} />
        <WelcomeModal isOpen={showWelcomeModal} onClose={() => setShowWelcomeModal(false)} />
      </>
    );
  }

  // Show main dashboard
  return (
    <>
      <MinimalistDashboard 
        onShowProfile={() => setShowProfile(true)} 
        showWelcomeOnLoad={showWelcomeModal}
        onWelcomeModalClose={() => setShowWelcomeModal(false)}
      />
    </>
  );
}

export default function Dashboard() {
  return (
    <AuthProvider>
      <WatchfulEyeDashboard />
    </AuthProvider>
  );
} 