import os
import logging
import pexpect

CURRENT_TASK_DIR = os.path.dirname(__file__)
CONFIG_FILE = os.path.join(CURRENT_TASK_DIR, 'config.json')

logger = logging.getLogger(__name__)

class BluetoothHandler:
    def __init__(self, mac_address):
        self.mac_address = mac_address

    def run_command(self, command, timeout=10):
        process = pexpect.spawn(command, timeout=timeout)
        process.expect(pexpect.EOF)
        return process.before.decode()

    def is_paired(self):
        logger.info(f"Checking if {self.mac_address} is paired...")
        bluetoothctl = pexpect.spawn('sudo bluetoothctl')
        bluetoothctl.sendline(f'info {self.mac_address}')
        try:
            bluetoothctl.expect(['Paired: yes', 'Device has not been found'], timeout=10)
            result = bluetoothctl.after.decode()
            bluetoothctl.sendline('exit')
            return 'Paired: yes' in result
        except pexpect.TIMEOUT:
            bluetoothctl.sendline('exit')
            return False

    def is_connected(self):
        logger.info(f"Checking if {self.mac_address} is connected...")
        bluetoothctl = pexpect.spawn('sudo bluetoothctl')
        bluetoothctl.sendline(f'info {self.mac_address}')
        try:
            bluetoothctl.expect(['Connected: yes', 'Device has not been found'], timeout=10)
            result = bluetoothctl.after.decode()
            bluetoothctl.sendline('exit')
            return 'Connected: yes' in result
        except pexpect.TIMEOUT:
            bluetoothctl.sendline('exit')
            return False

    def connect(self):
        if not self.is_paired():
            logger.info(f"Pairing with {self.mac_address}...")
            bluetoothctl = pexpect.spawn('sudo bluetoothctl')
            bluetoothctl.sendline(f'pair {self.mac_address}')
            bluetoothctl.expect('Pairing successful', timeout=10)
            bluetoothctl.sendline(f'trust {self.mac_address}')
            bluetoothctl.expect('trust succeeded', timeout=10)
            bluetoothctl.sendline('exit')
        else:
            logger.info(f"{self.mac_address} is already paired.")

        if not self.is_connected():
            logger.info(f"Connecting to {self.mac_address}...")
            bluetoothctl = pexpect.spawn('sudo bluetoothctl')
            bluetoothctl.sendline(f'connect {self.mac_address}')
            try:
                bluetoothctl.expect('Connection successful', timeout=10)
                logger.info("Successfully connected to the Bluetooth speaker.")
            except pexpect.TIMEOUT:
                logger.warning("Failed to connect to the Bluetooth speaker.")
            bluetoothctl.sendline('exit')

        # Double-check connection status
        if self.is_connected():
            logger.info("Verified: Successfully connected to the Bluetooth speaker.")
            return True
        else:
            logger.warning("Failed to verify connection to the Bluetooth speaker.")
            return False
