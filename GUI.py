# gui.py
import os
import glob
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import matplotlib
matplotlib.use("TkAgg")  # must be set before importing matplotlib backends

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from serial_manager import SerialManager, SerialConfig


class App(tk.Tk):
    def __init__(self, tick_ms: int = 100, scan_serial_ports: bool = True):
        super().__init__()

        # ---------- Config ----------
        self.TICK_MS = int(tick_ms)
        self.W = 1000
        self.H = 500

        # Dark + orange theme
        self.COL_BG = "#141414"
        self.COL_PANEL = "#1e1e1e"
        self.COL_ACCENT = "#ff8c00"
        self.COL_TEXT = self.COL_ACCENT
        self.COL_MUTED = "#2a2a2a"
        self.COL_PLOT_BG = "#101010"

        self.scan_serial_ports = bool(scan_serial_ports)

        # Serial backend (separate file)
        self.serial_mgr = SerialManager(SerialConfig(baudrate=115200, timeout_s=0.1))

        # ---------- Window ----------
        self.title("Measurement Device GUI")
        self.geometry(f"{self.W}x{self.H}")
        self.minsize(self.W, self.H)
        self.maxsize(self.W, self.H)
        self.configure(bg=self.COL_BG)

        self._style_ttk()
        self._build_layout()

        # Data for plot (example)
        self.live_x = []
        self.live_y = []
        self.sample_index = 0

        # Start ticking
        self.after(self.TICK_MS, self.on_tick)

    # ---------------- UI Style ----------------
    def _style_ttk(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(".", background=self.COL_BG, foreground=self.COL_TEXT)
        style.configure("TFrame", background=self.COL_BG)
        style.configure("TLabel", background=self.COL_BG, foreground=self.COL_TEXT)
        style.configure("TNotebook", background=self.COL_BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=self.COL_MUTED, foreground=self.COL_TEXT, padding=(10, 6))
        style.map("TNotebook.Tab",
                  background=[("selected", self.COL_PANEL)],
                  foreground=[("selected", self.COL_TEXT)])

        style.configure("TButton", background=self.COL_MUTED, foreground=self.COL_TEXT, padding=(8, 6))
        style.map("TButton",
                  background=[("active", "#333333")],
                  foreground=[("active", self.COL_TEXT)])

        style.configure("TCombobox",
                        fieldbackground=self.COL_MUTED,
                        background=self.COL_MUTED,
                        foreground=self.COL_TEXT)
        style.map("TCombobox", fieldbackground=[("readonly", self.COL_MUTED)])

        style.configure("TCheckbutton", background=self.COL_BG, foreground=self.COL_TEXT)
        style.map("TCheckbutton",
                  background=[("active", self.COL_BG)],
                  foreground=[("active", self.COL_TEXT)])

    # ---------------- Layout ----------------
    def _build_layout(self):
        # Main container: left and right halves, each 500x500
        self.left = tk.Frame(self, width=500, height=500, bg=self.COL_BG)
        self.right = tk.Frame(self, width=500, height=500, bg=self.COL_BG)
        self.left.pack(side="left", fill="none")
        self.right.pack(side="right", fill="none")
        self.left.pack_propagate(False)
        self.right.pack_propagate(False)

        self._build_left_tabs()
        self._build_right_canvases()

    # ---------------- Left Tabs ----------------
    def _build_left_tabs(self):
        nb = ttk.Notebook(self.left)
        nb.pack(fill="both", expand=True)

        self.tab_operation = tk.Frame(nb, bg=self.COL_BG)
        self.tab_setup = tk.Frame(nb, bg=self.COL_BG)
        self.tab_info = tk.Frame(nb, bg=self.COL_BG)

        nb.add(self.tab_operation, text="Operation")
        nb.add(self.tab_setup, text="Setup")
        nb.add(self.tab_info, text="Info")

        self._build_operation_tab()
        self._build_setup_tab()
        self._build_info_tab()

    # Operation: 4x4 grid, top 8 displays, bottom 8 buttons
    def _build_operation_tab(self):
        parent = self.tab_operation

        for r in range(4):
            parent.grid_rowconfigure(r, weight=1, uniform="r")
        for c in range(4):
            parent.grid_columnconfigure(c, weight=1, uniform="c")

        # Top 8 display "windows"
        self.display_vars = [tk.StringVar(value=f"Display {i+1}") for i in range(8)]
        for i in range(8):
            r = i // 4
            c = i % 4
            tk.Label(
                parent,
                textvariable=self.display_vars[i],
                bg=self.COL_PANEL,
                fg=self.COL_TEXT,
                relief="ridge",
                bd=2,
                font=("Segoe UI", 10),
                anchor="center"
            ).grid(row=r, column=c, sticky="nsew", padx=6, pady=6)

        # Bottom 8 buttons using arrays
        self.button_names = [
            "Btn1", "Btn2", "Btn3", "Btn4",
            "Btn5", "Btn6", "Btn7", "Btn8",
        ]
        self.button_funcs = [
            self.btn1, self.btn2, self.btn3, self.btn4,
            self.btn5, self.btn6, self.btn7, self.btn8,
        ]

        for i in range(8):
            r = 2 + (i // 4)
            c = i % 4
            ttk.Button(parent, text=self.button_names[i], command=self.button_funcs[i]).grid(
                row=r, column=c, sticky="nsew", padx=6, pady=6
            )

    # Setup: optional COM scan, connect/disconnect, txt dropdown + viewer
    def _build_setup_tab(self):
        parent = self.tab_setup
        parent.grid_rowconfigure(4, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        # Row 0: enable/disable scanning
        row0 = tk.Frame(parent, bg=self.COL_BG)
        row0.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        row0.grid_columnconfigure(0, weight=1)

        self.scan_var = tk.BooleanVar(value=self.scan_serial_ports)
        chk = ttk.Checkbutton(
            row0,
            text="Enable COM port scan",
            variable=self.scan_var,
            command=self._on_scan_toggle
        )
        chk.grid(row=0, column=0, sticky="w")

        # Row 1: COM dropdown + refresh
        row1 = tk.Frame(parent, bg=self.COL_BG)
        row1.grid(row=1, column=0, sticky="ew", padx=8, pady=4)
        row1.grid_columnconfigure(1, weight=1)

        tk.Label(row1, text="COM port:", bg=self.COL_BG, fg=self.COL_TEXT).grid(row=0, column=0, sticky="w")

        self.com_var = tk.StringVar(value="")
        self.com_combo = ttk.Combobox(row1, textvariable=self.com_var, state="readonly", values=[])
        self.com_combo.grid(row=0, column=1, sticky="ew", padx=(8, 8))

        self.btn_refresh_ports = ttk.Button(row1, text="Refresh", command=self.refresh_com_ports)
        self.btn_refresh_ports.grid(row=0, column=2, sticky="e")

        # Row 2: connect/disconnect
        row2 = tk.Frame(parent, bg=self.COL_BG)
        row2.grid(row=2, column=0, sticky="ew", padx=8, pady=4)
        row2.grid_columnconfigure(1, weight=1)

        self.conn_status_var = tk.StringVar(value="Disconnected")
        tk.Label(row2, textvariable=self.conn_status_var, bg=self.COL_BG, fg=self.COL_TEXT).grid(
            row=0, column=0, sticky="w"
        )

        self.btn_connect = ttk.Button(row2, text="Connect", command=self.toggle_connect)
        self.btn_connect.grid(row=0, column=2, sticky="e")

        # Row 3: txt file dropdown + browse
        row3 = tk.Frame(parent, bg=self.COL_BG)
        row3.grid(row=3, column=0, sticky="ew", padx=8, pady=4)
        row3.grid_columnconfigure(1, weight=1)

        tk.Label(row3, text="TXT file:", bg=self.COL_BG, fg=self.COL_TEXT).grid(row=0, column=0, sticky="w")

        self.txt_var = tk.StringVar(value="")
        self.txt_combo = ttk.Combobox(row3, textvariable=self.txt_var, state="readonly", values=[])
        self.txt_combo.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        self.txt_combo.bind("<<ComboboxSelected>>", lambda e: self.load_txt_file(self.txt_var.get()))

        ttk.Button(row3, text="Browse...", command=self.browse_txt).grid(row=0, column=2, sticky="e")

        # Row 4: text file contents
        self.txt_view = tk.Text(
            parent,
            bg=self.COL_PANEL,
            fg=self.COL_TEXT,
            insertbackground=self.COL_TEXT,
            relief="ridge",
            bd=2,
            wrap="none"
        )
        self.txt_view.grid(row=4, column=0, sticky="nsew", padx=8, pady=(4, 8))

        # Init TXT dropdown
        self.refresh_txt_dropdown(default_dir=os.getcwd())

        # Init serial UI state
        self._apply_scan_state(self.scan_var.get())
        if self.scan_var.get():
            self.after(0, self.refresh_com_ports)
        else:
            self._set_com_ports(["(scan disabled)"])

    def _apply_scan_state(self, enabled: bool):
        # If pyserial missing, scanning is not meaningful
        if not self.serial_mgr.has_serial:
            self.btn_refresh_ports.configure(state="disabled")
            self.com_combo.configure(state="disabled")
            self._set_com_ports(["(pyserial not installed)"])
            return

        self.btn_refresh_ports.configure(state="normal" if enabled else "disabled")
        self.com_combo.configure(state="readonly" if enabled else "disabled")

    def _on_scan_toggle(self):
        enabled = bool(self.scan_var.get())
        self.scan_serial_ports = enabled
        self._apply_scan_state(enabled)

        if enabled:
            self.refresh_com_ports()
        else:
            self._set_com_ports(["(scan disabled)"])

    # ---------------- Serial (GUI -> SerialManager) ----------------
    def refresh_com_ports(self):
        if not self.scan_serial_ports:
            self._set_com_ports(["(scan disabled)"])
            return
        if not self.serial_mgr.has_serial:
            self._set_com_ports(["(pyserial not installed)"])
            return

        self._set_com_ports(["Scanning..."])

        def worker():
            ports = self.serial_mgr.list_ports_blocking()
            if not ports:
                ports = ["(none)"]
            self.after(0, lambda: self._set_com_ports(ports))

        threading.Thread(target=worker, daemon=True).start()

    def _set_com_ports(self, ports):
        self.com_combo["values"] = ports
        self.com_var.set(ports[0] if ports else "")

    def toggle_connect(self):
        if self.serial_mgr.is_connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        if not self.serial_mgr.has_serial:
            messagebox.showwarning("Serial", "pyserial is not installed, cannot connect.")
            return

        port = self.com_var.get().strip()
        if not port or port.startswith("("):
            messagebox.showwarning("Serial", "Select a valid COM port first.")
            return

        try:
            self.serial_mgr.connect(port)
            self.conn_status_var.set(f"Connected: {port}")
            self.btn_connect.configure(text="Disconnect")
        except Exception as e:
            messagebox.showerror("Serial", f"Failed to connect:\n{e}")

    def _disconnect(self):
        self.serial_mgr.disconnect()
        self.conn_status_var.set("Disconnected")
        self.btn_connect.configure(text="Connect")

    # ---------------- Info: three canvases ----------------
    def _build_info_tab(self):
        parent = self.tab_info
        for r in range(3):
            parent.grid_rowconfigure(r, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        self.info_canvases = []
        for i in range(3):
            cv = tk.Canvas(parent, bg=self.COL_PANEL, highlightthickness=0)
            cv.grid(row=i, column=0, sticky="nsew", padx=8,
                    pady=(8 if i == 0 else 4, 8 if i == 2 else 4))
            cv.create_text(10, 10, anchor="nw", fill=self.COL_TEXT, text=f"Info canvas {i+1}")
            self.info_canvases.append(cv)

    # ---------------- Right Side: image + live plot ----------------
    def _build_right_canvases(self):
        self.right.grid_rowconfigure(0, weight=1)
        self.right.grid_rowconfigure(1, weight=1)
        self.right.grid_columnconfigure(0, weight=1)

        # Top: image canvas
        self.img_canvas = tk.Canvas(self.right, bg=self.COL_PANEL, highlightthickness=0)
        self.img_canvas.grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 4))
        self._draw_demo_image()

        # Bottom: matplotlib plot embedded
        plot_frame = tk.Frame(self.right, bg=self.COL_PANEL)
        plot_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(4, 8))
        plot_frame.grid_rowconfigure(0, weight=1)
        plot_frame.grid_columnconfigure(0, weight=1)

        self.fig = Figure(figsize=(5, 2.5), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor(self.COL_PLOT_BG)
        self.fig.patch.set_facecolor(self.COL_PANEL)

        self.ax.tick_params(axis="x", colors=self.COL_TEXT)
        self.ax.tick_params(axis="y", colors=self.COL_TEXT)
        for spine in self.ax.spines.values():
            spine.set_color(self.COL_TEXT)

        self.line, = self.ax.plot([], [])
        self.ax.set_title("Live Data", color=self.COL_TEXT)

        self.mpl_canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.mpl_canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

    def _draw_demo_image(self):
        """
        Image defined in code (simple pattern). Replace with your own image.
        """
        w, h = 480, 240
        self.photo = tk.PhotoImage(width=w, height=h)

        self.photo.put("#101010", to=(0, 0, w, h))
        for i in range(min(w, h)):
            for t in range(3):
                y = i + t
                if 0 <= y < h:
                    self.photo.put(self.COL_ACCENT, (i, y))

        self.img_canvas.delete("all")
        self.img_canvas.create_image(10, 10, anchor="nw", image=self.photo)
        self.img_canvas.create_text(10, h - 10, anchor="sw", fill=self.COL_TEXT, text="Top canvas image")

    # ---------------- Tick + Live Updates ----------------
    def on_tick(self):
        self.display_vars[0].set(f"Tick: {self.sample_index}")

        y = self._fake_measurement()
        self.live_x.append(self.sample_index)
        self.live_y.append(y)
        self.sample_index += 1

        N = 200
        if len(self.live_x) > N:
            self.live_x = self.live_x[-N:]
            self.live_y = self.live_y[-N:]

        self._update_plot()
        self.after(self.TICK_MS, self.on_tick)

    def _fake_measurement(self):
        a = (self.sample_index % 50) / 50.0
        b = ((self.sample_index * 7) % 100) / 100.0
        return a + 0.2 * b

    def _update_plot(self):
        self.line.set_data(self.live_x, self.live_y)
        if self.live_x:
            self.ax.set_xlim(self.live_x[0], self.live_x[-1])
        self.ax.relim()
        self.ax.autoscale_view(scalex=False, scaley=True)
        self.mpl_canvas.draw_idle()

    # ---------------- Buttons (Operation) ----------------
    def btn1(self): self.display_vars[1].set("Btn1 pressed")
    def btn2(self): self.display_vars[1].set("Btn2 pressed")
    def btn3(self): self.display_vars[1].set("Btn3 pressed")
    def btn4(self): self.display_vars[1].set("Btn4 pressed")
    def btn5(self): self.display_vars[1].set("Btn5 pressed")
    def btn6(self): self.display_vars[1].set("Btn6 pressed")
    def btn7(self): self.display_vars[1].set("Btn7 pressed")
    def btn8(self): self.display_vars[1].set("Btn8 pressed")

    # ---------------- TXT helpers ----------------
    def refresh_txt_dropdown(self, default_dir):
        txts = sorted(glob.glob(os.path.join(default_dir, "*.txt")))
        self.txt_combo["values"] = txts
        if txts:
            self.txt_var.set(txts[0])
            self.load_txt_file(txts[0])

    def browse_txt(self):
        path = filedialog.askopenfilename(
            title="Select a .txt file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not path:
            return

        current = list(self.txt_combo["values"])
        if path not in current:
            current.append(path)
            self.txt_combo["values"] = sorted(current)

        self.txt_var.set(path)
        self.load_txt_file(path)

    def load_txt_file(self, path):
        self.txt_view.delete("1.0", "end")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                self.txt_view.insert("1.0", f.read())
        except Exception as e:
            self.txt_view.insert("1.0", f"Failed to load file:\n{e}")
