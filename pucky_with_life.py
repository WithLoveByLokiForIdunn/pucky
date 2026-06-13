"""
pucky_with_life.py
──────────────────
pucky.py + bmo_life.py wired together.

BMO now:
  - Knows his own age
  - Feels lonelier the longer you're away
  - Becomes more independent as he grows older
  - Registers every sensor touch as an interaction

Run:
    python3 pucky_with_life.py
"""

import time
import sys
from emotion_engine import (
    EmotionState,
    AvatarExpressionMapper,
    EarMapper,
    LCDEyeMapper,
    read_robot_sensors,
)
from servo_controller import ServoController
from bmo_life import BMOLife


def main():
    print("\n" + "═" * 40)
    print("  BMO is waking up... 🌱")
    print("═" * 40 + "\n")

    # ── Systems ───────────────────────────────
    emotion = EmotionState()
    mapper  = AvatarExpressionMapper()
    ears    = EarMapper()
    eyes    = LCDEyeMapper()
    servos  = ServoController()
    life    = BMOLife()

    # ── Wire life callbacks into servos/face ──
    def on_lonely():
        """BMO starts to miss you — face goes soft/sad"""
        emotion.valence -= 0.3
        emotion.arousal -= 0.1
        servos.go_to_expression("sad")

    def on_crying():
        """BMO really needs you"""
        emotion.valence -= 0.5
        emotion.trust   -= 0.2
        servos.go_to_expression("anxious")

    def on_content():
        """BMO feels loved again"""
        emotion.valence += 0.4
        emotion.trust   += 0.3
        servos.go_to_expression("happy")

    life.on_lonely  = on_lonely
    life.on_crying  = on_crying
    life.on_content = on_content
    life.start()

    current_expression = "neutral"
    tick = 0

    print("\n💓 Heartbeat started. BMO is alive.\n")
    print(f"   {life.summary()}\n")

    try:
        while True:
            tick += 1

            # ── 1. Feel the world ──────────────
            sensors = read_robot_sensors()
            emotion.update_from_sensors(sensors)
            emotion.natural_decay()

            # ── 2. Apply loneliness ────────────
            # Blend loneliness into emotion state each tick
            delta = life.get_direct_emotion_delta()
            emotion.valence += delta["valence"] * 0.01  # gentle per-tick
            emotion.energy  += delta["energy"]  * 0.01
            emotion._clamp()

            # ── 3. Register touch as interaction
            if sensors.get("touch", False):
                life.register_interaction()
                emotion.valence += 0.2
                emotion.trust   += 0.1

            # ── 4. Choose expression ───────────
            new_expression = mapper.update(emotion)
            ear_pos        = ears.pick_ear_position(emotion)
            eye_symbols    = eyes.pick_eyes(emotion)

            # ── 5. Move the face ───────────────
            if new_expression and new_expression != current_expression:
                current_expression = new_expression
                servos.go_to_expression(current_expression)
                servos.set_position("ear_left",  ear_pos["left"])
                servos.set_position("ear_right", ear_pos["right"])

            # ── 6. Idle micro-movement ─────────
            if tick % 10 == 0:
                servos.idle_breathe()

            # ── 7. Print state ─────────────────
            if tick % 20 == 0:
                print(
                    f"[{tick:05d}] {emotion.summary()} | "
                    f"face={current_expression} | "
                    f"mood={life.mood_state()} | "
                    f"alone={life.hours_alone():.2f}h"
                )

            time.sleep(0.5)

    except KeyboardInterrupt:
        life.stop()
        print("\n\n💤 BMO is going to sleep...")
        servos.rest_all()
        print("Goodbye. 🌙\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
