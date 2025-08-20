#!/usr/bin/env python3
"""
Output Analysis Tool for DiatomsAI News Bot
Analyzes logged outputs to identify quality trends and issues.
"""

import json
import os
import glob
from datetime import datetime
from typing import List, Dict
import statistics

def load_metrics() -> List[Dict]:
    """Load all metrics files"""
    metrics_files = glob.glob("outputs/metrics/metrics_*.json")
    metrics = []
    
    for file_path in sorted(metrics_files):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                metrics.append(data)
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
    
    return metrics

def analyze_quality_trends(metrics: List[Dict]):
    """Analyze quality trends over time"""
    if not metrics:
        print("No metrics data found.")
        return
    
    print("=== QUALITY ANALYSIS ===")
    print(f"Total outputs analyzed: {len(metrics)}")
    
    # Quality scores
    scores = [m['quality_metrics']['overall_score'] for m in metrics]
    if scores:
        print(f"Average quality score: {statistics.mean(scores):.2f}/10")
        print(f"Best score: {max(scores):.2f}/10")
        print(f"Worst score: {min(scores):.2f}/10")
        if len(scores) > 1:
            print(f"Score std dev: {statistics.stdev(scores):.2f}")
    
    # Common issues
    all_issues = []
    for m in metrics:
        all_issues.extend(m['quality_metrics']['issues'])
    
    if all_issues:
        issue_counts = {}
        for issue in all_issues:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
        
        print("\n=== COMMON ISSUES ===")
        for issue, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / len(metrics)) * 100
            print(f"• {issue}: {count} times ({percentage:.1f}%)")
    
    # Performance metrics
    processing_times = [m['processing_time'] for m in metrics]
    message_lengths = [m['message_length'] for m in metrics]
    
    print(f"\n=== PERFORMANCE ===")
    if processing_times:
        print(f"Avg processing time: {statistics.mean(processing_times):.1f}s")
        print(f"Fastest: {min(processing_times):.1f}s")
        print(f"Slowest: {max(processing_times):.1f}s")
    
    if message_lengths:
        print(f"Avg message length: {statistics.mean(message_lengths):.0f} chars")
        print(f"Shortest: {min(message_lengths)} chars")
        print(f"Longest: {max(message_lengths)} chars")

def show_recent_outputs(metrics: List[Dict], count: int = 5):
    """Show recent outputs with quality scores"""
    if not metrics:
        return
    
    print(f"\n=== RECENT OUTPUTS (Last {count}) ===")
    
    recent = sorted(metrics, key=lambda x: x['timestamp_unix'], reverse=True)[:count]
    
    for i, m in enumerate(recent, 1):
        timestamp = datetime.fromtimestamp(m['timestamp_unix']).strftime('%Y-%m-%d %H:%M')
        score = m['quality_metrics']['overall_score']
        issues = m['quality_metrics']['issues']
        
        print(f"\n{i}. {timestamp} | Score: {score:.1f}/10")
        print(f"   Length: {m['message_length']} chars | Processing: {m['processing_time']:.1f}s")
        
        if issues:
            print(f"   Issues: {', '.join(issues)}")
        else:
            print("   ✅ No issues detected")

def show_worst_outputs(metrics: List[Dict], count: int = 3):
    """Show worst quality outputs for review"""
    if not metrics:
        return
    
    print(f"\n=== WORST OUTPUTS (Bottom {count}) ===")
    
    worst = sorted(metrics, key=lambda x: x['quality_metrics']['overall_score'])[:count]
    
    for i, m in enumerate(worst, 1):
        timestamp = datetime.fromtimestamp(m['timestamp_unix']).strftime('%Y-%m-%d %H:%M')
        score = m['quality_metrics']['overall_score']
        issues = m['quality_metrics']['issues']
        
        print(f"\n{i}. {timestamp} | Score: {score:.1f}/10")
        print(f"   Issues: {', '.join(issues) if issues else 'None'}")
        
        # Show first few lines of the output
        lines = m['formatted_message'].split('\n')[:5]
        print("   Preview:")
        for line in lines:
            if line.strip():
                print(f"   > {line[:80]}...")

def main():
    """Main analysis function"""
    print("🔍 DiatomsAI Output Analysis Tool")
    print("=" * 50)
    
    # Load metrics
    metrics = load_metrics()
    
    if not metrics:
        print("No output data found. Run the bot first to generate outputs.")
        return
    
    # Run analysis
    analyze_quality_trends(metrics)
    show_recent_outputs(metrics)
    show_worst_outputs(metrics)
    
    print(f"\n📁 Output files located in:")
    print(f"   • Formatted: outputs/formatted/")
    print(f"   • Raw analysis: outputs/raw_analysis/")
    print(f"   • Metrics: outputs/metrics/")

if __name__ == "__main__":
    main() 