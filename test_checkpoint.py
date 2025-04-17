#!/usr/bin/env python3
"""
Test script to demonstrate checkpoint functionality in wallet_cracker.py
"""

import os
import sys
import time
import signal
import subprocess

# Create directory for hashcat sessions
os.makedirs("hashcat_sessions", exist_ok=True)

# Create a test hash file
test_hash = "$bitcoin$32$28dc9bc9177c96f972fea7153d78831c$16$1883f9c7eff6$832000$sha256d$1$00"
with open("test_hash.txt", "w") as f:
    f.write(test_hash)

# Create a simple wordlist
with open("test_wordlist.txt", "w") as f:
    f.write("\n".join([f"test{i}" for i in range(1, 1000)]))

def run_test():
    print("\n=== Testing Checkpoint Functionality ===\n")
    
    # 1. First run with interruption
    print("Starting first run (will be interrupted after 5 seconds)...")
    
    # Start the process
    cmd = ["python", "wallet_cracker.py", "--test-hash", "test_hash.txt", 
           "--hashcat", "--cpu-only", "-d", "test_wordlist.txt"]
    
    process = subprocess.Popen(cmd)
    
    # Let it run for a few seconds
    time.sleep(5)
    
    # Interrupt the process
    print("\nInterrupting process...")
    process.send_signal(signal.SIGINT)
    
    # Wait for it to exit gracefully
    process.wait(timeout=10)
    
    print("\nProcess interrupted. Waiting 3 seconds before resuming...")
    time.sleep(3)
    
    # 2. Second run to test resuming
    print("\n=== Testing Resume Functionality ===\n")
    print("Starting second run (should resume from checkpoint)...")
    
    # Check if session files were created
    session_files = [f for f in os.listdir("hashcat_sessions") if f.endswith(".session") or f.endswith(".restore")]
    if session_files:
        print(f"Found session files: {session_files}")
    else:
        print("Warning: No session files found!")
    
    # Run the same command, should resume
    resume_process = subprocess.run(cmd)
    
    print("\n=== Testing No-Resume Option ===\n")
    
    # 3. Third run with --no-resume
    print("Starting third run with --no-resume (should start fresh)...")
    cmd_no_resume = cmd + ["--no-resume"]
    
    # Make sure the command is correct
    print(f"Command with no-resume: {' '.join(cmd_no_resume)}")
    
    no_resume_process = subprocess.run(cmd_no_resume)
    
    print("\n=== Test Complete ===\n")

if __name__ == "__main__":
    run_test() 