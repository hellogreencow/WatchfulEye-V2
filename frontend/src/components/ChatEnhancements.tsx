import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Copy, Share2, Download, MoreVertical, Sparkles, TrendingUp, Clock, Globe, Shield, DollarSign, ChevronRight } from 'lucide-react';
import { cn } from '../lib/utils';

interface MessageActionsProps {
  content: string;
  sources?: any[];
  messageId: string | number;
  onExport?: (format: 'markdown' | 'pdf') => void;
}

export function MessageActions({ content, sources, messageId, onExport }: MessageActionsProps) {
  const [copied, setCopied] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  
  const handleCopy = () => {
    let textToCopy = content;
    if (sources && sources.length > 0) {
      textToCopy += '\n\nSources:\n';
      sources.forEach((s, i) => {
        textToCopy += `[${i + 1}] ${s.title} - ${s.source}\n`;
      });
    }
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  
  const handleShare = () => {
    if (navigator && navigator.share) {
      navigator.share({
        title: 'WatchfulEye Analysis',
        text: content,
      }).catch(() => {
        // Share failed or cancelled
      });
    }
  };
  
  return (
    <div className="opacity-0 group-hover:opacity-100 absolute top-2 right-2 flex items-center gap-1 transition-opacity">
      <button
        onClick={handleCopy}
        className="p-1.5 hover:bg-white/80 dark:hover:bg-slate-800/80 rounded-lg transition-colors"
        title="Copy"
      >
        {copied ? (
          <motion.div
            initial={{ scale: 0.5 }}
            animate={{ scale: 1 }}
            className="text-green-600 text-xs font-bold"
          >
            ✓
          </motion.div>
        ) : (
          <Copy className="w-3.5 h-3.5 text-slate-500" />
        )}
      </button>
      
      {(typeof navigator !== 'undefined' && navigator.share) && (
        <button
          onClick={handleShare}
          className="p-1.5 hover:bg-white/80 dark:hover:bg-slate-800/80 rounded-lg transition-colors"
          title="Share"
        >
          <Share2 className="w-3.5 h-3.5 text-slate-500" />
        </button>
      )}
      
      <div className="relative">
        <button
          onClick={() => setShowMenu(!showMenu)}
          className="p-1.5 hover:bg-white/80 dark:hover:bg-slate-800/80 rounded-lg transition-colors"
          title="More options"
        >
          <MoreVertical className="w-3.5 h-3.5 text-slate-500" />
        </button>
        
        <AnimatePresence>
          {showMenu && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: -5 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: -5 }}
              className="absolute right-0 top-full mt-1 w-40 bg-white dark:bg-slate-800 rounded-lg shadow-lg border border-slate-200 dark:border-slate-700 py-1 z-50"
            >
              <button
                onClick={() => {
                  onExport?.('markdown');
                  setShowMenu(false);
                }}
                className="w-full px-3 py-1.5 text-left text-xs hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center gap-2"
              >
                <Download className="w-3 h-3" />
                Export as Markdown
              </button>
              <button
                onClick={() => {
                  onExport?.('pdf');
                  setShowMenu(false);
                }}
                className="w-full px-3 py-1.5 text-left text-xs hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center gap-2"
              >
                <Download className="w-3 h-3" />
                Export as PDF
              </button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

interface SmartSuggestionsProps {
  onSelect: (suggestion: string) => void;
  context?: {
    lastTopic?: string;
    recentCategories?: string[];
    timeRange?: string;
  };
}

export function SmartSuggestions({ onSelect, context }: SmartSuggestionsProps) {
  const suggestions = [
    {
      icon: TrendingUp,
      text: "What's trending today?",
      color: 'text-green-600',
      bgColor: 'bg-green-50 dark:bg-green-900/20',
      borderColor: 'border-green-200 dark:border-green-800',
    },
    {
      icon: Clock,
      text: "Changes in last 24h",
      color: 'text-blue-600',
      bgColor: 'bg-blue-50 dark:bg-blue-900/20',
      borderColor: 'border-blue-200 dark:border-blue-800',
    },
    {
      icon: Globe,
      text: "Geopolitical analysis",
      color: 'text-purple-600',
      bgColor: 'bg-purple-50 dark:bg-purple-900/20',
      borderColor: 'border-purple-200 dark:border-purple-800',
    },
    {
      icon: DollarSign,
      text: "Market implications",
      color: 'text-amber-600',
      bgColor: 'bg-amber-50 dark:bg-amber-900/20',
      borderColor: 'border-amber-200 dark:border-amber-800',
    },
  ];
  
  // Add context-aware suggestions
  if (context?.lastTopic) {
    suggestions.unshift({
      icon: Sparkles,
      text: `More on ${context.lastTopic}`,
      color: 'text-indigo-600',
      bgColor: 'bg-indigo-50 dark:bg-indigo-900/20',
      borderColor: 'border-indigo-200 dark:border-indigo-800',
    });
  }
  
  return (
    <div className="flex gap-2 px-3 pb-2 overflow-x-auto scrollbar-hide">
      {suggestions.slice(0, 4).map((suggestion, idx) => {
        const Icon = suggestion.icon;
        return (
          <button
            key={idx}
            onClick={() => onSelect(suggestion.text)}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-all hover:scale-105 border",
              suggestion.bgColor,
              suggestion.borderColor
            )}
          >
            <Icon className={cn("w-3.5 h-3.5", suggestion.color)} />
            <span className={suggestion.color}>{suggestion.text}</span>
          </button>
        );
      })}
    </div>
  );
}

