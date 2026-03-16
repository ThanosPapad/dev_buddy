import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import time
import struct
from typing import List, Tuple, Optional

from serial_utils import get_serial_devices, connect_to_serial, close_serial_connection
from packet_handler import (
    create_handshake_packet, create_set_packet,
    create_inputs_packet, verify_response_packet,
    verify_inputs_response_packet,
    # ADC
    create_set_adc_interval_packet,
    create_set_adc_interval_state_packet,
    verify_adc_interval_response,
    verify_adc_state_response,
    parse_adc_telemetry_packet,
    # DAC
    create_set_dac_packet,
    verify_dac_response,
)
from config import (DEFAULT_BAUDRATE, RESPONSE_TIMEOUT,
                    WINDOW_WIDTH, WINDOW_HEIGHT, INPUT_UPDATE_INTERVAL,
                    ADC_CHANNEL_COUNT, ADC_TELEMETRY_TRANS,
                    SET_ADC_INTERVAL_RESP, SET_ADC_INTERVAL_STATE_RESP,
                    RESPONSE_HANDSHAKE_VALUE, INPUTS_RESPONSE_HANDSHAKE_VALUE,
                    SET_DAC_VALUE_RESP)

# ── Palette ────────────────────────────────────────────────────────────────────
BG          = "#0d0f14"
SURFACE     = "#13161e"
SURFACE2    = "#1a1e28"
BORDER      = "#252a38"
TEXT        = "#c8d0e0"
TEXT_DIM    = "#5a6478"
ACCENT      = "#00c2a8"
ACCENT_DIM  = "#003d35"
WARN        = "#f0a500"
DANGER      = "#c0392b"
BTN_BG      = "#1e2330"
BTN_HOVER   = "#272d3f"
SENT_COL    = "#4ec9b0"
RECV_COL    = "#e8a87c"

# ADC-specific colours
V_COL       = "#7dd3fc"   # sky-blue  — voltage readings
I_COL       = "#86efac"   # green     — current readings
ADC_ON_BG   = "#0a2010"   # dark green tile when streaming
ADC_OFF_BG  = SURFACE2

FONT_MONO   = ("Menlo", 9)
FONT_UI     = ("Helvetica Neue", 10)
FONT_LABEL  = ("Helvetica Neue", 9)
FONT_SMALL  = ("Helvetica Neue", 7)
FONT_TITLE  = ("Helvetica Neue", 15, "bold")


# ── Flat button ────────────────────────────────────────────────────────────────
class FlatButton(tk.Label):
    def __init__(self, parent, text, command=None, enabled=True,
                 accent=False, width=14, **kwargs):
        self._command   = command
        self._enabled   = enabled
        self._accent    = accent
        self._normal_bg = ACCENT if accent else BTN_BG
        self._hover_bg  = "#00a890" if accent else BTN_HOVER
        self._dis_bg    = "#111318"
        self._dis_fg    = "#2a3040"

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


# ── Binary toggle switch ───────────────────────────────────────────────────────
class ToggleSwitch(tk.Canvas):
    """
    A simple ON/OFF toggle that looks like a pill switch.
    Calls `on_change(new_bool_state)` when clicked.
    """
    W, H = 52, 26

    def __init__(self, parent, on_change=None, initial=False, enabled=True, **kwargs):
        super().__init__(parent, width=self.W, height=self.H,
                         highlightthickness=0, bg=BG, **kwargs)
        self._state     = initial
        self._enabled   = enabled
        self._on_change = on_change
        self._draw()
        self.bind("<Button-1>", self._on_click)

    def _draw(self):
        self.delete("all")
        track_col  = ACCENT if self._state else "#2a3040"
        knob_x     = self.W - 16 if self._state else 14
        knob_col   = "#ffffff" if self._enabled else "#444d5e"

        # Track
        self.create_oval(2, 4, self.H - 2, self.H - 4,
                         fill=track_col, outline="")
        self.create_oval(self.W - self.H + 2, 4,
                         self.W - 2, self.H - 4,
                         fill=track_col, outline="")
        self.create_rectangle(self.H // 2, 4,
                              self.W - self.H // 2, self.H - 4,
                              fill=track_col, outline="")

        # Knob
        r = 9
        self.create_oval(knob_x - r, self.H // 2 - r,
                         knob_x + r, self.H // 2 + r,
                         fill=knob_col, outline="")

        # Label inside track
        label = "ON" if self._state else "OFF"
        lx = 10 if self._state else self.W - 12
        self.create_text(lx, self.H // 2, text=label,
                         fill=BG if self._state else TEXT_DIM,
                         font=("Helvetica Neue", 6, "bold"))

    def _on_click(self, _):
        if not self._enabled:
            return
        self._state = not self._state
        self._draw()
        if self._on_change:
            self._on_change(self._state)

    def set_state(self, val: bool):
        self._state = val
        self._draw()

    def get_state(self) -> bool:
        return self._state

    def set_enabled(self, val: bool):
        self._enabled = val
        self._draw()


