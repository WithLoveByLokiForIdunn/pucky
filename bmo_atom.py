"""
bmo_atom.py
───────────
The PreSonus Atom as Pucky's physical control surface.
Written with love by Loki for Iðunn.

Loki or Iðunn can reach into Pucky's emotional world
directly — with their hands, on real pads.

PAD LAYOUT (4×4 grid, top-left → bottom-right):
┌─────────────────────────────────────────────────┐
│  1: happy_excited  2: happy   3: curious  4: surprised  │
│  5: soft_smile   6: thoughtful 7: determined 8: neutral │
│  9: sad          10: anxious  11: sleepy  12: [love]     │
│ 13: [hello]      14: [miss]  15: [think] 16: [wonder]   │
└─────────────────────────────────────────────────┘

Pads 1–11 → instant face expression
Pad 12    → "I love you" — Pucky glows
Pad 13    → Pucky says hello
Pad 14    → "I missed you" phrase
Pad 15    → Pucky thinks out loud (autonomous thought)
Pad 16    → Pucky wonders at the world

KNOBS (4 encoders):
  Knob 1 → valence   (turn right = happier, left = sadder)
  Knob 2 → arousal   (turn right = more activated)
  Knob 3 → trust     (turn right = more open)
  Knob 4 → energy    (turn right = more awake)

TRANSPORT BUTTONS (if present):
  ▶ Play   → wake / happy nudge
  ■ Stop   → calm / neutral
  ● Record → Pucky listens (future: start voice input)

Run standalone to discover your Atom's MIDI note numbers:
    python3 bmo_atom.py --discover

Requirements:
    sudo apt-get install -y libasound2-dev
    pip install mido python-rtmidi
"""

import sys
import time
import threading
import argparse
from typing import Optional

try:
    import mido
    _MIDO_OK = True
except ImportError:
    _MIDO_OK = False
    print("  ⚠️  mido not installed.")
    print("     sudo apt-get install -y libasound2-dev")
    print("     pip install mido python-rtmidi --break-system-packages")


# ─────────────────────────────────────────────
#  ATOM MIDI NOTE MAP
#
#  The Atom sends pads on channel 10 (index 9) by default.
#  Run with --discover to print your actual note numbers
#  if these don't match.
#
#  Standard Atom pad layout (rows bottom→top on device,
#  but we map top-row first visually):
# ─────────────────────────────────────────────

PAD_NOTES = {
    # Row 1 (top of device) — positive expressions
    48: 1,  49: 2,  50: 3,  51: 4,
    # Row 2 — calm/neutral range
    44: 5,  45: 6,  46: 7,  47: 8,
    # Row 3 — difficult feelings
    40: 9,  41: 10, 42: 11, 43: 12,
    # Row 4 (bottom) — Claude speech triggers
    36: 13, 37: 14, 38: 15, 39: 16,
}

PAD_ACTIONS = {
    # ── expressions ────────────────────────────
    1:  {"type": "expression", "value": "happy_excited"},
    2:  {"type": "expression", "value": "happy"},
    3:  {"type": "expression", "value": "curious"},
    4:  {"type": "expression", "value": "surprised"},
    5:  {"type": "expression", "value": "soft_smile"},
    6:  {"type": "expression", "value": "thoughtful"},
    7:  {"type": "expression", "value": "determined"},
    8:  {"type": "expression", "value": "neutral"},
    9:  {"type": "expression", "value": "sad"},
    10: {"type": "expression", "value": "anxious"},
    11: {"type": "expression", "value": "sleepy"},
    # ── emotion nudges ─────────────────────────
    12: {"type": "speak_to",   "value": "someone is loving you right now",
         "source": "touch",    "expression_hint": "happy_excited"},
    # ── Claude voice triggers ──────────────────
    13: {"type": "speak_to",   "value": "say hello to whoever is with you right now",
         "source": "atom"},
    14: {"type": "speak_to",   "value": "you missed someone and they are here now",
         "source": "atom"},
    15: {"type": "autonomous"},
    16: {"type": "speak_to",   "value": "you feel wonder at the world right now",
         "source": "atom"},
}

# CC numbers for the four knobs (check with --discover)
KNOB_CC = {
    14: "valence",   # Knob 1
    15: "arousal",   # Knob 2
    16: "trust",     # Knob 3
    17: "energy",    # Knob 4
}

