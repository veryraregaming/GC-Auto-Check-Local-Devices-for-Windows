import subprocess
import time
import logging
import threading
from logging.handlers import RotatingFileHandler
from pystray import Icon as icon, Menu as menu, MenuItem as item
from PIL import Image, ImageDraw
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

# Main script logic
def run_script():
    try:
        adb_command('localhost', "start-server")

        while True:
            for device, device_ip in devices.items():
                print(f"\nProcessing {device} - {device_ip}")
                print("-" * 40)

                focused_app = get_focused_app(device_ip)
                launcher_running = adb_command(device_ip, "shell pgrep -f com.gocheats.launcher")

                if focused_app != "com.nianticlabs.pokemongo":
                    logging.warning(f"{device}: Pokémon GO is not in focus. Restarting both apps...")
                    restart_application(device_ip, "com.nianticlabs.pokemongo")
                    restart_application(device_ip, "com.gocheats.launcher")
                elif not launcher_running:
                    logging.warning(f"{device}: Launcher is not running. Restarting launcher...")
                    restart_application(device_ip, "com.gocheats.launcher")
                else:
                    logging.info(f"{device}: Pokémon GO is in focus and Launcher is running.")

                time.sleep(5)  # Delay between processing each device

            time.sleep(60)  # Delay before next round of checks

    except KeyboardInterrupt:
        logging.info("Script termination requested. Exiting...")

# Function to create an image for the system tray icon
def create_image():
    image = Image.new('RGB', (64, 64), color=(0, 0, 0))
    d = ImageDraw.Draw(image)
    d.rectangle([0, 0, 64, 64], fill=(255, 255, 255))
    d.text((10, 10), "Run", fill=(0, 0, 0))
    return image

# Function to stop the icon and script
def on_clicked(icon, item):
    icon.stop()

# Function to setup icon and start the script
def setup(icon):
    icon.visible = True
    threading.Thread(target=run_script).start()

# Function to run the system tray icon in a separate thread
def run_system_tray():
    icon('Device Monitor', create_image(), menu=menu(item('Quit', on_clicked))).run(setup)

# Main function
def main():
    # Run the system tray icon in a separate thread
    system_tray_thread = threading.Thread(target=run_system_tray)
    system_tray_thread.start()

    # Wait for the system tray thread to finish
    system_tray_thread.join()

if __name__ == "__main__":
    # Set up a signal handler for graceful shutdown
    signal.signal(signal.SIGINT, lambda sig, frame: logging.info("Script termination requested. Exiting..."))
    main()
