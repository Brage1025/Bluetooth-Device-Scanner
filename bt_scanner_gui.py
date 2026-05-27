#!/usr/bin/env python3
"""
Bluetooth Device Scanner - GUI
Cross-platform BLE and classic Bluetooth discovery.
"""

import asyncio
import json
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import subprocess
import sys
import csv
import os

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def check_hcitool_linux():
    if not sys.platform.startswith("linux"):
        return True
    try:
        subprocess.run(["which", "hcitool"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from bleak import BleakScanner, BleakClient
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData
except ImportError:
    print("Error: 'bleak' library not installed. Run: pip install bleak")
    sys.exit(1)

SERVICE_NAMES = {
    "00001800-0000-1000-8000-00805f9b34fb": "Generic Access",
    "00001801-0000-1000-8000-00805f9b34fb": "Generic Attribute",
    "0000180a-0000-1000-8000-00805f9b34fb": "Device Information",
    "0000180f-0000-1000-8000-00805f9b34fb": "Battery Service",
    "00001805-0000-1000-8000-00805f9b34fb": "Current Time",
    "0000180d-0000-1000-8000-00805f9b34fb": "Heart Rate",
    "00001812-0000-1000-8000-00805f9b34fb": "Human Interface Device",
    "0000fef3-0000-1000-8000-00805f9b34fb": "Google Fast Pair",
}

CHAR_NAMES = {
    "00002a00-0000-1000-8000-00805f9b34fb": "Device Name",
    "00002a01-0000-1000-8000-00805f9b34fb": "Appearance",
    "00002a19-0000-1000-8000-00805f9b34fb": "Battery Level",
    "00002a23-0000-1000-8000-00805f9b34fb": "System ID",
    "00002a24-0000-1000-8000-00805f9b34fb": "Model Number",
    "00002a25-0000-1000-8000-00805f9b34fb": "Serial Number",
    "00002a26-0000-1000-8000-00805f9b34fb": "Firmware Revision",
    "00002a27-0000-1000-8000-00805f9b34fb": "Hardware Revision",
    "00002a28-0000-1000-8000-00805f9b34fb": "Software Revision",
    "00002a29-0000-1000-8000-00805f9b34fb": "Manufacturer Name",
    "00002a50-0000-1000-8000-00805f9b34fb": "PnP ID",
}

MANUFACTURER_NAMES = {
    0x004C: "Apple Inc.", 0x0006: "Motorola", 0x060F: "Philips", 0x04C4: "Sennheiser",
    0x02E0: "Xiaomi", 0x0060: "Samsung", 0x0036: "Google", 0x0059: "Nordic",
    0x00E0: "Qualcomm", 0x001D: "Ericsson", 0x002A: "Nokia", 0x0032: "Huawei",
}

def decode_manufacturer_data(company_id: int, data: bytes) -> str:
    name = MANUFACTURER_NAMES.get(company_id, f"Unknown (0x{company_id:04X})")
    if company_id == 0x004C and len(data) >= 1:
        type_byte = data[0]
        if type_byte == 0x02: return f"{name} - iBeacon"
        if type_byte == 0x09: return f"{name} - AirDrop"
        if type_byte == 0x10: return f"{name} - AirPods/Find My"
    elif company_id == 0x060F: return f"{name} - Hue"
    return name

async def read_all_characteristics(client: BleakClient) -> Dict[str, Any]:
    result = {}
    for service in client.services:
        svc_uuid = service.uuid
        svc_name = SERVICE_NAMES.get(svc_uuid, svc_uuid)
        result[svc_uuid] = {"name": svc_name, "characteristics": {}}
        for char in service.characteristics:
            if "read" in char.properties:
                char_uuid = char.uuid
                char_name = CHAR_NAMES.get(char_uuid, char_uuid)
                try:
                    value = await client.read_gatt_char(char_uuid)
                    try:
                        decoded = value.decode("utf-8").strip()
                    except UnicodeDecodeError:
                        decoded = value.hex()
                    result[svc_uuid]["characteristics"][char_uuid] = {"name": char_name, "value": decoded}
                except Exception as e:
                    result[svc_uuid]["characteristics"][char_uuid] = {"name": char_name, "error": str(e)}
    return result

async def get_ble_device_details(device: BLEDevice, advertisement: AdvertisementData, timeout_sec: int = 12) -> Dict:
    connectable = getattr(advertisement, 'is_connectable', True)
    tx_power = getattr(advertisement, 'tx_power', None)
    details = {
        "type": "BLE",
        "address": device.address,
        "name": device.name or advertisement.local_name or "Unknown",
        "rssi": advertisement.rssi,
        "tx_power": tx_power,
        "manufacturer_data": {},
        "service_uuids": advertisement.service_uuids,
        "connectable": connectable,
        "services": {},
        "key_details": {}
    }
    for cid, data in advertisement.manufacturer_data.items():
        details["manufacturer_data"][f"0x{cid:04X}"] = decode_manufacturer_data(cid, data)

    if not connectable:
        details["key_details"]["error"] = "Not connectable"
        return details

    try:
        async with BleakClient(device, timeout=timeout_sec) as client:
            if not client.is_connected:
                details["key_details"]["error"] = "Connection failed"
                return details
            services_data = await read_all_characteristics(client)
            details["services"] = services_data

            gen_access = "00001800-0000-1000-8000-00805f9b34fb"
            if gen_access in services_data:
                chars = services_data[gen_access]["characteristics"]
                real_name = chars.get("00002a00-0000-1000-8000-00805f9b34fb", {}).get("value")
                if real_name and isinstance(real_name, str) and real_name.strip():
                    details["name"] = real_name.strip()

            dev_info = "0000180a-0000-1000-8000-00805f9b34fb"
            if dev_info in services_data:
                chars = services_data[dev_info]["characteristics"]
                details["key_details"]["manufacturer"] = chars.get("00002a29-0000-1000-8000-00805f9b34fb", {}).get("value")
                details["key_details"]["model_number"] = chars.get("00002a24-0000-1000-8000-00805f9b34fb", {}).get("value")
                details["key_details"]["serial_number"] = chars.get("00002a25-0000-1000-8000-00805f9b34fb", {}).get("value")
                details["key_details"]["firmware_revision"] = chars.get("00002a26-0000-1000-8000-00805f9b34fb", {}).get("value")
                details["key_details"]["hardware_revision"] = chars.get("00002a27-0000-1000-8000-00805f9b34fb", {}).get("value")
                details["key_details"]["software_revision"] = chars.get("00002a28-0000-1000-8000-00805f9b34fb", {}).get("value")
                details["key_details"]["pnp_id"] = chars.get("00002a50-0000-1000-8000-00805f9b34fb", {}).get("value")
                details["key_details"]["system_id"] = chars.get("00002a23-0000-1000-8000-00805f9b34fb", {}).get("value")

            battery = "0000180f-0000-1000-8000-00805f9b34fb"
            if battery in services_data:
                chars = services_data[battery]["characteristics"]
                batt_val = chars.get("00002a19-0000-1000-8000-00805f9b34fb", {}).get("value")
                if batt_val is not None:
                    try:
                        details["key_details"]["battery_level"] = int(batt_val)
                    except:
                        details["key_details"]["battery_level"] = batt_val
    except asyncio.TimeoutError:
        details["key_details"]["error"] = "Connection timeout"
    except Exception as e:
        details["key_details"]["error"] = str(e)
    return details

def get_classic_devices_linux() -> List[Dict]:
    devices = []
    try:
        output = subprocess.check_output(["hcitool", "scan"], stderr=subprocess.DEVNULL, timeout=15).decode()
        lines = output.strip().split("\n")
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 2:
                addr = parts[0]
                name = " ".join(parts[1:])
                devices.append({
                    "type": "Classic",
                    "address": addr,
                    "name": name,
                    "rssi": None,
                    "connectable": True,
                    "key_details": {},
                    "services": {}
                })
    except Exception:
        pass
    return devices

def get_classic_devices_windows() -> List[Dict]:
    devices = []
    try:
        cmd = ['powershell', '-Command', 'Get-PnpDevice -Class Bluetooth | Where-Object {$_.FriendlyName -like "*" -and $_.Status -eq "OK"} | Select-Object FriendlyName, InstanceId']
        output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=10).decode()
        for line in output.splitlines():
            if "Bluetooth" in line and ":" in line:
                name = line.strip()
                devices.append({
                    "type": "Classic",
                    "address": "Paired device (address not available)",
                    "name": name,
                    "rssi": None,
                    "connectable": True,
                    "key_details": {"info": "This is a paired device. Active classic scanning is not possible on Windows."},
                    "services": {}
                })
    except Exception:
        pass
    return devices

def scan_classic_devices() -> List[Dict]:
    if sys.platform.startswith("linux"):
        return get_classic_devices_linux()
    elif sys.platform.startswith("win"):
        return get_classic_devices_windows()
    return []

async def scan_ble_devices(duration_sec: int, max_devices: int, min_rssi: int, stop_event: asyncio.Event,
                           progress_callback=None, log_callback=None) -> List[Tuple]:
    devices_found = {}
    def callback(device: BLEDevice, adv: AdvertisementData):
        if min_rssi is not None and adv.rssi < min_rssi:
            return
        if device.address not in devices_found:
            devices_found[device.address] = (device, adv)

    if log_callback:
        log_callback(f"[*] Scanning for BLE devices for {duration_sec} seconds...")

    scanner = BleakScanner(callback)
    await scanner.start()
    for i in range(duration_sec):
        if stop_event.is_set():
            break
        await asyncio.sleep(1)
        if not stop_event.is_set() and progress_callback:
            progress_callback(i+1, duration_sec, "scanning_ble")
    await scanner.stop()

    items = list(devices_found.items())
    if max_devices > 0:
        items = items[:max_devices]
    if log_callback:
        log_callback(f"[*] Found {len(items)} device(s). Connecting to each to retrieve details...\n")
    return items

async def interrogate_ble_devices(items: List[Tuple], parallel: int, timeout: int, stop_event: asyncio.Event,
                                   progress_callback=None, log_callback=None) -> List[Dict]:
    results = []
    total = len(items)
    if parallel > 1:
        sem = asyncio.Semaphore(parallel)
        async def process_one_sem(addr, dev_adv, idx):
            if stop_event.is_set():
                return None
            async with sem:
                dev_name = dev_adv[0].name or dev_adv[1].local_name or "Unknown"
                if log_callback:
                    log_callback(f"  [{idx}/{total}] Processing {addr} - {dev_name}")
                if progress_callback:
                    progress_callback(idx, total, "connecting")
                return await get_ble_device_details(dev_adv[0], dev_adv[1], timeout)
        tasks = []
        for idx, (addr, (dev, adv)) in enumerate(items, 1):
            if stop_event.is_set():
                break
            tasks.append(process_one_sem(addr, (dev, adv), idx))
        gathered = await asyncio.gather(*tasks, return_exceptions=True)
        for r in gathered:
            if r and not isinstance(r, Exception):
                results.append(r)
    else:
        for idx, (addr, (dev, adv)) in enumerate(items, 1):
            if stop_event.is_set():
                break
            dev_name = dev.name or adv.local_name or "Unknown"
            if log_callback:
                log_callback(f"  [{idx}/{total}] Processing {addr} - {dev_name}")
            if progress_callback:
                progress_callback(idx, total, "connecting")
            details = await get_ble_device_details(dev, adv, timeout)
            results.append(details)
            await asyncio.sleep(0.2)
    return results

class BluetoothScannerApp:
    def __init__(self, root):
        self.root = root
        root.title("Bluetooth Device Scanner")
        root.geometry("920x650")
        root.minsize(850, 600)
        root.resizable(True, True)

        self.hcitool_available = check_hcitool_linux()
        if not self.hcitool_available and sys.platform.startswith("linux"):
            messagebox.showwarning(
                "Missing dependency",
                "The 'hcitool' command is not installed.\n\n"
                "Classic Bluetooth discovery will not work.\n"
                "To install it, run: sudo apt install bluez-utils\n\n"
                "BLE scanning will still work normally."
            )

        icon_path = resource_path("BluetoothDeviceScannerIcon.ico")
        if os.path.exists(icon_path):
            try:
                root.iconbitmap(icon_path)
            except Exception:
                pass

        main_frame = tk.Frame(root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        top_frame = tk.Frame(main_frame)
        top_frame.pack(fill=tk.X)

        control_frame = tk.Frame(top_frame)
        control_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        row0 = tk.Frame(control_frame)
        row0.pack(fill=tk.X, pady=2)
        tk.Label(row0, text="Max Devices:", font=("Arial", 9), width=12, anchor="e").pack(side=tk.LEFT, padx=2)
        self.max_devices_var = tk.StringVar(value="69")
        tk.Entry(row0, textvariable=self.max_devices_var, width=6).pack(side=tk.LEFT, padx=2)

        tk.Label(row0, text="Scan Time (sec):", font=("Arial", 9), width=14, anchor="e").pack(side=tk.LEFT, padx=2)
        self.scan_time_var = tk.StringVar(value="10")
        tk.Entry(row0, textvariable=self.scan_time_var, width=6).pack(side=tk.LEFT, padx=2)

        tk.Label(row0, text="Min RSSI (dBm):", font=("Arial", 9), width=14, anchor="e").pack(side=tk.LEFT, padx=2)
        self.min_rssi_var = tk.StringVar(value="-100")
        tk.Entry(row0, textvariable=self.min_rssi_var, width=6).pack(side=tk.LEFT, padx=2)

        tk.Label(row0, text="Parallel connections:", font=("Arial", 9), width=18, anchor="e").pack(side=tk.LEFT, padx=2)
        self.parallel_var = tk.StringVar(value="3")
        tk.Entry(row0, textvariable=self.parallel_var, width=4).pack(side=tk.LEFT, padx=2)

        row1 = tk.Frame(control_frame)
        row1.pack(fill=tk.X, pady=2)
        self.classic_var = tk.BooleanVar(value=False)
        self.classic_check = tk.Checkbutton(row1, text="Include Classic Bluetooth", variable=self.classic_var, font=("Arial", 9))
        self.classic_check.pack(side=tk.LEFT, padx=2)

        self.windows_warning_label = tk.Label(row1, text="* Windows: only paired devices", fg="orange", font=("Arial", 8, "italic"))
        self.windows_warning_label.pack_forget()

        if sys.platform.startswith("linux") and not self.hcitool_available:
            linux_warning = tk.Label(row1, text="* hcitool missing – classic disabled", fg="red", font=("Arial", 8, "italic"))
            linux_warning.pack(side=tk.LEFT, padx=5)
            self.classic_check.config(state=tk.DISABLED)

        if sys.platform.startswith("win"):
            def toggle_windows_warning(*args):
                if self.classic_var.get():
                    self.windows_warning_label.pack(side=tk.LEFT, padx=5)
                else:
                    self.windows_warning_label.pack_forget()
            self.classic_var.trace_add("write", toggle_windows_warning)

        self.scan_button = tk.Button(row1, text="Start Scan", command=self.start_scan, bg="#4CAF50", fg="white", font=("Arial", 9, "bold"), padx=8)
        self.scan_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = tk.Button(row1, text="Stop", command=self.stop_scan, state=tk.DISABLED, bg="#f44336", fg="white", font=("Arial", 9), padx=8)
        self.stop_button.pack(side=tk.LEFT, padx=3)

        self.save_txt_button = tk.Button(row1, text="Save .TXT", command=self.save_txt, state=tk.DISABLED, font=("Arial", 8))
        self.save_txt_button.pack(side=tk.LEFT, padx=3)
        self.save_json_button = tk.Button(row1, text="Save .JSON", command=self.save_json, state=tk.DISABLED, font=("Arial", 8))
        self.save_json_button.pack(side=tk.LEFT, padx=3)
        self.save_csv_button = tk.Button(row1, text="Save .CSV", command=self.save_csv, state=tk.DISABLED, font=("Arial", 8))
        self.save_csv_button.pack(side=tk.LEFT, padx=3)

        logo_frame = tk.Frame(top_frame, width=160, height=80, bg="#f0f0f0", relief=tk.RIDGE, bd=1)
        logo_frame.pack(side=tk.RIGHT, padx=(10,0), fill=None, expand=False)
        logo_frame.pack_propagate(False)

        self.logo_image = None
        logo_path = resource_path("BluetoothDeviceScannerLogo.png")
        if os.path.exists(logo_path) and PIL_AVAILABLE:
            try:
                img = Image.open(logo_path)
                img_resized = img.resize((160, 80), Image.Resampling.LANCZOS)
                self.logo_image = ImageTk.PhotoImage(img_resized)
                logo_label = tk.Label(logo_frame, image=self.logo_image, bg="#f0f0f0")
                logo_label.pack(expand=True)
            except Exception:
                tk.Label(logo_frame, text="Logo error", bg="#f0f0f0", fg="red", font=("Arial", 7)).pack(expand=True)
        else:
            tk.Label(logo_frame, text="Logo missing", bg="#f0f0f0", fg="#999", font=("Arial", 7, "italic")).pack(expand=True)

        self.progress_label = tk.Label(main_frame, text="", font=("Arial", 8), fg="blue")
        self.progress_label.pack(pady=(2,0), fill=tk.X)

        output_label_frame = tk.Frame(main_frame)
        output_label_frame.pack(fill=tk.X, pady=(2,0))
        tk.Label(output_label_frame, text="Output:", font=("Arial", 10, "bold"), anchor="w").pack(side=tk.LEFT)
        clear_button = tk.Button(output_label_frame, text="Clear Output", command=self.clear_output, font=("Arial", 8), padx=5)
        clear_button.pack(side=tk.RIGHT, padx=5)

        self.output_text = scrolledtext.ScrolledText(
            main_frame, wrap=tk.WORD, width=100, height=25,
            font=("Consolas", 8), bg="black", fg="white",
            insertbackground="white"
        )
        self.output_text.pack(padx=3, pady=(2,3), fill=tk.BOTH, expand=True)

        self.scan_results = []
        self.is_scanning = False
        self.stop_event = asyncio.Event()
        self.scan_task = None

    def clear_output(self):
        self.output_text.delete(1.0, tk.END)
        self.output_text.insert(tk.END, "[Output cleared]\n")

    def log_message(self, msg: str):
        self.output_text.insert(tk.END, msg + "\n")
        self.output_text.see(tk.END)

    def start_scan(self):
        if self.is_scanning:
            return

        try:
            max_dev = int(self.max_devices_var.get())
            scan_sec = int(self.scan_time_var.get())
            min_rssi = int(self.min_rssi_var.get())
            parallel = int(self.parallel_var.get())
            include_classic = self.classic_var.get()
        except ValueError:
            messagebox.showerror("Error", "All numeric fields must be integers.")
            return

        self.scan_button.config(state=tk.DISABLED, text="Scanning...")
        self.stop_button.config(state=tk.NORMAL)
        self.save_txt_button.config(state=tk.DISABLED)
        self.save_json_button.config(state=tk.DISABLED)
        self.save_csv_button.config(state=tk.DISABLED)
        self.output_text.delete(1.0, tk.END)
        self.scan_results = []
        self.is_scanning = True
        self.stop_event.clear()
        self.progress_label.config(text="Starting scan...")

        def run_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(
                    self._async_scan(scan_sec, max_dev, min_rssi, parallel, include_classic)
                )
                loop.close()
                self.root.after(0, self.scan_finished, results)
            except Exception as e:
                self.root.after(0, self.scan_error, str(e))

        self.scan_task = threading.Thread(target=run_async, daemon=True)
        self.scan_task.start()

    async def _async_scan(self, scan_sec, max_dev, min_rssi, parallel, include_classic):
        def log(msg):
            self.root.after(0, lambda: self.log_message(msg))

        try:
            ble_items = await scan_ble_devices(scan_sec, max_dev, min_rssi, self.stop_event,
                                               self.update_progress, log)
        except Exception as e:
            self.root.after(0, lambda: log(f"[!] Bluetooth error: {e}"))
            self.root.after(0, lambda: messagebox.showerror("Bluetooth Error", f"Failed to start scan.\n\nError: {e}\n\nPlease ensure Bluetooth is enabled and the adapter is working."))
            return []

        if self.stop_event.is_set():
            return []
        ble_results = await interrogate_ble_devices(ble_items, parallel, 12, self.stop_event,
                                                    self.update_progress, log)
        if self.stop_event.is_set():
            return []
        all_results = ble_results.copy()

        if include_classic and not self.stop_event.is_set():
            self.root.after(0, lambda: log("Scanning Classic devices..."))
            if sys.platform.startswith("linux") and not self.hcitool_available:
                self.root.after(0, lambda: log("[!] hcitool missing – classic scanning skipped. Install bluez-utils: sudo apt install bluez-utils"))
            elif sys.platform.startswith("win"):
                self.root.after(0, lambda: log("[!] Windows note: Only paired classic devices are listed."))
            else:
                classic = await asyncio.get_event_loop().run_in_executor(None, scan_classic_devices)
                if not self.stop_event.is_set():
                    all_results.extend(classic)
                    log(f"[*] Found {len(classic)} classic device(s).")
        return all_results

    def update_progress(self, current, total, phase):
        if self.stop_event.is_set():
            return
        if phase == "scanning_ble":
            percent = int((current / total) * 100)
            self.root.after(0, lambda: self.progress_label.config(text=f"BLE Scanning... {percent}% ({current}/{total} sec)"))
        elif phase == "connecting":
            self.root.after(0, lambda: self.progress_label.config(text=f"Connecting to device {current}/{total}..."))

    def stop_scan(self):
        self.stop_event.set()
        self.log_message("[!] Stopping scan...")
        self.progress_label.config(text="Stopping scan...")
        self.stop_button.config(state=tk.DISABLED)

    def scan_finished(self, results):
        self.is_scanning = False
        self.scan_button.config(state=tk.NORMAL, text="Start Scan")
        self.stop_button.config(state=tk.DISABLED)
        if not self.stop_event.is_set():
            self.scan_results = results
            self.save_txt_button.config(state=tk.NORMAL)
            self.save_json_button.config(state=tk.NORMAL)
            self.save_csv_button.config(state=tk.NORMAL)
            self.progress_label.config(text=f"Scan complete. Found {len(results)} devices.")
            self.log_message(f"\n[*] Scan complete. Found {len(results)} devices.\n")
            self.display_results(results)
        else:
            self.progress_label.config(text="Scan stopped by user.")
            self.log_message("Scan was stopped by user.")

    def scan_error(self, error_msg):
        self.is_scanning = False
        self.scan_button.config(state=tk.NORMAL, text="Start Scan")
        self.stop_button.config(state=tk.DISABLED)
        self.progress_label.config(text="Scan failed.")
        self.log_message(f"[!] Error: {error_msg}")
        messagebox.showerror("Scan Error", error_msg)

    def display_results(self, results):
        if not results:
            self.log_message("No devices found.")
            return

        for dev in results:
            self.log_message("=" * 70)
            self.log_message(f"Type          : {dev.get('type', 'BLE')}")
            self.log_message(f"Address       : {dev['address']}")
            self.log_message(f"Name          : {dev['name']}")
            self.log_message(f"RSSI          : {dev['rssi'] if dev['rssi'] is not None else 'N/A'} dBm")
            if dev.get('connectable'):
                self.log_message(f"Connectable   : {dev['connectable']}")
            if dev.get('tx_power'):
                self.log_message(f"TX Power      : {dev['tx_power']} dBm")
            if dev.get('manufacturer_data'):
                self.log_message("Manufacturer data:")
                for code, name in dev['manufacturer_data'].items():
                    self.log_message(f"  - {code}: {name}")
            if dev.get('service_uuids'):
                self.log_message(f"Advertised services ({len(dev['service_uuids'])}):")
                for uuid in dev['service_uuids']:
                    svc_name = SERVICE_NAMES.get(uuid, uuid)
                    self.log_message(f"  - {svc_name}")
            if dev.get('key_details'):
                self.log_message("Key details:")
                for key, val in dev['key_details'].items():
                    if val:
                        self.log_message(f"  - {key}: {val}")
            if dev.get('services') and dev.get('type', 'BLE') == 'BLE':
                self.log_message("Full characteristic dump:")
                for svc_uuid, svc_info in dev['services'].items():
                    svc_name = svc_info.get('name', svc_uuid)
                    self.log_message(f"  Service: {svc_name}")
                    for char_uuid, char_info in svc_info.get('characteristics', {}).items():
                        char_name = char_info.get('name', char_uuid)
                        if 'error' in char_info:
                            self.log_message(f"    - {char_name}: ERROR {char_info['error']}")
                        else:
                            val = char_info.get('value', '')
                            self.log_message(f"    - {char_name}: {val}")
            self.log_message("=" * 70 + "\n")

    def save_txt(self):
        if not self.scan_results:
            messagebox.showwarning("No data", "No scan results.")
            return
        filename = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files", "*.txt")])
        if filename:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"Bluetooth Scan Report - {datetime.now().isoformat()}\n\n")
                for dev in self.scan_results:
                    f.write("="*70 + "\n")
                    f.write(f"Type: {dev.get('type','BLE')}\n")
                    f.write(f"Address: {dev['address']}\n")
                    f.write(f"Name: {dev['name']}\n")
                    f.write(f"RSSI: {dev['rssi'] if dev['rssi'] is not None else 'N/A'} dBm\n")
                    if dev.get('connectable'):
                        f.write(f"Connectable: {dev['connectable']}\n")
                    if dev.get('tx_power'):
                        f.write(f"TX Power: {dev['tx_power']} dBm\n")
                    if dev.get('manufacturer_data'):
                        f.write("Manufacturer data:\n")
                        for code, name in dev['manufacturer_data'].items():
                            f.write(f"  - {code}: {name}\n")
                    if dev.get('service_uuids'):
                        f.write(f"Advertised services ({len(dev['service_uuids'])}):\n")
                        for uuid in dev['service_uuids']:
                            svc_name = SERVICE_NAMES.get(uuid, uuid)
                            f.write(f"  - {svc_name}\n")
                    if dev.get('key_details'):
                        f.write("Key details:\n")
                        for k, v in dev['key_details'].items():
                            if v:
                                f.write(f"  - {k}: {v}\n")
                    if dev.get('services') and dev.get('type', 'BLE') == 'BLE':
                        f.write("Full characteristic dump:\n")
                        for svc_uuid, svc_info in dev['services'].items():
                            svc_name = svc_info.get('name', svc_uuid)
                            f.write(f"  Service: {svc_name}\n")
                            for char_uuid, char_info in svc_info.get('characteristics', {}).items():
                                char_name = char_info.get('name', char_uuid)
                                if 'error' in char_info:
                                    f.write(f"    - {char_name}: ERROR {char_info['error']}\n")
                                else:
                                    f.write(f"    - {char_name}: {char_info.get('value', '')}\n")
                    f.write("\n")
            messagebox.showinfo("Saved", f"Saved to {filename}")

    def save_json(self):
        if not self.scan_results:
            messagebox.showwarning("No data", "No scan results.")
            return
        filename = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if filename:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump({"scan_time": datetime.now().isoformat(), "devices": self.scan_results}, f, indent=2, default=str)
            messagebox.showinfo("Saved", f"Saved to {filename}")

    def save_csv(self):
        if not self.scan_results:
            messagebox.showwarning("No data", "No scan results.")
            return
        filename = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if filename:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Type", "Address", "Name", "RSSI", "TX Power", "Connectable",
                    "Manufacturer", "Model Number", "Serial Number", "Firmware Revision",
                    "Hardware Revision", "Software Revision", "PnP ID", "System ID",
                    "Battery Level", "Advertised Service UUIDs", "Manufacturer Data", "Error"
                ])
                for dev in self.scan_results:
                    key = dev.get('key_details', {})
                    service_uuids = dev.get('service_uuids', [])
                    service_uuids_str = ";".join(service_uuids) if service_uuids else ""
                    manuf_data = dev.get('manufacturer_data', {})
                    manuf_str = ";".join([f"{code}:{name}" for code, name in manuf_data.items()]) if manuf_data else ""
                    writer.writerow([
                        dev.get('type', 'BLE'),
                        dev['address'],
                        dev['name'],
                        dev['rssi'] if dev['rssi'] is not None else '',
                        dev.get('tx_power', ''),
                        dev.get('connectable', ''),
                        key.get('manufacturer', ''),
                        key.get('model_number', ''),
                        key.get('serial_number', ''),
                        key.get('firmware_revision', ''),
                        key.get('hardware_revision', ''),
                        key.get('software_revision', ''),
                        key.get('pnp_id', ''),
                        key.get('system_id', ''),
                        key.get('battery_level', ''),
                        service_uuids_str,
                        manuf_str,
                        key.get('error', ''),
                    ])
            messagebox.showinfo("Saved", f"Saved to {filename}")

def main():
    root = tk.Tk()
    app = BluetoothScannerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()