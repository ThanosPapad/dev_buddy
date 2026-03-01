import tkinter as tk
from tkinter import ttk, messagebox, font as tkfont
import threading
import time
from typing import List
from serial_utils import get_serial_devices, connect_to_serial, close_serial_connection
from packet_handler import (create_handshake_packet, create_set_packet,
                             create_inputs_packet, verify_response_packet,
                             verify_inputs_response_packet)
from config import DEFAULT_BAUDRATE, RESPONSE_TIMEOUT, WINDOW_WIDTH, WINDOW_HEIGHT, INPUT_UPDATE_INTERVAL

# ── Palette ────────────────────────────────────────────────────────────────────
BG           = "#0d0f14"
SURFACE      = "#13161e"
SURFACE2     = "#1a1e28"
BORDER       = "#252a38"
TEXT         = "#c8d0e0"
TEXT_DIM     = "#5a6478"
ACCENT       = "#00c2a8"
ACCENT_DIM   = "#003d35"
WARN         = "#f0a500"
DANGER       = "#c0392b"
BTN_BG       = "#1e2330"
BTN_HOVER    = "#272d3f"
SENT_COL     = "#4ec9b0"
RECV_COL     = "#e8a87c"
SEP_COL      = "#1a1e28"

FONT_MONO    = ("Menlo", 9)
FONT_UI      = ("Helvetica Neue", 10)
FONT_LABEL   = ("Helvetica Neue", 9)
FONT_SMALL   = ("Helvetica Neue", 7)
FONT_TITLE   = ("Helvetica Neue", 15, "bold")
FONT_SUB     = ("Helvetica Neue", 9)


# ── Flat button (works on macOS/Windows/Linux) ─────────────────────────────────

