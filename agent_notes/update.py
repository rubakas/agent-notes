"""Pull latest changes, rebuild, and reinstall."""

import subprocess
import sys
from pathlib import Path

from .config import ROOT, Color

def update() -> None:
    """Pull latest changes, rebuild, and reinstall."""
    print("Updating agent-notes...")
    print("")
    
    # Check if git repo
    git_dir = ROOT / ".git"
    if not git_dir.exists():
        print(f"{Color.RED}Error:{Color.NC} Not a git repository. Update requires a git-based install.")
        print("If installed via brew, use: brew upgrade agent-notes")
        exit(1)
    
    # Pull latest
    print("Pulling latest changes...")
    
    try:
        # Get current commit
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True
        )
        before = result.stdout.strip()
        
        # Pull with fast-forward only
        subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True
        )
        
        # Get new commit
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True
        )
        after = result.stdout.strip()
        
        if before == after:
            print(f"{Color.GREEN}Already up to date.{Color.NC}")
        else:
            # Count commits
            result = subprocess.run(
                ["git", "log", "--oneline", f"{before}..{after}"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True
            )
            commit_lines = result.stdout.strip().split('\n') if result.stdout.strip() else []
            commit_count = len(commit_lines)
            
            print(f"{Color.GREEN}Updated{Color.NC} {commit_count} commits.")
            
            # Show recent commits (max 5)
            for line in commit_lines[:5]:
                print(line)
            print("")
    
    except subprocess.CalledProcessError as e:
        print(f"{Color.RED}Error:{Color.NC} Could not fast-forward. You may have local changes.")
        print(f"Resolve manually: cd {ROOT} && git status")
        exit(1)
    
    # Rebuild and reinstall
    print("")
    from .install import install
    install()