# RaspAutomator

RaspAutomator is a Python-based task scheduling system designed for Raspberry Pi and other Linux environments. It provides a simple yet powerful framework for running automated, recurring tasks such as a morning radio alarm or a sleep sounds player.

The core of the automator uses a lightweight, cooperative multitasking approach to manage and run multiple tasks concurrently, with each task's schedule and behavior defined by simple JSON configuration files.

## Features

*   **Flexible Task Scheduling**: Configure tasks to run on specific days of the week and at specific times.
*   **Continuous & Recurring Tasks**: Supports tasks that run once per scheduled time or repeat at a defined interval.
*   **Dynamic Task Loading**: Automatically discovers and runs tasks placed in the `tasks` directory.
*   **Task termination**: A task can be terminated by placing a .terminate file into the task directory, or a all.terminate file (where?)
*   **Bluetooth Speaker Integration**: Built-in handler to connect to Bluetooth audio devices before running a task.
*   **Service-based Installation**: Includes an installer to set up the automator as a `systemd` user service, ensuring it runs on boot and restarts automatically on failure.
*   **Modular Design**: Each task is self-contained in its own directory, making it easy to add, remove, or modify tasks.

## Prerequisites

Before you begin, ensure your system (e.g., Raspberry Pi OS) has the following dependencies installed.

### 1. Install required components

These packages are required for audio playback, Bluetooth connectivity, and downloading media.

```bash
# Install VLC, Bluetooth tools, and other utilities (required for audio playback and Bluetooth connectivity)
sudo apt install -y vlc bluez python3-pip

# Python packages
sudo apt install python3-vlc python3-psutil

# yt-dlp (installed through pipx for system-wide access without conflicts)
sudo apt install pipx
pipx ensurepath
pipx install yt-dlp

```

## 2. Installation

The included `installer.py` script automates the process of setting up RaspAutomator to run as a background service.

1.  **Clone the Repository, install the scripts**

    ```bash
    cd /Documents
    mkdir myservices
    cd /myservices
    git clone https://github.com/FraH90/raspautomator
    cd raspautomator
    
    # Make scripts executable and run the installer (WITHOUT SUDO OR IT WILL THROW ERROR!)
    chmod +x installer.sh automator.sh
    ./installer.sh
    ```

    The installation script will:
    *   Locate the `automator.sh` script.
    *   Create a `systemd` user service file (`~/.config/systemd/user/automator.service`).
    *   Enable the service to start on boot (`loginctl enable-linger`).
    *   Reload, enable, and start the service.

### Managing the Service

Once installed, you can manage the RaspAutomator service with standard `systemctl` commands:

*   **Check Status**: `systemctl --user status automator.service`
*   **View Logs**: `journalctl --user -u automator.service -f`
*   **Stop Service**: `systemctl --user stop automator.service`
*   **Start Service**: `systemctl --user start automator.service`
*   **Restart Service**: `systemctl --user restart automator.service`

Logs are also appended to `logs/output.out` in the project directory.

## Configuration

Each task is configured through JSON files within its directory (`tasks/<task_name>/`).

### Task Scheduling (`trigger.json`)

This file controls when and how a task runs.

*   `schedule_on`: If `true`, the task runs on the schedule defined by `days_of_week` and `time_of_day`. If `false`, it runs continuously (respecting `timeout_on`).
*   `timeout_on`: If `true`, the task repeats every `timeout_interval` seconds after its first run. If `false`, it runs only once per scheduled time.
*   `days_of_week`: A list of days to run the task (e.g., `"Monday"`, `"Tuesday"`).
*   `time_of_day`: The time to run the task in `HH:MM` format.
*   `timeout_interval`: The delay in seconds between repeated executions.

### Task-Specific Settings (`config.json`)

This file contains settings specific to the task's logic, such as API keys or device addresses. For the included tasks, this is where you set your Bluetooth speaker's MAC address.

## Production-Ready Tasks

The following tasks are located in the `tasks/` directory and are ready for use.

### 1. Radio Alarm

**Directory**: `tasks/radio_alarm/`

This task connects to a specified Bluetooth speaker and plays a random online radio stream for one hour. It's designed to function as a morning alarm clock.

**Configuration**:
*   `tasks/radio_alarm/config.json`: Set the `mac_address` of your Bluetooth speaker.
*   `tasks/radio_alarm/radio_stations.json`: Add or remove radio stream URLs.
*   `tasks/radio_alarm/trigger.json`: Configure the alarm schedule (e.g., weekdays at 08:00).

### 2. Sleep Sounds

**Directory**: `tasks/sleep_sounds/`

This task connects to a Bluetooth speaker, picks a random YouTube video from a list (e.g., rain sounds, white noise), and loops the audio until a specified stop time. It caches the audio locally to avoid re-downloading.

**Configuration**:
*   `tasks/sleep_sounds/config.json`:
    *   Set the `mac_address` of your Bluetooth speaker.
    *   Set the `stop_time` when the audio should stop playing (e.g., "23:30").
*   `tasks/sleep_sounds/sleep_sounds_sources.json`: Add or remove YouTube URLs for the sleep sounds.
*   `tasks/sleep_sounds/trigger.json`: Configure when the sleep sounds should start.

## How to Create a New Task

1.  Create a new folder inside the `tasks/` directory (e.g., `my_new_task`).
2.  Inside it, create a `trigger.json` file to define its schedule.
3.  Create a Python script that contains the core logic. It must have a `thread_loop()` function, which will be called by the scheduler.
4.  If your task requires specific configuration (like API keys or MAC addresses), create a `config.json` file.
5.  The automator will automatically detect and run your new task on the next restart.
