# .terminate File Fix and max_duration Feature - Implementation Details

## Previous Implementation (main branch)

### How Duration Was Handled

**Radio Alarm (`radio_alarm.py`):**
- Duration was **hardcoded** in the task itself: `time.sleep(3600)` (1 hour)
- Method was called `play_radio_for_one_hour()`
- Task blocked for entire duration with single long sleep
- **Terminate files could NOT interrupt** the task during this sleep

```python
# Old implementation (main branch)
def play_radio_for_one_hour(self, stream_url, radio_name):
    # ... setup code ...
    player.play()
    print(f"{time.strftime('%H:%M')} - Playing radio {radio_name}")
    # Play for 1 hour (3600 seconds) - BLOCKING!
    time.sleep(3600)
    # Stop the player
    player.stop()
    print(f"{time.strftime('%H:%M')} - Stopped playing radio {radio_name}")
```

**Sleep Sounds (`sleep_sounds.py`):**
- Duration was **hardcoded** via `stop_time` in config.json (e.g., "23:30")
- Method was called `loop_until_stop()`
- Calculated stop datetime and checked `while datetime.now() < stop_dt:`
- **Terminate files could NOT interrupt** the task during playback

```python
# Old implementation (main branch)
def loop_until_stop(self, audio_path):
    stop_dt = self.get_stop_datetime()
    self.logger.info(f"Playing sleep sounds until {stop_dt.strftime('%Y-%m-%d %H:%M')}")
    # ... VLC setup ...
    list_player.play()
    try:
        # Poll until it's time to stop - BLOCKING!
        while datetime.now() < stop_dt:
            time.sleep(2)  # Check every couple seconds
    finally:
        list_player.stop()
```

### How Terminate Files Were Handled (main branch)

In the **old implementation**, terminate file checking was done **AFTER** the task completed:

```python
# In task.py (main branch)
def run(self, self_task):
    # ... task execution ...
    self.task_module.thread_loop()  # Task runs here (blocking!)

    if self.config['timeout_on']:
        yield [pyRTOS.timeout(self.config['timeout_interval'])]
    else:
        yield

    # Check for terminate AFTER task finishes - TOO LATE!
    if os.path.exists(os.path.join(self.root_dir, 'all.terminate')) or \
       os.path.exists(os.path.join(self.root_dir, f'{self.task_name}.terminate')):
        return
```

**Problems with old approach:**
1. ❌ Terminate files only checked **between** task executions, not during
2. ❌ Tasks blocked for their entire duration (3600 seconds for radio, hours for sleep sounds)
3. ❌ No way to stop a running task immediately
4. ❌ Duration was in the task code, not configurable

## New Implementation (current branch)

### Architectural Change: Orchestrator Controls Duration

**Key principle:** Tasks should be simple and dumb - they just play audio. The orchestrator decides when to stop them.

### Changes Made

#### 1. **Introduced `max_duration` Parameter**

Added to `trigger.json` files:

```json
{
    "max_duration": 3600,  // 1 hour in seconds (radio_alarm)
    "max_duration": 12600, // 3.5 hours (sleep_sounds, replacing stop_time calculation)
    "schedule_on": true,
    "timeout_on": false,
    // ... other config ...
}
```

#### 2. **Simplified Task Implementation**

Tasks now run indefinitely - orchestrator controls when they stop:

**Radio Alarm (NEW):**
```python
def play_radio(self, stream_url, radio_name, stop_event):
    """Duration is controlled by orchestrator via max_duration or .terminate files."""
    # ... VLC setup ...
    player.play()

    # Play until stop_event is set by the orchestrator
    while not stop_event.is_set():
        time.sleep(1)  # Check every second

    print(f"{time.strftime('%H:%M')} - Stop event received, stopping radio")
```

**Sleep Sounds (NEW):**
```python
def loop_indefinitely(self, audio_path, stop_event):
    """Duration is controlled by orchestrator via max_duration or .terminate files."""
    # ... VLC setup ...
    list_player.play()

    try:
        # Loop until stop_event is set by the orchestrator
        while not stop_event.is_set():
            time.sleep(2)
        self.logger.info("Stop event received, stopping sleep sounds")
    finally:
        list_player.stop()
```

#### 3. **Thread-Based Monitoring in Orchestrator**

Created `_execute_task_with_monitoring()` method in `task.py`:

