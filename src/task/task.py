import os
import importlib.util
import pyRTOS
from datetime import datetime, timedelta
import json
from .bluetooth_handler import BluetoothHandler  # Import it in Task class
import logging
import threading

class Task:
    def __init__(self, task_file, debug=False):
        # Initialize the task by setting the task name and importing the task module
        self.task_name = os.path.dirname(task_file)
        self.task_module = self.import_task_module(task_file)
        self.root_dir = os.path.dirname(os.path.dirname(task_file))
        self.config = self.load_trigger_config()
        self.debug = debug  # Store debug mode
        
        # Initialize BluetoothHandler as a class property
        self.bluetooth = None

    def setup_bluetooth(self, mac_address):
        """Initialize bluetooth handler with given MAC address"""
        self.bluetooth = BluetoothHandler(mac_address)
        return self.bluetooth

    def import_task_module(self, module_path):
        # Dynamically import the task module from the given path
        module_name = os.path.basename(module_path).replace(".py", "")
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def load_trigger_config(self):
        config_path = os.path.join(os.path.dirname(self.task_module.__file__), 'trigger.json')
        with open(config_path, 'r') as f:
            return json.load(f)
        
    def setup(self):
        # Execute the setup function of the task module to initialize the task
        # The timeout of each specific task and the schedule are returned by the setup function
        self.task_timeout, self.schedule = self.task_module.setup()
        self.next_run = self.next_run_time(self.schedule)

    def calculate_next_run(self):
        if not self.config['schedule_on']:
            return datetime.now()  # Next run is "now" if scheduling is off
        now = datetime.now()
        time_of_day = datetime.strptime(self.config['time_of_day'], "%H:%M").time()
        next_run = datetime.combine(now.date(), time_of_day)
        while next_run <= now or next_run.strftime("%A") not in self.config['days_of_week']:
            next_run += timedelta(days=1)
        return next_run

    def should_run(self):
        # If in debug mode, always run
        if self.debug:
            return True
            
        # Normal schedule checking logic
        if not self.config.get('schedule_on', False):
            return True

        current_time = datetime.now()
        current_day = current_time.strftime('%A')
        current_hour = current_time.strftime('%H:%M')

        scheduled_days = self.config.get('days_of_week', [])
        scheduled_time = self.config.get('time_of_day', '')

        return current_day in scheduled_days and current_hour == scheduled_time

    def _execute_task_with_monitoring(self):
        """
        Execute the task in a thread and monitor for max_duration and .terminate files.
        Returns when the task completes, max_duration is reached, or .terminate file is found.
        """
        # Start task in a separate thread
        task_thread = threading.Thread(target=self.task_module.thread_loop, daemon=True)
        task_thread.start()

        # Get max_duration from config (optional parameter)
        max_duration = self.config.get('max_duration', None)
        start_time = datetime.now()

        # Monitor the task execution
        while task_thread.is_alive():
            # Check for .terminate files
            terminate_file = os.path.join(self.root_dir, f'{os.path.basename(self.task_name)}.terminate')
            all_terminate_file = os.path.join(self.root_dir, 'all.terminate')

            if os.path.exists(terminate_file) or os.path.exists(all_terminate_file):
                logger = logging.getLogger(__name__)
                logger.info(f"Terminate signal received for task {os.path.basename(self.task_name)}")
                # Task will stop on its own since we're using daemon threads
                return True  # Signal termination

            # Check max_duration if specified
            if max_duration and (datetime.now() - start_time).total_seconds() > max_duration:
                logger = logging.getLogger(__name__)
                logger.info(f"Task {os.path.basename(self.task_name)} reached max_duration of {max_duration}s")
                # Task will stop on its own since we're using daemon threads
                return False  # Normal completion

            # Brief sleep to avoid busy-waiting
            yield [pyRTOS.timeout(1)]

        # Task completed naturally
        return False

    def run(self, self_task):
        # If in debug mode, run immediately and continuously
        if self.debug:
            while True:
                # Execute task with monitoring in debug mode
                yield from self._execute_task_with_monitoring()
                yield [pyRTOS.timeout(1)]  # Small delay to prevent CPU hogging

        # Normal scheduling logic for non-debug mode
        next_run = self.calculate_next_run()
        yield

        while True:
            now = datetime.now()
            # If both scheduling and timeout are false, the task must not be executed.
            # Put it to sleep for 10 seconds
            if self.config['schedule_on']==False and self.config['timeout_on']==False:
                sleep_time = 10
                yield [pyRTOS.timeout(sleep_time)]
                continue
            # If scheduling is enabled, sleep until the next run time
            if self.config['schedule_on']:
                if now < next_run:
                    sleep_time = (next_run - now).total_seconds()
                    yield [pyRTOS.timeout(sleep_time)]
                    continue
                # Execute the main thread of the task with monitoring
                terminated = yield from self._execute_task_with_monitoring()
                if terminated:
                    return  # Exit if .terminate file was found

                if self.config['timeout_on']:
                    # Set next_run to be timeout_interval from now
                    next_run = now + timedelta(seconds=self.config['timeout_interval'])
                else:
                    # If timeout is off, calculate the next scheduled run
                    next_run = self.calculate_next_run()
            else:
                # If schedule is off and timeout is on, always execute
                terminated = yield from self._execute_task_with_monitoring()
                if terminated:
                    return  # Exit if .terminate file was found

            if self.config['timeout_on']:
                yield [pyRTOS.timeout(self.config['timeout_interval'])]
            else:
                yield