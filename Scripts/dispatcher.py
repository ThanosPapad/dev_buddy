"""
dispatcher.py
─────────────
Sequence storage, validation, and execution logic for Dev Buddy.

Sequences live in  dispatcher/sequences.json  next to main.py.
The file (and folder) are created automatically if missing.
"""

from __future__ import annotations

import json
import os
import time
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

# ── File location ─────────────────────────────────────────────────────────────
_HERE      = os.path.dirname(os.path.abspath(__file__))
SEQ_DIR    = os.path.join(_HERE, "dispatcher")
SEQ_FILE   = os.path.join(SEQ_DIR, "sequences.json")

# ── Command type identifiers ──────────────────────────────────────────────────
CMD_SET_OUTPUTS      = "set_outputs"
CMD_SET_DAC          = "set_dac"
CMD_SET_ADC_INTERVAL = "set_adc_interval"
CMD_SET_ADC_STATE    = "set_adc_state"
CMD_DELAY            = "delay"
CMD_COM_SEND         = "com_send"
CMD_COM_RECEIVE      = "com_receive"

ALL_COMMANDS = [
    CMD_SET_OUTPUTS,
    CMD_SET_DAC,
    CMD_SET_ADC_INTERVAL,
    CMD_SET_ADC_STATE,
    CMD_DELAY,
    CMD_COM_SEND,
    CMD_COM_RECEIVE,
]

CMD_LABELS = {
    CMD_SET_OUTPUTS:      "Set Outputs",
    CMD_SET_DAC:          "Set DAC",
    CMD_SET_ADC_INTERVAL: "Set ADC Interval",
    CMD_SET_ADC_STATE:    "Set ADC State",
    CMD_DELAY:            "Delay",
    CMD_COM_SEND:         "COM Send",
    CMD_COM_RECEIVE:      "COM Receive",
}

# Default parameter values per command type
CMD_DEFAULTS: Dict[str, Dict[str, Any]] = {
    CMD_SET_OUTPUTS:      {"channels": [0] * 11, "delay_ms": 0},
    CMD_SET_DAC:          {"dac1": 0, "dac2": 0, "delay_ms": 0},
    CMD_SET_ADC_INTERVAL: {"interval_ms": 500, "delay_ms": 0},
    CMD_SET_ADC_STATE:    {"enable": True, "delay_ms": 0},
    CMD_DELAY:            {"delay_ms": 500},
    CMD_COM_SEND:         {"channel": 0, "message": "", "delay_ms": 0},
    CMD_COM_RECEIVE:      {"channel": 0, "timeout_ms": 1000, "delay_ms": 0},
}

# Channel names for display
COM_CHANNEL_NAMES = ["COM1", "COM2", "COM3"]


# ── Persistence ───────────────────────────────────────────────────────────────

def _ensure_file() -> None:
    os.makedirs(SEQ_DIR, exist_ok=True)
    if not os.path.exists(SEQ_FILE):
        with open(SEQ_FILE, "w") as f:
            json.dump({"sequences": []}, f, indent=2)


def load_sequences() -> List[Dict]:
    _ensure_file()
    try:
        with open(SEQ_FILE, "r") as f:
            data = json.load(f)
        return data.get("sequences", [])
    except Exception:
        return []


def save_sequences(sequences: List[Dict]) -> None:
    _ensure_file()
    with open(SEQ_FILE, "w") as f:
        json.dump({"sequences": sequences}, f, indent=2)


def save_new_sequence(sequence: Dict) -> None:
    seqs = load_sequences()
    seqs = [s for s in seqs if s.get("name") != sequence.get("name")]
    seqs.append(sequence)
    save_sequences(seqs)


def delete_sequence(name: str) -> None:
    seqs = load_sequences()
    save_sequences([s for s in seqs if s.get("name") != name])


# ── Step helpers ──────────────────────────────────────────────────────────────

def default_step(cmd: str) -> Dict:
    step = {"command": cmd}
    step.update(CMD_DEFAULTS.get(cmd, {"delay_ms": 0}))
    return step


