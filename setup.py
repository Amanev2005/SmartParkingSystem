#!/usr/bin/env python
"""
Setup and run parking system with all checks
"""
import subprocess
import sys
import os

def run_command(cmd, description):
    """Run a command and return True if successful"""
    print(f"\n{'='*70}")
    print(f"  {description}")
    print(f"{'='*70}")
    try:
        result = subprocess.run(cmd, shell=True, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def main():
    print("\n" + "="*70)
    print("  SMART PARKING SYSTEM - COMPLETE SETUP")
    print("="*70)
    
    # Step 1: Install dependencies
    print("\n[1/3] Installing Python dependencies...")
    if not run_command(
        f"{sys.executable} -m pip install -q -r requirements.txt",
        "Installing dependencies from requirements.txt"
    ):
        print("Failed to install dependencies")
        return False
    print("✓ Dependencies installed")
    
    # Step 2: Initialize database
    print("\n[2/3] Initializing database...")
    if not run_command(
        f"{sys.executable} init_parking_db.py",
        "Setting up parking slots"
    ):
        print("Failed to initialize database")
        return False
    print("✓ Database ready")
    
    # Step 3: Instructions
    print("\n" + "="*70)
    print("  SETUP COMPLETE - NEXT STEPS")
    print("="*70)
    print("\n1. Start Flask server (in one terminal):")
    print("   python slot.py")
    print("\n2. In another terminal, run camera detection:")
    print("   python camera_capture.py --photo --dedup 20")
    print("\nOr run continuous detection:")
    print("   python camera_capture.py --local 0 --dedup 20")
    print("\n" + "="*70 + "\n")
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