```python
def _execute_task_with_monitoring(self):
    """
    Execute the task in a thread and monitor for max_duration and .terminate files.
    """
    logger = logging.getLogger(__name__)

    # Clear the stop event for this execution
    self.stop_event.clear()

    # Start task in a separate thread, passing the stop_event
    task_thread = threading.Thread(
        target=self.task_module.thread_loop,
        args=(self.stop_event,),
        daemon=True
    )
    task_thread.start()

    # Get max_duration from config
    max_duration = self.config.get('max_duration', None)
    start_time = datetime.now()

    # Monitor the task execution
    while task_thread.is_alive():
        # Check for .terminate files
        terminate_file = os.path.join(self.root_dir, f'{os.path.basename(self.task_name)}.terminate')
        all_terminate_file = os.path.join(self.root_dir, 'all.terminate')

        if os.path.exists(terminate_file) or os.path.exists(all_terminate_file):
            logger.info(f"MONITORING: TERMINATE FILE DETECTED!")
            # Signal the task to stop
            self.stop_event.set()
            # Wait for graceful shutdown
            task_thread.join(timeout=5)
            logger.info(f"MONITORING: Task thread stopped successfully!")
            return True  # Signal termination

        # Check max_duration if specified
        if max_duration and (datetime.now() - start_time).total_seconds() > max_duration:
            logger.info(f"MONITORING: MAX_DURATION REACHED!")
            # Signal the task to stop
            self.stop_event.set()
            # Wait for graceful shutdown
            task_thread.join(timeout=5)
            logger.info(f"MONITORING: Task thread stopped successfully!")
            return False  # Normal completion

        # Check every second
        yield [pyRTOS.timeout(1)]

    return False
```

## Problem with First Attempt (This Branch - Before Fix)

When we first moved to the thread-based approach, we had a critical bug:

```python
# BROKEN VERSION (what we started with)
def _execute_task_with_monitoring(self):
    task_thread = threading.Thread(target=self.task_module.thread_loop, daemon=True)
    task_thread.start()

    while task_thread.is_alive():
        if os.path.exists(terminate_file):
            logger.info("Terminate signal received")
            return True  # ❌ Returns but thread keeps running!

        yield [pyRTOS.timeout(1)]
```

**Problem:** Daemon threads don't stop automatically when the monitoring function returns!

