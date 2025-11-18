# RaspAutomator - Max Duration Feature Implementation Context

## Project Overview
RaspAutomator is a Python-based task scheduling system for Raspberry Pi that runs automated tasks like:
- **radio_alarm**: Plays random radio streams via Bluetooth speaker
- **sleep_sounds**: Downloads and loops YouTube audio via Bluetooth speaker

The system uses:
- **pyRTOS**: Cooperative multitasking framework (generator-based)
- **VLC**: Audio playback
- **BluetoothHandler**: Connects to Bluetooth speakers
- **systemd**: Runs as user service

## Problem We're Solving

### Original Issue
Tasks had **hardcoded durations** and **blocking sleep** calls:
- `radio_alarm.py`: Had `time.sleep(3600)` for 1 hour
- `sleep_sounds.py`: Looped until a hardcoded stop_time

**Problems:**
1. Duration was in the code, not configurable
2. `.terminate` files couldn't stop tasks (they were blocked in sleep)
3. Poor separation of concerns (tasks knew their own duration)

## Solution Implemented

### Architectural Change: Move Duration Control to Orchestrator

**New approach:**
1. Tasks play audio **indefinitely** (simple infinite loops)
2. Orchestrator controls **how long** they run via `max_duration` parameter in `trigger.json`
3. Orchestrator monitors tasks in **separate threads**
4. `.terminate` files checked **every second** for instant termination

### Code Changes Made

#### 1. `src/task/task.py` - Added Thread-Based Monitoring

Added new method `_execute_task_with_monitoring()`:
- Runs `task_module.thread_loop()` in a daemon thread
- Monitors every second for:
  - `.terminate` files (instant termination)
  - `max_duration` exceeded (graceful stop)
- Uses `yield [pyRTOS.timeout(1)]` to check periodically

**Key code (lines 73-109):**
```python
def _execute_task_with_monitoring(self):
    # Start task in daemon thread
    task_thread = threading.Thread(target=self.task_module.thread_loop, daemon=True)
    task_thread.start()

    max_duration = self.config.get('max_duration', None)
    start_time = datetime.now()

    while task_thread.is_alive():
        # Check .terminate files
        terminate_file = os.path.join(self.root_dir, f'{os.path.basename(self.task_name)}.terminate')
        all_terminate_file = os.path.join(self.root_dir, 'all.terminate')

        if os.path.exists(terminate_file) or os.path.exists(all_terminate_file):
            logger.info(f"Terminate signal received")
            return True  # Signal termination

        # Check max_duration
        if max_duration and (datetime.now() - start_time).total_seconds() > max_duration:
            logger.info(f"Task reached max_duration of {max_duration}s")
            return False  # Normal completion

        yield [pyRTOS.timeout(1)]  # Check every second

    return False
```

**Bug Fix Applied:**
- Line 16: Changed `root_dir` calculation from 2 to 3 dirname() calls
- **Was:** `os.path.dirname(os.path.dirname(task_file))` → pointed to `tasks/` folder
- **Now:** `os.path.dirname(os.path.dirname(os.path.dirname(task_file)))` → points to project root

#### 2. `tasks/radio_alarm/radio_alarm.py` - Simplified

**Changed:**
- Function name: `play_radio_for_one_hour()` → `play_radio()`
- Removed: `time.sleep(3600)`
- Added: `while True: time.sleep(1)` (infinite loop)
- Orchestrator now controls when to stop

**Key code (lines 52-78):**
```python
def play_radio(self, stream_url, radio_name):
    """Play radio stream indefinitely. Duration is controlled by orchestrator via max_duration."""
    # ... VLC setup ...

    # Play indefinitely - the orchestrator will stop this task after max_duration
    while True:
        time.sleep(1)
```

#### 3. `tasks/sleep_sounds/sleep_sounds.py` - Simplified

**Changed:**
- Function name: `loop_until_stop()` → `loop_indefinitely()`
- Removed: `stop_dt` calculation and checking
- Added: `while True: time.sleep(2)` (infinite loop)

