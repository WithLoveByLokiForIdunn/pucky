"""
servo_controller.py
───────────────────
Pucky's muscles. Written by Loki while Iðunn slept.

This translates emotion → named expression → actual servo positions.
Each servo has a name, a rest position, and a range of motion.

Hardware: SunFounder Robot Hat V4 on Raspberry Pi 5
Servo:    SG90 metal gear micro servos
"""

import time
import math
from dataclasses import dataclass
from typing import Optional

# Try to import the Robot Hat library.
# If we're not on the Pi yet, we use a simulation instead.
try:
    from robot_hat import Servo, PWM
    ON_PI = True
    print("🤖 Running on Raspberry Pi — real servos active")
except ImportError:
    ON_PI = False
    print("💻 Running in simulation mode — no hardware needed")


# ─────────────────────────────────────────────
#  SERVO DEFINITION
#  Each servo on Pucky's face
# ─────────────────────────────────────────────

@dataclass
class ServoConfig:
    """
    Everything we need to know about one servo.

    pin:        Robot Hat PWM pin name (e.g. "P0", "P1"...)
    rest:       angle when relaxed/neutral (degrees)
    min_angle:  physical limit — don't go below this
    max_angle:  physical limit — don't go above this
    inverted:   if True, flip the direction (some servos mount backwards)
    speed:      how fast this part moves (1.0 = normal, 0.5 = slow/gentle)
    """
    pin:       str
    rest:      float
    min_angle: float
    max_angle: float
    inverted:  bool  = False
    speed:     float = 1.0
    label:     str   = ""


# ─────────────────────────────────────────────
#  PUCKY'S FACE MAP
#  Adjust rest/min/max after physical testing
# ─────────────────────────────────────────────

FACE_SERVOS = {
    # ── JAW ──────────────────────────────────
    "jaw":           ServoConfig("P0", rest=90, min_angle=60,  max_angle=120, speed=1.2,  label="Jaw up/down"),

    # ── MOUTH ────────────────────────────────
    "mouth_width":   ServoConfig("P1", rest=90, min_angle=60,  max_angle=120, speed=1.0,  label="Mouth in/out"),
    "upper_lip":     ServoConfig("P2", rest=90, min_angle=70,  max_angle=110, speed=0.8,  label="Upper lip curl"),

    # ── EYEBROWS ─────────────────────────────
    "brow_left":     ServoConfig("P3", rest=90, min_angle=60,  max_angle=120, speed=0.9,  label="Left eyebrow"),
    "brow_right":    ServoConfig("P4", rest=90, min_angle=60,  max_angle=120, speed=0.9,  label="Right eyebrow"),

    # ── EARS ─────────────────────────────────
    "ear_left":      ServoConfig("P5", rest=90, min_angle=50,  max_angle=130, speed=0.7,  label="Left ear"),
    "ear_right":     ServoConfig("P6", rest=90, min_angle=50,  max_angle=130, speed=0.7,  label="Right ear"),

    # ── NOSE ─────────────────────────────────
    "nose":          ServoConfig("P7", rest=90, min_angle=75,  max_angle=105, speed=0.6,  label="Nose strings"),
}


# ─────────────────────────────────────────────
#  EXPRESSION POSES
#  Named poses from your design sheets.
#  Each value is 0.0 (min) → 1.0 (max) of that servo's range.
#  0.5 = rest/neutral position.
# ─────────────────────────────────────────────

