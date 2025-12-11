import re
import os
import numpy as np
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import zlib

# GTAV Heightmap dimensions
WIDTH = 183
HEIGHT = 249


def parse_hex_file(path, forced_width=None):
    with open(path, "r") as f:
        raw = f.read()
    tokens = [t for t in re.split(r'[\s,;:]+', raw) if t]
    try:
        values = [int(t, 16) for t in tokens]
    except ValueError:
        raise ValueError("File contains non-hex tokens")

    if forced_width:
        width = int(forced_width)
    else:
        width = WIDTH

    if width <= 0:
        raise ValueError("Could not determine width")

    if len(values) % width != 0:
        height = len(values) // width
        values = values[: height * width]
    else:
        height = len(values) // width

    arr = np.array(values, dtype=np.uint8).reshape((height, width))
    return arr


def parse_dat_file(path):
    print(f"[parse_dat_file] Reading: {path}")
    with open(path, 'rb') as f:
        raw = f.read()
    if len(raw) >= 4 and raw[:4] == b'HMAP':
        print('[parse_dat_file] Detected HMAP binary format')
        return _parse_hmap_binary(raw)
    raise ValueError('Unsupported file format: expected HMAP .dat')

    raise RuntimeError('Unexpected state')


def _parse_hmap_binary(data: bytes):
    # Parse GTA V Heightmap HMAP binary
    import struct
    off = 0
    if len(data) < 32:
        raise ValueError('HMAP file too small to contain header')
    magic_bytes = data[off:off+4]; off += 4
    if magic_bytes != b'HMAP':
        raise ValueError('Not an HMAP file')
    little_val = int.from_bytes(magic_bytes, byteorder='little')
    magic_const = 0x484D4150
    is_little = (little_val == magic_const)
    endian_prefix = '<' if is_little else '>'
    if off + 2 > len(data):
        raise ValueError('Corrupt HMAP: missing version bytes')
    verMajor = data[off]; verMinor = data[off+1]; off += 2
    if off + 2 > len(data):
        raise ValueError('Corrupt HMAP: missing pad')
    pad = struct.unpack(endian_prefix + 'H', data[off:off+2])[0]; off += 2
    if off + 4 > len(data):
        raise ValueError('Corrupt HMAP: missing compressed flag')
    compressed = struct.unpack(endian_prefix + 'I', data[off:off+4])[0]; off += 4
    if off + 4 > len(data):
        raise ValueError('Corrupt HMAP: missing width/height')
    width = struct.unpack(endian_prefix + 'H', data[off:off+2])[0]; off += 2
    height = struct.unpack(endian_prefix + 'H', data[off:off+2])[0]; off += 2
    if off + 24 > len(data):
        raise ValueError('Corrupt HMAP: missing BBMin/BBMax vectors')
    bbmin = struct.unpack(endian_prefix + 'fff', data[off:off+12]); off += 12
    bbmax = struct.unpack(endian_prefix + 'fff', data[off:off+12]); off += 12
    if off + 4 > len(data):
        raise ValueError('Corrupt HMAP: missing data length')
    length = struct.unpack(endian_prefix + 'I', data[off:off+4])[0]; off += 4

    # Read comp headers if compressed
    comp_headers = []
    if compressed > 0:
        needed = height * 8
        if off + needed > len(data):
            raise ValueError('Corrupt HMAP: not enough bytes for compression headers')
        for _ in range(height):
            start = struct.unpack(endian_prefix + 'H', data[off:off+2])[0]; off += 2
            count = struct.unpack(endian_prefix + 'H', data[off:off+2])[0]; off += 2
            data_offset = struct.unpack(endian_prefix + 'i', data[off:off+4])[0]; off += 4
            comp_headers.append((start, count, data_offset))

    # Read data blob of indicated length minus headers
    dlen = length
    remaining = len(data) - off
    if dlen > remaining:
        print(f"[HMAP] Length {dlen} exceeds remaining {remaining}; clamping")
        dlen = remaining
    blob = data[off:off+dlen]

    max_arr = np.zeros((height, width), dtype=np.uint8)
    min_arr = np.zeros((height, width), dtype=np.uint8)

    if compressed > 0:
        h2off = dlen // 2
        for y in range(height):
            start, count, data_offset = comp_headers[y]
            for i in range(count):
                x = start + i
                o = data_offset + x
                if 0 <= o < dlen and 0 <= (o + h2off) < dlen:
                    max_arr[y, x] = blob[o]
                    min_arr[y, x] = blob[o + h2off]
    else:
        flat_len = width * height
        if len(blob) >= flat_len:
            max_arr = np.frombuffer(blob[:flat_len], dtype=np.uint8).reshape((height, width))
        if len(blob) >= 2 * flat_len:
            min_arr = np.frombuffer(blob[flat_len:flat_len*2], dtype=np.uint8).reshape((height, width))

    return max_arr, min_arr, width, height