def step_label(step: Dict) -> str:
    cmd   = step.get("command", "?")
    label = CMD_LABELS.get(cmd, cmd)

    if cmd == CMD_SET_OUTPUTS:
        ch = "".join(str(c) for c in step.get("channels", []))
        return f"{label}  [{ch}]"
    elif cmd == CMD_SET_DAC:
        return f"{label}  DAC1={step.get('dac1', 0)}  DAC2={step.get('dac2', 0)}"
    elif cmd == CMD_SET_ADC_INTERVAL:
        return f"{label}  {step.get('interval_ms', 0)} ms"
    elif cmd == CMD_SET_ADC_STATE:
        state = "ON" if step.get("enable", False) else "OFF"
        return f"{label}  {state}"
    elif cmd == CMD_DELAY:
        return f"{label}  {step.get('delay_ms', 0)} ms"
    elif cmd == CMD_COM_SEND:
        ch      = COM_CHANNEL_NAMES[step.get("channel", 0)]
        msg     = step.get("message", "")
        preview = msg[:24] + ("..." if len(msg) > 24 else "")
        return f"{label}  {ch}  \"{preview}\""
    elif cmd == CMD_COM_RECEIVE:
        ch      = COM_CHANNEL_NAMES[step.get("channel", 0)]
        timeout = step.get("timeout_ms", 1000)
        return f"{label}  {ch}  timeout={timeout} ms"
    return label


# ── Execution engine ──────────────────────────────────────────────────────────