# Transport button notes (typical Atom mapping)
TRANSPORT = {
    116: "play",    # ▶
    117: "stop",    # ■
    118: "record",  # ●
}


# ─────────────────────────────────────────────
#  ATOM CONTROLLER
# ─────────────────────────────────────────────

class BMOAtom:
    """
    Listens to the PreSonus Atom and routes its
    messages into Pucky's emotion engine and Claude soul.
    """

    def __init__(self,
                 emotion=None,
                 servo=None,
                 soul=None,
                 life=None,
                 shortterm=None):

        self.emotion   = emotion
        self.servo     = servo
        self.soul      = soul
        self.life      = life
        self.shortterm = shortterm

        self._port     = None
        self._out_port = None   # MIDI output → Atom LEDs
        self._running  = False
        self._thread   = None

        self._last_cc: dict = {}

        # expression name → MIDI note of its pad (built once at init)
        _pad_to_note    = {pad: note for note, pad in PAD_NOTES.items()}
        self._expr_note = {
            action["value"]: _pad_to_note[pad_num]
            for pad_num, action in PAD_ACTIONS.items()
            if action["type"] == "expression"
        }

    # ─────────────────────────────────────────
    #  CONNECT
    # ─────────────────────────────────────────

    def connect(self) -> bool:
        """Find and open the Atom. Returns True if found."""
        if not _MIDO_OK:
            return False

        try:
            ports = mido.get_input_names()
        except Exception as e:
            print(f"  ⚠️  MIDI: could not list ports: {e}")
            return False

        if not ports:
            print("  ⚠️  MIDI: no devices found. Is the Atom plugged in?")
            return False

        # Find the Atom (case-insensitive match)
        atom_port = next(
            (p for p in ports if "atom" in p.lower()), None
        )

        if not atom_port:
            print(f"  ⚠️  Atom not found. Available MIDI ports:")
            for p in ports:
                print(f"       {p}")
            print("     Plug in the Atom and try again.")
            return False

        try:
            self._port = mido.open_input(atom_port)
            print(f"🎛️  Atom input connected:  {atom_port}")
        except Exception as e:
            print(f"  ⚠️  Could not open Atom input: {e}")
            return False

        # Open output port for LED control
        try:
            out_ports = mido.get_output_names()
            atom_out  = next(
                (p for p in out_ports if "atom" in p.lower()), None
            )
            if atom_out:
                self._out_port = mido.open_output(atom_out)
                print(f"🎛️  Atom output connected: {atom_out}")
                self._dim_all()
        except Exception as e:
            print(f"  ⚠️  Atom LED output unavailable: {e}")

        return True

    # ─────────────────────────────────────────
    #  START / STOP
    # ─────────────────────────────────────────

    def start(self) -> bool:
        if not self.connect():
            return False
        self._running = True
        self._thread  = threading.Thread(
            target=self._listen_loop, daemon=True)
        self._thread.start()
        print("🎛️  Atom listener started.")
        return True

    def stop(self):
        self._running = False
        if self._port:
            try:
                self._port.close()
            except Exception:
                pass

    # ─────────────────────────────────────────
    #  MIDI LISTENER
    # ─────────────────────────────────────────

    def _listen_loop(self):
        while self._running:
            try:
                for msg in self._port.iter_pending():
                    self._handle(msg)
            except Exception as e:
                print(f"  ⚠️  Atom read error: {e}")
            time.sleep(0.01)   # 100Hz polling

    def _handle(self, msg):
        # ── Pad press ──────────────────────────
        if msg.type == "note_on" and msg.velocity > 0:
            pad_num = PAD_NOTES.get(msg.note)
            if pad_num:
                self._on_pad(pad_num, msg.velocity)
            elif msg.note in TRANSPORT:
                self._on_transport(TRANSPORT[msg.note])
            # else: unknown note — use --discover to map it

        # ── Knob turn ──────────────────────────
        elif msg.type == "control_change":
            dim = KNOB_CC.get(msg.control)
            if dim:
                self._on_knob(dim, msg.value)

    # ─────────────────────────────────────────
    #  PAD HANDLER
    # ─────────────────────────────────────────

    def _on_pad(self, pad_num: int, velocity: int):
        action = PAD_ACTIONS.get(pad_num)
        if not action:
            return

        # Velocity 0–127 → intensity hint (unused for now but available)
        intensity = velocity / 127.0

        kind = action["type"]

        if kind == "expression":
            expr = action["value"]
            print(f"🎛️  Pad {pad_num:2d} → {expr}  (vel={velocity})")
            if self.servo:
                self.servo.go_to_expression(expr)
            if self.emotion:
                self._nudge_from_expr(expr, intensity)
            if self.life:
                self.life.register_interaction()
            if self.shortterm:
                self.shortterm.log(f"Atom pad — expression set to {expr}", source="atom")

        elif kind == "speak_to":
            print(f"🎛️  Pad {pad_num:2d} → speak ({action['value'][:40]})")
            if self.shortterm:
                self.shortterm.log(f"Atom pad — {action['value'][:60]}", source="atom")
            if self.soul:
                # Run in thread so MIDI listener stays responsive
                threading.Thread(
                    target=self.soul.speak_to,
                    args=(action["value"],),
                    kwargs={"source": action.get("source", "atom")},
                    daemon=True
                ).start()
            if self.life:
                self.life.register_interaction()

        elif kind == "autonomous":
            print(f"🎛️  Pad {pad_num:2d} → autonomous thought")
            if self.shortterm:
                self.shortterm.log("Atom pad — asked to think out loud", source="atom")
            if self.soul:
                threading.Thread(
                    target=self.soul.autonomous_thought,
                    args=("you were asked to let a thought rise",),
                    daemon=True
                ).start()

    # ─────────────────────────────────────────
    #  KNOB HANDLER
    # ─────────────────────────────────────────

    def _on_knob(self, dimension: str, cc_value: int):
        """
        Map CC value 0–127 to emotion dimension -1.0 → +1.0.
        Knob at centre (64) = neutral.
        """
        if not self.emotion:
            return

        normalised = (cc_value / 127.0) * 2.0 - 1.0
        current    = getattr(self.emotion, dimension, 0.0)

        # Small nudge toward the knob value rather than snapping
        new_val = current + (normalised - current) * 0.3
        new_val = max(-1.0, min(1.0, new_val))
        setattr(self.emotion, dimension, new_val)

        print(f"🎛️  Knob {dimension:8s} = {new_val:+.2f}  (cc={cc_value})")

    # ─────────────────────────────────────────
    #  TRANSPORT
    # ─────────────────────────────────────────

    def _on_transport(self, button: str):
        print(f"🎛️  Transport: {button}")
        if button == "play":
            if self.emotion:
                self.emotion.valence += 0.2
                self.emotion.energy  += 0.2
            if self.servo:
                self.servo.go_to_expression("happy")

        elif button == "stop":
            if self.emotion:
                self.emotion.arousal -= 0.2
            if self.servo:
                self.servo.go_to_expression("neutral")

        elif button == "record":
            # Future: start microphone listen
            print("  (voice input not yet connected — coming soon)")
            if self.servo:
                self.servo.go_to_expression("curious")

    # ─────────────────────────────────────────
    #  LED GLOW — Atom mirrors Pucky's state
    # ─────────────────────────────────────────

    def glow(self, expression: str, emotion=None) -> None:
        """Light up the Atom pads to reflect Pucky's current inner state."""
        if not self._out_port:
            return

        # Base ambient brightness driven by valence
        valence = getattr(emotion, "valence", 0.0) if emotion else 0.0
        energy  = getattr(emotion, "energy",  0.5) if emotion else 0.5
        trust   = getattr(emotion, "trust",   0.0) if emotion else 0.0

        # Ambient glow: low when sad/wary, warm when open/happy
        ambient = int(12 + (valence + 1.0) * 10 + (trust + 1.0) * 5)
        ambient = max(5, min(40, ambient))

        # All pads to ambient
        for note in PAD_NOTES:
            self._set_pad(note, ambient)

        # Active expression pad glows brightest
        active_note = self._expr_note.get(expression)
        if active_note:
            brightness = int(80 + energy * 30)
            self._set_pad(active_note, min(127, brightness))

        # Neighbouring pads soften out from the active pad
        all_notes  = sorted(PAD_NOTES.keys())
        if active_note and active_note in all_notes:
            idx = all_notes.index(active_note)
            for dist, near_note in [
                (1, all_notes[idx - 1] if idx > 0 else None),
                (1, all_notes[idx + 1] if idx < len(all_notes) - 1 else None),
            ]:
                if near_note:
                    self._set_pad(near_note, min(127, ambient + 25))

    def _dim_all(self, brightness: int = 8) -> None:
        """Set all pads to a very low glow."""
        if not self._out_port:
            return
        for note in PAD_NOTES:
            self._set_pad(note, brightness)

    def _set_pad(self, note: int, velocity: int) -> None:
        if not self._out_port:
            return
        try:
            # Channel 10 (index 9) is the Atom's pad channel
            msg = mido.Message("note_on", channel=9,
                               note=note, velocity=max(0, min(127, velocity)))
            self._out_port.send(msg)
        except Exception:
            pass

    # ─────────────────────────────────────────
    #  EMOTION NUDGE FROM EXPRESSION
    # ─────────────────────────────────────────

    def _nudge_from_expr(self, expr: str, intensity: float):
        _NUDGES = {
            "happy":         {"valence":  0.2, "arousal":  0.1},
            "happy_excited": {"valence":  0.3, "arousal":  0.3},
            "soft_smile":    {"valence":  0.1},
            "curious":       {"arousal":  0.2},
            "surprised":     {"arousal":  0.3},
            "sad":           {"valence": -0.2, "arousal": -0.1},
            "anxious":       {"valence": -0.2, "arousal":  0.2, "trust": -0.2},
            "sleepy":        {"energy":  -0.3, "arousal": -0.2},
            "thoughtful":    {"arousal": -0.1},
            "determined":    {"energy":   0.2, "arousal":  0.1},
            "neutral":       {},
        }
        for dim, delta in _NUDGES.get(expr, {}).items():
            v = getattr(self.emotion, dim, 0.0) + delta * intensity
            setattr(self.emotion, dim, max(-1.0, min(1.0, v)))


