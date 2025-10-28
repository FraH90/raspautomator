import os
import sys
import subprocess
import getpass

"""
This script creates a systemd user service to run the selected shell script at startup.
The service will automatically restart if it crashes.
"""

def find_sh_files():
    return [f for f in os.listdir() if f.endswith('.sh')]

def prompt_for_script_choice(scripts):
    print("Multiple .sh files found:")
    for idx, script in enumerate(scripts, start=1):
        print(f"{idx}. {script}")
    choice = input(f"Enter the number of the script you want to install (1-{len(scripts)}): ")
    
    try:
        choice = int(choice)
        if 1 <= choice <= len(scripts):
            return scripts[choice - 1]
        else:
            print("Invalid choice. Please run the script again and select a valid option.")
            sys.exit(1)
    except ValueError:
        print("Invalid input. Please enter a number.")
        sys.exit(1)

def create_systemd_service(shell_script_path, output_path):
    # Create systemd user directory if it doesn't exist
    systemd_dir = os.path.expanduser("~/.config/systemd/user")
    os.makedirs(systemd_dir, exist_ok=True)

    # Get the working directory of the script
    working_dir = os.path.dirname(os.path.abspath(shell_script_path))
    
    # Get current user's PATH
    current_path = os.environ.get('PATH', '')
    
    # Create service file content
    service_content = f"""[Unit]
Description=Automator Service
After=network.target

[Service]
Type=simple
Environment="PATH={current_path}"
ExecStart=/bin/bash {shell_script_path}
WorkingDirectory={working_dir}
Restart=always
RestartSec=10
StandardOutput=append:{output_path}
StandardError=append:{output_path}

[Install]
WantedBy=default.target
"""
    
    # Write service file
    service_name = "automator.service"
    service_path = os.path.join(systemd_dir, service_name)
    with open(service_path, "w") as f:
        f.write(service_content)
    
    return service_name

def enable_and_start_service(service_name):
    try:
        # Reload systemd daemon
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        
        # Enable the service
        subprocess.run(["systemctl", "--user", "enable", service_name], check=True)
        
        # Start the service
        subprocess.run(["systemctl", "--user", "start", service_name], check=True)
        
        # Enable lingering for the current user (allows user services to run at boot)
        username = getpass.getuser()
        subprocess.run(["sudo", "loginctl", "enable-linger", username], check=True)
        
    except subprocess.CalledProcessError as e:
        print(f"Error setting up service: {e}")
        sys.exit(1)

def main():
    sh_files = find_sh_files()

    if sh_files:
        if len(sh_files) == 1:
            selected_script = sh_files[0]
        else:
            selected_script = prompt_for_script_choice(sh_files)
    else:
        print("No .sh files found in the current directory.")
        input_choice = input("Would you like to provide the absolute or relative path to the script? (a/r): ").strip().lower()
        
        if input_choice == 'a':
            selected_script = input("Enter the absolute path to the shell script: ").strip()
        elif input_choice == 'r':
            selected_script = input("Enter the relative path to the shell script: ").strip()
        else:
            print("Invalid option. Please run the script again and select a valid option.")
            sys.exit(1)

    absolute_path = os.path.abspath(selected_script)
    script_dir = os.path.dirname(absolute_path)

    if not os.path.exists(absolute_path):
        print(f"Error: The file {absolute_path} does not exist.")
        sys.exit(1)

    if not os.access(absolute_path, os.X_OK):
        print(f"Warning: The script {absolute_path} is not executable. Attempting to make it executable...")
        try:
            os.chmod(absolute_path, 0o755)
            print("Successfully made the script executable.")
        except OSError:
            print(f"Error: Unable to make {absolute_path} executable. Please check file permissions.")
            sys.exit(1)

    # Create logs directory and set output path
    logs_dir = os.path.join(script_dir, "logs")
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    output_path = os.path.join(logs_dir, "output.out")

    # Create and enable systemd service
    service_name = create_systemd_service(absolute_path, output_path)
    enable_and_start_service(service_name)
    
    print(f"Installation complete. The service has been created and enabled.")
    print(f"Service name: {service_name}")
    print(f"Script path: {absolute_path}")
    print(f"Output will be written to: {output_path}")
    print("\nUseful commands:")
    print(f"- Check service status: systemctl --user status {service_name}")
    print(f"- View logs: journalctl --user -u {service_name}")
    print(f"- Stop service: systemctl --user stop {service_name}")
    print(f"- Start service: systemctl --user start {service_name}")
    print(f"- Restart service: systemctl --user restart {service_name}")

if __name__ == "__main__":
    main()