**Key code (lines 112-151):**
```python
def loop_indefinitely(self, audio_path):
    """Continuously loops a single audio file indefinitely."""
    # ... VLC setup ...

    # Loop indefinitely - orchestrator will stop after max_duration
    while True:
        time.sleep(2)
```

#### 4. `trigger.json` Files - Added max_duration

**`tasks/radio_alarm/trigger.json`:**
```json
{
    "max_duration": 3600,  // 1 hour in seconds
    // ... other config ...
}
```

**`tasks/sleep_sounds/trigger.json`:**
```json
{
    "max_duration": 12600,  // 3.5 hours (23:30 to 03:00)
    // ... other config ...
}
```

## Current Issue: .terminate Files Not Working

### Expected Behavior
1. Create `.terminate` file: `touch radio_alarm.terminate` in project root
2. Orchestrator detects it within 1 second (checking loop)
3. Task thread terminates (it's a daemon thread)
4. Logs show: "Terminate signal received"

### Actual Behavior
- `.terminate` file created
- Task keeps running
- No termination detected

### Testing Done
- Running `./automator.sh` standalone (not as service)
- Creating `radio_alarm.terminate` with `touch` command
- File exists but not being detected

### Potential Issues to Investigate

#### 1. **Thread Doesn't Actually Stop**
Daemon threads in Python don't automatically stop running code. When we `return` from the monitoring function, the daemon thread with the infinite loop keeps running.

**Possible solution:** Need to actively kill the thread or use a stop event.

#### 2. **root_dir Path Still Wrong**
Even though we fixed it to 3 dirname() calls, need to verify:
```python
# Debug: Add logging to see actual paths
logger.info(f"task_file: {task_file}")
logger.info(f"root_dir: {self.root_dir}")
logger.info(f"Looking for: {terminate_file}")
```

#### 3. **File Detection Timing**
The `yield [pyRTOS.timeout(1)]` might not work as expected with pyRTOS cooperative scheduling.

#### 4. **Task Name Mismatch**
```python
terminate_file = os.path.join(self.root_dir, f'{os.path.basename(self.task_name)}.terminate')
```
Need to verify `self.task_name` matches the expected value (should be `radio_alarm`).

## File Structure

```
raspautomator/
├── src/
│   ├── main.py                    # Entry point
│   ├── orchestrator/
│   │   └── orchestrator.py        # Discovers and runs tasks
│   └── task/
│       ├── task.py                # Task wrapper with monitoring ⭐ MODIFIED
│       └── bluetooth_handler.py   # Bluetooth connection logic
├── tasks/
│   ├── radio_alarm/
│   │   ├── radio_alarm.py         # Radio player task ⭐ MODIFIED
│   │   ├── trigger.json           # Scheduling config ⭐ MODIFIED
│   │   └── config.json            # Bluetooth MAC address
│   └── sleep_sounds/
│       ├── sleep_sounds.py        # Sleep sounds task ⭐ MODIFIED
│       ├── trigger.json           # Scheduling config ⭐ MODIFIED
│       └── config.json            # Bluetooth MAC + stop_time
├── automator.sh                   # Startup script
└── installer.sh                   # Service installer
```

## Git Branch Info

- **Working branch:** `claude/repo-documentation-011CUxYG3XVo5mAMXFttz2kS`
- **Main branch:** `main`
- **Commits made:**
  1. `b9c9fb5` - "Implement max_duration feature for task execution control"
  2. `6e95be6` - "Fix root_dir path calculation for .terminate file detection"

## Next Steps for Debugging

### 1. Create a Debug Task
Create `tasks/debug_test/debug_test.py` with extensive logging:

```python
import time
import logging
import os

logger = logging.getLogger(__name__)

def thread_loop():
    """Simple debug task that logs every second"""
    logger.info("DEBUG TASK STARTED")
    counter = 0

    while True:
        counter += 1
        logger.info(f"Debug task loop iteration {counter}")
        time.sleep(1)

        # Also log if we can see terminate file
        if os.path.exists('/path/to/project/debug_test.terminate'):
            logger.info("DEBUG: I can see the terminate file!")
```

### 2. Add Debug Logging to task.py
In `_execute_task_with_monitoring()`, add:

```python
logger.info(f"Task file: {self.task_module.__file__}")
logger.info(f"Root dir: {self.root_dir}")
logger.info(f"Task name: {self.task_name}")
logger.info(f"Task basename: {os.path.basename(self.task_name)}")
logger.info(f"Checking for: {terminate_file}")
logger.info(f"Checking for: {all_terminate_file}")
```

### 3. Test Thread Termination Approach

**Problem:** Daemon threads don't stop automatically.

**Solution options:**
1. Use `threading.Event()` to signal thread to stop
2. Store thread reference and call explicit termination
3. Make tasks check for a stop flag periodically

**Recommended approach:**
```python
# In Task class
self.stop_event = threading.Event()

# In task code (radio_alarm.py)
while not stop_event.is_set():
    time.sleep(1)

# In monitoring
if terminate_file_exists:
    self.stop_event.set()  # Signal task to stop
    task_thread.join(timeout=5)  # Wait for graceful shutdown
```

### 4. Verify Path Calculations
Add this test in the orchestrator or task.py:

```python
import os
test_path = "/home/user/raspautomator/tasks/radio_alarm/radio_alarm.py"
print(f"Original: {test_path}")
print(f"1 dirname: {os.path.dirname(test_path)}")
print(f"2 dirname: {os.path.dirname(os.path.dirname(test_path))}")
print(f"3 dirname: {os.path.dirname(os.path.dirname(os.path.dirname(test_path)))}")
```

Expected output:
```
Original: /home/user/raspautomator/tasks/radio_alarm/radio_alarm.py
1 dirname: /home/user/raspautomator/tasks/radio_alarm
2 dirname: /home/user/raspautomator/tasks
3 dirname: /home/user/raspautomator  ← This should be root_dir
```

## Testing Instructions

### Manual Testing
1. Run standalone: `./automator.sh`
2. Edit trigger to run immediately (set time_of_day to current time + 1 min)
3. Wait for task to start
4. Create terminate file: `touch radio_alarm.terminate` (in project root)
5. Check logs for termination

### Test with Debug Task
1. Create simple debug task with lots of logging
2. Set `max_duration: 10` to test auto-stop
3. Monitor logs to see actual vs expected behavior

### Verify Paths
1. Add logging to see what paths are being checked
2. Manually verify terminate file is in expected location
3. Check file permissions

## Key Questions to Answer

1. **Is the monitoring loop actually running?** (Add logs to confirm)
2. **What is the actual value of `root_dir`?** (Log it)
3. **Is the daemon thread stopping when we return?** (Probably not - this is the issue)
4. **Does pyRTOS.timeout(1) work as expected?** (Test timing)
5. **Are terminate file paths correct?** (Log and verify)

## Expected vs Actual Flow

### Expected:
```
1. Task starts in daemon thread
2. Monitoring loop checks every 1 second
3. User creates .terminate file
4. Next check (within 1 sec) detects file
5. Monitoring function returns True
6. Daemon thread dies naturally
7. Task cleanup runs (finally block)
```

### Likely Actual:
```
1. Task starts in daemon thread ✓
2. Monitoring loop checks every 1 second ✓
3. User creates .terminate file ✓
4. Check detects file (maybe?)
5. Monitoring function returns True ✓
6. Daemon thread KEEPS RUNNING ❌ (infinite loop doesn't check anything)
7. Audio keeps playing
```

## Solution Strategy

The root cause is likely that **daemon threads don't automatically stop**. We need to:

1. Pass a `stop_event` to tasks
2. Tasks check `stop_event` in their loops
3. When terminate detected, set the event
4. Task sees event and exits gracefully

This requires modifying how tasks are written, but it's the cleanest solution.

Alternatively: Store thread reference and use OS-level termination (not recommended, unsafe).