interface InsightBadgeProps {
  type: 'trend' | 'alert' | 'opportunity' | 'risk';
  text: string;
  onClick?: () => void;
}

export function InsightBadge({ type, text, onClick }: InsightBadgeProps) {
  const configs = {
    trend: {
      icon: TrendingUp,
      color: 'text-green-600',
      bgColor: 'bg-green-50 dark:bg-green-900/20',
      borderColor: 'border-green-200 dark:border-green-800',
    },
    alert: {
      icon: Shield,
      color: 'text-red-600',
      bgColor: 'bg-red-50 dark:bg-red-900/20',
      borderColor: 'border-red-200 dark:border-red-800',
    },
    opportunity: {
      icon: Sparkles,
      color: 'text-blue-600',
      bgColor: 'bg-blue-50 dark:bg-blue-900/20',
      borderColor: 'border-blue-200 dark:border-blue-800',
    },
    risk: {
      icon: Shield,
      color: 'text-amber-600',
      bgColor: 'bg-amber-50 dark:bg-amber-900/20',
      borderColor: 'border-amber-200 dark:border-amber-800',
    },
  };
  
  const config = configs[type];
  const Icon = config.icon;
  
  return (
    <motion.button
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-medium transition-all hover:scale-105",
        config.bgColor,
        config.borderColor
      )}
    >
      <Icon className={cn("w-3.5 h-3.5", config.color)} />
      <span className={config.color}>{text}</span>
      {onClick && <ChevronRight className={cn("w-3 h-3", config.color)} />}
    </motion.button>
  );
}

interface ConversationExportProps {
  messages: any[];
  format: 'markdown' | 'pdf';
}

export function exportConversation({ messages, format }: ConversationExportProps): void {
  if (format === 'markdown') {
    const markdown = messages.map(m => {
      let content = `## ${m.role === 'user' ? 'You' : 'WatchfulEye'}\n\n${m.content}\n`;
      
      if (m.metadata?.sources && m.metadata.sources.length > 0) {
        content += '\n### Sources\n';
        m.metadata.sources.forEach((s: any, i: number) => {
          content += `${i + 1}. [${s.title}](${s.url}) - ${s.source}\n`;
        });
      }
      
      return content;
    }).join('\n---\n\n');
    
    const blob = new Blob([markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `watchfuleye-chat-${new Date().toISOString().split('T')[0]}.md`;
    a.click();
    URL.revokeObjectURL(url);
  } else if (format === 'pdf') {
    // For PDF export, we'd need a library like jsPDF
    // For now, just export as HTML that can be printed to PDF
    const html = `
      <!DOCTYPE html>
      <html>
      <head>
        <title>WatchfulEye Chat Export</title>
        <style>
          body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 40px; }
          .message { margin-bottom: 30px; }
          .role { font-weight: bold; color: #1e40af; margin-bottom: 10px; }
          .content { line-height: 1.6; color: #334155; }
          .sources { margin-top: 15px; padding: 10px; background: #f1f5f9; border-radius: 8px; }
          .source { margin: 5px 0; }
          .source a { color: #2563eb; text-decoration: none; }
          hr { border: none; border-top: 1px solid #e2e8f0; margin: 30px 0; }
        </style>
      </head>
      <body>
        <h1>WatchfulEye Intelligence Analysis</h1>
        <p>Exported on ${new Date().toLocaleDateString()}</p>
        <hr>
        ${messages.map(m => `
          <div class="message">
            <div class="role">${m.role === 'user' ? 'You' : 'WatchfulEye'}</div>
            <div class="content">${m.content.replace(/\n/g, '<br>')}</div>
            ${m.metadata?.sources && m.metadata.sources.length > 0 ? `
              <div class="sources">
                <strong>Sources:</strong><br>
                ${m.metadata.sources.map((s: any, i: number) => 
                  `<div class="source">${i + 1}. <a href="${s.url}">${s.title}</a> - ${s.source}</div>`
                ).join('')}
              </div>
            ` : ''}
          </div>
          <hr>
        `).join('')}
      </body>
      </html>
    `;
    
    const blob = new Blob([html], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `watchfuleye-chat-${new Date().toISOString().split('T')[0]}.html`;
    a.click();
    URL.revokeObjectURL(url);
  }
}

export default { MessageActions, SmartSuggestions, InsightBadge, exportConversation };
