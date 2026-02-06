#!/usr/bin/env python3
"""
RaspAutomator Task Configuration Editor
A modern dark-themed GUI for editing task trigger.json files
"""

import sys
import os
import json
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QCheckBox, QTimeEdit, QSpinBox,
    QPushButton, QGroupBox, QMessageBox, QFormLayout, QSlider,
    QScrollArea, QFrame, QPlainTextEdit
)
from PyQt6.QtCore import Qt, QTime
from PyQt6.QtGui import QPalette, QColor, QFont


class DaySelector(QWidget):
    """Custom widget for selecting days of the week"""
    def __init__(self):
        super().__init__()
        self.days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        self.checkboxes = {}
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        for day in self.days:
            checkbox = QCheckBox(day[:3])  # Mon, Tue, Wed, etc.
            checkbox.setToolTip(day)
            self.checkboxes[day] = checkbox
            layout.addWidget(checkbox)

        self.setLayout(layout)

    def set_selected_days(self, days):
        """Set which days are selected"""
        for day in self.days:
            self.checkboxes[day].setChecked(day in days)

    def get_selected_days(self):
        """Get list of selected days"""
        return [day for day in self.days if self.checkboxes[day].isChecked()]


class ScheduleRow(QWidget):
    """A single schedule row with day selector, time picker, and remove button"""
    def __init__(self, on_remove=None):
        super().__init__()
        self._on_remove = on_remove
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 2, 0, 2)

        # Time picker
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setFixedWidth(80)
        layout.addWidget(self.time_edit)

        # Day selector
        self.days_selector = DaySelector()
        layout.addWidget(self.days_selector)

        # Remove button
        self.remove_button = QPushButton("X")
        self.remove_button.setFixedWidth(30)
        self.remove_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                border-radius: 3px;
                padding: 2px;
            }
            QPushButton:hover { background-color: #da190b; }
        """)
        self.remove_button.setToolTip("Remove this schedule")
        self.remove_button.clicked.connect(self._remove)
        layout.addWidget(self.remove_button)

        self.setLayout(layout)

    def _remove(self):
        if self._on_remove:
            self._on_remove(self)

    def set_data(self, days, time_str):
        """Load data into the row"""
        self.days_selector.set_selected_days(days)
        hour, minute = map(int, time_str.split(":"))
        self.time_edit.setTime(QTime(hour, minute))

    def get_data(self):
        """Extract data from the row"""
        return {
            "days": self.days_selector.get_selected_days(),
            "time": self.time_edit.time().toString("HH:mm")
        }


class TaskConfigTab(QWidget):
    """Tab for editing a single task's configuration"""
    def __init__(self, task_name, task_path, trigger_data, task_config_data):
        super().__init__()
        self.task_name = task_name
        self.task_path = task_path
        self.trigger_file = os.path.join(task_path, "trigger.json")
        self.task_config_file = os.path.join(task_path, "config.json")
        self.trigger_data = trigger_data
        self.task_config_data = task_config_data
        self.schedule_rows = []
        self.init_ui()
        self.load_config()

    def init_ui(self):
        main_layout = QVBoxLayout()

        # Task info
        info_label = QLabel(f"<h3>Task: {self.task_name}</h3>")
        info_label.setStyleSheet("color: #4CAF50; padding: 10px;")
        main_layout.addWidget(info_label)

        # Scheduling group
        schedule_group = QGroupBox("Scheduling Configuration")
        schedule_outer_layout = QVBoxLayout()

        # Schedule On/Off
        schedule_toggle_layout = QHBoxLayout()
        schedule_toggle_layout.addWidget(QLabel("Schedule Enabled:"))
        self.schedule_on = QCheckBox()
        schedule_toggle_layout.addWidget(self.schedule_on)
        schedule_toggle_layout.addStretch()
        schedule_outer_layout.addLayout(schedule_toggle_layout)

        # Schedule rows container
        self.schedules_container = QVBoxLayout()
        self.schedules_container.setSpacing(4)
        schedule_outer_layout.addLayout(self.schedules_container)

        # Add schedule button
        add_schedule_btn = QPushButton("+ Add Schedule")
        add_schedule_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 6px 16px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1976D2; }
        """)
        add_schedule_btn.clicked.connect(self.add_schedule_row)
        schedule_outer_layout.addWidget(add_schedule_btn)

        schedule_group.setLayout(schedule_outer_layout)
        main_layout.addWidget(schedule_group)

        # Timeout group
        timeout_group = QGroupBox("Timeout Configuration")
        timeout_layout = QFormLayout()

        # Timeout On/Off
        self.timeout_on = QCheckBox()
        timeout_layout.addRow("Timeout Enabled:", self.timeout_on)

        # Timeout Interval (seconds)
        self.timeout_interval = QSpinBox()
        self.timeout_interval.setRange(1, 86400)  # 1 second to 24 hours
        self.timeout_interval.setSuffix(" seconds")
        self.timeout_interval.setToolTip("Time between task executions when timeout is enabled")
        timeout_layout.addRow("Timeout Interval:", self.timeout_interval)

        timeout_group.setLayout(timeout_layout)
        main_layout.addWidget(timeout_group)

        # Duration group
        duration_group = QGroupBox("Duration Configuration")
        duration_layout = QFormLayout()

        # Max Duration (seconds)
        self.max_duration = QSpinBox()
        self.max_duration.setRange(0, 86400)  # 0 to 24 hours
        self.max_duration.setSuffix(" seconds")
        self.max_duration.setSpecialValueText("No limit")
        self.max_duration.setToolTip("Maximum time the task should run (0 = no limit)")
        duration_layout.addRow("Max Duration:", self.max_duration)

        duration_group.setLayout(duration_layout)
        main_layout.addWidget(duration_group)

        # Volume group (only show if config.json has volume settings)
        volume_group = QGroupBox("Volume Configuration")
        volume_layout = QFormLayout()

        # System Volume slider with label showing value
        system_volume_container = QWidget()
        system_volume_layout = QHBoxLayout()
        system_volume_layout.setContentsMargins(0, 0, 0, 0)

        self.system_volume = QSlider(Qt.Orientation.Horizontal)
        self.system_volume.setRange(0, 100)
        self.system_volume.setSingleStep(5)
        self.system_volume.setPageStep(10)
        self.system_volume.setToolTip("System (PulseAudio) volume for Bluetooth speaker (0-100%)")

        self.system_volume_label = QLabel("70%")
        self.system_volume_label.setMinimumWidth(50)
        self.system_volume_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self.system_volume.valueChanged.connect(
            lambda v: self.system_volume_label.setText(f"{v}%")
        )

        system_volume_layout.addWidget(self.system_volume)
        system_volume_layout.addWidget(self.system_volume_label)
        system_volume_container.setLayout(system_volume_layout)
        volume_layout.addRow("System Volume:", system_volume_container)

        # VLC Volume slider with label showing value
        vlc_volume_container = QWidget()
        vlc_volume_layout = QHBoxLayout()
        vlc_volume_layout.setContentsMargins(0, 0, 0, 0)

        self.vlc_volume = QSlider(Qt.Orientation.Horizontal)
        self.vlc_volume.setRange(0, 100)
        self.vlc_volume.setSingleStep(5)
        self.vlc_volume.setPageStep(10)
        self.vlc_volume.setToolTip("VLC player volume (0-100%)")

        self.vlc_volume_label = QLabel("50%")
        self.vlc_volume_label.setMinimumWidth(50)
        self.vlc_volume_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self.vlc_volume.valueChanged.connect(
            lambda v: self.vlc_volume_label.setText(f"{v}%")
        )

        vlc_volume_layout.addWidget(self.vlc_volume)
        vlc_volume_layout.addWidget(self.vlc_volume_label)
        vlc_volume_container.setLayout(vlc_volume_layout)
        volume_layout.addRow("VLC Volume:", vlc_volume_container)

        volume_group.setLayout(volume_layout)
        main_layout.addWidget(volume_group)

        # Store reference to volume group so we can hide it if needed
        self.volume_group = volume_group

        # Buttons
        button_layout = QHBoxLayout()

        # Terminate button (extreme left)
        self.terminate_button = QPushButton("Terminate Task")
        self.terminate_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                padding: 10px 30px;
                font-size: 14px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #c1190b;
            }
        """)
        self.terminate_button.setToolTip("Create .terminate file to stop this task immediately")
        self.terminate_button.clicked.connect(self.terminate_task)
        button_layout.addWidget(self.terminate_button)

        # Stretch space in the middle
        button_layout.addStretch()

        # Save button (extreme right)
        self.save_button = QPushButton("Save Configuration")
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 10px 30px;
                font-size: 14px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        self.save_button.clicked.connect(self.save_config)
        button_layout.addWidget(self.save_button)

        main_layout.addLayout(button_layout)
        main_layout.addStretch()

        self.setLayout(main_layout)

    def add_schedule_row(self, days=None, time_str="08:00"):
        """Add a new schedule row to the UI"""
        row = ScheduleRow(on_remove=self.remove_schedule_row)
        if days:
            row.set_data(days, time_str)
        self.schedule_rows.append(row)
        self.schedules_container.addWidget(row)
        self._update_remove_buttons()
        return row

    def remove_schedule_row(self, row):
        """Remove a schedule row from the UI"""
        if len(self.schedule_rows) <= 1:
            return  # Keep at least one row
        self.schedule_rows.remove(row)
        self.schedules_container.removeWidget(row)
        row.deleteLater()
        self._update_remove_buttons()

    def _update_remove_buttons(self):
        """Hide remove button if only one schedule row remains"""
        for row in self.schedule_rows:
            row.remove_button.setVisible(len(self.schedule_rows) > 1)

    def load_config(self):
        """Load configuration from JSON data into UI controls"""
        # Schedule settings (from trigger.json)
        self.schedule_on.setChecked(self.trigger_data.get("schedule_on", False))

        # Load schedules (support both old and new format)
        if "schedules" in self.trigger_data:
            schedules = self.trigger_data["schedules"]
        elif "days_of_week" in self.trigger_data:
            # Old format: convert to schedules
            schedules = [{
                "days": self.trigger_data.get("days_of_week", []),
                "time": self.trigger_data.get("time_of_day", "00:00")
            }]
        else:
            schedules = [{"days": [], "time": "00:00"}]

        # Create schedule rows
        for schedule in schedules:
            self.add_schedule_row(
                days=schedule.get("days", []),
                time_str=schedule.get("time", "00:00")
            )

        # If no schedules loaded, add an empty one
        if not self.schedule_rows:
            self.add_schedule_row()

        # Timeout settings
        self.timeout_on.setChecked(self.trigger_data.get("timeout_on", False))
        self.timeout_interval.setValue(self.trigger_data.get("timeout_interval", 60))

        # Max duration
        self.max_duration.setValue(self.trigger_data.get("max_duration", 0))

        # Volume settings (from config.json)
        if self.task_config_data and "volume" in self.task_config_data:
            volume_config = self.task_config_data["volume"]
            self.system_volume.setValue(volume_config.get("system_volume", 70))
            self.vlc_volume.setValue(volume_config.get("vlc_volume", 50))
            self.volume_group.setVisible(True)
        else:
            # Hide volume group if not supported by this task
            self.volume_group.setVisible(False)

    def save_config(self):
        """Save configuration from UI controls to JSON files"""
        # Build schedules from rows
        schedules = [row.get_data() for row in self.schedule_rows]

        # Build trigger config dictionary (new format)
        trigger_config = {
            "schedule_on": self.schedule_on.isChecked(),
            "timeout_on": self.timeout_on.isChecked(),
            "schedules": schedules,
            "timeout_interval": self.timeout_interval.value()
        }

        # Only add max_duration if it's not 0
        max_dur = self.max_duration.value()
        if max_dur > 0:
            trigger_config["max_duration"] = max_dur

        # Save trigger.json
        try:
            with open(self.trigger_file, 'w') as f:
                json.dump(trigger_config, f, indent=4)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save trigger configuration:\n{str(e)}"
            )
            return

        # Save volume settings to config.json if it exists and has volume
        if self.task_config_data and self.volume_group.isVisible():
            try:
                # Update volume settings in task config
                if "volume" not in self.task_config_data:
                    self.task_config_data["volume"] = {}

                self.task_config_data["volume"]["system_volume"] = self.system_volume.value()
                self.task_config_data["volume"]["vlc_volume"] = self.vlc_volume.value()

                # Save updated config.json
                with open(self.task_config_file, 'w') as f:
                    json.dump(self.task_config_data, f, indent=4)

            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to save volume configuration:\n{str(e)}"
                )
                return

        reply = QMessageBox.question(
            self,
            "Configuration Saved",
            f"Configuration for '{self.task_name}' saved successfully!\n\n"
            "Do you want to restart the service to apply changes?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                result = subprocess.run(
                    ["systemctl", "--user", "restart", SERVICE_NAME],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    QMessageBox.information(self, "Success", "Service restarted successfully.")
                else:
                    QMessageBox.warning(
                        self, "Warning",
                        f"Service restart returned an error:\n{result.stderr.strip()}"
                    )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to restart service:\n{str(e)}")

    def terminate_task(self):
        """Create a .terminate file to stop the task immediately"""
        # Get the tasks directory (parent of task_path)
        tasks_dir = os.path.dirname(self.task_path)
        terminate_file = os.path.join(tasks_dir, f"{self.task_name}.terminate")

        # Confirm action
        reply = QMessageBox.question(
            self,
            "Terminate Task",
            f"This will stop the '{self.task_name}' task immediately.\n\nAre you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Create the terminate file
                with open(terminate_file, 'w') as f:
                    f.write("")  # Empty file

                QMessageBox.information(
                    self,
                    "Success",
                    f"Terminate signal sent to '{self.task_name}'.\n\n"
                    f"The task will stop within 1 second if it's running."
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to create terminate file:\n{str(e)}"
                )


SERVICE_NAME = "automator.service"


class ServiceTab(QWidget):
    """Tab for managing the automator systemd service"""
    def __init__(self, project_root):
        super().__init__()
        self.project_root = project_root
        self.log_file = os.path.join(project_root, "logs", "output.out")
        self.init_ui()
        self.refresh_status()
        self.refresh_logs()

    def init_ui(self):
        main_layout = QVBoxLayout()

        # --- Service Status ---
        status_group = QGroupBox("Service Status")
        status_layout = QVBoxLayout()

        self.status_label = QLabel("Checking...")
        self.status_label.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        status_layout.addWidget(self.status_label)

        refresh_status_btn = QPushButton("Refresh Status")
        refresh_status_btn.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                padding: 6px 16px;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #666; }
        """)
        refresh_status_btn.clicked.connect(self.refresh_status)
        status_layout.addWidget(refresh_status_btn)

        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)

        # --- Service Controls ---
        controls_group = QGroupBox("Service Controls")
        controls_layout = QHBoxLayout()

        start_btn = QPushButton("Start Service")
        start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; color: white;
                padding: 10px 20px; font-size: 14px;
                border-radius: 5px; font-weight: bold;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        start_btn.clicked.connect(lambda: self.service_action("start"))
        controls_layout.addWidget(start_btn)

        stop_btn = QPushButton("Stop Service")
        stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336; color: white;
                padding: 10px 20px; font-size: 14px;
                border-radius: 5px; font-weight: bold;
            }
            QPushButton:hover { background-color: #da190b; }
        """)
        stop_btn.clicked.connect(lambda: self.service_action("stop"))
        controls_layout.addWidget(stop_btn)

        restart_btn = QPushButton("Restart Service")
        restart_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3; color: white;
                padding: 10px 20px; font-size: 14px;
                border-radius: 5px; font-weight: bold;
            }
            QPushButton:hover { background-color: #1976D2; }
        """)
        restart_btn.clicked.connect(lambda: self.service_action("restart"))
        controls_layout.addWidget(restart_btn)

        controls_group.setLayout(controls_layout)
        main_layout.addWidget(controls_group)

        # --- Service Logs ---
        logs_group = QGroupBox("Service Logs")
        logs_layout = QVBoxLayout()

        self.log_viewer = QPlainTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setFont(QFont("Monospace", 9))
        self.log_viewer.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #555;
                border-radius: 3px;
            }
        """)
        self.log_viewer.setMinimumHeight(300)
        logs_layout.addWidget(self.log_viewer)

        log_buttons_layout = QHBoxLayout()

        refresh_logs_btn = QPushButton("Refresh Logs")
        refresh_logs_btn.setStyleSheet("""
            QPushButton {
                background-color: #555; color: white;
                padding: 6px 16px; border-radius: 3px;
            }
            QPushButton:hover { background-color: #666; }
        """)
        refresh_logs_btn.clicked.connect(self.refresh_logs)
        log_buttons_layout.addWidget(refresh_logs_btn)

        clear_logs_btn = QPushButton("Clear Logs")
        clear_logs_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336; color: white;
                padding: 6px 16px; border-radius: 3px;
            }
            QPushButton:hover { background-color: #da190b; }
        """)
        clear_logs_btn.clicked.connect(self.clear_logs)
        log_buttons_layout.addWidget(clear_logs_btn)

        log_buttons_layout.addStretch()
        logs_layout.addLayout(log_buttons_layout)

        logs_group.setLayout(logs_layout)
        main_layout.addWidget(logs_group)

        self.setLayout(main_layout)

    def refresh_status(self):
        """Check and display the service status"""
        try:
            result = subprocess.run(
                ["systemctl", "--user", "is-active", SERVICE_NAME],
                capture_output=True, text=True
            )
            state = result.stdout.strip()
        except Exception:
            state = "unknown"

        color_map = {
            "active": "#4CAF50",
            "inactive": "#888",
            "failed": "#f44336",
        }
        color = color_map.get(state, "#FF9800")
        self.status_label.setText(f"Service: {state}")
        self.status_label.setStyleSheet(
            f"font-size: 16px; font-weight: bold; padding: 10px; color: {color};"
        )

    def service_action(self, action):
        """Run a systemctl action (start/stop/restart)"""
        try:
            result = subprocess.run(
                ["systemctl", "--user", action, SERVICE_NAME],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                QMessageBox.information(self, "Success", f"Service {action} successful.")
            else:
                QMessageBox.warning(
                    self, "Warning",
                    f"Service {action} returned an error:\n{result.stderr.strip()}"
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to {action} service:\n{str(e)}")
        self.refresh_status()

    def refresh_logs(self):
        """Load the last 200 lines from the log file"""
        if not os.path.exists(self.log_file):
            self.log_viewer.setPlainText("(Log file not found)")
            return
        try:
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
            tail = lines[-200:] if len(lines) > 200 else lines
            self.log_viewer.setPlainText("".join(tail))
            # Scroll to bottom
            scrollbar = self.log_viewer.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        except Exception as e:
            self.log_viewer.setPlainText(f"Error reading log file:\n{str(e)}")

    def clear_logs(self):
        """Truncate the log file after confirmation"""
        reply = QMessageBox.question(
            self, "Clear Logs",
            "This will delete all log contents. Are you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                with open(self.log_file, 'w') as f:
                    f.truncate(0)
                self.log_viewer.setPlainText("")
                QMessageBox.information(self, "Success", "Logs cleared.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear logs:\n{str(e)}")


class MainWindow(QMainWindow):
    """Main application window"""
    def __init__(self, tasks_dir):
        super().__init__()
        self.tasks_dir = tasks_dir
        self.init_ui()
        self.load_tasks()

    def init_ui(self):
        self.setWindowTitle("RaspAutomator - Task Configuration Editor")
        self.setGeometry(100, 100, 800, 600)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        layout = QVBoxLayout()

        # Header
        header = QLabel("<h1>RaspAutomator Task Editor</h1>")
        header.setStyleSheet("color: #4CAF50; padding: 20px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #555;
                border-radius: 5px;
                padding: 10px;
            }
            QTabBar::tab {
                background: #2b2b2b;
                color: white;
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }
            QTabBar::tab:selected {
                background: #4CAF50;
            }
            QTabBar::tab:hover {
                background: #3d3d3d;
            }
        """)
        layout.addWidget(self.tabs)

        # Footer
        footer = QLabel("Edit task configurations and click Save to apply changes")
        footer.setStyleSheet("color: #888; padding: 10px;")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)

        central_widget.setLayout(layout)

    def load_tasks(self):
        """Discover and load all tasks from tasks directory"""
        if not os.path.exists(self.tasks_dir):
            QMessageBox.critical(
                self,
                "Error",
                f"Tasks directory not found: {self.tasks_dir}"
            )
            return

        # Find all task directories
        task_count = 0
        for item in sorted(os.listdir(self.tasks_dir)):
            task_path = os.path.join(self.tasks_dir, item)

            # Skip if not a directory
            if not os.path.isdir(task_path):
                continue

            # Check if trigger.json exists
            trigger_file = os.path.join(task_path, "trigger.json")
            if not os.path.exists(trigger_file):
                continue

            # Load trigger configuration
            try:
                with open(trigger_file, 'r') as f:
                    trigger_data = json.load(f)

                # Try to load task config.json (optional)
                task_config_file = os.path.join(task_path, "config.json")
                task_config_data = None
                if os.path.exists(task_config_file):
                    try:
                        with open(task_config_file, 'r') as f:
                            task_config_data = json.load(f)
                    except Exception as e:
                        print(f"Warning: Could not load config.json for {item}: {e}")

                # Create tab for this task
                tab = TaskConfigTab(item, task_path, trigger_data, task_config_data)
                self.tabs.addTab(tab, item)
                task_count += 1

            except Exception as e:
                print(f"Error loading {item}: {e}")

        if task_count == 0:
            QMessageBox.warning(
                self,
                "No Tasks Found",
                "No tasks with trigger.json files were found in the tasks directory."
            )

        # Add Service tab at the end
        project_root = os.path.dirname(self.tasks_dir)
        self.service_tab = ServiceTab(project_root)
        self.tabs.addTab(self.service_tab, "Service")

        # Auto-refresh service status when switching to Service tab
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, index):
        """Refresh service status when switching to the Service tab"""
        widget = self.tabs.widget(index)
        if isinstance(widget, ServiceTab):
            widget.refresh_status()
            widget.refresh_logs()


def set_dark_theme(app):
    """Apply dark theme to the application"""
    app.setStyle("Fusion")

    dark_palette = QPalette()
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(25, 25, 25))
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)

    # Disabled colors
    dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(127, 127, 127))
    dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(127, 127, 127))
    dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(127, 127, 127))
    dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight, QColor(80, 80, 80))
    dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.HighlightedText, QColor(127, 127, 127))

    app.setPalette(dark_palette)


def main():
    # Determine tasks directory (assume script is in gui/, tasks are in ../tasks/)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    tasks_dir = os.path.join(project_root, "tasks")

    app = QApplication(sys.argv)
    set_dark_theme(app)

    window = MainWindow(tasks_dir)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
