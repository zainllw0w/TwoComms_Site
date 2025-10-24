#!/usr/bin/env python3
"""
Script to remove console.log statements from JavaScript files
Preserves console.error and console.warn for production debugging
"""
import re
import os
import sys
from pathlib import Path


def remove_console_logs(file_path):
    """Remove console.log statements from a JavaScript file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Remove console.log statements (but keep console.error and console.warn)
    # Pattern matches:
    # - console.log(...);
    # - console.log(...) (without semicolon)
    # Handles multi-line console.log statements
    
    # Remove simple console.log statements
    content = re.sub(r'console\.log\([^)]*\);?\s*\n?', '', content)
    
    # Remove multi-line console.log statements
    content = re.sub(r'console\.log\([^)]*\n[^)]*\);?\s*\n?', '', content, flags=re.MULTILINE)
    
    # Remove console.log with template literals (backticks)
    content = re.sub(r'console\.log\(`[^`]*`\);?\s*\n?', '', content)
    
    # Remove console.log with emoji and complex strings
    content = re.sub(r'console\.log\([^;]*\);?\s*\n?', '', content)
    
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False


def main():
    """Main function to process all JavaScript files"""
    js_dir = Path(__file__).parent / 'twocomms' / 'static' / 'js'
    
    if not js_dir.exists():
        print(f"Error: Directory {js_dir} does not exist")
        sys.exit(1)
    
    js_files = list(js_dir.glob('**/*.js'))
    
    print(f"Found {len(js_files)} JavaScript files")
    modified_count = 0
    
    for js_file in js_files:
        print(f"Processing {js_file.name}...", end=' ')
        if remove_console_logs(js_file):
            print("✓ Modified")
            modified_count += 1
        else:
            print("- No changes")
    
    print(f"\n✅ Complete! Modified {modified_count} files")


if __name__ == '__main__':
    main()

