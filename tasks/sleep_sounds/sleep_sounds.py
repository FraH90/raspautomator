import sys
import json
import random
import time
import vlc
import os
import threading
import psutil
import logging
import subprocess
import re
from datetime import datetime, timedelta

# Same as your radio example, but referencing the same package structure:
from utils.bluetooth_handler import BluetoothHandler
from utils.volume_controller import SystemVolumeController

CURRENT_TASK_DIR = os.path.dirname(__file__)
CONFIG_FILE = os.path.join(CURRENT_TASK_DIR, 'config.json')
SOURCES_FILE = os.path.join(CURRENT_TASK_DIR, 'sleep_sounds_sources.json')
PID_FILE = os.path.join(CURRENT_TASK_DIR, 'sleep_sounds.pid')
CACHE_DIR = os.path.join(CURRENT_TASK_DIR, 'cache')


class SleepSoundsPlayer:
    """
    A singleton class that picks a single YouTube URL from a list, downloads
    it (if needed), and loops that audio until 'stop_time'.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(SleepSoundsPlayer, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Make sure we only init once in the singleton
        if getattr(self, 'initialized', False):
            return

        self.logger = logging.getLogger(__name__)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        )

        self.load_config()
        self.is_playing = False
        self.initialized = True

    def load_config(self):
        """
        Loads config for the bluetooth address & stop_time.
        Loads sources for the YouTube URL list.
        Creates the cache folder if needed.
        """
        try:
            with open(CONFIG_FILE, 'r') as f:
                self.config = json.load(f)
            # e.g. "bluetooth_devices": [{"mac_address": "..."}], "stop_time": "23:30"
            self.bluetooth_mac = self.config['bluetooth_devices'][0]['mac_address']
            self.stop_time_str = self.config['stop_time']

            # Load volume settings (with defaults if not present)
            volume_config = self.config.get('volume', {})
            self.system_volume = volume_config.get('system_volume', 70)
            self.vlc_volume = volume_config.get('vlc_volume', 50)

            with open(SOURCES_FILE, 'r') as f:
                sources = json.load(f)
            self.youtube_urls = sources['youtube_urls']

            if not os.path.isdir(CACHE_DIR):
                os.makedirs(CACHE_DIR, exist_ok=True)

        except Exception as e:
            self.logger.error(f"Error loading config/sources: {e}")
            raise

    def start(self, stop_event):
        """
        1) Connect to Bluetooth
        2) Pick 1 random track from youtube_urls
        3) Download if needed, then loop until stop_event is set

        Args:
            stop_event: threading.Event() that signals when to stop
        """
        try:
            if self.is_playing:
                self.logger.info("Sleep sounds are already playing. Skipping start request.")
                return

            # Connect via Bluetooth
            bt_handler = BluetoothHandler(self.bluetooth_mac)
            if not bt_handler.connect():
                self.logger.error("Failed to connect to Bluetooth speaker. Exiting.")
                return False

            self.logger.info(f"Connected to Bluetooth device: {self.bluetooth_mac}")

            # Wait for PulseAudio to detect the Bluetooth sink (takes a moment after connection)
            self.logger.info("Waiting for PulseAudio to detect Bluetooth sink...")
            time.sleep(3)

            # Set system volume before playing
            volume_controller = SystemVolumeController(self.logger)
            if volume_controller.set_bluetooth_volume(self.bluetooth_mac, self.system_volume):
                self.logger.info(f"System volume set to {self.system_volume}%")
            else:
                self.logger.warning(f"Failed to set system volume, continuing with current volume")

            # Pick a single random track from the list
            chosen_url = random.choice(self.youtube_urls)
            self.logger.info(f"Chosen track: {chosen_url}")

            # Download if needed
            audio_path = self.download_audio_if_needed(chosen_url)
            if not audio_path:
                self.logger.error("Could not download or locate audio file. Exiting.")
                return False

            # Loop that single file until stop_event is set (duration controlled by orchestrator)
            self.loop_indefinitely(audio_path, stop_event)
        except Exception as e:
            self.logger.error(f"Error in start(): {e}")
            return False

    def loop_indefinitely(self, audio_path, stop_event):
        """
        Continuously loops a single audio file until stop_event is set.
        Duration is controlled by orchestrator via max_duration or .terminate files.

        Args:
            audio_path: Path to the audio file to loop
            stop_event: threading.Event() that signals when to stop
        """
        self.is_playing = True
        self.logger.info(f"Playing sleep sounds (duration controlled by orchestrator)")

        # Setup VLC with a MediaList containing only this single track
        vlc_instance = vlc.Instance('--network-caching=3000',
                                    '--file-caching=3000',
                                    '--live-caching=3000',
                                    '--aout=pulse')

        media_list = vlc_instance.media_list_new([audio_path])
        list_player = vlc_instance.media_list_player_new()
        list_player.set_media_list(media_list)

        # Set loop mode
        list_player.set_playback_mode(vlc.PlaybackMode.loop)

        # We can set volume on the underlying media player object
        media_player = list_player.get_media_player()
        media_player.audio_set_volume(self.vlc_volume)

        # Start playing in loop
        list_player.play()
        self.logger.info(f"Now looping: {audio_path}")

        try:
            # Loop until stop_event is set by the orchestrator
            while not stop_event.is_set():
                time.sleep(2)
            self.logger.info("Stop event received, stopping sleep sounds")
        finally:
            list_player.stop()
            list_player.release()
            vlc_instance.release()
            self.is_playing = False
            self.logger.info("Stopped playing sleep sounds.")

    def get_stop_datetime(self):
        """
        Parse stop_time_str (e.g. '23:30') into a datetime for today.
        If that time is already past, schedule for tomorrow.
        """
        now = datetime.now()
        hh, mm = map(int, self.stop_time_str.split(':'))
        stop_dt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)

        if stop_dt <= now:
            stop_dt += timedelta(days=1)
        return stop_dt

    def download_audio_if_needed(self, youtube_url):
        """
        1) Extract video ID & title from YouTube (via yt-dlp metadata).
        2) Sanitize them and form a final filename: "<id>-<title>.m4a"
        3) If file exists, return it; otherwise download using yt-dlp.
        """
        self.logger.info(f"Checking/Downloading track: {youtube_url}")

        # Get metadata first (JSON) to find "id" and "title"
        try:
            # Try to find yt-dlp full path
            try:
                yt_dlp_path = subprocess.check_output(['which', 'yt-dlp'], text=True).strip()
                self.logger.info(f"Found yt-dlp at: {yt_dlp_path}")
            except subprocess.CalledProcessError:
                # Try common locations
                common_paths = [
                    '/usr/local/bin/yt-dlp',
                    '/usr/bin/yt-dlp',
                    '/opt/homebrew/bin/yt-dlp'
                ]
                yt_dlp_path = next((p for p in common_paths if os.path.exists(p)), 'yt-dlp')
                self.logger.info(f"Using yt-dlp from path: {yt_dlp_path}")
            
            cmd = [yt_dlp_path, '-J', youtube_url]  # -J => dump JSON metadata
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)

            video_id = info.get('id', 'unknownid')
            # Some videos might contain "title" at top level or in "title" key
            video_title = info.get('title', 'UnknownTitle')
        except subprocess.CalledProcessError as e:
            self.logger.error(f"yt-dlp metadata fetch failed: {e}")
            return None
        except json.JSONDecodeError as e:
            self.logger.error(f"Could not parse metadata JSON: {e}")
            return None

        # sanitize the title for filesystem
        safe_title = self._sanitize_filename(video_title)
        filename = f"{video_id}-{safe_title}.m4a"
        audio_path = os.path.join(CACHE_DIR, filename)

        if os.path.isfile(audio_path) and os.path.getsize(audio_path) > 0:
            self.logger.info("File already exists in cache. Skipping download.")
            return audio_path

        # Otherwise, download
        self.logger.info(f"Downloading audio to {audio_path}")
        try:
            # Use the same yt-dlp path found above
            dl_cmd = [
                yt_dlp_path,
                '-q',                  # quiet
                '-x',                  # extract audio
                '--audio-format', 'm4a',
                '--output', audio_path,
                youtube_url
            ]
            subprocess.run(dl_cmd, check=True)
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Audio download failed: {e}")
            return None

        # Check if file now exists
        if os.path.isfile(audio_path):
            return audio_path
        else:
            return None

    def _sanitize_filename(self, text):
        """
        Removes or replaces characters likely to be invalid on various filesystems.
        """
        # Example simple approach: remove anything that's not letters, digits, underscore or space
        return re.sub(r'[^0-9a-zA-Z \-_]+', '', text).strip()


def check_if_already_running():
    """
    Create a PID file to ensure only one instance runs at a time,
    same style as your radio task.
    """
    if os.path.isfile(PID_FILE):
        try:
            with open(PID_FILE, 'r') as f:
                old_pid = int(f.read().strip())
            if psutil.pid_exists(old_pid):
                # Double check it's python
                try:
                    process = psutil.Process(old_pid)
                    if "python" in process.name().lower():
                        print(f"Another instance is already running (PID: {old_pid})")
                        sys.exit()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            # If we get here, the PID file is stale
            os.remove(PID_FILE)
        except (ValueError, IOError):
            logging.warning("Invalid/corrupted PID file. Removing it.")
            os.remove(PID_FILE)

    # Write current PID
    try:
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
    except IOError as e:
        logging.error(f"Could not write PID file: {e}")
        sys.exit(1)

def delete_pid_file():
    """
    Remove the PID file at the end, so subsequent runs can proceed.
    """
    if os.path.isfile(PID_FILE):
        os.remove(PID_FILE)

def main(stop_event=None):
    """
    Main entry point for sleep sounds player.

    Args:
        stop_event: Optional threading.Event() for graceful shutdown.
                   If None, creates a dummy event that never gets set (for standalone mode).
    """
    # Create a dummy event that never gets set if running standalone
    if stop_event is None:
        stop_event = threading.Event()

    check_if_already_running()
    try:
        player = SleepSoundsPlayer()
        player.start(stop_event)
    finally:
        delete_pid_file()

def thread_loop(stop_event):
    """
    Entry point when running as a scheduled task.

    Args:
        stop_event: threading.Event() that signals when to stop
    """
    main(stop_event)

if __name__ == "__main__":
    main()
