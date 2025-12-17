# GTAV HeightMap Editor

A desktop GUI to view, export, edit, and re-pack GTA V heightmap data. Supports reading `heightmap.dat` files (Max/Min arrays) directly, previewing with orientation fixed, exporting PNG/HEX, and updating the original `.dat` with edited PNGs.

<img width="1918" height="1032" alt="image" src="https://github.com/user-attachments/assets/c402e7d0-bdce-4700-b831-9547caed31c7" />

## Features
- Load HMAP `.dat` files and parse Max/Min arrays
- Preview normalized MinHeight/MaxHeight images with correct orientation
- Export Min/Max to PNG or HEX text format
- Convert edited PNGs back to HEX text
- Update an existing `.dat` with edited Min or Max PNGs (headers and compression preserved)
- Clean dark theme via `sv-ttk` when available, graceful fallback otherwise

## Requirements
- Windows, Python 3.11+
- Packages: `Pillow`, `numpy`, `sv-ttk`, `pyinstaller` for building
- Standard library: `tkinter`, `zlib`

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

## Usage Tips
- Use the Browse button to select your `.dat`
- Previews show normalized images for visual clarity
- Export buttons save exactly the visual orientation, if you edit the PNG and want to re-pack, enable the "Apply Inverse" toggle so the app reverses preview transformations when converting/applying
- Updating DAT validates array sizes against the original header and preserves compression layout

## Troubleshooting
- If `tkinter` import fails, ensure your Python installation includes `tcl/tk`
- If PyInstaller build fails, update pip, then reinstall requirements
	```cmd
	python -m pip install --upgrade pip
	python -m pip install -r requirements.txt
	```

## License
[license.md](https://github.com/ruptz/Rup-HeightMapEditor/blob/master/license.md)
