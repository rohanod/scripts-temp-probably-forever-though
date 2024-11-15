import os
import subprocess
import sys
import time
import shutil
import hashlib
import json
from pathlib import Path

class PicoDuckySetup:
    def __init__(self):
        self.config = {
            "drives": {
                "bootloader": "/Volumes/RPI-RP2",
                "circuitpy": "/Volumes/CIRCUITPY"
            },
            "files": {
                "flash_nuke": {
                    "name": "flash_nuke.uf2",
                    "url": "https://cdn-learn.adafruit.com/assets/assets/000/099/419/original/flash_nuke.uf2"
                },
                "circuitpy": {
                    "name": "adafruit-circuitpython-raspberry_pi_pico-en_US-8.0.0.uf2",
                    "url": "https://downloads.circuitpython.org/bin/raspberry_pi_pico/en_US/adafruit-circuitpython-raspberry_pi_pico-en_US-8.0.0.uf2"
                }
            },
            "repo": {
                "url": "https://github.com/rohanod/copy_to_py.git",
                "folder": "copy_to_py"
            }
        }
        self.state = self.load_state()

    def load_state(self):
        if os.path.exists('setup_state.json'):
            with open('setup_state.json', 'r') as f:
                return json.load(f)
        return {"completed_steps": []}

    def save_state(self):
        with open('setup_state.json', 'w') as f:
            json.dump(self.state, f)

    def verify_checksum(self, file_path, expected_hash=None):
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest() if not expected_hash else sha256_hash.hexdigest() == expected_hash

    def run_command(self, command, cwd=None):
        try:
            result = subprocess.run(
                command,
                shell=True,
                check=True,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(f"Error: {e.stderr}")
            raise RuntimeError(f"Command failed: {e.stderr}")

    def wait_for_drive(self, drive_path, timeout=30):
        print(f"Waiting for drive: {drive_path}")
        start_time = time.time()
        while time.time() - start_time < timeout:
            if os.path.exists(drive_path) and os.path.ismount(drive_path):
                time.sleep(2)
                print(f"Drive {drive_path} found.")
                return True
            time.sleep(1)
        raise RuntimeError(f"Timeout waiting for drive: {drive_path}")

    def download_file(self, url, filename):
        if not os.path.exists(filename):
            print(f"Downloading {filename} from {url}")
            self.run_command(f"curl -L -o {filename} {url}")
        print(f"Verifying checksum for {filename}")
        return self.verify_checksum(filename)

    def copy_to_drive(self, src, dest_drive):
        print(f"Copying {src} to {dest_drive}")
        if not self.wait_for_drive(dest_drive):
            raise RuntimeError(f"Drive {dest_drive} not available")
        shutil.copy2(src, dest_drive)
        time.sleep(2)

    def setup_repo(self):
        if "repo_setup" in self.state["completed_steps"]:
            print("Repository already set up")
            return

        print("Setting up repository...")
        repo_folder = self.config["repo"]["folder"]
        if not os.path.exists(repo_folder):
            print(f"Cloning repository from {self.config['repo']['url']}")
            self.run_command(f"git clone {self.config['repo']['url']}")

        self.state["completed_steps"].append("repo_setup")
        self.save_state()

    def flash_device(self):
        if "device_flashed" in self.state["completed_steps"]:
            print("Device already flashed")
            return

        print("Flashing the device...")
        bootloader_drive = self.config["drives"]["bootloader"]

        for file_key, file_info in self.config["files"].items():
            print(f"Processing file: {file_info['name']}")
            if not self.wait_for_drive(bootloader_drive):
                raise RuntimeError("Bootloader drive not found")

            self.download_file(file_info["url"], file_info["name"])
            self.copy_to_drive(file_info["name"], bootloader_drive)
            time.sleep(5)

        self.state["completed_steps"].append("device_flashed")
        self.save_state()

    def copy_files(self):
        if "files_copied" in self.state["completed_steps"]:
            print("Files already copied")
            return

        print("Copying project files to CircuitPy...")
        circuitpy_drive = self.config["drives"]["circuitpy"]
        if not self.wait_for_drive(circuitpy_drive):
            raise RuntimeError("CircuitPy drive not found")

        source_folder = Path(self.config["repo"]["folder"])
        for item in source_folder.iterdir():
            if item.name == ".DS_Store":
                continue

            dest = Path(circuitpy_drive) / item.name
            if item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

        self.state["completed_steps"].append("files_copied")
        self.save_state()

    def cleanup(self):
        print("Cleaning up temporary files...")
        for file_info in self.config["files"].values():
            if os.path.exists(file_info["name"]):
                os.remove(file_info["name"])

    def run(self):
        try:
            print("Starting PicoDucky setup process...")
            if os.path.exists(self.config["drives"]["circuitpy"]):
                print("CircuitPy drive detected, skipping to file copy")
                self.setup_repo()
                self.copy_files()
            else:
                self.setup_repo()
                self.flash_device()
                self.copy_files()

            print("Setup completed successfully")
            self.cleanup()

        except Exception as e:
            print(f"Setup failed: {str(e)}")
            raise

def main():
    try:
        setup = PicoDuckySetup()
        setup.run()
    except PermissionError:
        print(f"Permission denied. Try: sudo {sys.executable} {' '.join(sys.argv)}")
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
