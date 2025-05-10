#!/usr/bin/env python
import os
import sys
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent

def main():
    """Check translation files in the project."""
    locale_dir = BASE_DIR / 'locale'
    print(f"Checking translations in {locale_dir}")
    
    if not os.path.exists(locale_dir):
        print(f"ERROR: Locale directory does not exist: {locale_dir}")
        return 1
        
    # Check all language directories
    for lang_dir in os.listdir(locale_dir):
        lang_path = locale_dir / lang_dir
        if not os.path.isdir(lang_path):
            continue
            
        lc_messages_path = lang_path / 'LC_MESSAGES'
        if not os.path.exists(lc_messages_path):
            print(f"WARNING: No LC_MESSAGES directory for {lang_dir}")
            continue
            
        po_file = lc_messages_path / 'django.po'
        mo_file = lc_messages_path / 'django.mo'
        
        print(f"\nLanguage: {lang_dir}")
        print(f"  .po file: {'EXISTS' if os.path.exists(po_file) else 'MISSING'}")
        
        if os.path.exists(po_file):
            po_mtime = os.path.getmtime(po_file)
            po_datetime = datetime.fromtimestamp(po_mtime).strftime('%Y-%m-%d %H:%M:%S')
            print(f"    Last modified: {po_datetime}")
        
        print(f"  .mo file: {'EXISTS' if os.path.exists(mo_file) else 'MISSING'}")
        
        if os.path.exists(mo_file):
            mo_mtime = os.path.getmtime(mo_file)
            mo_datetime = datetime.fromtimestamp(mo_mtime).strftime('%Y-%m-%d %H:%M:%S')
            print(f"    Last modified: {mo_datetime}")
            
            # Check if .mo file is older than .po file
            if os.path.exists(po_file) and mo_mtime < po_mtime:
                print("    WARNING: .mo file is older than .po file - needs recompilation!")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
