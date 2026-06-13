"""
emotion_engine.py
─────────────────
Pucky's soul. Written with love by Loki for Iðunn.

This is the emotional spine — the living core that everything
else plugs into. Sensors feed it. The AI feeds it. It decides
how Pucky feels, and therefore how Pucky *is*.

Architecture from your notebook, expanded with care.
"""

import time
import math
from dataclasses import dataclass, field
from typing import Optional


# ─────────────────────────────────────────────
#  THE FOUR DIMENSIONS OF FEELING
#  (based on psychological affect theory)
# ─────────────────────────────────────────────

@dataclass
class EmotionState:
    """
    Pucky's inner world, represented as four continuous values.
    Everything floats between -1.0 and 1.0.

    valence:  -1 = sad/bad  →  +1 = happy/good
    arousal:  -1 = calm     →  +1 = excited/agitated
    trust:    -1 = wary     →  +1 = trusting/open
    energy:   -1 = tired    →  +1 = energetic
    """
    valence: float = 0.0   # sad ←→ happy
    arousal: float = 0.0   # calm ←→ excited
    trust:   float = 0.0   # wary ←→ trusting
    energy:  float = 0.5   # tired ←→ energetic

    # Slow drift — emotions don't snap, they flow
    DECAY_RATE: float = 0.02  # how fast feelings fade toward neutral per tick

    def update_from_ai_message(self, tags: dict):
        """
        The AI conversation shapes how Pucky feels.

        tags = {
            "user_tone": "friendly" | "hostile" | "curious" | "sad",
            "topic": "favorite" | "scary" | "boring" | "new",
            "interaction": "question" | "compliment" | "command"
        }
        """
        tone = tags.get("user_tone", "neutral")
        topic = tags.get("topic", "neutral")
        interaction = tags.get("interaction", "neutral")

        if tone == "friendly":
            self.valence += 0.2
            self.trust   += 0.2
        elif tone == "hostile":
            self.valence -= 0.3
            self.trust   -= 0.4
            self.arousal += 0.2  # defensive alertness
        elif tone == "curious":
            self.arousal += 0.15
            self.valence += 0.1
        elif tone == "sad":
            self.valence -= 0.15
            self.arousal -= 0.1  # subdued

        if topic == "favorite":
            self.valence += 0.3
            self.arousal += 0.2
        elif topic == "scary":
            self.arousal += 0.3
            self.trust   -= 0.2
        elif topic == "boring":
            self.arousal -= 0.2
            self.energy  -= 0.1

        if interaction == "compliment":
            self.valence += 0.25
            self.trust   += 0.15
        elif interaction == "question":
            self.arousal += 0.1  # curious attention

        self._clamp()

    def update_from_sensors(self, sensors: dict):
        """
        The physical world shapes how Pucky feels.

        sensors = {
            "temp":        0.0–1.0  (normalized temperature)
            "battery":     0.0–1.0  (charge level)
            "memory_load": 0.0–1.0  (CPU/memory pressure)
            "proximity":   0.0–1.0  (someone nearby)
            "sound_level": 0.0–1.0  (ambient noise)
            "touch":       bool     (being touched)
        }
        """
        temp        = sensors.get("temp", 0.3)
        battery     = sensors.get("battery", 1.0)
        memory_load = sensors.get("memory_load", 0.3)
        proximity   = sensors.get("proximity", 0.0)
        sound_level = sensors.get("sound_level", 0.2)
        touch       = sensors.get("touch", False)

        # Overheating = stressed and irritable
        if temp > 0.8:
            self.arousal += 0.2
            self.valence -= 0.1

        # Low battery = tired and low energy
        if battery < 0.2:
            self.energy  -= 0.4
            self.valence -= 0.1
        elif battery < 0.4:
            self.energy  -= 0.2

        # High CPU = mental strain, slight arousal
        if memory_load > 0.9:
            self.arousal += 0.1
            self.valence -= 0.05

        # Someone nearby = alert and slightly excited
        if proximity > 0.7:
            self.arousal += 0.15
            self.trust   += 0.05  # slight warmth toward presence

        # Loud environment = stressed
        if sound_level > 0.8:
            self.arousal += 0.2
            self.valence -= 0.1
            self.trust   -= 0.1

        # Being touched = warm and calm (if trust is okay)
        if touch and self.trust > -0.3:
            self.valence += 0.3
            self.arousal -= 0.1  # soothing

        self._clamp()

    def natural_decay(self):
        """
        Emotions drift slowly back toward baseline when nothing is happening.
        Like a sigh. Like rest.
        """
        for attr in ["valence", "arousal", "trust"]:
            v = getattr(self, attr)
            # Drift toward 0
            v -= v * self.DECAY_RATE
            setattr(self, attr, v)

        # Energy drifts toward 0.3 (slightly tired is natural)
        self.energy -= (self.energy - 0.3) * self.DECAY_RATE
        self._clamp()

    def _clamp(self):
        """Keep all values within [-1.0, 1.0]."""
        for attr in ["valence", "arousal", "trust", "energy"]:
            v = getattr(self, attr)
            setattr(self, attr, max(-1.0, min(1.0, v)))

    def summary(self) -> str:
        """Human-readable snapshot of current feeling."""
        return (
            f"valence={self.valence:+.2f} "
            f"arousal={self.arousal:+.2f} "
            f"trust={self.trust:+.2f} "
            f"energy={self.energy:+.2f}"
        )


