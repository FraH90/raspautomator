"""
Configuration file watcher for RaspAutomator
Monitors trigger.json files for changes and reloads configurations dynamically
"""

import os
import json
import time
import logging
from threading import Thread
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)


class TaskRegistry:
    """
    Shared registry to store Task instances so the file watcher
    can update their configurations when files change.
    """
    _tasks = {}  # task_name -> Task instance

    @classmethod
    def register(cls, task_name, task_instance):
        """Register a Task instance"""
        cls._tasks[task_name] = task_instance
        logger.info(f"Registered task '{task_name}' in registry")

    @classmethod
    def get(cls, task_name):
        """Get a Task instance by name"""
        return cls._tasks.get(task_name)

    @classmethod
    def list_tasks(cls):
        """List all registered task names"""
        return list(cls._tasks.keys())


class ConfigFileHandler(FileSystemEventHandler):
    """Handles file system events for trigger.json and config.json files"""

    def __init__(self, tasks_dir):
        super().__init__()
        self.tasks_dir = tasks_dir

    def on_modified(self, event):
        """Called when a file is modified"""
        if event.is_directory:
            return

        filename = os.path.basename(event.src_path)

        # Check if it's a trigger.json file
        if filename == "trigger.json":
            self._reload_trigger_config(event.src_path)
        # Check if it's a config.json file
        elif filename == "config.json":
            self._reload_task_config(event.src_path)

    def _reload_trigger_config(self, config_path):
        """Reload trigger.json configuration for a specific task"""
        try:
            # Get task name from path (parent directory name)
            task_dir = os.path.dirname(config_path)
            task_name = os.path.basename(task_dir)

            # Load new configuration
            with open(config_path, 'r') as f:
                new_config = json.load(f)

            # Get the task instance from registry
            task_instance = TaskRegistry.get(task_name)
            if task_instance:
                # Update the task's trigger configuration
                old_config = task_instance.config.copy()
                task_instance.config = new_config

                logger.info(f"📝 Trigger configuration reloaded for task '{task_name}'")

                # Log what changed
                changes = []
                for key in new_config:
                    if old_config.get(key) != new_config.get(key):
                        changes.append(f"{key}: {old_config.get(key)} → {new_config.get(key)}")

                if changes:
                    logger.info(f"   Changes: {', '.join(changes)}")
                else:
                    logger.info("   (No changes detected)")

            else:
                logger.warning(f"Task '{task_name}' not found in registry, skipping reload")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {config_path}: {e}")
        except Exception as e:
            logger.error(f"Error reloading trigger config for {config_path}: {e}")

    def _reload_task_config(self, config_path):
        """
        Log when config.json is modified.
        These changes (volume, bluetooth, etc.) will take effect on the next task execution.
        """
        try:
            # Get task name from path (parent directory name)
            task_dir = os.path.dirname(config_path)
            task_name = os.path.basename(task_dir)

            # Load and validate the new configuration
            with open(config_path, 'r') as f:
                new_config = json.load(f)

            logger.info(f"🔧 Task config.json modified for '{task_name}'")

            # Log relevant changes if volume settings are present
            if 'volume' in new_config:
                volume = new_config['volume']
                logger.info(f"   Volume settings: System={volume.get('system_volume', 'N/A')}%, "
                          f"VLC={volume.get('vlc_volume', 'N/A')}%")

            logger.info(f"   → Changes will apply on next task execution")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {config_path}: {e}")
        except Exception as e:
            logger.error(f"Error processing config.json change for {config_path}: {e}")


class ConfigWatcher:
    """
    Watches the tasks directory for changes to trigger.json and config.json files
    and automatically reloads configurations.

    - trigger.json changes: Applied immediately (affects scheduling)
    - config.json changes: Applied on next task execution (affects task behavior like volume)
    """

    def __init__(self, tasks_dir):
        self.tasks_dir = tasks_dir
        self.observer = None
        self.running = False

    def start(self):
        """Start watching for configuration changes"""
        if self.running:
            logger.warning("Config watcher is already running")
            return

        try:
            self.observer = Observer()
            event_handler = ConfigFileHandler(self.tasks_dir)

            # Watch the tasks directory recursively
            self.observer.schedule(event_handler, self.tasks_dir, recursive=True)
            self.observer.start()

            self.running = True
            logger.info(f"🔍 Config watcher started, monitoring: {self.tasks_dir}")

        except Exception as e:
            logger.error(f"Failed to start config watcher: {e}")
            logger.info("Tasks will continue with static configurations")

    def stop(self):
        """Stop watching for configuration changes"""
        if self.observer and self.running:
            self.observer.stop()
            self.observer.join()
            self.running = False
            logger.info("Config watcher stopped")

    def __del__(self):
        """Cleanup when object is destroyed"""
        self.stop()