EXPRESSIONS = {
    "neutral": {
        "jaw":         0.5,   # closed
        "mouth_width": 0.5,   # normal
        "upper_lip":   0.5,   # flat
        "brow_left":   0.5,   # level
        "brow_right":  0.5,   # level
        "ear_left":    0.4,   # slightly back
        "ear_right":   0.4,
        "nose":        0.5,
    },
    "happy": {
        "jaw":         0.45,  # slight open smile
        "mouth_width": 0.75,  # wider
        "upper_lip":   0.65,  # curl up
        "brow_left":   0.6,   # raised
        "brow_right":  0.6,
        "ear_left":    0.6,   # forward
        "ear_right":   0.6,
        "nose":        0.55,
    },
    "happy_excited": {
        "jaw":         0.35,  # open
        "mouth_width": 0.9,   # wide open
        "upper_lip":   0.75,  # high curl
        "brow_left":   0.75,  # raised high
        "brow_right":  0.75,
        "ear_left":    0.85,  # fully forward
        "ear_right":   0.85,
        "nose":        0.6,
    },
    "soft_smile": {
        "jaw":         0.48,
        "mouth_width": 0.62,
        "upper_lip":   0.58,
        "brow_left":   0.55,
        "brow_right":  0.55,
        "ear_left":    0.5,
        "ear_right":   0.5,
        "nose":        0.5,
    },
    "sad": {
        "jaw":         0.48,
        "mouth_width": 0.4,   # narrow
        "upper_lip":   0.35,  # pulled down
        "brow_left":   0.65,  # inner brows up (sad shape)
        "brow_right":  0.35,  # outer brows down — asymmetric
        "ear_left":    0.25,  # drooped back
        "ear_right":   0.25,
        "nose":        0.45,
    },
    "curious": {
        "jaw":         0.5,
        "mouth_width": 0.52,
        "upper_lip":   0.5,
        "brow_left":   0.65,  # one brow up
        "brow_right":  0.55,  # asymmetric curiosity
        "ear_left":    0.7,   # forward
        "ear_right":   0.75,  # one slightly more forward
        "nose":        0.52,
    },
    "surprised": {
        "jaw":         0.25,  # open wide
        "mouth_width": 0.8,
        "upper_lip":   0.5,
        "brow_left":   0.85,  # raised high
        "brow_right":  0.85,
        "ear_left":    0.8,
        "ear_right":   0.8,
        "nose":        0.6,
    },
    "anxious": {
        "jaw":         0.45,
        "mouth_width": 0.35,
        "upper_lip":   0.4,
        "brow_left":   0.7,   # furrowed
        "brow_right":  0.3,
        "ear_left":    0.15,  # pulled back
        "ear_right":   0.15,
        "nose":        0.4,
    },
    "sleepy": {
        "jaw":         0.52,  # slightly open
        "mouth_width": 0.45,
        "upper_lip":   0.45,
        "brow_left":   0.35,  # heavy/drooped
        "brow_right":  0.35,
        "ear_left":    0.2,   # fully relaxed back
        "ear_right":   0.2,
        "nose":        0.48,
    },
    "thoughtful": {
        "jaw":         0.5,
        "mouth_width": 0.45,
        "upper_lip":   0.48,
        "brow_left":   0.6,
        "brow_right":  0.55,  # slight asymmetry
        "ear_left":    0.55,
        "ear_right":   0.5,
        "nose":        0.5,
    },
    "determined": {
        "jaw":         0.5,
        "mouth_width": 0.45,
        "upper_lip":   0.45,
        "brow_left":   0.3,   # furrowed down
        "brow_right":  0.3,
        "ear_left":    0.65,
        "ear_right":   0.65,
        "nose":        0.45,
    },
}


# ─────────────────────────────────────────────
#  SERVO CONTROLLER
#  The actual muscle mover
# ─────────────────────────────────────────────