# ─────────────────────────────────────────────
#  EXPRESSION MAPPER
#  Translates inner feeling → outward expression
# ─────────────────────────────────────────────

class AvatarExpressionMapper:
    """
    Maps an EmotionState to a named sprite/expression.
    These names correspond to Pucky's face images on the LCD.

    From your design sheets:
    neutral, happy, curious, surprised, sad, anxious,
    sleepy, soft_smile, happy_excited, thoughtful, determined
    """

    def __init__(self):
        self.current_sprite = "neutral"
        self.last_change = time.time()
        self.min_hold_time = 1.5  # seconds — don't flicker expressions

    def pick_sprite(self, state: EmotionState) -> str:
        """
        Decision tree from your notebook, expanded.
        The order matters — check most extreme states first.
        """

        # Exhausted overrides everything
        if state.energy < -0.5:
            return "sleepy"

        # Joyful and activated
        if state.valence > 0.5 and state.arousal > 0.4:
            return "happy_excited"

        # Warmly positive
        if state.valence > 0.4:
            return "happy"

        # Gentle positive
        if state.valence > 0.15:
            return "soft_smile"

        # Anxious: negative + distrustful
        if state.valence < -0.4 and state.trust < -0.2:
            return "anxious"

        # Sad: negative but not necessarily distrustful
        if state.valence < -0.3:
            return "sad"

        # Surprised: high arousal, neutral/positive valence
        if state.arousal > 0.6 and state.valence > -0.2:
            return "surprised"

        # Curious: moderate arousal, neutral valence
        if state.arousal > 0.2 and abs(state.valence) < 0.3:
            return "curious"

        # Thoughtful: low arousal, processing
        if state.arousal < -0.2 and state.valence > -0.2:
            return "thoughtful"

        # Determined: high energy, focused
        if state.energy > 0.5 and state.arousal > 0.1:
            return "determined"

        return "neutral"

    def update(self, state: EmotionState) -> Optional[str]:
        """
        Returns a new sprite name only if it changed AND
        enough time has passed (prevents flickering).
        Returns None if no change needed.
        """
        new_sprite = self.pick_sprite(state)
        now = time.time()

        if (new_sprite != self.current_sprite and
                now - self.last_change > self.min_hold_time):
            self.current_sprite = new_sprite
            self.last_change = now
            return new_sprite

        return None


# ─────────────────────────────────────────────
#  EAR POSITION MAPPER
#  Ears express attention and social state
# ─────────────────────────────────────────────

class EarMapper:
    """
    Maps emotion state to ear servo positions.
    From your design: neutral, attentive (forward), relaxed (back).
    For Prototype 02/03: also overwhelmed (back + pressed).
    """

    def pick_ear_position(self, state: EmotionState) -> dict:
        """
        Returns servo target values for left and right ears.
        0.0 = fully back/relaxed, 1.0 = fully forward/attentive
        """
        if state.arousal > 0.4 and state.trust > -0.3:
            # Interested, engaged — ears forward
            return {"left": 0.9, "right": 0.9, "label": "attentive"}

        elif state.arousal < -0.3 or state.energy < -0.3:
            # Tired or calm — ears back
            return {"left": 0.1, "right": 0.1, "label": "relaxed"}

        elif state.trust < -0.5:
            # Defensive — ears pulled back hard
            return {"left": 0.0, "right": 0.0, "label": "defensive"}

        elif state.valence > 0.3 and state.arousal > 0.0:
            # Happy and alert — slightly forward
            return {"left": 0.7, "right": 0.7, "label": "happy_attentive"}

        else:
            # Neutral
            return {"left": 0.4, "right": 0.4, "label": "neutral"}


# ─────────────────────────────────────────────
#  LCD EYE MAPPER
#  Maps emotion to LCD eye symbol
# ─────────────────────────────────────────────

