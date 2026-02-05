#!/usr/bin/env python3
"""
RaspAutomator Task Configuration Editor
A modern dark-themed GUI for editing task trigger.json files
"""

import sys
import os
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QCheckBox, QTimeEdit, QSpinBox,
    QPushButton, QGroupBox, QMessageBox, QFormLayout, QSlider
)
from PyQt6.QtCore import Qt, QTime
from PyQt6.QtGui import QPalette, QColor


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
        schedule_layout = QFormLayout()

        # Schedule On/Off
        self.schedule_on = QCheckBox()
        schedule_layout.addRow("Schedule Enabled:", self.schedule_on)

        # Time of Day
        self.time_of_day = QTimeEdit()
        self.time_of_day.setDisplayFormat("HH:mm")
        schedule_layout.addRow("Time of Day:", self.time_of_day)

        # Days of Week
        self.days_selector = DaySelector()
        schedule_layout.addRow("Days of Week:", self.days_selector)

        schedule_group.setLayout(schedule_layout)
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
        self.terminate_button = QPushButton("🛑 Terminate Task")
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
        self.save_button = QPushButton("💾 Save Configuration")
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

    def load_config(self):
        """Load configuration from JSON data into UI controls"""
        # Schedule settings (from trigger.json)
        self.schedule_on.setChecked(self.trigger_data.get("schedule_on", False))

        # Time of day
        time_str = self.trigger_data.get("time_of_day", "00:00")
        hour, minute = map(int, time_str.split(":"))
        self.time_of_day.setTime(QTime(hour, minute))

        # Days of week
        days = self.trigger_data.get("days_of_week", [])
        self.days_selector.set_selected_days(days)

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
        # Build trigger config dictionary
        trigger_config = {
            "schedule_on": self.schedule_on.isChecked(),
            "timeout_on": self.timeout_on.isChecked(),
            "days_of_week": self.days_selector.get_selected_days(),
            "time_of_day": self.time_of_day.time().toString("HH:mm"),
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

        QMessageBox.information(
            self,
            "Success",
            f"Configuration for '{self.task_name}' saved successfully!"
        )

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
        header = QLabel("<h1>🤖 RaspAutomator Task Editor</h1>")
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
