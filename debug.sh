#!/bin/bash

# Check if a task name was provided
if [ $# -eq 0 ]; then
    echo "Usage: ./debug.sh <task_name>"
    exit 1
fi

# Run the debug script with the provided task name
python3 src/debug.py "$1" 