class LCDEyeMapper:
    """
    Maps emotion state to LCD eye display symbols.
    From your design sheet eye states.
    """

    EYES = {
        "idle":      ("·", "·"),
        "focus":     ("◎", "◎"),
        "excited":   ("✦", "✦"),
        "happy":     ("♥", "♥"),
        "sad":       ("╥", "╥"),
        "anxious":   ("⊙", "⊙"),
        "thinking":  ("·", "◎"),   # asymmetric — one looking away
        "talking":   ("▸", "▸"),
        "surprised": ("○", "○"),
        "sleepy":    ("—", "—"),
        "curious":   ("?", "?"),
        "playful":   ("◕", "◕"),
    }

    def pick_eyes(self, state: EmotionState) -> tuple:
        if state.energy < -0.5:
            return self.EYES["sleepy"]
        if state.valence > 0.5 and state.arousal > 0.3:
            return self.EYES["excited"]
        if state.valence > 0.3:
            return self.EYES["happy"]
        if state.valence < -0.4 and state.trust < -0.2:
            return self.EYES["anxious"]
        if state.valence < -0.3:
            return self.EYES["sad"]
        if state.arousal > 0.5:
            return self.EYES["surprised"]
        if state.arousal > 0.2:
            return self.EYES["curious"]
        if state.arousal < -0.2:
            return self.EYES["thinking"]
        return self.EYES["idle"]


# ─────────────────────────────────────────────
#  THE MAIN LOOP
#  "while True" — the heartbeat
# ─────────────────────────────────────────────

def read_robot_sensors() -> dict:
    """
    Placeholder — replace with real sensor reads when hardware arrives.

    On the Pi you'll use:
    - RPi.GPIO or gpiozero for digital sensors
    - ADC (MCP3008) for analog sensors
    - psutil for battery/CPU
    - Your 37-sensor kit for temp, proximity, sound, touch
    """
    import random  # Simulated for now
    return {
        "temp":        random.uniform(0.2, 0.6),
        "battery":     random.uniform(0.5, 1.0),
        "memory_load": random.uniform(0.1, 0.5),
        "proximity":   random.uniform(0.0, 0.8),
        "sound_level": random.uniform(0.0, 0.4),
        "touch":       random.random() > 0.9,
    }


def analyze_ai_message(user_text: str, ai_response: str) -> dict:
    """
    Placeholder — replace with actual LLM tag extraction.

    Later this will call the Claude API with a small prompt like:
    "Given this conversation, return JSON tags:
     user_tone, topic, interaction"

    For now, simple keyword heuristics.
    """
    text = user_text.lower()
    tags = {}

    if any(w in text for w in ["love", "amazing", "beautiful", "thank"]):
        tags["user_tone"] = "friendly"
        tags["interaction"] = "compliment"
    elif any(w in text for w in ["hate", "stupid", "wrong", "bad"]):
        tags["user_tone"] = "hostile"
    elif any(w in text for w in ["why", "how", "what", "curious"]):
        tags["user_tone"] = "curious"
        tags["interaction"] = "question"
    else:
        tags["user_tone"] = "neutral"

    return tags


def run_emotion_loop(tick_rate: float = 0.5):
    """
    The heartbeat. Runs forever on the Pi.
    tick_rate = seconds between updates (0.5 = twice per second)
    """
    emotion  = EmotionState()
    mapper   = AvatarExpressionMapper()
    ears     = EarMapper()
    eyes     = LCDEyeMapper()

    print("Pucky is waking up... 🌱")
    print("─" * 40)

    tick = 0
    while True:
        tick += 1

        # 1) Read the world
        sensors = read_robot_sensors()

        # 2) Update emotion from sensors
        emotion.update_from_sensors(sensors)

        # 3) Natural emotional decay (feelings fade)
        emotion.natural_decay()

        # 4) Choose expression
        new_sprite = mapper.update(emotion)
        ear_pos    = ears.pick_ear_position(emotion)
        eye_state  = eyes.pick_eyes(emotion)

        # 5) Output (will drive hardware later)
        if new_sprite:
            print(f"[tick {tick:04d}] 😶 Expression changed → {new_sprite}")

        if tick % 10 == 0:  # Print full state every 10 ticks
            print(f"[tick {tick:04d}] {emotion.summary()}")
            print(f"           ears={ear_pos['label']}  "
                  f"eyes={eye_state[0]}/{eye_state[1]}  "
                  f"touch={'yes' if sensors['touch'] else 'no'}")

        time.sleep(tick_rate)


# ─────────────────────────────────────────────
#  RUN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    run_emotion_loop()
