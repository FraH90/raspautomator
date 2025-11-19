#!/usr/bin/env python3
"""
Debug runner to test a single task with extensive logging.
Usage: python3 debug_runner.py <task_name>
Example: python3 debug_runner.py debug_test
"""

import sys
import os
import logging

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from orchestrator.orchestrator import Orchestrator

# Set up logging to see everything
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/debug.log')
    ]
)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 debug_runner.py <task_name>")
        print("Example: python3 debug_runner.py debug_test")
        sys.exit(1)

    task_name = sys.argv[1]

    ROOT_DIR = os.getcwd()
    TASKS_ROOT_FOLDER = os.path.join(ROOT_DIR, "tasks")

    print(f"Starting debug mode for task: {task_name}")
    print(f"Root directory: {ROOT_DIR}")
    print(f"Tasks folder: {TASKS_ROOT_FOLDER}")
    print(f"To terminate: touch {task_name}.terminate in {ROOT_DIR}")
    print("-" * 80)

    orchestrator = Orchestrator(TASKS_ROOT_FOLDER)
    try:
        orchestrator.run_task_debug(task_name)
    except KeyboardInterrupt:
        print("\nDebug runner interrupted by user")
    except Exception as e:
        print(f"\nError running task: {e}")
        raise

if __name__ == '__main__':
    main()
