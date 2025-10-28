import sys
import json
import random
import time
import vlc
import os
import threading
import psutil
from task.bluetooth_handler import BluetoothHandler
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
        except Exception as e:
            self.logger.error(f"Error loading configuration: {str(e)}")
            raise

    def load_radio_streams(self):
        with open(RADIO_STREAM_FILE, 'r') as f:
            return json.load(f)

    def play_radio_for_one_hour(self, stream_url, radio_name):
        if self.is_playing:
            print("Radio is already playing. Skipping new play request.")
            return

        self.is_playing = True  # Set the flag to True when starting to play
        try:
            # Increase VLC buffer and set audio output to ALSA
            instance = vlc.Instance('--network-caching=3000', '--file-caching=3000', '--live-caching=3000', '--aout=pulse')
            player = instance.media_player_new()
            media = instance.media_new(stream_url)
            player.set_media(media)
            player.audio_set_volume(50)
            player.play()

            print(f"{time.strftime('%H:%M')} - Playing radio {radio_name}")
            # Play for 1 hour (3600 seconds)
            time.sleep(3600)
            # Stop the player
            player.stop()
            print(f"{time.strftime('%H:%M')} - Stopped playing radio {radio_name}")
        finally:
            player.stop()
            player.release()
            instance.release()
            self.is_playing = False  # Reset the flag when done playing

    def start(self):
        """Initialize and start radio playback"""
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
                self.play_radio_for_one_hour(radio_stream_url, radio_name)
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
                        print(f"Another instance is already running (PID: {old_pid})")
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
def main():
    check_if_already_running()
    try:
        radio_player = RadioPlayer()
        radio_player.start()
    finally:
        delete_pid_file()

# This is if we want to run the script as a task
def thread_loop():
    main()

# This is if we want to run the script as a standalone program
if __name__ == "__main__":
    main()
