from wakeonlan import send_magic_packet

def main():
    # Replace with your TV's MAC address
    mac_address = "F4:CA:E7:5C:97:C8"
    
    # Send the magic packet to wake the TV
    send_magic_packet(mac_address)
    print(f"Sent magic packet to {mac_address}")

if __name__ == "__main__":
    main()
