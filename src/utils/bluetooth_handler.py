import logging
import pexpect
import time

class BluetoothHandler:
    """Linux implementation using a single bluetoothctl session"""

    def __init__(self, devices):
        self.devices = devices if isinstance(devices, list) else [devices]
        self.timeout = 10
        self.max_retries = 3
        self.retry_delay = 2
        self.logger = logging.getLogger(__name__)

        # Spawn a single bluetoothctl process
        self.btctl = pexpect.spawn("bluetoothctl", timeout=self.timeout)
        # Turn agent on and set as default agent to handle pairing/passkey
        self.btctl.sendline("agent on")
        self.btctl.sendline("default-agent")

        # Optional: Power on the Bluetooth adapter
        self.btctl.sendline("power on")
        # We expect a prompt or final line after each command; 
        # so let's do a quick read to clear any immediate response.
        try:
            self.btctl.expect(r"\[bluetooth\]?.*#", timeout=2)
        except pexpect.TIMEOUT:
            pass

    def run_command(self, command, expect_patterns, timeout=None):
        """
        Send a command to the single bluetoothctl session.
        Return (index, output) from pexpect, where:
          - index is which pattern from expect_patterns matched
          - output is the text before the match
        """
        if timeout is None:
            timeout = self.timeout

        # Send the command
        self.logger.debug(f"Running command: {command}")
        self.btctl.sendline(command)

        # Build a combined pattern list that also includes the prompt
        # so we can know when bluetoothctl is "done" with its output.
        combined_patterns = expect_patterns + [r"\[bluetooth\]?.*#"]
        index = -1
        output = ""

        try:
            # Keep reading patterns until we hit the prompt or one of our patterns
            while True:
                i = self.btctl.expect(combined_patterns, timeout=timeout)
                # If i corresponds to one of our custom patterns (not the last prompt),
                # return immediately.
                if i < len(expect_patterns):
                    # We matched one of our relevant patterns
                    output = self.btctl.before.decode(errors="replace")
                    return i, output
                else:
                    # We matched the prompt; 
                    # this might mean none of our custom patterns appeared
                    output = self.btctl.before.decode(errors="replace")
                    return -1, output  # or some indicator that no pattern matched
        except pexpect.TIMEOUT:
            self.logger.error(f"Command timed out: {command}")
            return -1, ""

    def is_paired(self, mac_address):
        """
        Check if device is paired by parsing 'info <MAC>'.
        We'll look for 'Paired: yes' in the output.
        """
        cmd = f"info {mac_address}"
        index, output = self.run_command(cmd, ["Paired: yes", "Paired: no", "not available"])
        # index = 0 -> matched "Paired: yes"
        # index = 1 -> matched "Paired: no"
        # index = 2 -> matched "not available"
        # index = -1 -> we only matched the prompt (no direct pattern)
        
        # If we matched "Paired: yes", the device is paired.
        if index == 0:
            return True
        return False

    def is_connected(self, mac_address):
        """Check if device is connected by parsing 'info'."""
        index, output = self.run_command(
            f"info {mac_address}",
            ["Connected: yes", "Connected: no", "not available"]
        )
        # If we matched index 0 -> "Connected: yes"
        if index == 0:
            return True
        # Could also parse the 'output' string if the matching lines differ
        return False

    def connect(self):
        """Try to connect to any of the configured devices."""
        for device in self.devices:
            # Handle both dictionary and string inputs
            if isinstance(device, dict):
                mac = device["mac_address"].upper()
                name = device.get("name", "Unknown Device")
            else:
                mac = device.upper()
                name = "Unknown Device"

            self.logger.info(f"Attempting to connect to {name} ({mac})")

            # Check if already connected
            if self.is_connected(mac):
                self.logger.info(f"Device {name} ({mac}) is already connected")
                return True

            # Try to connect with retries
            for attempt in range(self.max_retries):
                try:
                    # If not paired, try pairing first
                    if not self.is_paired(mac):
                        self.logger.info(f"Device {mac} not paired; attempting to pair...")
                        index, output = self.run_command(
                            f"pair {mac}",
                            ["Pairing successful", "Failed to pair", "Already paired"],
                            timeout=30
                        )
                        if index not in [0, 2]:  # Not successful or not "Already paired"
                            self.logger.warning(f"Pair failed: {output.strip()}")
                            continue

                        # Trust the device
                        index, output = self.run_command(
                            f"trust {mac}",
                            ["trust succeeded", "trust failed"]
                        )
                        if index != 0:
                            self.logger.warning(f"Trust failed: {output.strip()}")
                            continue

                    # Now attempt to connect
                    self.logger.info(f"Attempting connection to {mac} (attempt {attempt+1})...")
                    index, output = self.run_command(
                        f"connect {mac}",
                        [
                            "Connection successful",
                            "Failed to connect",
                            "Device is already connected"
                        ],
                        timeout=15
                    )

                    # index = 0 means we matched "Connection successful"
                    # index = 2 means "Device is already connected"
                    if index in [0, 2]:
                        self.logger.info(f"Successfully connected to {name} ({mac})")
                        return True
                    else:
                        self.logger.warning(f"Connect attempt failed: {output.strip()}")

                except Exception as e:
                    self.logger.error(f"Attempt {attempt + 1} error: {str(e)}")

                if attempt < self.max_retries - 1:
                    self.logger.info(f"Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)

            self.logger.error(f"Failed to connect to {name} ({mac}) after {self.max_retries} attempts")

        self.logger.error("Failed to connect to any configured Bluetooth devices")
        return False

    def disconnect(self):
        """Disconnect from any connected device."""
        disconnected_any = False
        for device in self.devices:
            if isinstance(device, dict):
                mac = device["mac_address"].upper()
            else:
                mac = device.upper()

            if self.is_connected(mac):
                index, output = self.run_command(
                    f"disconnect {mac}",
                    ["Successful disconnected", "Failed to disconnect"]
                )
                if index == 0:
                    self.logger.info(f"Successfully disconnected from {mac}")
                    disconnected_any = True
                else:
                    self.logger.error(f"Failed to disconnect from {mac} - {output.strip()}")
        return disconnected_any

    def cleanup(self):
        """Cleanly exit bluetoothctl session."""
        if self.btctl.isalive():
            self.btctl.sendline("exit")
            self.btctl.close(force=True)