def _update_hmap_binary(data: bytes, new_arr: np.ndarray, which: str):
    # Replace either Max or Min array in existing HMAP blob
    import struct
    if data[:4] != b'HMAP':
        raise ValueError('Not an HMAP file')
    little_val = int.from_bytes(data[:4], 'little')
    magic_const = 0x484D4150
    is_little = (little_val == magic_const)
    endian = '<' if is_little else '>'
    off = 4
    verMajor = data[off]; verMinor = data[off+1]; off += 2
    pad = struct.unpack(endian + 'H', data[off:off+2])[0]; off += 2
    compressed = struct.unpack(endian + 'I', data[off:off+4])[0]; off += 4
    width = struct.unpack(endian + 'H', data[off:off+2])[0]; off += 2
    height = struct.unpack(endian + 'H', data[off:off+2])[0]; off += 2
    bbmin = struct.unpack(endian + 'fff', data[off:off+12]); off += 12
    bbmax = struct.unpack(endian + 'fff', data[off:off+12]); off += 12
    length = struct.unpack(endian + 'I', data[off:off+4])[0]; off += 4

    if new_arr.shape != (height, width):
        raise ValueError(f'Edited image must be {width}x{height}')
    new_arr = np.array(new_arr, dtype=np.uint8)

    comp_headers = []
    comp_headers_off = off
    if compressed > 0:
        for _ in range(height):
            start = struct.unpack(endian + 'H', data[off:off+2])[0]; off += 2
            count = struct.unpack(endian + 'H', data[off:off+2])[0]; off += 2
            data_offset = struct.unpack(endian + 'i', data[off:off+4])[0]; off += 4
            comp_headers.append((start, count, data_offset))

    blob_off = off
    dlen = length
    remaining = len(data) - blob_off
    if dlen > remaining:
        dlen = remaining
    blob = bytearray(data[blob_off:blob_off+dlen])

    if compressed > 0:
        half = dlen // 2
        for y in range(height):
            start, count, data_offset = comp_headers[y]
            for i in range(count):
                x = start + i
                o = data_offset + x
                if 0 <= o < dlen and 0 <= (o + half) < dlen:
                    val = int(new_arr[y, x])
                    if which == 'max':
                        blob[o] = val
                    else:
                        blob[o + half] = val
    else:
        flat_len = width * height
        if which == 'max':
            blob[:flat_len] = new_arr.astype(np.uint8).tobytes()
        else:
            blob[flat_len:flat_len*2] = new_arr.astype(np.uint8).tobytes()

    # Reassemble file
    new_data = bytearray(data)
    new_data[blob_off:blob_off+dlen] = blob[:dlen]
    return bytes(new_data)


def _normalize_to_uint8(arr):
    a = arr.astype(np.float32)
    mn = float(a.min())
    mx = float(a.max())
    if mx <= mn:
        return (a * 0).astype(np.uint8)
    out = ((a - mn) / (mx - mn) * 255.0).astype(np.uint8)
    return out


