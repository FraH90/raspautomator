"""
SystemVolumeController - Handles PulseAudio volume control for Bluetooth speakers
"""

import subprocess
import logging
import re
from typing import Optional


class SystemVolumeController:
    """
    Controls system (PulseAudio) volume for Bluetooth audio devices.

    This is useful for ensuring Bluetooth speakers are at the desired volume level
    before starting audio playback tasks, as many Bluetooth speakers sync their
    hardware volume with the system volume via AVRCP profile.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize the SystemVolumeController.

        Args:
            logger: Optional logger instance. If not provided, creates a default logger.
        """
        self.logger = logger or self._create_logger()

    def _create_logger(self) -> logging.Logger:
        """Create a default logger if none provided"""
        logger = logging.getLogger("SystemVolumeController")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def get_bluetooth_sink(self, mac_address: str) -> Optional[str]:
        """
        Find the PulseAudio sink ID for a Bluetooth device by MAC address.

        Args:
            mac_address: MAC address of the Bluetooth device (e.g., "AA:BB:CC:DD:EE:FF")

        Returns:
            Sink ID (e.g., "bluez_sink.AA_BB_CC_DD_EE_FF") or None if not found
        """
        try:
            # Normalize MAC address format (replace : with _)
            normalized_mac = mac_address.replace(":", "_")

            # Run pactl list short sinks to get all audio sinks
            result = subprocess.run(
                ["pactl", "list", "short", "sinks"],
                capture_output=True,
                text=True,
                check=True
            )

            # Look for bluez sink matching the MAC address
            for line in result.stdout.splitlines():
                if f"bluez_sink.{normalized_mac}" in line:
                    # Extract sink ID (first column)
                    sink_id = line.split()[0]
                    self.logger.info(f"Found Bluetooth sink: {sink_id}")
                    return sink_id

            self.logger.warning(f"No Bluetooth sink found for MAC address: {mac_address}")
            return None

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error getting Bluetooth sink: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error getting Bluetooth sink: {e}")
            return None

    def set_volume(self, sink_id: str, volume_percent: int) -> bool:
        """
        Set the volume for a specific PulseAudio sink.

        Args:
            sink_id: PulseAudio sink identifier
            volume_percent: Volume level (0-100)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Clamp volume to valid range
            volume_percent = max(0, min(100, volume_percent))

            # pactl set-sink-volume expects percentage
            subprocess.run(
                ["pactl", "set-sink-volume", sink_id, f"{volume_percent}%"],
                check=True,
                capture_output=True
            )

            self.logger.info(f"Set volume to {volume_percent}% for sink {sink_id}")
            return True

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error setting volume: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error setting volume: {e}")
            return False

    def get_volume(self, sink_id: str) -> Optional[int]:
        """
        Get the current volume for a specific PulseAudio sink.

        Args:
            sink_id: PulseAudio sink identifier

        Returns:
            Volume level (0-100) or None if unable to retrieve
        """
        try:
            result = subprocess.run(
                ["pactl", "list", "sinks"],
                capture_output=True,
                text=True,
                check=True
            )

            # Parse the output to find our sink and its volume
            current_sink = None
            for line in result.stdout.splitlines():
                # Check if this is our sink
                if "Name:" in line and sink_id in line:
                    current_sink = sink_id

                # If we're in our sink section, look for volume
                if current_sink == sink_id and "Volume:" in line:
                    # Extract percentage (format: "Volume: front-left: 65536 / 100% / ...")
                    match = re.search(r'(\d+)%', line)
                    if match:
                        volume = int(match.group(1))
                        self.logger.info(f"Current volume for {sink_id}: {volume}%")
                        return volume

            self.logger.warning(f"Could not find volume for sink: {sink_id}")
            return None

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error getting volume: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error getting volume: {e}")
            return None

    def set_bluetooth_volume(self, mac_address: str, volume_percent: int) -> bool:
        """
        Convenience method to set volume for a Bluetooth device by MAC address.

        Args:
            mac_address: MAC address of the Bluetooth device
            volume_percent: Volume level (0-100)

        Returns:
            True if successful, False otherwise
        """
        sink_id = self.get_bluetooth_sink(mac_address)
        if not sink_id:
            self.logger.error(f"Could not find Bluetooth sink for {mac_address}")
            return False

        return self.set_volume(sink_id, volume_percent)
