# GTAV HeightMap Editor

A desktop GUI to view, export, edit, and re-pack GTA V heightmap data. Supports reading HMAP `.dat` files (Max/Min arrays) directly, previewing with orientation fixed, exporting PNG/HEX, and updating the original `.dat` with edited PNGs.

<img width="1918" height="1032" alt="image" src="https://github.com/user-attachments/assets/c402e7d0-bdce-4700-b831-9547caed31c7" />

## Features
- Load HMAP `.dat` files and parse Max/Min arrays
- Preview normalized Min/Max images with correct orientation
- Export Min/Max to PNG or HEX text format
- Convert edited PNGs back to HEX text
- Update an existing `.dat` with edited Min or Max PNGs (headers and compression preserved)
- Clean dark theme via `sv-ttk` when available, graceful fallback otherwise

## Requirements
- Windows, Python 3.11+
- Packages: `Pillow`, `numpy`, `sv-ttk` (optional), `pyinstaller` for building
- Standard library: `tkinter` (ships with Windows Python), `zlib`

Install dependencies:

```cmd
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run

```cmd
python height_tool_gui.py
```

## Build an EXE (Windows)

A helper script is included:

```cmd
build_exe.bat
```

This produces `dist/HeightMapEditor.exe` using PyInstaller, bundles the app icon, and runs as a windowed executable (no console).

### Notes about the icon
- The executable file icon is set via `--icon`
- The Tk window/dialog icon is loaded at runtime; the code checks `sys._MEIPASS` for PyInstaller onefile builds and falls back to the script directory otherwise
- Ensure `OZyXBv0.ico` is located next to `height_tool_gui.py` in source; it is bundled via `--add-data` in the build script

## Usage Tips
- Use the Browse button to select your `.dat`
- Previews show normalized images for visual clarity (actual data range is reported in the status bar)
- Export buttons save exactly the visual orientation; if you edit the PNG and want to re-pack, enable the "Apply Inverse" toggle so the app reverses preview transformations when converting/applying
- Updating DAT validates array sizes against the original header and preserves compression layout

## Troubleshooting
- If `tkinter` import fails, ensure your Python installation includes `tcl/tk`
- If PyInstaller build fails, update pip, then reinstall requirements
	```cmd
	python -m pip install --upgrade pip
	python -m pip install -r requirements.txt
	```
- For antivirus false-positives on onefile executables, prefer `--onedir` in the builder or sign the exe

## Repository Structure
- `height_tool_gui.py`: main GUI application
- `requirements.txt`: runtime + build dependencies
- `build_exe.bat`: Windows build script using PyInstaller
- `OZyXBv0.ico`: application icon

## License
Proprietary or project-specific; add your preferred license here.
