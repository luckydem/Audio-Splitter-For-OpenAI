#!/usr/bin/env python3
"""
Log Cleanup Script for Audio Splitter

This script helps manage log files by removing old logs and keeping only
the most recent ones to prevent disk space issues.

Usage:
    python cleanup_logs.py --days 30  # Keep logs from last 30 days
    python cleanup_logs.py --count 10 # Keep last 10 log files
"""

import argparse
import os
from datetime import datetime, timedelta
from pathlib import Path
import logging

def cleanup_old_logs(log_dir, days=None, count=None):
    """
    Clean up old log files based on age or count
    
    Args:
        log_dir: Directory containing log files
        days: Keep logs newer than this many days
        count: Keep this many most recent log files
    """
    log_dir = Path(log_dir)
    if not log_dir.exists():
        print(f"Log directory doesn't exist: {log_dir}")
        return
    
    # Find all log files
    log_files = list(log_dir.glob("audio_splitter_*.log"))
    
    if not log_files:
        print("No log files found")
        return
    
    print(f"Found {len(log_files)} log files")
    
    files_to_delete = []
    
    if days:
        # Delete files older than specified days
        cutoff_date = datetime.now() - timedelta(days=days)
        for log_file in log_files:
            file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
            if file_time < cutoff_date:
                files_to_delete.append(log_file)
        print(f"Files older than {days} days: {len(files_to_delete)}")
    
    elif count:
        # Keep only the most recent N files
        log_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        if len(log_files) > count:
            files_to_delete = log_files[count:]
        print(f"Files to delete (keeping {count} most recent): {len(files_to_delete)}")
    
    # Delete the files
    total_size = 0
    for log_file in files_to_delete:
        size = log_file.stat().st_size
        total_size += size
        print(f"Deleting: {log_file.name} ({size / 1024:.1f} KB)")
        log_file.unlink()
    
    if files_to_delete:
        print(f"Deleted {len(files_to_delete)} log files, freed {total_size / 1024:.1f} KB")
    else:
        print("No files to delete")

def main():
    parser = argparse.ArgumentParser(description="Clean up old audio splitter log files")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--days', type=int, help='Keep logs newer than this many days')
    group.add_argument('--count', type=int, help='Keep this many most recent log files')
    parser.add_argument('--log-dir', default='logs', help='Log directory (default: logs)')
    
    args = parser.parse_args()
    
    cleanup_old_logs(args.log_dir, args.days, args.count)

if __name__ == '__main__':
    main()