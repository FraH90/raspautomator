import glob
import os
import pyRTOS
import time
import logging
from task import Task
from config_watcher import ConfigWatcher

logger = logging.getLogger(__name__)

class Orchestrator:
    # Future idea: insert in the orchestrator object the list of all the tasks (as objects) present in the folder
    def __init__(self, tasks_root_folder):
        self.tasks_root_folder = tasks_root_folder
        self.task_files = self.discover_task_files()
        self.config_watcher = None

    # Get a list of all task scripts in the current directory and subdirectories
    def discover_task_files(self):
        task_files = []
        for root, dirs, files in os.walk(self.tasks_root_folder):
            for dir_name in dirs:
                task_file = os.path.join(root, dir_name, f"{dir_name}.py")
                if os.path.isfile(task_file):
                    task_files.append(task_file)
        return task_files
    
    def run(self):
        # Delete all the .terminate files in the tasks folder (otherwise tasks won't restart)
        terminate_list = glob.glob(os.path.join(self.tasks_root_folder, "*.terminate"))
        for terminate_item in terminate_list:
            os.remove(terminate_item)

        # Start the config watcher to monitor trigger.json files
        self.config_watcher = ConfigWatcher(self.tasks_root_folder)
        self.config_watcher.start()

        # Create a robust wrapper for each task, then add to pyRTOS
        for task_file in self.task_files:
            pyRTOS.add_task(self._create_robust_pyRTOS_task(task_file))
        # Add a service routine to slow down the execution
        pyRTOS.add_service_routine(lambda: time.sleep(0.1))

        try:
            # Start pyRTOS
            pyRTOS.start()
        finally:
            # Stop the config watcher when pyRTOS exits
            if self.config_watcher:
                self.config_watcher.stop()

    def run_task_debug(self, task_name):
        """Run a specific task in debug mode"""
        # Find the task file
        task_file = None
        for root, dirs, files in os.walk(self.tasks_root_folder):
            for dir_name in dirs:
                if dir_name == task_name:
                    task_file = os.path.join(root, dir_name, f"{dir_name}.py")
                    break
            if task_file:
                break

        if not task_file:
            raise ValueError(f"Task {task_name} not found")

        # Create that task in debug mode and add it
        def debug_wrapper(self_task):
            while True:
                # Re-instantiate a Task object each time we “restart”
                task_instance = Task(task_file, debug=True)
                try:
                    yield from task_instance.run(self_task)
                except Exception as e:
                    logger.error(f"Task {task_name} crashed in debug mode: {e}")
                    # Wait 5s, then restart
                    yield [pyRTOS.timeout(5)]
                    continue
                else:
                    # If it exits normally, break from the loop
                    break
        
        pyRTOS.add_task(pyRTOS.Task(debug_wrapper, name=task_name))
        pyRTOS.add_service_routine(lambda: time.sleep(0.1))
        pyRTOS.start()

    
    def _create_robust_pyRTOS_task(self, task_file):
        """
        Returns a pyRTOS.Task whose generator re-creates and re-runs `Task(task_file)`
        if it crashes with an unhandled exception.
        """
        task_name = os.path.basename(os.path.dirname(task_file)) or "unknown_task"

        def robust_task_generator(self_task):
            """A generator that wraps the real Task.run in a try/except loop."""
            while True:
                # Each loop iteration, we create a fresh Task object
                task_instance = Task(task_file)
                try:
                    # The user’s actual code
                    yield from task_instance.run(self_task)
                except Exception as e:
                    logger.error(f"Task {task_name} crashed: {e}")
                    logger.info(f"Restarting {task_name} in 5 seconds...")
                    # Wait 5s before attempting to restart
                    yield [pyRTOS.timeout(5)]
                    continue
                else:
                    # If the task's generator exits cleanly (or finds a .terminate), we stop
                    break
        
        return pyRTOS.Task(robust_task_generator, name=task_name)
    