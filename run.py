import subprocess
import time
import logging
from logging.handlers import RotatingFileHandler
import signal

# Logging Configurations
LOG_FILE = 'logs/device_monitor.log'
LOG_MAX_SIZE = 5242880  # 5MB
LOG_BACKUP_COUNT = 5

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        RotatingFileHandler(LOG_FILE, maxBytes=LOG_MAX_SIZE, backupCount=LOG_BACKUP_COUNT),
        logging.StreamHandler()
    ]
)

# Device Configurations
devices_config = '''
ATV01 192.168.50.101
ATV02 192.168.50.102
ATV03 192.168.50.103
ATV04 192.168.50.104
ATV05 192.168.50.105
ATV06 192.168.50.106
ATV07 192.168.50.107
ATV08 192.168.50.108
'''

# Function to read device configurations from the string
def read_device_config(config_string):
    devices = {}
    for line in config_string.strip().split('\n'):
        parts = line.strip().split()
        if len(parts) == 2:
            device_name, device_ip = parts
            devices[device_name] = device_ip
    return devices

# Read device configurations from the config string
devices = read_device_config(devices_config)

# Function to run adb command
def adb_command(device_ip, command):
    try:
        result = subprocess.run(
            f"adb -s {device_ip} {command}", 
            shell=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True, 
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        error_msg = f"Error running command: {e.cmd}, Error: {e.stderr.strip()}"
        logging.error(error_msg)
        return None

# Function to connect to a device
def connect_to_device(device_ip):
    try:
        result = subprocess.run(
            f"adb connect {device_ip}",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        if "connected" in result.stdout:
            logging.info(f"Successfully connected to {device_ip}")
            return True
        else:
            logging.error(f"Failed to connect to {device_ip}: {result.stdout}")
            return False
    except subprocess.CalledProcessError as e:
        logging.error(f"Error connecting to device {device_ip}: {e.stderr.strip()}")
        return False

# Function to restart ADB server
def restart_adb_server():
    try:
        subprocess.run("adb kill-server", shell=True, check=True)
        subprocess.run("adb start-server", shell=True, check=True)
        logging.info("ADB server restarted")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error restarting ADB server: {e.stderr.strip()}")

# Function to attempt reconnecting to a device
def attempt_reconnect(device_ip, max_attempts=3):
    for attempt in range(max_attempts):
        logging.info(f"Attempting to reconnect to {device_ip}, attempt {attempt + 1}")
        if connect_to_device(device_ip):
            return True
        time.sleep(5)  # Wait before retrying
    return False

# Function to get the currently focused app
def get_focused_app(device_ip):
    command = "shell dumpsys window windows"
    result = adb_command(device_ip, command)
    if result:
        lines = result.split('\n')
        for line in lines:
            if 'mCurrentFocus' in line:
                focused_app = line.split()[-1].split('/')[0]
                logging.info(f"{device_ip}: Current focused app is {focused_app}")
                return focused_app

        logging.error(f"{device_ip}: Unable to determine the focused app.")
    else:
        logging.error(f"{device_ip}: Failed to retrieve window information.")
    return None

# Function to stop and start an application
def restart_application(device_ip, package_name):
    logging.info(f"{device_ip}: Restarting {package_name}...")
    adb_command(device_ip, f"shell am force-stop {package_name}")
    adb_command(device_ip, f"shell am start -n {package_name}/.MainActivity")

# Function to process a single device
def process_device(device_name, device_ip):
    print(f"\nProcessing {device_name} - {device_ip}")
    print("-" * 40)

    if not connect_to_device(device_ip):
        if not attempt_reconnect(device_ip):
            logging.warning(f"Failed to connect to {device_ip} after initial attempts. Restarting ADB server...")
            restart_adb_server()
            if not attempt_reconnect(device_ip):
                logging.error(f"Failed to connect to {device_ip} after ADB restart. Skipping...")
                return

    focused_app = get_focused_app(device_ip)
    launcher_running = adb_command(device_ip, "shell pgrep -f com.gocheats.launcher")

    if focused_app != "com.nianticlabs.pokemongo":
        logging.warning(f"{device_ip}: Pokémon GO is not in focus. Restarting both apps...")
        restart_application(device_ip, "com.nianticlabs.pokemongo")
        restart_application(device_ip, "com.gocheats.launcher")
    elif not launcher_running:
        logging.warning(f"{device_ip}: Launcher is not running. Restarting launcher...")
        restart_application(device_ip, "com.gocheats.launcher")
    else:
        logging.info(f"{device_ip}: Pokémon GO is in focus and Launcher is running.")

# Main script logic
def run_script():
    try:
        while True:
            for device_name, device_ip in devices.items():
                process_device(device_name, device_ip)
                time.sleep(5)  # Delay between processing each device

            time.sleep(60)  # Delay before next round of checks

    except KeyboardInterrupt:
        logging.info("Script termination requested. Exiting...")

# Main function
def main():
    run_script()

if __name__ == "__main__":
    # Set up a signal handler for graceful shutdown
    signal.signal(signal.SIGINT, lambda sig, frame: logging.info("Script termination requested. Exiting..."))
    main()
