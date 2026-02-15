import sys
import json
import random
import time
import vlc
import os
import threading
import psutil
import subprocess
from utils.bluetooth_handler import BluetoothHandler
from utils.volume_controller import SystemVolumeController
import logging

CURRENT_TASK_DIR = os.path.dirname(__file__)

CONFIG_FILE = os.path.join(CURRENT_TASK_DIR, 'config.json')
RADIO_STREAM_FILE = os.path.join(CURRENT_TASK_DIR, 'radio_stations.json')

class RadioPlayer:
    # Implementing the singleton pattern for RadioPlayer ot ensure that only one istance of the player is created
    # We also ensure that the automator properly manages threads and does not create multiple threads for the same task
    # Moreover we'll add some logging
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(RadioPlayer, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        self.load_config()
        self.bluetooth_handler = None
        self.logger = logging.getLogger(__name__)
        self.is_playing = False  # Add a flag to check if the radio is playing
        self.initialized = True
    
    def load_config(self):
        try:
            with open(CONFIG_FILE, 'r') as f:
                self.config = json.load(f)
            # Get the first bluetooth device's MAC address from config
            self.bluetooth_mac = self.config['bluetooth_devices'][0]['mac_address']
            self.radio_streams = self.load_radio_streams()

            # Load volume settings (with defaults if not present)
            volume_config = self.config.get('volume', {})
            self.system_volume = volume_config.get('system_volume', 70)
            self.vlc_volume = volume_config.get('vlc_volume', 50)
        except Exception as e:
            self.logger.error(f"Error loading configuration: {str(e)}")
            raise

    def load_radio_streams(self):
        with open(RADIO_STREAM_FILE, 'r') as f:
            return json.load(f)

    def debug_audio_state(self, mac_address):
        """Debug function to log complete Bluetooth and audio state"""
        self.logger.info("=" * 80)
        self.logger.info("DEBUG: Full Audio & Bluetooth State")
        self.logger.info("=" * 80)

        # 1. Check Bluetooth device connection status
        try:
            result = subprocess.run(
                ["bluetoothctl", "info", mac_address],
                capture_output=True, text=True, timeout=5
            )
            self.logger.info("BLUETOOTH INFO:")
            for line in result.stdout.splitlines():
                if any(keyword in line for keyword in ["Connected:", "Paired:", "Trusted:", "Name:"]):
                    self.logger.info(f"  {line.strip()}")
        except Exception as e:
            self.logger.error(f"Failed to get Bluetooth info: {e}")

        # 2. List all PulseAudio/PipeWire sinks
        try:
            result = subprocess.run(
                ["pactl", "list", "short", "sinks"],
                capture_output=True, text=True, timeout=5
            )
            self.logger.info("AVAILABLE AUDIO SINKS:")
            for line in result.stdout.splitlines():
                self.logger.info(f"  {line.strip()}")
        except Exception as e:
            self.logger.error(f"Failed to list sinks: {e}")

        # 3. Get detailed volume info for Bluetooth sink
        try:
            normalized_mac = mac_address.replace(":", "_")
            result = subprocess.run(
                ["pactl", "list", "sinks"],
                capture_output=True, text=True, timeout=5
            )
            lines = result.stdout.splitlines()
            in_bt_sink = False
            self.logger.info("BLUETOOTH SINK DETAILS:")
            for line in lines:
                if normalized_mac in line or "bluez_output" in line:
                    in_bt_sink = True
                if in_bt_sink:
                    if any(keyword in line for keyword in ["Name:", "Volume:", "Mute:", "State:"]):
                        self.logger.info(f"  {line.strip()}")
                    if line.startswith("Sink #") and normalized_mac not in line:
                        break
        except Exception as e:
            self.logger.error(f"Failed to get sink details: {e}")

        # 4. Get default sink
        try:
            result = subprocess.run(
                ["pactl", "get-default-sink"],
                capture_output=True, text=True, timeout=5
            )
            self.logger.info(f"DEFAULT SINK: {result.stdout.strip()}")
        except Exception as e:
            self.logger.error(f"Failed to get default sink: {e}")

        self.logger.info("=" * 80)

    def play_radio(self, stream_url, radio_name, stop_event, volume_controller=None):
        """
        Play radio stream until stop_event is set.
        Duration is controlled by orchestrator via max_duration or .terminate files.

        Args:
            stream_url: URL of the radio stream
            radio_name: Name of the radio station
            stop_event: threading.Event() that signals when to stop playing
            volume_controller: Optional SystemVolumeController to re-set volume after playback starts
        """
        if self.is_playing:
            self.logger.info("Radio is already playing. Skipping new play request.")
            return

        self.is_playing = True  # Set the flag to True when starting to play
        try:
            # Increase VLC buffer and set audio output to PulseAudio/PipeWire
            instance = vlc.Instance('--network-caching=3000', '--file-caching=3000', '--live-caching=3000', '--aout=pulse')
            player = instance.media_player_new()
            media = instance.media_new(stream_url)
            player.set_media(media)
            player.audio_set_volume(self.vlc_volume)
            player.play()

            # Wait a moment for VLC to actually start playing
            time.sleep(2)

            self.logger.info(f"Playing radio {radio_name}")
            self.logger.info(f"VLC volume set to {self.vlc_volume}%")

            # Re-set system volume AFTER VLC starts to force AVRCP sync
            if volume_controller:
                self.logger.info("Re-setting system volume after VLC started...")
                if volume_controller.set_bluetooth_volume(self.bluetooth_mac, self.system_volume):
                    self.logger.info(f"System volume re-confirmed at {self.system_volume}%")
                    # DEBUG: Check if volume actually changed
                    self.debug_audio_state(self.bluetooth_mac)
                else:
                    self.logger.warning("Failed to re-set system volume")

            # Play until stop_event is set by the orchestrator
            while not stop_event.is_set():
                time.sleep(1)

            self.logger.info(f"Stop event received, stopping radio {radio_name}")
        finally:
            self.logger.info(f"Stopping radio {radio_name}")
            player.stop()
            player.release()
            instance.release()
            self.is_playing = False  # Reset the flag when done playing

    def start(self, stop_event):
        """
        Initialize and start radio playback.

        Args:
            stop_event: threading.Event() that signals when to stop
        """
        try:
            # Select random radio stream
            radio_stream = random.choice(self.radio_streams)
            radio_stream_url = radio_stream['url']
            radio_name = radio_stream['name']

            # Initialize Bluetooth connection with single MAC address
            bluetooth_handler = BluetoothHandler(self.bluetooth_mac)

            # Try to connect
            if bluetooth_handler.connect():
                self.logger.info(f"Connected to Bluetooth device: {self.bluetooth_mac}")

                # Wait for PulseAudio to detect the Bluetooth sink (takes a moment after connection)
                self.logger.info("Waiting for PulseAudio to detect Bluetooth sink...")
                time.sleep(3)

                # DEBUG: Log full audio and Bluetooth state
                self.debug_audio_state(self.bluetooth_mac)

                # Set system volume before playing
                volume_controller = SystemVolumeController(self.logger)
                if volume_controller.set_bluetooth_volume(self.bluetooth_mac, self.system_volume):
                    self.logger.info(f"System volume set to {self.system_volume}%")
                else:
                    self.logger.warning(f"Failed to set system volume, continuing with current volume")

                # DEBUG: Log audio state AFTER setting volume
                self.logger.info("DEBUG: Audio state AFTER volume set:")
                self.debug_audio_state(self.bluetooth_mac)

                # Start playing radio
                self.play_radio(radio_stream_url, radio_name, stop_event, volume_controller)
            else:
                self.logger.error("Failed to connect to Bluetooth speaker. Exiting.")
                return False

        except Exception as e:
            self.logger.error(f"Error in start(): {str(e)}")
            return False


def check_if_already_running():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pid_file = os.path.join(script_dir, 'radio_alarm.pid')
    
    if os.path.isfile(pid_file):
        try:
            with open(pid_file, 'r') as f:
                old_pid = int(f.read().strip())
            
            # Check if process with this PID exists
            if psutil.pid_exists(old_pid):
                # Double check it's our process by checking the name
                try:
                    process = psutil.Process(old_pid)
                    if "python" in process.name().lower():
                        logging.warning(f"Another instance is already running (PID: {old_pid})")
                        sys.exit()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    # Process doesn't exist anymore or we can't access it
                    pass
            
            # If we get here, the PID file is stale
            os.remove(pid_file)
            
        except (ValueError, IOError) as e:
            # Invalid content in PID file or can't read it
            logging.warning(f"Invalid or corrupted PID file: {e}")
            os.remove(pid_file)
    
    # Write our PID
    try:
        with open(pid_file, 'w') as f:
            f.write(str(os.getpid()))
    except IOError as e:
        logging.error(f"Could not write PID file: {e}")
        sys.exit(1)

def delete_pid_file():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pid_file = os.path.join(script_dir, 'radio_alarm.pid')
    if os.path.isfile(pid_file):
        os.remove(pid_file)

# Entry point of the program
def main(stop_event=None):
    """
    Main entry point for radio alarm.

    Args:
        stop_event: Optional threading.Event() for graceful shutdown.
                   If None, creates a dummy event that never gets set (for standalone mode).
    """
    # Create a dummy event that never gets set if running standalone
    if stop_event is None:
        stop_event = threading.Event()

    check_if_already_running()
    try:
        radio_player = RadioPlayer()
        radio_player.start(stop_event)
    finally:
        delete_pid_file()

# This is if we want to run the script as a task
def thread_loop(stop_event):
    """Entry point when running as a scheduled task"""
    main(stop_event)

# This is if we want to run the script as a standalone program
if __name__ == "__main__":
    main()
