# RaspAutomator Task Configuration Editor

A modern dark-themed GUI application for editing task configurations.

## Features

- **Tabbed Interface**: One tab per task, automatically discovered from `tasks/` folder
- **Dark Theme**: Modern dark mode interface
- **Smart Controls**:
  - ✅ **Checkboxes** for boolean values (schedule_on, timeout_on)
  - 🕐 **Time Picker** for time_of_day (HH:mm format)
  - 📅 **Day Selector** with individual checkboxes for each day of the week
  - 🔢 **Spin Boxes** for numeric values (timeout_interval, max_duration) with units displayed
- **Real-time Editing**: Load current values, edit, and save back to JSON
- **Validation**: Input validation and error handling

## Requirements

```bash
# Install PyQt6
pip install PyQt6
```

## Usage

### Run from GUI directory:
```bash
cd gui
python3 task_config_editor.py
```

### Or run from project root:
```bash
python3 gui/task_config_editor.py
```

## Interface Overview

### Main Window
- **Header**: Application title with emoji
- **Tabs**: One tab for each task in `tasks/` folder
- **Footer**: Instructions for users

### Each Task Tab Contains:

#### Scheduling Configuration
- **Schedule Enabled**: Enable/disable scheduled execution
- **Time of Day**: Time picker (24-hour format HH:mm)
- **Days of Week**: Individual checkboxes for Mon-Sun

#### Timeout Configuration
- **Timeout Enabled**: Enable/disable repeated execution
- **Timeout Interval**: Seconds between executions (1-86400)

#### Duration Configuration
- **Max Duration**: Maximum runtime in seconds (0 = no limit)

#### Actions
- **💾 Save Configuration**: Saves changes to the task's trigger.json file

## How It Works

1. **Discovery**: Scans `tasks/` directory for subdirectories with `trigger.json` files
2. **Loading**: Reads each trigger.json and creates a tab
3. **Editing**: All controls are bound to JSON fields
4. **Saving**: Writes changes back to trigger.json with proper formatting

## JSON Fields Mapping

| JSON Field | Control Type | Notes |
|------------|--------------|-------|
| `schedule_on` | Checkbox | Boolean |
| `timeout_on` | Checkbox | Boolean |
| `time_of_day` | Time Edit | HH:mm format |
| `days_of_week` | Day Selector | Array of day names |
| `timeout_interval` | Spin Box | 1-86400 seconds |
| `max_duration` | Spin Box | 0-86400 seconds (0 = no limit) |

## Notes

- Changes are saved immediately when you click the Save button
- The application validates input ranges automatically
- Spin boxes show units ("seconds") for clarity
- Max duration of 0 means "no limit" and won't be saved to JSON
- Days of week selector uses 3-letter abbreviations (Mon, Tue, etc.) with full names in tooltips

## Troubleshooting

**No tasks appear:**
- Ensure you're running from the project directory
- Check that tasks have `trigger.json` files

**PyQt6 not found:**
```bash
pip install PyQt6
```

**Permission denied:**
```bash
chmod +x gui/task_config_editor.py
```