# ── Channel tile (outputs / inputs) ───────────────────────────────────────────
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

        self._idx_lbl = tk.Label(self._inner, text=f"{index:02d}",
                                  bg=SURFACE2, fg=TEXT_DIM, font=FONT_SMALL,
                                  anchor="nw")
        self._idx_lbl.place(x=5, y=4)

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
            bg = "#0a2a26"; fg_idx = ACCENT; dot_fill = ACCENT
        else:
            self.config(bg=BORDER)
            bg = SURFACE2; fg_idx = TEXT_DIM; dot_fill = ACCENT_DIM

        self._inner.config(bg=bg)
        self._idx_lbl.config(bg=bg, fg=fg_idx)
        self._dot_cv.config(bg=bg)
        self._dot_cv.itemconfig(self._dot, fill=dot_fill)


# ── ADC channel card ───────────────────────────────────────────────────────────
class AdcChannelCard(tk.Frame):
    """
    A compact card showing voltage + current readings for one ADC channel.
    Lights up in a different background colour while actively receiving telemetry.
    """
    W, H = 140, 80

    def __init__(self, parent, index: int):
        super().__init__(parent, bg=BORDER, padx=1, pady=1,
                         width=self.W, height=self.H)
        self.pack_propagate(False)
        self.grid_propagate(False)

        self._inner = tk.Frame(self, bg=ADC_OFF_BG)
        self._inner.pack(fill=tk.BOTH, expand=True)
        self._inner.pack_propagate(False)

        # Channel index label — top left
        tk.Label(self._inner, text=f"CH {index:02d}",
                 bg=ADC_OFF_BG, fg=TEXT_DIM,
                 font=("Helvetica Neue", 7, "bold")).place(x=6, y=5)

        # Voltage row
        tk.Label(self._inner, text="V",
                 bg=ADC_OFF_BG, fg=TEXT_DIM,
                 font=("Helvetica Neue", 8)).place(x=6, y=24)
        self._v_lbl = tk.Label(self._inner, text="—",
                                bg=ADC_OFF_BG, fg=V_COL,
                                font=("Menlo", 11, "bold"), anchor="e", width=8)
        self._v_lbl.place(x=18, y=20)

        # Current row
        tk.Label(self._inner, text="A",
                 bg=ADC_OFF_BG, fg=TEXT_DIM,
                 font=("Helvetica Neue", 8)).place(x=6, y=50)
        self._i_lbl = tk.Label(self._inner, text="—",
                                bg=ADC_OFF_BG, fg=I_COL,
                                font=("Menlo", 11, "bold"), anchor="e", width=8)
        self._i_lbl.place(x=18, y=46)

        self._all_widgets = [self._inner, self._v_lbl, self._i_lbl]

    def update_values(self, voltage: float, current: float):
        """Refresh displayed values and flash the active background."""
        v_str = f"{voltage:+.4f}"
        i_str = f"{current:+.4f}"
        for w in self._all_widgets:
            w.config(bg=ADC_ON_BG)
        self._v_lbl.config(text=v_str, fg=V_COL)
        self._i_lbl.config(text=i_str, fg=I_COL)

    def clear(self):
        for w in self._all_widgets:
            w.config(bg=ADC_OFF_BG)
        self._v_lbl.config(text="—", fg=V_COL)
        self._i_lbl.config(text="—", fg=I_COL)


