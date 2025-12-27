import React from 'react';
import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown, Activity, BarChart3, PieChart, Globe, Calendar } from 'lucide-react';
import { cn } from '../lib/utils';

interface SentimentTrendProps {
  data: Array<{ date: string; score: number }>;
  width?: number;
  height?: number;
  className?: string;
}

export function SentimentTrend({ data, width = 120, height = 40, className }: SentimentTrendProps) {
  if (!data || data.length < 2) return null;
  
  // Normalize data to fit in the SVG viewport
  const minScore = Math.min(...data.map(d => d.score));
  const maxScore = Math.max(...data.map(d => d.score));
  const range = maxScore - minScore || 1;
  
  const points = data.map((d, i) => {
    const x = (i / (data.length - 1)) * (width - 10) + 5;
    const y = height - ((d.score - minScore) / range) * (height - 10) - 5;
    return `${x},${y}`;
  }).join(' ');
  
  const trend = data[data.length - 1].score > data[0].score ? 'up' : 'down';
  const trendColor = trend === 'up' ? 'text-green-600' : 'text-red-600';
  const gradientId = `gradient-${Math.random().toString(36).substr(2, 9)}`;
  
  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      className={cn("inline-flex items-center gap-2 px-3 py-2 bg-slate-50 dark:bg-slate-900/30 rounded-lg", className)}
    >
      <div className="flex flex-col">
        <span className="text-xs font-medium text-slate-600 dark:text-slate-400">Sentiment Trend</span>
        <div className="flex items-center gap-1 mt-1">
          {trend === 'up' ? (
            <TrendingUp className={cn("w-3.5 h-3.5", trendColor)} />
          ) : (
            <TrendingDown className={cn("w-3.5 h-3.5", trendColor)} />
          )}
          <span className={cn("text-xs font-semibold", trendColor)}>
            {((data[data.length - 1].score - data[0].score) * 100).toFixed(1)}%
          </span>
        </div>
      </div>
      
      <svg width={width} height={height} className="overflow-visible">
        <defs>
          <linearGradient id={gradientId} x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor={trend === 'up' ? '#10b981' : '#ef4444'} stopOpacity="0.3" />
            <stop offset="100%" stopColor={trend === 'up' ? '#10b981' : '#ef4444'} stopOpacity="0.05" />
          </linearGradient>
        </defs>
        
        {/* Area fill */}
        <polygon
          points={`${points} ${width - 5},${height - 5} 5,${height - 5}`}
          fill={`url(#${gradientId})`}
        />
        
        {/* Line */}
        <polyline
          points={points}
          fill="none"
          stroke={trend === 'up' ? '#10b981' : '#ef4444'}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        
        {/* Dots */}
        {data.map((d, i) => {
          const x = (i / (data.length - 1)) * (width - 10) + 5;
          const y = height - ((d.score - minScore) / range) * (height - 10) - 5;
          return (
            <circle
              key={i}
              cx={x}
              cy={y}
              r="2"
              fill={trend === 'up' ? '#10b981' : '#ef4444'}
              className="opacity-80"
            />
          );
        })}
      </svg>
    </motion.div>
  );
}

interface CategoryDistributionProps {
  categories: Array<{ name: string; count: number; color?: string }>;
  className?: string;
}