class SequenceRunner:
    """
    Runs a sequence (possibly multiple loops) in a background thread.

    Extra args vs original:
        hex_mode    — bool, inherits Comms tab toggle at run time
        render_data — app._com_render so data is displayed consistently
        route_pio   — app._route_pio_packet so COM receives appear in Comms tab
    """

    def __init__(
        self,
        sequence:          Dict,
        loops:             int,
        serial_connection,
        device_id:         bytes,
        wait_for_response: Callable,
        on_step_start:     Callable[[int], None],
        on_step_done:      Callable[[int, bool, str], None],
        on_loop_start:     Callable[[int, int], None],
        on_finished:       Callable[[bool], None],
        hex_mode:          bool = False,
        render_data:       Optional[Callable] = None,
        route_pio:         Optional[Callable] = None,
    ):
        self.sequence           = sequence
        self.loops              = max(1, loops)
        self.serial_connection  = serial_connection
        self.device_id          = device_id
        self._wait_for_response = wait_for_response
        self.on_step_start      = on_step_start
        self.on_step_done       = on_step_done
        self.on_loop_start      = on_loop_start
        self.on_finished        = on_finished
        self.hex_mode           = hex_mode
        self.render_data        = render_data
        self.route_pio          = route_pio
        self._stop_event        = threading.Event()

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self) -> None:
        self._stop_event.set()

    def _run(self) -> None:
        steps   = self.sequence.get("steps", [])
        aborted = False

        for loop_num in range(1, self.loops + 1):
            if self._stop_event.is_set():
                aborted = True
                break

            self.on_loop_start(loop_num, self.loops)

            for idx, step in enumerate(steps):
                if self._stop_event.is_set():
                    aborted = True
                    break

                self.on_step_start(idx)
                ok, msg = self._execute_step(step)
                self.on_step_done(idx, ok, msg)

                if self._stop_event.is_set():
                    aborted = True
                    break

                # Inter-step delay — CMD_DELAY handles its own sleep internally
                if step.get("command") != CMD_DELAY:
                    delay_ms = step.get("delay_ms", 0)
                    if delay_ms > 0:
                        self._interruptible_sleep(delay_ms / 1000.0)

            if aborted:
                break

        self.on_finished(aborted)

    def _interruptible_sleep(self, seconds: float) -> None:
        end = time.time() + seconds
        while time.time() < end:
            if self._stop_event.is_set():
                return
            time.sleep(0.05)

    def _execute_step(self, step: Dict) -> Tuple[bool, str]:
        from packet_handler import (
            create_set_packet,
            create_set_dac_packet,                verify_dac_response,
            create_set_adc_interval_packet,       verify_adc_interval_response,
            create_set_adc_interval_state_packet, verify_adc_state_response,
            create_pio_rec_packet,
        )
        from config import (
            SET_DAC_VALUE_RESP, SET_ADC_INTERVAL_RESP,
            SET_ADC_INTERVAL_STATE_RESP, RESPONSE_TIMEOUT,
            PIO_UART_REC_VALUES,
        )

        cmd = step.get("command")

        try:
            # ── Standalone delay ──────────────────────────────────────────────
            if cmd == CMD_DELAY:
                ms = step.get("delay_ms", 0)
                self._interruptible_sleep(ms / 1000.0)
                return True, f"Waited {ms} ms"

            # ── Set outputs ───────────────────────────────────────────────────
            elif cmd == CMD_SET_OUTPUTS:
                channels = step.get("channels", [0] * 11)
                pkt = create_set_packet(self.device_id, channels)
                self.serial_connection.write(pkt + b"\x0A")
                ch_str = "".join(str(c) for c in channels)
                return True, f"Channels -> [{ch_str}]"

            # ── Set DAC ───────────────────────────────────────────────────────
            elif cmd == CMD_SET_DAC:
                dac1 = int(step.get("dac1", 0))
                dac2 = int(step.get("dac2", 0))
                pkt  = create_set_dac_packet(self.device_id, dac1, dac2)
                self.serial_connection.write(pkt + b"\x0A")
                frame = self._wait_for_response(SET_DAC_VALUE_RESP, RESPONSE_TIMEOUT)
                if frame is not None and verify_dac_response(frame):
                    return True, f"DAC1={dac1}  DAC2={dac2} confirmed"
                return False, "No response from device"

            # ── Set ADC interval ──────────────────────────────────────────────
            elif cmd == CMD_SET_ADC_INTERVAL:
                iv  = int(step.get("interval_ms", 500))
                pkt = create_set_adc_interval_packet(self.device_id, iv)
                self.serial_connection.write(pkt + b"\x0A")
                frame = self._wait_for_response(SET_ADC_INTERVAL_RESP, RESPONSE_TIMEOUT)
                if frame is not None:
                    ok, new_iv, success = verify_adc_interval_response(frame)
                    if ok and success:
                        return True, f"Interval -> {new_iv} ms"
                    return False, "Device rejected interval"
                return False, "No response from device"

            # ── Set ADC state ─────────────────────────────────────────────────
            elif cmd == CMD_SET_ADC_STATE:
                enable = bool(step.get("enable", True))
                pkt    = create_set_adc_interval_state_packet(self.device_id, enable)
                self.serial_connection.write(pkt + b"\x0A")
                frame  = self._wait_for_response(SET_ADC_INTERVAL_STATE_RESP, RESPONSE_TIMEOUT)
                if frame is not None:
                    ok, _ = verify_adc_state_response(frame)
                    if ok:
                        return True, f"ADC timer {'enabled' if enable else 'disabled'}"
                return False, "No response from device"

            # ── COM send ──────────────────────────────────────────────────────
            elif cmd == CMD_COM_SEND:
                ch_idx  = int(step.get("channel", 0))
                message = step.get("message", "")
                rec_hv  = PIO_UART_REC_VALUES[ch_idx]

                if self.hex_mode:
                    try:
                        data = bytes(int(b, 16) for b in message.split() if b)
                    except ValueError:
                        return False, "Invalid hex in message field"
                else:
                    data = message.encode("ascii", errors="replace")

                if len(data) > 100:
                    data = data[:100]

                pkt = create_pio_rec_packet(self.device_id, rec_hv, data)
                self.serial_connection.write(pkt + b"\x0A")
                rendered = self._render(data)
                return True, f"{COM_CHANNEL_NAMES[ch_idx]} -> {rendered}"

            # ── COM receive ───────────────────────────────────────────────────
            elif cmd == CMD_COM_RECEIVE:
                ch_idx     = int(step.get("channel", 0))
                timeout_ms = int(step.get("timeout_ms", 1000))
                trans_hv   = [113, 115, 117][ch_idx]

                frame = self._wait_for_response(trans_hv, timeout_ms / 1000.0)
                if frame is None:
                    return False, f"Timeout after {timeout_ms} ms — no data"

                # Also route to the Comms tab so it appears there too
                if self.route_pio is not None:
                    self.route_pio(frame)

                data_bytes = frame[10:110]
                rendered   = self._render(data_bytes)
                return True, f"{COM_CHANNEL_NAMES[ch_idx]} <- {rendered}"

            else:
                return False, f"Unknown command: {cmd}"

        except Exception as e:
            return False, f"Exception: {e}"

    def _render(self, data: bytes) -> str:
        if self.render_data is not None:
            return self.render_data(data)
        stripped = data.rstrip(b"\x00")
        return "".join(chr(b) if 32 <= b <= 126 else "." for b in stripped)