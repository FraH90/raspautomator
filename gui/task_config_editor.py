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
    QPushButton, QGroupBox, QMessageBox, QFormLayout
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
    def __init__(self, task_name, task_path, config_data):
        super().__init__()
        self.task_name = task_name
        self.task_path = task_path
        self.config_file = os.path.join(task_path, "trigger.json")
        self.config_data = config_data
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

        # Save button
        button_layout = QHBoxLayout()
        button_layout.addStretch()

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
        # Schedule settings
        self.schedule_on.setChecked(self.config_data.get("schedule_on", False))

        # Time of day
        time_str = self.config_data.get("time_of_day", "00:00")
        hour, minute = map(int, time_str.split(":"))
        self.time_of_day.setTime(QTime(hour, minute))

        # Days of week
        days = self.config_data.get("days_of_week", [])
        self.days_selector.set_selected_days(days)

        # Timeout settings
        self.timeout_on.setChecked(self.config_data.get("timeout_on", False))
        self.timeout_interval.setValue(self.config_data.get("timeout_interval", 60))

        # Max duration
        self.max_duration.setValue(self.config_data.get("max_duration", 0))

    def save_config(self):
        """Save configuration from UI controls to JSON file"""
        # Build config dictionary
        config = {
            "schedule_on": self.schedule_on.isChecked(),
            "timeout_on": self.timeout_on.isChecked(),
            "days_of_week": self.days_selector.get_selected_days(),
            "time_of_day": self.time_of_day.time().toString("HH:mm"),
            "timeout_interval": self.timeout_interval.value()
        }

        # Only add max_duration if it's not 0
        max_dur = self.max_duration.value()
        if max_dur > 0:
            config["max_duration"] = max_dur

        # Save to file
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)

            QMessageBox.information(
                self,
                "Success",
                f"Configuration for '{self.task_name}' saved successfully!"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save configuration:\n{str(e)}"
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
            config_file = os.path.join(task_path, "trigger.json")
            if not os.path.exists(config_file):
                continue

            # Load configuration
            try:
                with open(config_file, 'r') as f:
                    config_data = json.load(f)

                # Create tab for this task
                tab = TaskConfigTab(item, task_path, config_data)
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