export function CategoryDistribution({ categories, className }: CategoryDistributionProps) {
  if (!categories || categories.length === 0) return null;
  
  const total = categories.reduce((sum, c) => sum + c.count, 0);
  const colors = ['bg-blue-500', 'bg-green-500', 'bg-amber-500', 'bg-purple-500', 'bg-red-500'];
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn("p-3 bg-slate-50 dark:bg-slate-900/30 rounded-lg", className)}
    >
      <div className="flex items-center gap-2 mb-2">
        <PieChart className="w-4 h-4 text-slate-600 dark:text-slate-400" />
        <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">Category Breakdown</span>
      </div>
      
      {/* Bar chart */}
      <div className="space-y-2">
        {categories.slice(0, 5).map((cat, idx) => {
          const percentage = (cat.count / total) * 100;
          const color = cat.color || colors[idx % colors.length];
          
          return (
            <div key={cat.name} className="flex items-center gap-2">
              <span className="text-xs text-slate-600 dark:text-slate-400 w-20 truncate">
                {cat.name}
              </span>
              <div className="flex-1 bg-slate-200 dark:bg-slate-700 rounded-full h-4 relative overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${percentage}%` }}
                  transition={{ duration: 0.5, delay: idx * 0.1 }}
                  className={cn("h-full rounded-full", color)}
                />
              </div>
              <span className="text-xs font-medium text-slate-700 dark:text-slate-300 w-10 text-right">
                {cat.count}
              </span>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}

interface TimelineVisualizationProps {
  events: Array<{
    date: string;
    title: string;
    type: 'positive' | 'negative' | 'neutral';
    impact?: 'high' | 'medium' | 'low';
  }>;
  className?: string;
}

export function TimelineVisualization({ events, className }: TimelineVisualizationProps) {
  if (!events || events.length === 0) return null;
  
  const typeColors = {
    positive: 'bg-green-500',
    negative: 'bg-red-500',
    neutral: 'bg-gray-400',
  };
  
  const impactSizes = {
    high: 'w-3 h-3',
    medium: 'w-2.5 h-2.5',
    low: 'w-2 h-2',
  };
  
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className={cn("p-3 bg-slate-50 dark:bg-slate-900/30 rounded-lg", className)}
    >
      <div className="flex items-center gap-2 mb-3">
        <Calendar className="w-4 h-4 text-slate-600 dark:text-slate-400" />
        <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">Event Timeline</span>
      </div>
      
      <div className="relative">
        {/* Timeline line */}
        <div className="absolute left-2 top-2 bottom-2 w-0.5 bg-slate-300 dark:bg-slate-600" />
        
        {/* Events */}
        <div className="space-y-3">
          {events.slice(0, 5).map((event, idx) => (
            <motion.div
              key={idx}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.1 }}
              className="flex items-start gap-3 relative"
            >
              {/* Event dot */}
              <div className={cn(
                "rounded-full z-10 ring-2 ring-white dark:ring-slate-800",
                typeColors[event.type],
                impactSizes[event.impact || 'medium']
              )} />
              
              {/* Event content */}
              <div className="flex-1 -mt-0.5">
                <div className="text-xs font-medium text-slate-800 dark:text-slate-200 line-clamp-1">
                  {event.title}
                </div>
                <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  {new Date(event.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </motion.div>
  );
}

interface NetworkGraphProps {
  nodes: Array<{ id: string; label: string; type: string; connections: string[] }>;
  className?: string;
}

export function NetworkGraph({ nodes, className }: NetworkGraphProps) {
  if (!nodes || nodes.length === 0) return null;
  
  const width = 200;
  const height = 150;
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = 50;
  
  // Position nodes in a circle
  const positions = nodes.slice(0, 6).map((node, i) => {
    const angle = (i / Math.min(nodes.length, 6)) * 2 * Math.PI;
    return {
      ...node,
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
    };
  });
  
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      className={cn("p-3 bg-slate-50 dark:bg-slate-900/30 rounded-lg", className)}
    >
      <div className="flex items-center gap-2 mb-2">
        <Globe className="w-4 h-4 text-slate-600 dark:text-slate-400" />
        <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">Connection Map</span>
      </div>
      
      <svg width={width} height={height} className="w-full">
        {/* Draw connections */}
        {positions.map((node, i) => 
          node.connections?.map(targetId => {
            const target = positions.find(n => n.id === targetId);
            if (!target) return null;
            return (
              <line
                key={`${node.id}-${targetId}`}
                x1={node.x}
                y1={node.y}
                x2={target.x}
                y2={target.y}
                stroke="currentColor"
                strokeWidth="1"
                className="text-slate-300 dark:text-slate-600"
                opacity="0.5"
              />
            );
          })
        )}
        
        {/* Draw nodes */}
        {positions.map((node, i) => (
          <g key={node.id}>
            <motion.circle
              initial={{ r: 0 }}
              animate={{ r: 8 }}
              transition={{ delay: i * 0.1 }}
              cx={node.x}
              cy={node.y}
              fill="currentColor"
              className={cn(
                node.type === 'primary' ? 'text-blue-500' :
                node.type === 'secondary' ? 'text-green-500' :
                'text-gray-400'
              )}
            />
            <text
              x={node.x}
              y={node.y - 12}
              textAnchor="middle"
              className="text-xs fill-slate-600 dark:fill-slate-400"
              fontSize="10"
            >
              {node.label}
            </text>
          </g>
        ))}
      </svg>
    </motion.div>
  );
}

interface QuickStatsProps {
  stats: Array<{ label: string; value: string | number; change?: number; icon?: React.ElementType }>;
  className?: string;
}

export function QuickStats({ stats, className }: QuickStatsProps) {
  if (!stats || stats.length === 0) return null;
  
  return (
    <div className={cn("grid grid-cols-2 sm:grid-cols-4 gap-2", className)}>
      {stats.map((stat, idx) => {
        const Icon = stat.icon || Activity;
        const changeColor = stat.change && stat.change > 0 ? 'text-green-600' : stat.change && stat.change < 0 ? 'text-red-600' : 'text-gray-500';
        
        return (
          <motion.div
            key={idx}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.05 }}
            className="p-2 bg-white dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700"
          >
            <div className="flex items-center gap-2 mb-1">
              <Icon className="w-3.5 h-3.5 text-slate-500" />
              <span className="text-xs text-slate-600 dark:text-slate-400">{stat.label}</span>
            </div>
            <div className="flex items-baseline gap-1">
              <span className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                {stat.value}
              </span>
              {stat.change !== undefined && (
                <span className={cn("text-xs", changeColor)}>
                  {stat.change > 0 ? '+' : ''}{stat.change}%
                </span>
              )}
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}

export default { 
  SentimentTrend, 
  CategoryDistribution, 
  TimelineVisualization, 
  NetworkGraph, 
  QuickStats 
};