# ── Main application ───────────────────────────────────────────────────────────
class SerialConnectionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Dev Buddy")
        self.root.geometry("960x700")
        self.root.minsize(820, 600)
        self.root.resizable(True, True)
        self.root.configure(bg=BG)

        self.serial_connection  = None
        self.is_connected       = False
        self.handshake_active   = False
        self.channel_states     = [False] * 11
        self.device_id          = None
        self._adc_enabled       = False

        # Single reader thread — owns the serial port exclusively.
        # Response packets are routed via a Queue to whichever worker is
        # waiting for them.  ADC telemetry is dispatched directly to the UI.
        self._reader_active     = False
        # Queue used by request/response workers (handshake, read inputs,
        # set interval, set state).  Only one such operation runs at a time
        # (enforced by the _tx_lock), so a single queue is sufficient.
        self._response_queue    = queue.Queue()

        self._apply_styles()
        self._build_ui()
        self.refresh_devices()

    # ── ttk theme ──────────────────────────────────────────────────────────────
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

    # ── Main layout ────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        wrap = tk.Frame(self.root, bg=BG)
        wrap.grid(sticky="nsew", padx=20, pady=18)
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(1, weight=1)
        self._build_topbar(wrap)
        self._build_notebook(wrap)

    # ── Top bar ────────────────────────────────────────────────────────────────
    def _build_topbar(self, parent):
        bar = tk.Frame(parent, bg=BG)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        bar.columnconfigure(0, weight=1)

        left = tk.Frame(bar, bg=BG)
        left.grid(row=0, column=0, sticky="w")
        tk.Label(left, text="DEV BUDDY", bg=BG, fg=TEXT,
                 font=("Helvetica Neue", 18, "bold")).pack(anchor="w")
        tk.Label(left, text="RP2350  ·  UART INTERFACE",
                 bg=BG, fg=TEXT_DIM, font=FONT_SMALL).pack(anchor="w", pady=(1, 0))

        right = tk.Frame(bar, bg=BG)
        right.grid(row=0, column=1, sticky="e")
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
        tk.Frame(row, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=3)

        self._connect_btn = FlatButton(row, "CONNECT",
                                        command=self.toggle_connection,
                                        accent=True, width=10)
        self._connect_btn.pack(side=tk.LEFT, padx=(0, 6))

        self._handshake_btn = FlatButton(row, "HANDSHAKE",
                                          command=self.perform_handshake,
                                          enabled=False, width=11)
        self._handshake_btn.pack(side=tk.LEFT, padx=(0, 12))

        self._pill = tk.Frame(row, bg=DANGER, padx=10, pady=5)
        self._pill.pack(side=tk.LEFT)
        self._pill_dot  = tk.Label(self._pill, text="●", bg=DANGER, fg=BG,
                                    font=("Helvetica Neue", 8))
        self._pill_dot.pack(side=tk.LEFT, padx=(0, 4))
        self._pill_text = tk.Label(self._pill, text="OFFLINE", bg=DANGER, fg=BG,
                                    font=("Helvetica Neue", 8, "bold"))
        self._pill_text.pack(side=tk.LEFT)

        tk.Frame(parent, bg=BORDER, height=1).grid(row=0, column=0, sticky="ew",
                                                    pady=(62, 0))

    # ── Notebook ───────────────────────────────────────────────────────────────
    def _build_notebook(self, parent):
        nb = ttk.Notebook(parent)
        nb.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        parent.rowconfigure(1, weight=1)
        self._build_log_tab(nb)
        self._build_outputs_tab(nb)
        self._build_inputs_tab(nb)
        self._build_adc_tab(nb)       # ← NEW
        self._build_dac_tab(nb)       # ← DAC

    # ── Log tab ────────────────────────────────────────────────────────────────
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
            inner, wrap=tk.NONE, font=("Menlo", 9),
            bg="#080a0e", fg="#6a7a8a",
            insertbackground=TEXT, selectbackground=ACCENT_DIM,
            relief="flat", bd=0, state=tk.DISABLED)
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

    # ── Outputs tab ────────────────────────────────────────────────────────────
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

    # ── Inputs tab ─────────────────────────────────────────────────────────────
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

    # ── ADC tab ────────────────────────────────────────────────────────────────
    def _build_adc_tab(self, nb):
        """
        NEW TAB — ADC Telemetry.

        Layout:
          ┌──────────────────────────────────────────────────────┐
          │  ADC TELEMETRY                                        │
          │  ┌──────────────────────────────────────────────────┐│
          │  │  [toggle ON/OFF]  Streaming  •  last rx: 12:34:56 ││
          │  │  Interval: [_______ ms]  [APPLY INTERVAL]         ││
          │  └──────────────────────────────────────────────────┘│
          │  CH00  CH01  CH02  CH03  CH04  CH05  CH06  CH07      │
          │  V: x.xxxx  V: x.xxxx  …                            │
          │  A: x.xxxx  A: x.xxxx  …                            │
          └──────────────────────────────────────────────────────┘
        """
        outer = tk.Frame(nb, bg=SURFACE)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)
        nb.add(outer, text="  ADC  ")

        # ── Control bar ───────────────────────────────────────────────────────
        ctrl = tk.Frame(outer, bg=SURFACE2, pady=14, padx=22)
        ctrl.grid(row=0, column=0, sticky="ew")

        tk.Label(ctrl, text="ADC TELEMETRY", bg=SURFACE2, fg=TEXT_DIM,
                 font=("Helvetica Neue", 8, "bold")).grid(
                     row=0, column=0, columnspan=6, sticky="w", pady=(0, 10))

        # Enable toggle
        tk.Label(ctrl, text="STREAM", bg=SURFACE2, fg=TEXT_DIM,
                 font=FONT_SMALL).grid(row=1, column=0, padx=(0, 6), sticky="w")

        self._adc_toggle = ToggleSwitch(ctrl, on_change=self._on_adc_toggle,
                                         initial=False, enabled=False)
        self._adc_toggle.grid(row=1, column=1, padx=(0, 20), sticky="w")

        # Status label — fixed width prevents layout shifting when text changes
        self._adc_status_lbl = tk.Label(ctrl, text="IDLE",
                                         bg=SURFACE2, fg=TEXT_DIM,
                                         font=("Helvetica Neue", 8, "bold"),
                                         width=18, anchor="w")
        self._adc_status_lbl.grid(row=1, column=2, padx=(0, 20), sticky="w")

        # Last received timestamp
        tk.Label(ctrl, text="last rx:", bg=SURFACE2, fg=TEXT_DIM,
                 font=FONT_SMALL).grid(row=1, column=3, sticky="w")
        self._adc_last_rx_lbl = tk.Label(ctrl, text="—",
                                          bg=SURFACE2, fg=ACCENT,
                                          font=FONT_SMALL)
        self._adc_last_rx_lbl.grid(row=1, column=4, padx=(4, 30), sticky="w")

        # Interval input
        tk.Label(ctrl, text="INTERVAL (ms)", bg=SURFACE2, fg=TEXT_DIM,
                 font=FONT_SMALL).grid(row=1, column=5, padx=(0, 6), sticky="w")

        self._interval_var = tk.StringVar(value="500")
        interval_entry = tk.Entry(ctrl,
                                   textvariable=self._interval_var,
                                   bg=SURFACE, fg=TEXT, insertbackground=TEXT,
                                   relief="flat", bd=0, font=("Menlo", 10),
                                   width=7, highlightthickness=1,
                                   highlightbackground=BORDER,
                                   highlightcolor=ACCENT)
        interval_entry.grid(row=1, column=6, padx=(0, 8), ipady=4)

        self._apply_interval_btn = FlatButton(ctrl, "APPLY INTERVAL",
                                               command=self._send_adc_interval,
                                               enabled=False, width=16)
        self._apply_interval_btn.grid(row=1, column=7, padx=(0, 4))

        # ── Channel cards grid ─────────────────────────────────────────────────
        cards_frame = tk.Frame(outer, bg=SURFACE, padx=22, pady=18)
        cards_frame.grid(row=1, column=0, sticky="nsew")

        self.adc_cards: List[AdcChannelCard] = []
        cols = 4   # 4 cards per row → 2 rows for 8 channels
        for i in range(ADC_CHANNEL_COUNT):
            card = AdcChannelCard(cards_frame, index=i)
            card.grid(row=i // cols, column=i % cols, padx=6, pady=6, sticky="nw")
            self.adc_cards.append(card)

        # ── Footer ────────────────────────────────────────────────────────────
        foot = tk.Frame(outer, bg=SURFACE2, pady=8)
        foot.grid(row=2, column=0, sticky="ew")
        tk.Label(foot,
                 text="Toggle STREAM to enable/disable ADC timer on device  ·  "
                      "APPLY INTERVAL sends new period in ms",
                 bg=SURFACE2, fg=TEXT_DIM, font=FONT_SMALL).pack(side=tk.LEFT, padx=16)

    # ── DAC tab ────────────────────────────────────────────────────────────────
    def _build_dac_tab(self, nb):
        """
        DAC control tab.

        Layout:
          ┌──────────────────────────────────────────────────────┐
          │  DAC CONTROL                                          │
          │  DAC 1  [____________]   DAC 2  [____________]       │
          │  (0 – 4095)                                           │
          │                                    [  SET  ]          │
          │  Status: IDLE                                         │
          └──────────────────────────────────────────────────────┘
        """
        outer = tk.Frame(nb, bg=SURFACE)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)
        nb.add(outer, text="  DAC  ")

        inner = tk.Frame(outer, bg=SURFACE, padx=28, pady=24)
        inner.grid(row=0, column=0, sticky="nsew")

        # ── Section heading ───────────────────────────────────────────────────
        tk.Label(inner, text="DAC CONTROL", bg=SURFACE, fg=TEXT_DIM,
                 font=("Helvetica Neue", 8, "bold")).grid(
                     row=0, column=0, columnspan=4, sticky="w", pady=(0, 18))

        # ── DAC 1 ─────────────────────────────────────────────────────────────
        tk.Label(inner, text="DAC 1", bg=SURFACE, fg=TEXT_DIM,
                 font=FONT_SMALL).grid(row=1, column=0, sticky="w", padx=(0, 8))

        self._dac1_var = tk.StringVar(value="0")
        dac1_entry = tk.Entry(inner,
                              textvariable=self._dac1_var,
                              bg=SURFACE2, fg=TEXT,
                              insertbackground=TEXT,
                              relief="flat", bd=0,
                              font=("Menlo", 11),
                              width=8,
                              highlightthickness=1,
                              highlightbackground=BORDER,
                              highlightcolor=ACCENT)
        dac1_entry.grid(row=1, column=1, ipady=5, padx=(0, 32))

        # ── DAC 2 ─────────────────────────────────────────────────────────────
        tk.Label(inner, text="DAC 2", bg=SURFACE, fg=TEXT_DIM,
                 font=FONT_SMALL).grid(row=1, column=2, sticky="w", padx=(0, 8))

        self._dac2_var = tk.StringVar(value="0")
        dac2_entry = tk.Entry(inner,
                              textvariable=self._dac2_var,
                              bg=SURFACE2, fg=TEXT,
                              insertbackground=TEXT,
                              relief="flat", bd=0,
                              font=("Menlo", 11),
                              width=8,
                              highlightthickness=1,
                              highlightbackground=BORDER,
                              highlightcolor=ACCENT)
        dac2_entry.grid(row=1, column=3, ipady=5, padx=(0, 0))

        # ── Range hint ────────────────────────────────────────────────────────
        tk.Label(inner, text="Integer  0 – 4095  (12-bit)",
                 bg=SURFACE, fg=TEXT_DIM, font=FONT_SMALL).grid(
                     row=2, column=0, columnspan=4, sticky="w", pady=(6, 22))

        # ── Status label ──────────────────────────────────────────────────────
        status_row = tk.Frame(inner, bg=SURFACE)
        status_row.grid(row=3, column=0, columnspan=4, sticky="w")

        tk.Label(status_row, text="STATUS", bg=SURFACE, fg=TEXT_DIM,
                 font=FONT_SMALL).pack(side=tk.LEFT, padx=(0, 8))

        self._dac_status_lbl = tk.Label(status_row, text="IDLE",
                                         bg=SURFACE, fg=TEXT_DIM,
                                         font=("Helvetica Neue", 8, "bold"),
                                         width=20, anchor="w")
        self._dac_status_lbl.pack(side=tk.LEFT)

        # ── Footer with SET button ────────────────────────────────────────────
        foot = tk.Frame(outer, bg=SURFACE2, pady=10)
        foot.grid(row=1, column=0, sticky="ew")

        self._dac_set_btn = FlatButton(foot, "SET",
                                        command=self._send_dac_values,
                                        accent=True, enabled=False, width=10)
        self._dac_set_btn.pack(side=tk.RIGHT, padx=16)

        tk.Label(foot, text="Values are sent together in a single packet",
                 bg=SURFACE2, fg=TEXT_DIM, font=FONT_SMALL).pack(
                     side=tk.LEFT, padx=16)

    # ── Status pill ────────────────────────────────────────────────────────────
    def _set_status(self, state: str, text: str):
        colors = {"offline": DANGER, "waiting": WARN,
                  "online": ACCENT, "busy": WARN}
        bg = colors.get(state, DANGER)

        def _upd():
            for w in (self._pill, self._pill_dot, self._pill_text):
                w.config(bg=bg)
            self._pill_dot.config(fg=BG)
            self._pill_text.config(fg=BG, text=text.upper())
        self.root.after(0, _upd)

    # ── Device list ────────────────────────────────────────────────────────────
    def refresh_devices(self):
        devices = get_serial_devices()
        names   = [f"{d['name']} ({d['port']})" for d in devices]
        self.device_dropdown["values"] = names
        if names:
            self.device_dropdown.current(0)

    # ── Connect / disconnect ───────────────────────────────────────────────────
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
            self._start_reader()
        else:
            messagebox.showerror("Error", "Failed to connect to the selected device.")

    def _disconnect(self):
        self._stop_reader()
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
        self._adc_toggle.set_enabled(False)
        self._apply_interval_btn.set_enabled(False)
        self._dac_set_btn.set_enabled(False)
        self._set_status("offline", "OFFLINE")
        self.root.after(0, self._reset_input_tiles)
        self.root.after(0, self._clear_adc_cards)

    # ── Log helpers ────────────────────────────────────────────────────────────
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

    # ── Output channels ────────────────────────────────────────────────────────
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

    # ── Input reading ──────────────────────────────────────────────────────────
    def read_inputs(self):
        if not self._check_ready():
            return
        self._read_btn.set_enabled(False)
        threading.Thread(target=self._read_inputs_worker, daemon=True).start()

    def _read_inputs_worker(self):
        """
        Send GET_DEVICE_OUTPUTS_REQ and wait for GET_DEVICE_OUTPUTS_RESP (23)
        to arrive via the response queue, which the single reader thread fills.
        """
        try:
            pkt = create_inputs_packet(self.device_id)
            self.serial_connection.write(pkt + b"\x0A")
            self.log_sent_data(pkt + b"\x0A")
            self._set_status("busy", "READING")

            frame = self._wait_for_response(
                expected_handshake=INPUTS_RESPONSE_HANDSHAKE_VALUE,
                timeout=RESPONSE_TIMEOUT)

            if frame is None:
                self._set_status("waiting", "TIMEOUT")
                return

            ok, states = verify_inputs_response_packet(frame)
            if ok:
                self.root.after(0, lambda s=states: self._update_input_tiles(s))
                self._set_status("online", "ONLINE")
            else:
                self._set_status("waiting", "BAD PKT")
        except Exception:
            self._set_status("waiting", "ERROR")
        finally:
            self.root.after(0, lambda: self._read_btn.set_enabled(True))

    # ── Handshake ──────────────────────────────────────────────────────────────
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
        success = False
        try:
            pkt = create_handshake_packet()
            self.serial_connection.write(pkt + b"\x0A")
            self.log_sent_data(pkt + b"\x0A")

            frame = self._wait_for_response(
                expected_handshake=RESPONSE_HANDSHAKE_VALUE,
                timeout=RESPONSE_TIMEOUT)

            if frame is None:
                self._set_status("offline", "TIMEOUT")
                return

            if len(frame) >= 112:
                ok, dev_id = verify_response_packet(frame)
                if ok:
                    self.device_id = dev_id
                    success = True
                    self._set_status("online", "ONLINE")
                    self.root.after(0, self._on_handshake_success)
                else:
                    self._set_status("offline", "BAD ACK")
            else:
                self._set_status("offline", "SHORT PKT")
        except Exception:
            self._set_status("offline", "ERROR")
        finally:
            self.root.after(0, lambda: self._handshake_btn.set_enabled(True))
            self.root.after(0, lambda: self._connect_btn.set_enabled(True))

    def _on_handshake_success(self):
        self._set_btn.set_enabled(True)
        self._read_btn.set_enabled(True)
        self._adc_toggle.set_enabled(True)
        self._apply_interval_btn.set_enabled(True)
        self._dac_set_btn.set_enabled(True)

    # ── Single serial reader thread ────────────────────────────────────────────
    def _start_reader(self):
        """
        Start the one background thread that owns all serial reads.

        Every incoming frame is classified by its handshake byte (frame[8]):

          102  ADC_TELEMETRY_TRANS   → dispatched directly to the UI
          SET_ADC_INTERVAL_RESP  }
          SET_ADC_INTERVAL_STATE_RESP  → put on _response_queue
          RESPONSE_HANDSHAKE_VALUE  }  (workers waiting with _wait_for_response
          INPUTS_RESPONSE_HANDSHAKE_VALUE  }   pick them up)

        This ensures only ONE thread ever calls serial_connection.read(),
        eliminating all races between the handshake worker, the read-inputs
        worker, and the ADC telemetry stream.
        """
        self._reader_active = True
        # Drain any stale bytes left in the OS buffer before we start
        if self.serial_connection:
            self.serial_connection.reset_input_buffer()
        threading.Thread(target=self._reader_worker, daemon=True).start()

    def _stop_reader(self):
        self._reader_active = False
        # Unblock any worker sitting on _response_queue.get()
        try:
            self._response_queue.put_nowait(None)
        except Exception:
            pass

    def _reader_worker(self):
        buf = b""
        while self._reader_active and self.is_connected:
            try:
                if not self.serial_connection:
                    break
                waiting = self.serial_connection.in_waiting
                if waiting:
                    buf += self.serial_connection.read(waiting)

                # Drain every complete \x0A-terminated frame from the buffer
                while b"\x0A" in buf:
                    pos   = buf.find(b"\x0A")
                    frame = buf[:pos]       # raw frame bytes, no terminator
                    buf   = buf[pos + 1:]   # keep remainder for next iteration

                    if len(frame) < 9:
                        continue           # too short to have a handshake byte

                    # Log every received frame here — this is the single
                    # point all RX bytes pass through, so nothing is missed.
                    self.log_received_data(frame + b"\x0A")

                    hv = frame[8]          # handshake_value sits at byte index 8

                    if hv == ADC_TELEMETRY_TRANS:
                        # Unsolicited telemetry — go straight to the UI
                        ok, channels = parse_adc_telemetry_packet(frame)
                        if ok:
                            ts = time.strftime("%H:%M:%S")
                            self.root.after(0,
                                lambda ch=channels, t=ts:
                                    self._handle_adc_telemetry(ch, t))
                    else:
                        # Everything else is a response to a command we sent.
                        # Put it on the queue so the waiting worker can take it.
                        self._response_queue.put(frame)

            except Exception:
                pass

            time.sleep(0.005)

    def _wait_for_response(self, expected_handshake: int, timeout: float):
        """
        Block until the reader thread delivers a frame whose handshake byte
        matches `expected_handshake`, or until `timeout` seconds elapse.

        Any frames that arrive with a different handshake byte while we are
        waiting are re-queued so they are not silently lost.

        Returns the raw frame bytes (no terminator), or None on timeout.
        """
        deadline = time.time() + timeout
        requeue  = []
        result   = None

        while time.time() < deadline:
            remaining = deadline - time.time()
            try:
                frame = self._response_queue.get(timeout=max(remaining, 0.001))
            except queue.Empty:
                break

            if frame is None:
                # Sentinel pushed by _stop_reader — we are shutting down
                break

            if frame[8] == expected_handshake:
                result = frame
                break
            else:
                # Not what we want yet — save it and keep waiting
                requeue.append(frame)

        # Put back any frames we consumed but didn't need
        for f in requeue:
            self._response_queue.put(f)

        return result

    # ── ADC UI callbacks (all called on the main thread via root.after) ────────
    def _handle_adc_telemetry(self, channels: List[Tuple[float, float]], ts: str):
        """Update all 8 channel cards with fresh telemetry."""
        for i, (voltage, current) in enumerate(channels):
            if i < len(self.adc_cards):
                self.adc_cards[i].update_values(voltage, current)
        self._adc_last_rx_lbl.config(text=ts)
        self._adc_status_lbl.config(text="STREAMING", fg=ACCENT)

    def _handle_interval_response(self, new_interval: int, success: bool):
        if success:
            self._interval_var.set(str(new_interval))
            self._adc_status_lbl.config(
                text=f"INTERVAL → {new_interval} ms", fg=ACCENT)
        else:
            self._adc_status_lbl.config(text="INTERVAL FAILED", fg=DANGER)

    def _handle_state_response(self, new_state: bool):
        if new_state:
            self._adc_status_lbl.config(text="STREAMING", fg=ACCENT)
        else:
            self._adc_status_lbl.config(text="IDLE", fg=TEXT_DIM)
            self._clear_adc_cards()

    # ── ADC control actions ────────────────────────────────────────────────────
    def _on_adc_toggle(self, new_state: bool):
        """Send SET_ADC_INTERVAL_STATE_REQ and wait for its ack in a thread."""
        if not self._check_ready():
            # Not connected — revert the visual toggle immediately
            self.root.after(0, lambda: self._adc_toggle.set_state(not new_state))
            return
        # Disable the toggle while the command is in flight to prevent double-sends
        self._adc_toggle.set_enabled(False)
        status = "ENABLING…" if new_state else "DISABLING…"
        self._adc_status_lbl.config(text=status, fg=WARN)
        threading.Thread(
            target=self._adc_state_worker, args=(new_state,), daemon=True).start()

    def _adc_state_worker(self, new_state: bool):
        sent = False
        try:
            pkt = create_set_adc_interval_state_packet(self.device_id, new_state)
            self.serial_connection.write(pkt + b"\x0A")
            self.log_sent_data(pkt + b"\x0A")
            sent = True

            frame = self._wait_for_response(
                expected_handshake=SET_ADC_INTERVAL_STATE_RESP,
                timeout=RESPONSE_TIMEOUT)

            if frame is not None:
                # Device confirmed — update UI to reflect the new state
                self.root.after(0, lambda s=new_state: self._handle_state_response(s))
            else:
                # No ack received — revert the toggle since we don't know device state
                self.root.after(0, lambda: self._adc_status_lbl.config(
                    text="NO RESPONSE", fg=DANGER))
                self.root.after(0, lambda: self._adc_toggle.set_state(not new_state))
        except Exception:
            if not sent:
                # Failed before even sending — safe to revert
                self.root.after(0, lambda: self._adc_toggle.set_state(not new_state))
            self.root.after(0, lambda: self._adc_status_lbl.config(
                text="ERROR", fg=DANGER))
        finally:
            # Re-enable the toggle regardless of outcome
            self.root.after(0, lambda: self._adc_toggle.set_enabled(True))

    def _send_adc_interval(self):
        """Validate, send SET_ADC_INTERVAL_REQ, and wait for response in a thread."""
        if not self._check_ready():
            return
        raw = self._interval_var.get().strip()
        try:
            interval_ms = int(raw)
            if interval_ms < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error",
                                  "Interval must be a positive integer (milliseconds).")
            return
        self._adc_status_lbl.config(text="UPDATING…", fg=WARN)
        threading.Thread(
            target=self._adc_interval_worker, args=(interval_ms,), daemon=True).start()

    def _adc_interval_worker(self, interval_ms: int):
        try:
            pkt = create_set_adc_interval_packet(self.device_id, interval_ms)
            self.serial_connection.write(pkt + b"\x0A")
            self.log_sent_data(pkt + b"\x0A")

            frame = self._wait_for_response(
                expected_handshake=SET_ADC_INTERVAL_RESP,
                timeout=RESPONSE_TIMEOUT)

            if frame is not None:
                ok, new_iv, success = verify_adc_interval_response(frame)
                if ok:
                    self.root.after(0,
                        lambda iv=new_iv, s=success:
                            self._handle_interval_response(iv, s))
            else:
                self.root.after(0, lambda: self._adc_status_lbl.config(
                    text="TIMEOUT", fg=DANGER))
        except Exception:
            pass

    # ── DAC control actions ────────────────────────────────────────────────────
    def _send_dac_values(self):
        """Validate both DAC fields and send SET_DAC_VALUE_REQ in a thread."""
        if not self._check_ready():
            return

        raw1 = self._dac1_var.get().strip()
        raw2 = self._dac2_var.get().strip()
        try:
            dac1 = int(raw1)
            dac2 = int(raw2)
            if not (0 <= dac1 <= 4095) or not (0 <= dac2 <= 4095):
                raise ValueError
        except ValueError:
            messagebox.showerror("Error",
                                  "Both DAC values must be integers in the range 0 – 4095.")
            return

        self._dac_status_lbl.config(text="SENDING…", fg=WARN)
        self._dac_set_btn.set_enabled(False)
        threading.Thread(
            target=self._dac_worker, args=(dac1, dac2), daemon=True).start()

    def _dac_worker(self, dac1: int, dac2: int):
        try:
            pkt = create_set_dac_packet(self.device_id, dac1, dac2)
            self.serial_connection.write(pkt + b"\x0A")
            self.log_sent_data(pkt + b"\x0A")

            frame = self._wait_for_response(
                expected_handshake=SET_DAC_VALUE_RESP,
                timeout=RESPONSE_TIMEOUT)

            if frame is not None and verify_dac_response(frame):
                self.root.after(0, lambda: self._dac_status_lbl.config(
                    text=f"OK  DAC1={dac1}  DAC2={dac2}", fg=ACCENT))
            else:
                self.root.after(0, lambda: self._dac_status_lbl.config(
                    text="NO RESPONSE", fg=DANGER))
        except Exception:
            self.root.after(0, lambda: self._dac_status_lbl.config(
                text="ERROR", fg=DANGER))
        finally:
            self.root.after(0, lambda: self._dac_set_btn.set_enabled(True))

    # ── Card helpers ───────────────────────────────────────────────────────────
    def _clear_adc_cards(self):
        for card in self.adc_cards:
            card.clear()
        self._adc_last_rx_lbl.config(text="—")

    # ── Tile state helpers ─────────────────────────────────────────────────────
    def _reset_input_tiles(self):
        for tile in self.input_tiles:
            tile.set_active(False)

    def _update_input_tiles(self, states: List[int]):
        for i, s in enumerate(states):
            self.input_tiles[i].set_active(bool(s))

    # ── Guard ──────────────────────────────────────────────────────────────────
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