### Flow of Broken Version:
1. Task starts in daemon thread with `while True: time.sleep(1)` ✓
2. Monitoring loop checks for `.terminate` file every second ✓
3. Monitoring detects file and returns `True` ✓
4. **Daemon thread keeps running** ❌ (infinite loop doesn't check anything)
5. Audio/task continues indefinitely

## Final Solution: threading.Event() Pattern

### How It Works Now

1. **Task class creates stop event:**
   ```python
   def __init__(self, task_file, debug=False):
       # ... other init ...
       self.stop_event = threading.Event()
   ```

2. **Pass event to task:**
   ```python
   task_thread = threading.Thread(
       target=self.task_module.thread_loop,
       args=(self.stop_event,),  # Pass the event
       daemon=True
   )
   ```

3. **Task checks event in its loop:**
   ```python
   def thread_loop(stop_event):
       while not stop_event.is_set():  # Check event every iteration
           time.sleep(1)
   ```

4. **Monitoring signals and waits:**
   ```python
   if terminate_file_detected:
       self.stop_event.set()           # Signal task to stop
       task_thread.join(timeout=5)     # Wait for graceful shutdown
   ```

### New Flow (Fixed):
1. Task class creates `self.stop_event = threading.Event()`
2. Pass `stop_event` to task's `thread_loop(stop_event)` function
3. Task checks `while not stop_event.is_set():` in its loop
4. Monitoring detects `.terminate` file or `max_duration` reached
5. Monitoring calls `self.stop_event.set()`
6. Monitoring waits with `task_thread.join(timeout=5)`
7. Task sees event is set and exits gracefully ✓
8. Monitoring confirms thread stopped ✓

## Summary of Changes from main Branch

### Core Framework (src/task/task.py)
- ✅ Fixed `root_dir` calculation (3 levels up instead of 2)
- ✅ Added `self.stop_event = threading.Event()`
- ✅ Created `_execute_task_with_monitoring()` method
- ✅ Pass `stop_event` to tasks
- ✅ Monitor every second for terminate files AND max_duration
- ✅ Set event and wait for graceful shutdown
- ✅ Moved terminate checking INSIDE task execution (not after)

### Tasks
**radio_alarm.py:**
- ✅ Renamed: `play_radio_for_one_hour()` → `play_radio()`
- ✅ Removed: `time.sleep(3600)` hardcoded duration
- ✅ Added: `stop_event` parameter to all functions
- ✅ Changed: `while True:` → `while not stop_event.is_set():`
- ✅ Duration now in `trigger.json`: `"max_duration": 3600`

**sleep_sounds.py:**
- ✅ Renamed: `loop_until_stop()` → `loop_indefinitely()`
- ✅ Removed: `stop_dt` calculation and `while datetime.now() < stop_dt`
- ✅ Added: `stop_event` parameter to all functions
- ✅ Changed: `while datetime.now() < stop_dt:` → `while not stop_event.is_set():`
- ✅ Duration now in `trigger.json`: `"max_duration": 12600` (replaces stop_time calculation)

### Trigger Configurations
Both task trigger.json files now have:
```json
{
    "max_duration": <seconds>,  // NEW - controls how long task runs
    "schedule_on": true/false,
    "timeout_on": true/false,
    // ... other config ...
}
```

## Benefits of New Architecture

### Separation of Concerns
- **Tasks:** Simple, just play audio until told to stop
- **Orchestrator:** Decides when to stop (via max_duration or .terminate files)
- **Configuration:** Duration is in JSON, not code

### Immediate Response
- **Old:** Terminate files only checked between task runs (could be hours!)
- **New:** Terminate files checked every second, tasks stop within 1 second

### Flexibility
- **Old:** Change duration = change code and restart service
- **New:** Change duration = edit JSON and wait for next run

### Graceful Shutdown
- **Old:** Abrupt termination (if it worked at all)
- **New:** Tasks clean up properly (stop VLC, release resources, etc.)

## Testing Results

### Test 1: Terminate File Detection ✅
```bash
python3 debug_runner.py debug_test
touch debug_test.terminate
```

**Result:**
```
MONITORING: TERMINATE FILE DETECTED!
MONITORING: Setting stop_event to signal task thread...
DEBUG TASK: stop_event is SET! I will exit now!
DEBUG TASK: stop_event detected! Exiting gracefully...
MONITORING: Task thread stopped successfully!
```
**Time to stop:** < 1 second

### Test 2: max_duration ✅
Debug task configured with `max_duration: 30` seconds:
```
MONITORING: MAX_DURATION REACHED!
MONITORING: Elapsed: 30.1s, max_duration: 30s
MONITORING: Setting stop_event to signal task thread...
MONITORING: Task thread stopped successfully!
```

## Files Modified

### Core Framework
- **src/task/task.py** - Complete rewrite of task execution and monitoring

### Production Tasks
- **tasks/radio_alarm/radio_alarm.py** - Simplified, accepts stop_event
- **tasks/sleep_sounds/sleep_sounds.py** - Simplified, accepts stop_event
- **tasks/helloworld/helloworld.py** - Updated signature for consistency

### Configuration
- **tasks/radio_alarm/trigger.json** - Added `max_duration: 3600`
- **tasks/sleep_sounds/trigger.json** - Added `max_duration: 12600`

### New Files
- **tasks/debug_test/** - Debug task for testing
- **debug_runner.py** - Run single tasks for testing
- **context/terminate_fix_implementation.md** - This document

## Usage

### Terminating a Running Task

**Option 1: Task-specific termination**
```bash
cd /path/to/raspautomator
touch radio_alarm.terminate
```

**Option 2: Terminate all tasks**
```bash
cd /path/to/raspautomator
touch all.terminate
```

**Result:** Task stops within 1 second

### Configuring Task Duration

Edit the task's `trigger.json`:
```json
{
    "max_duration": 3600,  // Duration in seconds
    // ... other config ...
}
```

### Creating New Tasks

All tasks **must** accept `stop_event` parameter:

```python
def thread_loop(stop_event):
    """
    Task code here.

    Args:
        stop_event: threading.Event() that signals when to stop
    """
    # Initialization...

    # Main loop - MUST check stop_event
    while not stop_event.is_set():
        # Your task logic here
        time.sleep(1)

    # Cleanup code here
    print("Task stopping gracefully")
```

## Key Takeaways

1. **Orchestrator controls duration** - Tasks don't know or care how long they run
2. **Cooperative shutdown** - Tasks check `stop_event` and exit gracefully
3. **Responsive termination** - Terminate files work within 1 second
4. **Configurable duration** - Change max_duration in JSON, not code
5. **Proper cleanup** - Tasks have time to release resources before stopping