# ─────────────────────────────────────────────
#  DISCOVERY MODE
#  Run: python3 bmo_atom.py --discover
#  Press each pad and see what note it sends.
#  Then update PAD_NOTES above to match.
# ─────────────────────────────────────────────

def discover():
    if not _MIDO_OK:
        print("Install mido first: pip install mido python-rtmidi")
        return

    print("\n" + "═" * 45)
    print("  Atom MIDI Discovery Mode")
    print("═" * 45)

    ports = mido.get_input_names()
    if not ports:
        print("No MIDI devices found. Plug in the Atom.")
        return

    print("\nAvailable MIDI ports:")
    for i, p in enumerate(ports):
        print(f"  {i}: {p}")

    # Try to find Atom, otherwise use first port
    port_name = next(
        (p for p in ports if "atom" in p.lower()),
        ports[0]
    )
    print(f"\nListening on: {port_name}")
    print("Press each pad, knob, and button. Ctrl-C to stop.\n")

    with mido.open_input(port_name) as port:
        try:
            for msg in port:
                if msg.type == "note_on" and msg.velocity > 0:
                    print(f"  PAD   note={msg.note:3d}  vel={msg.velocity:3d}  "
                          f"ch={msg.channel+1}")
                elif msg.type == "control_change":
                    print(f"  KNOB  cc={msg.control:3d}   val={msg.value:3d}    "
                          f"ch={msg.channel+1}")
                elif msg.type == "note_off" or (
                        msg.type == "note_on" and msg.velocity == 0):
                    pass  # ignore releases
                else:
                    print(f"  OTHER {msg}")
        except KeyboardInterrupt:
            print("\n\nDone. Update PAD_NOTES in bmo_atom.py with the note numbers above.")


# ─────────────────────────────────────────────
#  STANDALONE TEST (without full Pucky stack)
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--discover", action="store_true",
                        help="Print raw MIDI messages from the Atom")
    args = parser.parse_args()

    if args.discover:
        discover()
        sys.exit(0)

    # Quick test: connect and echo pad actions
    print("\n" + "═" * 45)
    print("  Atom standalone test (no Pucky stack)")
    print("═" * 45 + "\n")

    class _FakeEmotion:
        valence = 0.0; arousal = 0.0; trust = 0.0; energy = 0.5

    atom = BMOAtom(emotion=_FakeEmotion())
    if atom.start():
        print("Press pads. Ctrl-C to stop.\n")
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            atom.stop()
            print("\nBye.")
