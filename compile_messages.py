#!/usr/bin/env python
import os
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def main():
    """Compile translation messages."""
    # Change to project directory
    os.chdir(BASE_DIR)
    
    # Compile messages
    try:
        subprocess.run(
            ["django-admin", "compilemessages"],
            check=True
        )
        print("Messages successfully compiled!")
    except subprocess.CalledProcessError as e:
        print(f"Error compiling messages: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
