#!/usr/bin/env python
import os
import sys
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def check_locale_dirs():
    """Check if locale directories exist and are properly set up."""
    locale_dir = BASE_DIR / 'locale'
    
    if not os.path.exists(locale_dir):
        print(f"ERROR: Locale directory does not exist: {locale_dir}")
        return False
        
    # Check for at least one language directory
    languages = [d for d in os.listdir(locale_dir) 
                if os.path.isdir(os.path.join(locale_dir, d))]
    
    if not languages:
        print(f"ERROR: No language directories found in {locale_dir}")
        return False
        
    # Check for .po files
    has_po_files = False
    for lang in languages:
        po_path = os.path.join(locale_dir, lang, 'LC_MESSAGES', 'django.po')
        if os.path.exists(po_path):
            has_po_files = True
            break
    
    if not has_po_files:
        print("ERROR: No django.po files found in any language directory")
        return False
        
    return True

def main():
    """Compile translation messages."""
    print("Checking locale directories...")
    if not check_locale_dirs():
        return 1
        
    # Change to project directory
    os.chdir(BASE_DIR)
    
    # Check if 'msgfmt' command is available
    try:
        subprocess.run(["msgfmt", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("WARNING: 'msgfmt' command not found. Make sure gettext is installed.")
        
    # Compile messages
    print("Compiling messages...")
    try:
        process = subprocess.run(
            ["django-admin", "compilemessages", "--verbosity=2"],
            check=False,
            capture_output=True,
            text=True
        )
        
        # Print output
        if process.stdout:
            print(process.stdout)
            
        if process.stderr:
            print(f"ERRORS/WARNINGS:\n{process.stderr}", file=sys.stderr)
            
        if process.returncode != 0:
            print(f"Error: compilemessages failed with return code {process.returncode}")
            return process.returncode
            
        print("Messages successfully compiled!")
        
        # Verify .mo files were created
        locale_dir = BASE_DIR / 'locale'
        mo_files_created = []
        
        for lang in os.listdir(locale_dir):
            mo_path = os.path.join(locale_dir, lang, 'LC_MESSAGES', 'django.mo')
            if os.path.exists(mo_path):
                mo_files_created.append(lang)
                
        print(f"Created .mo files for languages: {', '.join(mo_files_created)}")
        
    except Exception as e:
        print(f"Error compiling messages: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