class FlatButton(tk.Label):
    def __init__(self, parent, text, command=None, enabled=True,
                 accent=False, width=14, **kwargs):
        self._command    = command
        self._enabled    = enabled
        self._accent     = accent
        self._normal_bg  = ACCENT if accent else BTN_BG
        self._hover_bg   = "#00a890" if accent else BTN_HOVER
        self._dis_bg     = "#111318"
        self._dis_fg     = "#2a3040"

        super().__init__(
            parent,
            text=text,
            bg=self._normal_bg if enabled else self._dis_bg,
            fg=(BG if accent else TEXT) if enabled else self._dis_fg,
            font=("Helvetica Neue", 9, "bold"),
            width=width, height=1,
            padx=12, pady=6,
            relief="flat",
            cursor="hand2" if enabled else "arrow",
            **kwargs
        )
        self.bind("<Enter>",    self._on_enter)
        self.bind("<Leave>",    self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _on_enter(self, _):
        if self._enabled:
            self.config(bg=self._hover_bg)

    def _on_leave(self, _):
        if self._enabled:
            self.config(bg=self._normal_bg)

    def _on_click(self, _):
        if self._enabled and self._command:
            self._command()

    def set_enabled(self, val: bool):
        self._enabled = val
        if val:
            super().config(bg=self._normal_bg,
                           fg=BG if self._accent else TEXT,
                           cursor="hand2")
        else:
            super().config(bg=self._dis_bg, fg=self._dis_fg, cursor="arrow")

    def config(self, **kw):
        state = kw.pop("state", None)
        if state == "disabled":
            self.set_enabled(False)
        elif state == "normal":
            self.set_enabled(True)
        super().config(**kw)


# ── Channel tile ───────────────────────────────────────────────────────────────

class ChannelTile(tk.Frame):
    W, H = 70, 62

    def __init__(self, parent, index: int, clickable: bool = True):
        super().__init__(parent, bg=BORDER, padx=1, pady=1,
                         width=self.W, height=self.H)
        self.pack_propagate(False)
        self.grid_propagate(False)

        self._index     = index
        self._active    = False
        self._clickable = clickable
        self._command   = None

        self._inner = tk.Frame(self, bg=SURFACE2)
        self._inner.pack(fill=tk.BOTH, expand=True)
        self._inner.pack_propagate(False)

        # Top: index label
        self._idx_lbl = tk.Label(self._inner, text=f"{index:02d}",
                                  bg=SURFACE2, fg=TEXT_DIM, font=FONT_SMALL,
                                  anchor="nw")
        self._idx_lbl.place(x=5, y=4)

        # Centre: dot indicator
        self._dot_cv = tk.Canvas(self._inner, width=12, height=12,
                                  bg=SURFACE2, highlightthickness=0)
        self._dot_cv.place(relx=0.5, rely=0.55, anchor="center")
        self._dot = self._dot_cv.create_oval(1, 1, 11, 11,
                                              fill=ACCENT_DIM, outline="")

        if clickable:
            self.config(cursor="hand2")
            for w in (self, self._inner, self._idx_lbl, self._dot_cv):
                w.bind("<Button-1>", self._on_click)
                w.bind("<Enter>",    self._on_enter)
                w.bind("<Leave>",    self._on_leave)

    def set_command(self, fn):
        self._command = fn

    def _on_click(self, _):
        if self._clickable and self._command:
            self._command()

    def _on_enter(self, _):
        if self._clickable and not self._active:
            for w in (self._inner, self._idx_lbl, self._dot_cv):
                w.config(bg=BTN_HOVER)

    def _on_leave(self, _):
        bg = "#0a2a26" if self._active else SURFACE2
        for w in (self._inner, self._idx_lbl, self._dot_cv):
            w.config(bg=bg)

    def set_active(self, active: bool):
        self._active = active
        if active:
            self.config(bg=ACCENT)
            bg = "#0a2a26"
            fg_idx = ACCENT
            dot_fill = ACCENT
        else:
            self.config(bg=BORDER)
            bg = SURFACE2
            fg_idx = TEXT_DIM
            dot_fill = ACCENT_DIM

        self._inner.config(bg=bg)
        self._idx_lbl.config(bg=bg, fg=fg_idx)
        self._dot_cv.config(bg=bg)
        self._dot_cv.itemconfig(self._dot, fill=dot_fill)


# ── Main app ───────────────────────────────────────────────────────────────────

class SerialConnectionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Dev Buddy")
        self.root.geometry("880x660")
        self.root.minsize(780, 580)
        self.root.resizable(True, True)
        self.root.configure(bg=BG)

        self.serial_connection     = None
        self.is_connected          = False
        self.handshake_active      = False
        self.channel_states        = [False] * 11
        self.device_id             = None
        self._periodic_read_active = False
        self._periodic_after_id    = None

        self._apply_styles()
        self._build_ui()
        self.refresh_devices()

    # ── ttk theme ──────────────────────────────────────────────────────

    def _apply_styles(self):
        s = ttk.Style(self.root)
        s.theme_use("clam")
        s.configure(".",
                     background=BG, foreground=TEXT,
                     troughcolor=SURFACE2, bordercolor=BORDER,
                     darkcolor=SURFACE, lightcolor=SURFACE,
                     selectbackground=ACCENT, selectforeground=BG,
                     font=FONT_UI)
        s.configure("TNotebook", background=BG, borderwidth=0, tabmargins=[0, 0, 0, 0])
        s.configure("TNotebook.Tab",
                     background=SURFACE, foreground=TEXT_DIM,
                     padding=[20, 9], borderwidth=0, focuscolor=BG,
                     font=("Helvetica Neue", 9, "bold"))
        s.map("TNotebook.Tab",
              background=[("selected", SURFACE2)],
              foreground=[("selected", TEXT)])
        s.configure("TCombobox",
                     fieldbackground=SURFACE2, background=SURFACE2,
                     foreground=TEXT, bordercolor=BORDER, arrowcolor=TEXT_DIM)
        s.map("TCombobox", fieldbackground=[("readonly", SURFACE2)])
        s.configure("TScrollbar",
                     background=SURFACE2, troughcolor=SURFACE,
                     bordercolor=BORDER, arrowcolor=TEXT_DIM, relief="flat")

    # ── Main layout ────────────────────────────────────────────────────

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        wrap = tk.Frame(self.root, bg=BG)
        wrap.grid(sticky="nsew", padx=20, pady=18)
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(1, weight=1)

        self._build_topbar(wrap)
        self._build_notebook(wrap)

    # ── Top bar ────────────────────────────────────────────────────────

    def _build_topbar(self, parent):
        bar = tk.Frame(parent, bg=BG)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        bar.columnconfigure(0, weight=1)

        # Left: title block
        left = tk.Frame(bar, bg=BG)
        left.grid(row=0, column=0, sticky="w")

        tk.Label(left, text="DEV BUDDY", bg=BG, fg=TEXT,
                 font=("Helvetica Neue", 18, "bold")).pack(anchor="w")
        tk.Label(left, text="RP2350  ·  UART INTERFACE",
                 bg=BG, fg=TEXT_DIM, font=FONT_SMALL).pack(anchor="w", pady=(1, 0))

        # Right: controls
        right = tk.Frame(bar, bg=BG)
        right.grid(row=0, column=1, sticky="e")

        # Port selector row
        row = tk.Frame(right, bg=BG)
        row.pack(anchor="e")

        tk.Label(row, text="PORT", bg=BG, fg=TEXT_DIM,
                 font=FONT_SMALL).pack(side=tk.LEFT, padx=(0, 5))

        self.device_var = tk.StringVar()
        self.device_dropdown = ttk.Combobox(row, textvariable=self.device_var,
                                             state="readonly", width=30,
                                             font=FONT_LABEL)
        self.device_dropdown.pack(side=tk.LEFT, padx=(0, 6))

        self._refresh_btn = FlatButton(row, "⟳", command=self.refresh_devices, width=3)
        self._refresh_btn.pack(side=tk.LEFT, padx=(0, 6))

        # 1 px vertical divider
        tk.Frame(row, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=3)

        self._connect_btn = FlatButton(row, "CONNECT",
                                        command=self.toggle_connection,
                                        accent=True, width=10)
        self._connect_btn.pack(side=tk.LEFT, padx=(0, 6))

        self._handshake_btn = FlatButton(row, "HANDSHAKE",
                                          command=self.perform_handshake,
                                          enabled=False, width=11)
        self._handshake_btn.pack(side=tk.LEFT, padx=(0, 12))

        # Status pill
        self._pill = tk.Frame(row, bg=DANGER, padx=10, pady=5)
        self._pill.pack(side=tk.LEFT)
        self._pill_dot  = tk.Label(self._pill, text="●", bg=DANGER, fg=BG,
                                    font=("Helvetica Neue", 8))
        self._pill_dot.pack(side=tk.LEFT, padx=(0, 4))
        self._pill_text = tk.Label(self._pill, text="OFFLINE", bg=DANGER, fg=BG,
                                    font=("Helvetica Neue", 8, "bold"))
        self._pill_text.pack(side=tk.LEFT)

        # Thin separator
        tk.Frame(parent, bg=BORDER, height=1).grid(row=0, column=0, sticky="ew",
                                                    pady=(62, 0))

    # ── Notebook ───────────────────────────────────────────────────────

    def _build_notebook(self, parent):
        nb = ttk.Notebook(parent)
        nb.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        parent.rowconfigure(1, weight=1)

        self._build_log_tab(nb)
        self._build_outputs_tab(nb)
        self._build_inputs_tab(nb)

    # ── Log tab ────────────────────────────────────────────────────────

    def _build_log_tab(self, nb):
        outer = tk.Frame(nb, bg=SURFACE)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)
        nb.add(outer, text="  LOG  ")

        inner = tk.Frame(outer, bg=SURFACE, padx=12, pady=12)
        inner.grid(sticky="nsew")
        inner.columnconfigure(0, weight=1)
        inner.rowconfigure(0, weight=1)

        self.data_text = tk.Text(
            inner, wrap=tk.NONE,
            font=("Menlo", 9),
            bg="#080a0e", fg="#6a7a8a",
            insertbackground=TEXT,
            selectbackground=ACCENT_DIM,
            relief="flat", bd=0,
            state=tk.DISABLED
        )
        self.data_text.grid(row=0, column=0, sticky="nsew")
        self.data_text.tag_config("sent",     foreground=SENT_COL)
        self.data_text.tag_config("received", foreground=RECV_COL)
        self.data_text.tag_config("body",     foreground="#4a5a6a")

        vsb = ttk.Scrollbar(inner, orient=tk.VERTICAL,   command=self.data_text.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        hsb = ttk.Scrollbar(inner, orient=tk.HORIZONTAL, command=self.data_text.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        self.data_text.config(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        foot = tk.Frame(outer, bg=SURFACE2, pady=8)
        foot.grid(row=1, column=0, sticky="ew")
        FlatButton(foot, "CLEAR", command=self._clear_log, width=8).pack(side=tk.RIGHT, padx=12)
        tk.Label(foot, text="Hex dump  ·  sent in teal  ·  received in amber",
                 bg=SURFACE2, fg=TEXT_DIM, font=FONT_SMALL).pack(side=tk.LEFT, padx=12)

    # ── Outputs tab ────────────────────────────────────────────────────

    def _build_outputs_tab(self, nb):
        outer = tk.Frame(nb, bg=SURFACE)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)
        nb.add(outer, text="  OUTPUTS  ")

        inner = tk.Frame(outer, bg=SURFACE, padx=22, pady=18)
        inner.grid(sticky="nsew")

        tk.Label(inner, text="OUTPUT CHANNELS", bg=SURFACE, fg=TEXT_DIM,
                 font=("Helvetica Neue", 8, "bold")).pack(anchor="w", pady=(0, 12))

        grid = tk.Frame(inner, bg=SURFACE)
        grid.pack(anchor="w")

        self.channel_tiles: List[ChannelTile] = []
        for i in range(11):
            tile = ChannelTile(grid, index=i, clickable=True)
            tile.grid(row=i // 4, column=i % 4, padx=5, pady=5)
            tile.set_command(lambda idx=i: self.toggle_channel(idx))
            self.channel_tiles.append(tile)

        foot = tk.Frame(outer, bg=SURFACE2, pady=10)
        foot.grid(row=1, column=0, sticky="ew")

        self._set_btn = FlatButton(foot, "SEND OUTPUT STATE",
                                    command=self.set_channel_data,
                                    accent=True, enabled=False, width=20)
        self._set_btn.pack(side=tk.RIGHT, padx=16)
        tk.Label(foot, text="Click tiles to toggle  ·  press Send to transmit",
                 bg=SURFACE2, fg=TEXT_DIM, font=FONT_SMALL).pack(side=tk.LEFT, padx=16)

    # ── Inputs tab ─────────────────────────────────────────────────────

    def _build_inputs_tab(self, nb):
        outer = tk.Frame(nb, bg=SURFACE)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)
        nb.add(outer, text="  INPUTS  ")

        inner = tk.Frame(outer, bg=SURFACE, padx=22, pady=18)
        inner.grid(sticky="nsew")

        tk.Label(inner, text="INPUT CHANNELS", bg=SURFACE, fg=TEXT_DIM,
                 font=("Helvetica Neue", 8, "bold")).pack(anchor="w", pady=(0, 12))

        grid = tk.Frame(inner, bg=SURFACE)
        grid.pack(anchor="w")

        self.input_tiles: List[ChannelTile] = []
        for i in range(11):
            tile = ChannelTile(grid, index=i, clickable=False)
            tile.grid(row=i // 4, column=i % 4, padx=5, pady=5)
            self.input_tiles.append(tile)

        foot = tk.Frame(outer, bg=SURFACE2, pady=10)
        foot.grid(row=1, column=0, sticky="ew")

        self._read_btn = FlatButton(foot, "READ INPUTS",
                                     command=self.read_inputs,
                                     accent=True, enabled=False, width=14)
        self._read_btn.pack(side=tk.RIGHT, padx=16)
        tk.Label(foot, text=f"Auto-polls every {INPUT_UPDATE_INTERVAL}s after handshake",
                 bg=SURFACE2, fg=TEXT_DIM, font=FONT_SMALL).pack(side=tk.LEFT, padx=16)

    # ── Status pill ────────────────────────────────────────────────────

    def _set_status(self, state: str, text: str):
        colors = {"offline": DANGER, "waiting": WARN, "online": ACCENT, "busy": WARN}
        bg = colors.get(state, DANGER)
        txt_fg = BG if state in ("online", "offline") else BG

        def _upd():
            for w in (self._pill, self._pill_dot, self._pill_text):
                w.config(bg=bg)
            self._pill_dot.config(fg=txt_fg)
            self._pill_text.config(fg=txt_fg, text=text.upper())
        self.root.after(0, _upd)

    # ── Device list ────────────────────────────────────────────────────

    def refresh_devices(self):
        devices = get_serial_devices()
        names   = [f"{d['name']} ({d['port']})" for d in devices]
        self.device_dropdown["values"] = names
        if names:
            self.device_dropdown.current(0)

    # ── Connect / disconnect ───────────────────────────────────────────

    def toggle_connection(self):
        if not self.is_connected:
            self._connect()
        else:
            self._disconnect()

    def _connect(self):
        sel = self.device_var.get()
        if not sel:
            messagebox.showerror("Error", "Please select a device first.")
            return
        port = sel.split("(")[-1].strip(")")
        self.serial_connection = connect_to_serial(port, DEFAULT_BAUDRATE)
        if self.serial_connection:
            self.is_connected = True
            self._connect_btn.config(text="DISCONNECT")
            self._handshake_btn.set_enabled(True)
            self._set_status("waiting", "WAITING")
        else:
            messagebox.showerror("Error", "Failed to connect to the selected device.")

    def _disconnect(self):
        self._stop_periodic_reading()
        self.handshake_active = False
        if self.serial_connection:
            close_serial_connection(self.serial_connection)
            self.serial_connection = None
        self.is_connected = False
        self.device_id    = None
        self._connect_btn.config(text="CONNECT")
        self._handshake_btn.set_enabled(False)
        self._set_btn.set_enabled(False)
        self._read_btn.set_enabled(False)
        self._set_status("offline", "OFFLINE")
        self.root.after(0, self._reset_input_tiles)

    # ── Log helpers ────────────────────────────────────────────────────

    def _fmt_hex(self, data: bytes) -> str:
        lines = []
        for i in range(0, len(data), 16):
            chunk = data[i:i + 16]
            h = " ".join(f"{b:02X}" for b in chunk)
            a = "".join(chr(b) if 32 <= b <= 126 else "·" for b in chunk)
            lines.append(f"  {i:04X}  {h:<48}  {a}")
        return "\n".join(lines)

    def log_sent_data(self, data: bytes):
        ts = time.strftime("%H:%M:%S")
        t  = f"▶ SENT    {ts}  ({len(data)} B)"
        b  = self._fmt_hex(data)
        self.root.after(0, lambda: self._append_log(t, b, "sent"))

    def log_received_data(self, data: bytes):
        ts = time.strftime("%H:%M:%S")
        t  = f"◀ RECV    {ts}  ({len(data)} B)"
        b  = self._fmt_hex(data)
        self.root.after(0, lambda: self._append_log(t, b, "received"))

    def _append_log(self, title: str, body: str, tag: str):
        self.data_text.config(state=tk.NORMAL)
        if self.data_text.get("1.0", tk.END).strip():
            self.data_text.insert(tk.END, "\n\n")
        self.data_text.insert(tk.END, title + "\n", tag)
        self.data_text.insert(tk.END, body + "\n", "body")
        self.data_text.see(tk.END)
        self.data_text.config(state=tk.DISABLED)

    def _clear_log(self):
        self.data_text.config(state=tk.NORMAL)
        self.data_text.delete("1.0", tk.END)
        self.data_text.config(state=tk.DISABLED)

    # ── Output channels ────────────────────────────────────────────────

    def toggle_channel(self, channel: int):
        self.channel_states[channel] = not self.channel_states[channel]
        self.channel_tiles[channel].set_active(self.channel_states[channel])

    def set_channel_data(self):
        if not self._check_ready():
            return
        try:
            pkt = create_set_packet(self.device_id, self.channel_states)
            self.serial_connection.write(pkt + b"\x0A")
            self.log_sent_data(pkt + b"\x0A")
            self._set_status("online", "ONLINE")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send set packet:\n{e}")

    # ── Input reading ──────────────────────────────────────────────────

    def read_inputs(self):
        if not self._check_ready():
            return
        self._read_btn.set_enabled(False)
        threading.Thread(target=self._read_inputs_worker, daemon=True).start()

    def _read_inputs_worker(self):
        try:
            pkt = create_inputs_packet(self.device_id)
            self.serial_connection.write(pkt + b"\x0A")
            self.log_sent_data(pkt + b"\x0A")
            self._set_status("busy", "READING")

            buf, start = b"", time.time()
            while time.time() - start < RESPONSE_TIMEOUT:
                if not self.serial_connection:
                    break
                w = self.serial_connection.in_waiting
                if w:
                    buf += self.serial_connection.read(w)
                    if b"\x0A" in buf:
                        pos  = buf.find(b"\x0A")
                        dev  = buf[:pos]
                        self.log_received_data(buf[:pos + 1])
                        ok, states = verify_inputs_response_packet(dev)
                        if ok:
                            self.root.after(0, lambda s=states: self._update_input_tiles(s))
                            self._set_status("online", "ONLINE")
                        else:
                            self._set_status("waiting", "BAD PKT")
                        return
                time.sleep(0.01)
            self._set_status("waiting", "TIMEOUT")
        except Exception:
            self._set_status("waiting", "ERROR")
        finally:
            self.root.after(0, lambda: self._read_btn.set_enabled(True))

    # ── Handshake ──────────────────────────────────────────────────────

    def perform_handshake(self):
        if not self.is_connected or not self.serial_connection:
            messagebox.showerror("Error", "Not connected to any device.")
            return
        self._handshake_btn.set_enabled(False)
        self._connect_btn.set_enabled(False)
        self._set_btn.set_enabled(False)
        self._read_btn.set_enabled(False)
        self._set_status("busy", "HANDSHAKE")
        threading.Thread(target=self._handshake_worker, daemon=True).start()

    def _handshake_worker(self):
        self.handshake_active = True
        success = False
        try:
            pkt = create_handshake_packet()
            self.serial_connection.write(pkt + b"\x0A")
            self.log_sent_data(pkt + b"\x0A")

            buf, start = b"", time.time()
            while time.time() - start < RESPONSE_TIMEOUT and self.handshake_active:
                if not self.serial_connection:
                    break
                w = self.serial_connection.in_waiting
                if w:
                    buf += self.serial_connection.read(w)
                    if b"\x0A" in buf:
                        pos = buf.find(b"\x0A")
                        dev = buf[:pos]
                        self.log_received_data(buf[:pos + 1])
                        if len(dev) >= 112:
                            ok, dev_id = verify_response_packet(dev)
                            if ok:
                                self.device_id = dev_id
                                success = True
                                self._set_status("online", "ONLINE")
                                self.root.after(0, self._on_handshake_success)
                            else:
                                self._set_status("offline", "BAD ACK")
                        else:
                            self._set_status("offline", "SHORT PKT")
                        return
                time.sleep(0.01)
            if not success:
                self._set_status("offline", "TIMEOUT")
        except Exception:
            self._set_status("offline", "ERROR")
        finally:
            self.handshake_active = False
            self.root.after(0, lambda: self._handshake_btn.set_enabled(True))
            self.root.after(0, lambda: self._connect_btn.set_enabled(True))

    def _on_handshake_success(self):
        self._set_btn.set_enabled(True)
        self._read_btn.set_enabled(True)
        self._start_periodic_reading()

    # ── Periodic polling ───────────────────────────────────────────────

    def _start_periodic_reading(self):
        self._periodic_read_active = True
        self._schedule_next_read()

    def _stop_periodic_reading(self):
        self._periodic_read_active = False
        if self._periodic_after_id:
            try:
                self.root.after_cancel(self._periodic_after_id)
            except Exception:
                pass
            self._periodic_after_id = None

    def _schedule_next_read(self):
        if self._periodic_read_active and self.is_connected and self.device_id is not None:
            self._periodic_after_id = self.root.after(
                INPUT_UPDATE_INTERVAL * 1000, self._periodic_read_tick)

    def _periodic_read_tick(self):
        if not self._periodic_read_active or not self.is_connected or self.device_id is None:
            return
        threading.Thread(target=self._periodic_read_worker, daemon=True).start()

    def _periodic_read_worker(self):
        try:
            pkt = create_inputs_packet(self.device_id)
            self.serial_connection.write(pkt + b"\x0A")
            buf, start = b"", time.time()
            while time.time() - start < RESPONSE_TIMEOUT:
                if not self.serial_connection or not self.is_connected:
                    return
                w = self.serial_connection.in_waiting
                if w:
                    buf += self.serial_connection.read(w)
                    if b"\x0A" in buf:
                        dev = buf[:buf.find(b"\x0A")]
                        ok, states = verify_inputs_response_packet(dev)
                        if ok:
                            self.root.after(0, lambda s=states: self._update_input_tiles(s))
                        return
                time.sleep(0.01)
        except Exception:
            pass
        finally:
            self.root.after(0, self._schedule_next_read)

    # ── Tile state helpers ─────────────────────────────────────────────

    def _reset_input_tiles(self):
        for tile in self.input_tiles:
            tile.set_active(False)

    def _update_input_tiles(self, states: List[int]):
        for i, s in enumerate(states):
            self.input_tiles[i].set_active(bool(s))

    # ── Guard ──────────────────────────────────────────────────────────

    def _check_ready(self) -> bool:
        if not self.is_connected or not self.serial_connection:
            messagebox.showerror("Error", "Not connected to any device.")
            return False
        if self.device_id is None:
            messagebox.showerror("Error", "Please complete a handshake first.")
            return False
        return True


def main():
    root = tk.Tk()
    SerialConnectionApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()