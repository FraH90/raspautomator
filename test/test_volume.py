#!/usr/bin/env python3
"""Quick test script for SystemVolumeController"""

import sys
import subprocess

# Add src to path
sys.path.insert(0, 'src')

from task.volume_controller import SystemVolumeController

MAC = "EC:81:93:F8:23:2B"

vc = SystemVolumeController()

# 1. List all sinks
print("=== All PulseAudio sinks ===")
result = subprocess.run(["pactl", "list", "short", "sinks"], capture_output=True, text=True)
print(result.stdout or "(no sinks found)")
print()

# 2. Try to find the Bluetooth sink
print(f"=== Looking for Bluetooth sink: {MAC} ===")
sink = vc.get_bluetooth_sink(MAC)
print(f"Result: {sink}")
print()

if sink:
    # 3. Get current volume
    print("=== Current volume ===")
    vol = vc.get_volume(sink)
    print(f"Volume: {vol}%")
    print()

    # 4. Set volume to 70%
    print("=== Setting volume to 70% ===")
    ok = vc.set_volume(sink, 70)
    print(f"Success: {ok}")
    print()

    # 5. Verify
    print("=== Verify new volume ===")
    vol = vc.get_volume(sink)
    print(f"Volume: {vol}%")
else:
    print("No Bluetooth sink found! Is the speaker connected?")
    print()
    print("Trying 'pactl list sinks' for more detail:")
    result = subprocess.run(["pactl", "list", "sinks"], capture_output=True, text=True)
    # Print just the Name lines
    for line in result.stdout.splitlines():
        if "Name:" in line or "Description:" in line:
            print(f"  {line.strip()}")
