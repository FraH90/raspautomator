import os
import sys
from orchestrator.orchestrator import Orchestrator

ROOT_DIR = os.getcwd()
TASKS_ROOT_FOLDER = os.path.join(ROOT_DIR, "tasks")

def main():
    if len(sys.argv) != 2:
        print("Usage: python debug.py <task_name>")
        sys.exit(1)

    task_name = sys.argv[1]
    orchestrator = Orchestrator(TASKS_ROOT_FOLDER)
    
    try:
        orchestrator.run_task_debug(task_name)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()