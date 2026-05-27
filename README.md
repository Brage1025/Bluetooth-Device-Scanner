# Bluetooth Device Scanner

A cross‑platform GUI tool to discover Bluetooth Low Energy (BLE) devices, connect to them, and extract detailed information (manufacturer, model, serial number, firmware, battery level, and all readable characteristics). Also supports **limited classic Bluetooth** discovery (Linux: full scan, Windows: paired devices only).

![Screenshot](./screenshot.png)

---

## Features

- **BLE scanning** – finds all advertising BLE devices
- **Deep device interrogation** – reads all available characteristics (Device Information, Battery, etc.)
- **Parallel connections** – speeds up scanning of many devices
- **Export results** – save as TXT, JSON, or CSV (rich columns)
- **Stop button** – cancel scan at any time
- **Platform awareness**
  - Windows: classic Bluetooth shows **only paired** devices (active scan not possible)
  - Linux: requires `hcitool` for classic scanning (BLE works without it)
- **Live output** – see discovered devices and connection progress in real time
- **Clear Output** button – keeps log manageable
- **Custom logo & icon** – professional branding

---

## Requirements

### Runtime (when running from source)

- Python 3.7 or later
- `bleak` – BLE library
- `Pillow` – for logo display (optional, falls back to text)

Install with:

```bash
pip install bleak Pillow
```

### For classic Bluetooth on Linux

Install `bluez-utils`:

```bash
sudo apt install bluez-utils   # Debian/Ubuntu
```

## Usage

### Run from source

```bash
python bt_scanner_gui.py
```

### Build standalone executable

1. Install PyInstaller: `pip install pyinstaller`

2. Run the build command (Windows example):

```bash
python -m PyInstaller --onefile --windowed --name "BTScanner" --icon=BluetoothDeviceScannerIcon.ico --add-data "BluetoothDeviceScannerLogo.png;." --add-data "BluetoothDeviceScannerIcon.ico;." --hidden-import PIL --hidden-import PIL.Image --hidden-import PIL.ImageTk bt_scanner_gui.py
```

3. The executable will be in the `dist` folder.

> **Note for Linux/macOS: replace semicolons `;` with colons `:` in `--add-data`.**

## Interface

- **Max Devices** – limit the number of devices processed (0 = unlimited)

- **Scan Time (sec)** – how long to listen for advertisements

- **Min RSSI (dBm)** – ignore signals weaker than this (e.g., -80)

- **Parallel connections** – number of simultaneous BLE connections

- **Include Classic Bluetooth** – on Windows: paired devices only; on Linux: full scan (requires `hcitool`)

- **Start Scan / Stop** – start or cancel the scan

- **Save .TXT / .JSON / .CSV** – export results after scan

- **Clear Output** – erase the log

## Output Files

- **TXT** – full characteristic dump for each device, human‑readable

- **JSON** – complete structured data, ideal for scripting

- **CSV** – flattened summary with columns:

```text
Type, Address, Name, RSSI, TX Power, Connectable, Manufacturer, Model Number, Serial Number, Firmware Revision, Hardware Revision, Software Revision, PnP ID, System ID, Battery Level, Advertised Service UUIDs, Manufacturer Data, Error
```

## Platform Limitations

| Platform | BLE                              | Classic Bluetooth                                                                            |
| -------- | -------------------------------- | -------------------------------------------------------------------------------------------- |
| Windows  | Full support                     | **Only** already paired devices are listed (Windows does not allow active classic discovery) |
| Linux    | Full support                     | Full scan via `hcitool` – install `bluez-utils`                                              |
| macOS    | Full support (via CoreBluetooth) | **Not supported**                                                                            |

## Troubleshooting

- **No Bluetooth adapter found?**

  Ensure Bluetooth is enabled and the adapter is working. The app does not pre‑check the adapter
  – if scanning fails, an error message will appear.

- **Linux classic scan doesn’t work**

  Install `bluez-utils`: `sudo apt install bluez-utils`
  <br>You may also need to run the executable with `sudo` if permission is denied. <br>

- **Logo or icon not showing in the built** `.exe`
  Make sure you used `--add-data` correctly and that the files are in the same folder when building.

- **CSV columns are too many**
  The CSV is designed for data analysis. Use JSON or TXT for full detail.

## License

[MIT](LICENSE) – free to use, modify, and distribute.

## Acknowledgements

[bleak](https://github.com/hbldh/bleak) – cross‑platform BLE library

[PyInstaller](https://pyinstaller.org/en/stable/) – for making standalone executables

## Contact / Support

For issues or feature requests, please open an issue on the repository (replace with the actual URL).

---

<div align="center">

_"To &lt;div&gt; or not to &lt;div&gt;, that is the question."_
— [Brage1025](https://github.com/Brage1025)

</div>
