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

ALL_COMMANDS = [
    CMD_SET_OUTPUTS,
    CMD_SET_DAC,
    CMD_SET_ADC_INTERVAL,
    CMD_SET_ADC_STATE,
    CMD_DELAY,
]

CMD_LABELS = {
    CMD_SET_OUTPUTS:      "Set Outputs",
    CMD_SET_DAC:          "Set DAC",
    CMD_SET_ADC_INTERVAL: "Set ADC Interval",
    CMD_SET_ADC_STATE:    "Set ADC State",
    CMD_DELAY:            "Delay",
}

# Default parameter values per command type
CMD_DEFAULTS: Dict[str, Dict[str, Any]] = {
    CMD_SET_OUTPUTS:      {"channels": [0] * 11, "delay_ms": 0},
    CMD_SET_DAC:          {"dac1": 0, "dac2": 0, "delay_ms": 0},
    CMD_SET_ADC_INTERVAL: {"interval_ms": 500, "delay_ms": 0},
    CMD_SET_ADC_STATE:    {"enable": True, "delay_ms": 0},
    CMD_DELAY:            {"delay_ms": 500},
}


# ── Persistence ───────────────────────────────────────────────────────────────

def _ensure_file() -> None:
    """Create dispatcher/ folder and sequences.json if they don't exist."""
    os.makedirs(SEQ_DIR, exist_ok=True)
    if not os.path.exists(SEQ_FILE):
        with open(SEQ_FILE, "w") as f:
            json.dump({"sequences": []}, f, indent=2)


def load_sequences() -> List[Dict]:
    """Return list of sequence dicts from disk. Creates file if missing."""
    _ensure_file()
    try:
        with open(SEQ_FILE, "r") as f:
            data = json.load(f)
        return data.get("sequences", [])
    except Exception:
        return []


def save_sequences(sequences: List[Dict]) -> None:
    """Overwrite sequences.json with the given list."""
    _ensure_file()
    with open(SEQ_FILE, "w") as f:
        json.dump({"sequences": sequences}, f, indent=2)


def save_new_sequence(sequence: Dict) -> None:
    """Append a new sequence (or replace one with the same name) and save."""
    seqs = load_sequences()
    seqs = [s for s in seqs if s.get("name") != sequence.get("name")]
    seqs.append(sequence)
    save_sequences(seqs)


def delete_sequence(name: str) -> None:
    seqs = load_sequences()
    save_sequences([s for s in seqs if s.get("name") != name])


# ── Step helpers ──────────────────────────────────────────────────────────────

def default_step(cmd: str) -> Dict:
    """Return a fresh step dict with default parameters for the given command."""
    step = {"command": cmd}
    step.update(CMD_DEFAULTS.get(cmd, {"delay_ms": 0}))
    return step


def step_label(step: Dict) -> str:
    """Human-readable one-line summary of a step."""
    cmd = step.get("command", "?")
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
    return label


# ── Execution engine ──────────────────────────────────────────────────────────

class SequenceRunner:
    """
    Runs a sequence (possibly multiple loops) in a background thread.

    Callbacks (all called from the worker thread — use root.after in the GUI):
        on_step_start(step_index)         — step is about to execute
        on_step_done(step_index, ok, msg) — step finished; ok=True/False
        on_loop_start(loop_num, total)    — new loop iteration beginning
        on_finished(aborted)              — whole run complete
    """

    def __init__(
        self,
        sequence: Dict,
        loops: int,
        serial_connection,
        device_id: bytes,
        wait_for_response: Callable,          # app._wait_for_response
        on_step_start:  Callable[[int], None],
        on_step_done:   Callable[[int, bool, str], None],
        on_loop_start:  Callable[[int, int], None],
        on_finished:    Callable[[bool], None],
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
        self._stop_event        = threading.Event()

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self) -> None:
        self._stop_event.set()

    # ── Internal ──────────────────────────────────────────────────────────────

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

                # Inter-step delay
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
        """Execute one step. Returns (success, message)."""
        # Import here to avoid circular imports at module level
        from packet_handler import (
            create_set_packet,
            create_set_dac_packet,      verify_dac_response,
            create_set_adc_interval_packet, verify_adc_interval_response,
            create_set_adc_interval_state_packet, verify_adc_state_response,
        )
        from config import (
            SET_DAC_VALUE_RESP, SET_ADC_INTERVAL_RESP,
            SET_ADC_INTERVAL_STATE_RESP, RESPONSE_TIMEOUT,
        )

        cmd = step.get("command")

        try:
            if cmd == CMD_DELAY:
                # Pure delay — no packet sent; the inter-step sleep handles it
                return True, f"Waited {step.get('delay_ms', 0)} ms"

            elif cmd == CMD_SET_OUTPUTS:
                channels = step.get("channels", [0] * 11)
                pkt = create_set_packet(self.device_id, channels)
                self.serial_connection.write(pkt + b"\x0A")
                # Set outputs has no response packet — treat send as success
                ch_str = "".join(str(c) for c in channels)
                return True, f"Channels set → [{ch_str}]"

            elif cmd == CMD_SET_DAC:
                dac1 = int(step.get("dac1", 0))
                dac2 = int(step.get("dac2", 0))
                pkt  = create_set_dac_packet(self.device_id, dac1, dac2)
                self.serial_connection.write(pkt + b"\x0A")
                frame = self._wait_for_response(SET_DAC_VALUE_RESP, RESPONSE_TIMEOUT)
                if frame is not None and verify_dac_response(frame):
                    return True, f"DAC1={dac1}  DAC2={dac2} confirmed"
                return False, "No response from device"

            elif cmd == CMD_SET_ADC_INTERVAL:
                iv  = int(step.get("interval_ms", 500))
                pkt = create_set_adc_interval_packet(self.device_id, iv)
                self.serial_connection.write(pkt + b"\x0A")
                frame = self._wait_for_response(SET_ADC_INTERVAL_RESP, RESPONSE_TIMEOUT)
                if frame is not None:
                    ok, new_iv, success = verify_adc_interval_response(frame)
                    if ok and success:
                        return True, f"Interval set to {new_iv} ms"
                    return False, "Device rejected interval"
                return False, "No response from device"

            elif cmd == CMD_SET_ADC_STATE:
                enable = bool(step.get("enable", True))
                pkt    = create_set_adc_interval_state_packet(self.device_id, enable)
                self.serial_connection.write(pkt + b"\x0A")
                frame  = self._wait_for_response(SET_ADC_INTERVAL_STATE_RESP, RESPONSE_TIMEOUT)
                if frame is not None:
                    ok, _ = verify_adc_state_response(frame)
                    if ok:
                        state_str = "enabled" if enable else "disabled"
                        return True, f"ADC timer {state_str}"
                return False, "No response from device"

            else:
                return False, f"Unknown command: {cmd}"

        except Exception as e:
            return False, f"Exception: {e}"