def hex_to_png(in_path, out_path, width_override=None, scale=1):
    # always use fixed width
    arr = parse_hex_file(in_path, width_override or WIDTH)
    img = Image.fromarray(arr, mode='L')
    if scale and int(scale) > 1:
        img = img.resize((img.width * int(scale), img.height * int(scale)), Image.NEAREST)
    img.save(out_path)


def png_to_hex(in_path, out_path, width_override=None, height_override=None, scale=1, leading_spaces=True, uppercase=True):
    img = Image.open(in_path).convert('L')
    img = img.resize((WIDTH, HEIGHT), Image.Resampling.BICUBIC)

    arr = np.array(img, dtype=np.uint8).flatten()
    width = WIDTH

    with open(out_path, "w") as f:
        for i in range(0, len(arr), width):
            line = ' '.join(f'{h:02X}' for h in arr[i:i+width])
            if leading_spaces:
                f.write('  ' + line + '\n')
            else:
                f.write(line + '\n')


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GTAV HeightMap Editor - By Ruptz")
        # Set window icon
        try:
            import sys
            base_dir = os.path.dirname(__file__)
            if hasattr(sys, '_MEIPASS'):
                base_dir = sys._MEIPASS
            icon_path = os.path.join(base_dir, 'OZyXBv0.ico')
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass
        # Start app as windowed fullscreen
        try:
            self.state('zoomed')
        except Exception:
            self.geometry("1280x800")
        self._setup_style()
        self._build_widgets()

    def _setup_style(self):
        # Cool theme bc ugly if not
        try:
            import sv_ttk
            sv_ttk.set_theme("dark")
        except Exception:
            style = ttk.Style(self)
            style.theme_use('clam')
            bg = '#121212'
            fg = '#EDEDED'
            accent = '#2A9D8F'
            entry_bg = '#1E1E1E'
            style.configure('.', background=bg, foreground=fg, fieldbackground=entry_bg)
            style.configure('TLabel', background=bg, foreground=fg)
            style.configure('TButton', background='#2b2b2b', foreground=fg)
            style.map('TButton', background=[('active', accent)])
            style.configure('TEntry', fieldbackground=entry_bg, foreground=fg)
            style.configure('TCombobox', fieldbackground=entry_bg, selectbackground=entry_bg, foreground=fg)

    def _build_widgets(self):
        pad = 8
        frm = ttk.Frame(self)
        frm.pack(fill='both', expand=True, padx=16, pady=12)
        for c in range(5):
            frm.columnconfigure(c, weight=1)
        for r in range(10):
            frm.rowconfigure(r, weight=0)
        frm.rowconfigure(4, weight=1)

        # Input
        ttk.Label(frm, text='Input:').grid(row=1, column=0, sticky='w')
        self.input_entry = ttk.Entry(frm)
        self.input_entry.grid(row=1, column=1, columnspan=3, sticky='ew')
        ttk.Button(frm, text='Browse', command=self.browse_input).grid(row=1, column=4, sticky='e')

        # Inline placeholder
        self.input_placeholder = 'Provide a heightmap.dat'
        self.input_entry.insert(0, self.input_placeholder)
        self.input_entry.bind('<FocusIn>', self._on_input_focus_in)
        self.input_entry.bind('<FocusOut>', self._on_input_focus_out)

        # Options area
        opts = ttk.LabelFrame(frm, text='Options')
        opts.grid(row=3, column=0, columnspan=5, pady=(12, 0), sticky='ew')
        for c in range(6):
            opts.columnconfigure(c, weight=1)

        ttk.Label(opts, text='Width:').grid(row=0, column=0, sticky='w', padx=6, pady=6)
        self.width_var = tk.StringVar(value=str(WIDTH))
        e_w = ttk.Entry(opts, textvariable=self.width_var, width=10, state='disabled')
        e_w.grid(row=0, column=1, sticky='w', padx=6)

        ttk.Label(opts, text='Height:').grid(row=0, column=2, sticky='w', padx=6)
        self.height_var = tk.StringVar(value=str(HEIGHT))
        e_h = ttk.Entry(opts, textvariable=self.height_var, width=10, state='disabled')
        e_h.grid(row=0, column=3, sticky='w', padx=6)

        ttk.Label(opts, text='Scale:').grid(row=0, column=4, sticky='w', padx=6)
        self.scale_var = tk.StringVar(value='1')
        ttk.Entry(opts, textvariable=self.scale_var, width=6).grid(row=0, column=5, sticky='w', padx=6)

        self.leading_spaces = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, text='Leading spaces', variable=self.leading_spaces).grid(row=1, column=0, columnspan=3, sticky='w', padx=6)
        # I had some issues with inversion so I added this to make it easier or any issues
        self.edited_png_is_preview = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, text='Apply Inverse)', variable=self.edited_png_is_preview).grid(row=1, column=3, columnspan=3, sticky='e', padx=6)

        # Previews for Min / Max images
        pv = ttk.LabelFrame(frm, text='Previews')
        pv.grid(row=4, column=0, columnspan=5, pady=(12, 0), sticky='nsew')
        pv.columnconfigure(0, weight=1)
        pv.columnconfigure(1, weight=1)
        pv.rowconfigure(0, weight=1)
        # Preview zoom control
        ttk.Label(pv, text='Preview Zoom:').grid(row=1, column=0, sticky='e', padx=8)
        self.preview_scale_var = tk.StringVar(value='2')
        zoom = ttk.Combobox(pv, textvariable=self.preview_scale_var, values=['1','2','3','4'], width=4, state='readonly')
        zoom.grid(row=1, column=1, sticky='w', padx=8)
        zoom.bind('<<ComboboxSelected>>', lambda e: self._refresh_previews())

        left = ttk.LabelFrame(pv, text='MinHeights')
        left.grid(row=0, column=0, padx=8, pady=8, sticky='nsew')
        left.columnconfigure(0, weight=1)
        left.columnconfigure(1, weight=0)
        left.rowconfigure(0, weight=1)
        left.rowconfigure(1, weight=0)
        left.rowconfigure(2, weight=0)
        # Scrollable canvas for preview
        self.min_canvas = tk.Canvas(left, background='#1E1E1E', highlightthickness=0)
        self.min_canvas.grid(row=0, column=0, sticky='nsew', padx=6, pady=(6, 0))
        self.min_vscroll = ttk.Scrollbar(left, orient='vertical', command=self.min_canvas.yview)
        self.min_hscroll = ttk.Scrollbar(left, orient='horizontal', command=self.min_canvas.xview)
        self.min_canvas.configure(yscrollcommand=self.min_vscroll.set, xscrollcommand=self.min_hscroll.set)
        self.min_vscroll.grid(row=0, column=1, sticky='ns', padx=(0, 6), pady=(6, 0))
        self.min_hscroll.grid(row=1, column=0, sticky='ew', padx=6)
        # Controls
        controls_left = ttk.Frame(left)
        controls_left.grid(row=2, column=0, columnspan=2, sticky='ew', padx=6, pady=(8, 8))
        controls_left.columnconfigure(0, weight=1)
        btn_min_png = ttk.Button(controls_left, text='Save Min PNG', command=self.save_min_png)
        btn_min_png.grid(row=0, column=0, sticky='ew')
        btn_min_hex = ttk.Button(controls_left, text='Save Min HEX', command=self.save_min_hex)
        btn_min_hex.grid(row=1, column=0, sticky='ew', pady=(6, 0))
        btn_min_png2hex = ttk.Button(controls_left, text='Convert Edited Min PNG → HEX', command=self.convert_min_png_to_hex)
        btn_min_png2hex.grid(row=2, column=0, sticky='ew', pady=(6, 0))
        btn_min_update_dat = ttk.Button(controls_left, text='Update DAT with Edited Min PNG', command=lambda: self.update_dat_with_png(which='min'))
        btn_min_update_dat.grid(row=3, column=0, sticky='ew', pady=(6, 0))

        right = ttk.LabelFrame(pv, text='MaxHeights')
        right.grid(row=0, column=1, padx=8, pady=8, sticky='nsew')
        right.columnconfigure(0, weight=1)
        right.columnconfigure(1, weight=0)
        right.rowconfigure(0, weight=1)
        right.rowconfigure(1, weight=0)
        right.rowconfigure(2, weight=0)
        self.max_canvas = tk.Canvas(right, background='#1E1E1E', highlightthickness=0)
        self.max_canvas.grid(row=0, column=0, sticky='nsew', padx=6, pady=(6, 0))
        self.max_vscroll = ttk.Scrollbar(right, orient='vertical', command=self.max_canvas.yview)
        self.max_hscroll = ttk.Scrollbar(right, orient='horizontal', command=self.max_canvas.xview)
        self.max_canvas.configure(yscrollcommand=self.max_vscroll.set, xscrollcommand=self.max_hscroll.set)
        self.max_vscroll.grid(row=0, column=1, sticky='ns', padx=(0, 6), pady=(6, 0))
        self.max_hscroll.grid(row=1, column=0, sticky='ew', padx=6)
        # Controls
        controls_right = ttk.Frame(right)
        controls_right.grid(row=2, column=0, columnspan=2, sticky='ew', padx=6, pady=(8, 8))
        controls_right.columnconfigure(0, weight=1)
        btn_max_png = ttk.Button(controls_right, text='Save Max PNG', command=self.save_max_png)
        btn_max_png.grid(row=0, column=0, sticky='ew')
        btn_max_hex = ttk.Button(controls_right, text='Save Max HEX', command=self.save_max_hex)
        btn_max_hex.grid(row=1, column=0, sticky='ew', pady=(6, 0))
        btn_max_png2hex = ttk.Button(controls_right, text='Convert Edited Max PNG → HEX', command=self.convert_max_png_to_hex)
        btn_max_png2hex.grid(row=2, column=0, sticky='ew', pady=(6, 0))
        btn_max_update_dat = ttk.Button(controls_right, text='Update DAT with Edited Max PNG', command=lambda: self.update_dat_with_png(which='max'))
        btn_max_update_dat.grid(row=3, column=0, sticky='ew', pady=(6, 0))

        actions = ttk.Frame(frm)
        actions.grid(row=5, column=0, columnspan=5, sticky='ew', pady=12)
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=0)
        ttk.Button(actions, text='Load & Preview', command=self.run).grid(row=0, column=0, sticky='w')
        ttk.Button(actions, text='Quit', command=self.destroy).grid(row=0, column=1, sticky='e')

        self.status = ttk.Label(frm, text='Ready')
        self.status.grid(row=6, column=0, columnspan=5, sticky='w')
        self._preview_images = {'min': None, 'max': None}

    def browse_input(self):
        # only allow .dat files
        p = filedialog.askopenfilename(filetypes=[('DAT/XML files', '*.dat;*.txt;*.xml'), ('All', '*.*')])
        if p:
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, p)

    def run(self):
        inp = self.input_entry.get().strip()
        if inp == getattr(self, 'input_placeholder', ''):
            inp = ''
        if not inp:
            messagebox.showerror('Missing path', 'Please set an input .dat path')
            return

        try:
            print(f"[GUI] Loading DAT: {inp}")
            max_arr, min_arr, w, h = parse_dat_file(inp)
        except Exception as e:
            messagebox.showerror('Error parsing .dat', str(e))
            return

        # Create preview images
        try:
            self._full_max_array = max_arr
            self._full_min_array = min_arr

            # Build normalized images for preview/PNG export
            vis_max = _normalize_to_uint8(max_arr)
            vis_min = _normalize_to_uint8(min_arr)
            print(f"[GUI] Max range: ({int(max_arr.min())}, {int(max_arr.max())}) | Min range: ({int(min_arr.min())}, {int(min_arr.max())})")
            # Convert to RGB for preview
            img_max_vis = Image.fromarray(vis_max, mode='L').rotate(180).transpose(Image.FLIP_LEFT_RIGHT).convert('RGB')
            img_min_vis = Image.fromarray(vis_min, mode='L').rotate(180).transpose(Image.FLIP_LEFT_RIGHT).convert('RGB')
        except Exception as e:
            messagebox.showerror('Error creating images', str(e))
            return

        # Store visual images for saving and previewing
        self._full_max_vis = img_max_vis
        self._full_min_vis = img_min_vis

        self._update_preview('min', img_min_vis)
        self._update_preview('max', img_max_vis)
        rng_max = (int(max_arr.min()), int(max_arr.max()))
        rng_min = (int(min_arr.min()), int(min_arr.max()))
        self.status.config(text=f'Loaded {os.path.basename(inp)} — {w}x{h} | Max range {rng_max} | Min range {rng_min}')

    # Placeholder handlers for the input path field
    def _on_input_focus_in(self, _event=None):
        if self.input_entry.get() == getattr(self, 'input_placeholder', ''):
            self.input_entry.delete(0, tk.END)

    def _on_input_focus_out(self, _event=None):
        if not self.input_entry.get():
            self.input_entry.insert(0, getattr(self, 'input_placeholder', ''))

    def _update_preview(self, which, pil_img):
        # Show preview at scaled size, centered, without affecting saved PNGs
        img = pil_img.copy()
        try:
            scale = int(self.preview_scale_var.get()) if hasattr(self, 'preview_scale_var') else 1
        except Exception:
            scale = 1
        if scale > 1:
            img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
        tkimg = ImageTk.PhotoImage(img)
        def draw_centered(canvas, key):
            self._preview_images[key] = tkimg
            canvas.delete('all')
            cw = max(canvas.winfo_width(), 1)
            ch = max(canvas.winfo_height(), 1)
            ox = 0 if img.width >= cw else (cw - img.width) // 2
            oy = 0 if img.height >= ch else (ch - img.height) // 2
            canvas.create_image(ox, oy, image=tkimg, anchor='nw')
            canvas.configure(scrollregion=(0, 0, img.width, img.height))

        if which == 'min':
            draw_centered(self.min_canvas, 'min')
        else:
            draw_centered(self.max_canvas, 'max')

    def _refresh_previews(self):
        if hasattr(self, '_full_min_vis'):
            self._update_preview('min', self._full_min_vis)
        if hasattr(self, '_full_max_vis'):
            self._update_preview('max', self._full_max_vis)

    def save_min_png(self):
        if not hasattr(self, '_full_min_vis'):
            messagebox.showerror('No image', 'No Min image loaded')
            return
        p = filedialog.asksaveasfilename(defaultextension='.png', filetypes=[('PNG', '*.png')])
        if p:
            self._full_min_vis.convert('RGB').save(p)
            messagebox.showinfo('Saved', f'Saved {p}')

    def save_max_png(self):
        if not hasattr(self, '_full_max_vis'):
            messagebox.showerror('No image', 'No Max image loaded')
            return
        p = filedialog.asksaveasfilename(defaultextension='.png', filetypes=[('PNG', '*.png')])
        if p:
            self._full_max_vis.convert('RGB').save(p)
            messagebox.showinfo('Saved', f'Saved {p}')

    def _save_array_as_hex(self, arr, path):
        with open(path, 'w') as f:
            for i in range(0, arr.size, arr.shape[1]):
                line = ' '.join(f'{h:02X}' for h in arr.flatten()[i:i+arr.shape[1]])
                f.write('  ' + line + '\n')

    def _edited_png_to_hex(self):
        p_in = filedialog.askopenfilename(filetypes=[('PNG', '*.png')])
        if not p_in:
            return None, None
        try:
            img = Image.open(p_in).convert('L')
        except Exception as e:
            messagebox.showerror('Error', f'Failed to open PNG: {e}')
            return None, None
        img = img.resize((WIDTH, HEIGHT), Image.Resampling.BICUBIC)
        if self.edited_png_is_preview.get():
            img_raw_oriented = img.transpose(Image.FLIP_LEFT_RIGHT).rotate(180)
        else:
            img_raw_oriented = img
        arr = np.array(img_raw_oriented, dtype=np.uint8)
        p_out = filedialog.asksaveasfilename(defaultextension='.txt', filetypes=[('Text', '*.txt')])
        if not p_out:
            return None, None
        self._save_array_as_hex(arr, p_out)
        return p_in, p_out

    def convert_min_png_to_hex(self):
        res = self._edited_png_to_hex()
        if res and res[1]:
            messagebox.showinfo('Converted', f'Edited Min PNG converted to HEX: {res[1]}')

    def convert_max_png_to_hex(self):
        res = self._edited_png_to_hex()
        if res and res[1]:
            messagebox.showinfo('Converted', f'Edited Max PNG converted to HEX: {res[1]}')

    def update_dat_with_png(self, which: str):
        inp_dat = self.input_entry.get().strip()
        if not inp_dat:
            messagebox.showerror('Missing DAT', 'Please set an input .dat path')
            return
        p_png = filedialog.askopenfilename(filetypes=[('PNG', '*.png')])
        if not p_png:
            return
        try:
            img = Image.open(p_png).convert('L')
            img = img.resize((WIDTH, HEIGHT), Image.Resampling.BICUBIC)
            if self.edited_png_is_preview.get():
                img_raw = img.transpose(Image.FLIP_LEFT_RIGHT).rotate(180)
            else:
                img_raw = img
            arr = np.array(img_raw, dtype=np.uint8)
        except Exception as e:
            messagebox.showerror('Error', f'Failed to process PNG: {e}')
            return

        # Read DAT bytes, update, and write to new file. I just replace the heightmap I am editing...
        try:
            with open(inp_dat, 'rb') as f:
                data = f.read()
            new_data = _update_hmap_binary(data, arr, which=which)
        except Exception as e:
            messagebox.showerror('Update failed', str(e))
            return

        out_path = filedialog.asksaveasfilename(defaultextension='.dat', filetypes=[('DAT', '*.dat')])
        if not out_path:
            return
        try:
            with open(out_path, 'wb') as f:
                f.write(new_data)
        except Exception as e:
            messagebox.showerror('Write failed', str(e))
            return
        messagebox.showinfo('Updated', f'Wrote updated DAT: {out_path}')

    def save_min_hex(self):
        if not hasattr(self, '_full_min_array'):
            messagebox.showerror('No data', 'No Min data loaded')
            return
        p = filedialog.asksaveasfilename(defaultextension='.txt', filetypes=[('Text', '*.txt')])
        if p:
            arr = np.array(self._full_min_array, dtype=np.uint8)
            self._save_array_as_hex(arr, p)
            messagebox.showinfo('Saved', f'Saved {p}')

    def save_max_hex(self):
        if not hasattr(self, '_full_max_array'):
            messagebox.showerror('No data', 'No Max data loaded')
            return
        p = filedialog.asksaveasfilename(defaultextension='.txt', filetypes=[('Text', '*.txt')])
        if p:
            arr = np.array(self._full_max_array, dtype=np.uint8)
            self._save_array_as_hex(arr, p)
            messagebox.showinfo('Saved', f'Saved {p}')


if __name__ == '__main__':
    app = App()
    app.mainloop()