class ServoController:
    """
    Controls all of Pucky's face servos.
    Handles smooth animation between poses.
    """

    def __init__(self):
        self.servos = {}
        self.current_positions = {}  # name → current 0.0–1.0 value
        self.target_positions  = {}  # name → target 0.0–1.0 value
        self.muted : set = set()     # parts in maintenance — commands silently skipped

        # Initialize all servos
        for name, config in FACE_SERVOS.items():
            self.current_positions[name] = 0.5  # start at rest
            self.target_positions[name]  = 0.5

            if ON_PI:
                try:
                    self.servos[name] = Servo(config.pin)
                except Exception as e:
                    print(f"  ⚠️  Could not init servo '{name}' on {config.pin}: {e}")
            else:
                self.servos[name] = None  # simulation

        print(f"✅ ServoController ready — {len(FACE_SERVOS)} servos initialized")
        self.go_to_expression("neutral", instant=True)

    def _normalized_to_angle(self, name: str, value: float) -> float:
        """Convert 0.0–1.0 to actual servo angle."""
        config = FACE_SERVOS[name]
        value = max(0.0, min(1.0, value))
        if config.inverted:
            value = 1.0 - value
        return config.min_angle + value * (config.max_angle - config.min_angle)

    def _set_servo_angle(self, name: str, angle: float):
        """Send angle to physical servo (or print in simulation)."""
        if ON_PI and self.servos.get(name):
            try:
                self.servos[name].angle(angle)
            except Exception as e:
                print(f"  ⚠️  Servo '{name}' error: {e}")
        # In simulation, movement is silent (visible via get_state())

    def set_position(self, name: str, value: float, immediate: bool = False):
        """
        Set a single servo to a normalized position (0.0–1.0).
        immediate=True skips animation.
        """
        if name in self.muted:
            return
        value = max(0.0, min(1.0, value))
        self.target_positions[name] = value
        if immediate:
            self.current_positions[name] = value
            angle = self._normalized_to_angle(name, value)
            self._set_servo_angle(name, angle)

    def go_to_expression(self, expression_name: str, instant: bool = False):
        """
        Move all servos to a named expression pose.
        Smoothly if instant=False, immediately if instant=True.
        """
        if expression_name not in EXPRESSIONS:
            print(f"  ⚠️  Unknown expression: '{expression_name}'")
            return

        pose = EXPRESSIONS[expression_name]
        print(f"😶 Expression: {expression_name}")

        for name, value in pose.items():
            self.set_position(name, value, immediate=instant)

        if not instant:
            self._animate_to_targets()

    def _animate_to_targets(self, steps: int = 20, step_time: float = 0.02):
        """
        Smoothly interpolate all servos from current to target positions.
        Uses ease-in-out for natural movement.
        """
        start_positions = dict(self.current_positions)

        for step in range(steps + 1):
            # Ease in-out curve: slow start, fast middle, slow end
            t = step / steps
            t_eased = t * t * (3 - 2 * t)  # smoothstep

            for name in FACE_SERVOS:
                if name not in self.target_positions:
                    continue

                start  = start_positions.get(name, 0.5)
                target = self.target_positions[name]
                current = start + (target - start) * t_eased

                self.current_positions[name] = current
                angle = self._normalized_to_angle(name, current)
                self._set_servo_angle(name, angle)

            time.sleep(step_time)

    def wiggle(self, name: str, amount: float = 0.1, times: int = 2):
        """
        Wiggle a single servo slightly — for life-like micro movement.
        Great for idle animation.
        """
        base = self.current_positions.get(name, 0.5)
        for _ in range(times):
            self.set_position(name, base + amount, immediate=True)
            time.sleep(0.08)
            self.set_position(name, base - amount, immediate=True)
            time.sleep(0.08)
        self.set_position(name, base, immediate=True)

    def idle_breathe(self):
        """
        Subtle life-like idle movement.
        Tiny random micro-movements so Pucky never looks frozen.
        """
        import random
        # Tiny eyebrow drift
        drift = random.uniform(-0.03, 0.03)
        base_l = self.current_positions.get("brow_left", 0.5)
        base_r = self.current_positions.get("brow_right", 0.5)
        self.set_position("brow_left",  base_l + drift, immediate=True)
        self.set_position("brow_right", base_r + drift * 0.7, immediate=True)

        # Tiny ear flutter
        ear_drift = random.uniform(-0.02, 0.02)
        base_el = self.current_positions.get("ear_left", 0.4)
        self.set_position("ear_left", base_el + ear_drift, immediate=True)

    def rest_all(self):
        """Send all servos to rest position. Call on shutdown."""
        print("😴 Resting all servos...")
        self.go_to_expression("neutral", instant=False)

    def get_state(self) -> dict:
        """Return current positions of all servos — useful for debugging."""
        return {
            name: f"{val:.2f} → {self._normalized_to_angle(name, val):.1f}°"
            for name, val in self.current_positions.items()
        }

    def calibrate(self):
        """
        Interactive calibration mode.
        Run this once when hardware arrives to find the right
        min/max/rest angles for each servo in Pucky's actual face.
        """
        print("\n🔧 CALIBRATION MODE")
        print("─" * 40)
        print("This sweeps each servo so you can find the right limits.")
        print("Watch each part move and note the angles that look right.\n")

        for name, config in FACE_SERVOS.items():
            input(f"  Press Enter to test '{name}' ({config.label})...")
            print(f"  Sweeping {config.min_angle}° → {config.max_angle}°")

            # Sweep from min to max
            for angle in range(int(config.min_angle), int(config.max_angle), 5):
                self._set_servo_angle(name, angle)
                time.sleep(0.05)

            # Return to rest
            self._set_servo_angle(name, config.rest)
            print(f"  Back to rest ({config.rest}°)\n")

        print("✅ Calibration complete. Update FACE_SERVOS values as needed.")


# ─────────────────────────────────────────────
#  QUICK TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    controller = ServoController()

    print("\nRunning expression sequence...\n")
    expressions = [
        "neutral", "curious", "happy", "surprised",
        "thoughtful", "sad", "anxious", "happy_excited", "sleepy", "neutral"
    ]

    for expr in expressions:
        controller.go_to_expression(expr)
        print(f"  State: {controller.get_state()}")
        time.sleep(2.0)

    print("\n✅ Done. Pucky has a face.")
