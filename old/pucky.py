"""
pucky.py
────────
The main brain. Connects everything together.

Run this on the Pi:
    python3 pucky.py

It will:
1. Wake up the emotion engine
2. Wake up the servo controller
3. Run the feeling loop forever
4. Move Pucky's face based on how she feels
"""

import time
import sys
from emotion_engine import (
    EmotionState,
    AvatarExpressionMapper,
    EarMapper,
    LCDEyeMapper,
    read_robot_sensors,
    analyze_ai_message,
)
from servo_controller import ServoController


def main():
    print("\n" + "═" * 40)
    print("  Pucky is waking up... 🌱")
    print("═" * 40 + "\n")

    # Initialize all systems
    emotion    = EmotionState()
    mapper     = AvatarExpressionMapper()
    ears       = EarMapper()
    eyes       = LCDEyeMapper()
    servos     = ServoController()

    current_expression = "neutral"
    tick = 0

    print("\n💓 Heartbeat started. Pucky is alive.\n")

    try:
        while True:
            tick += 1

            # ── 1. Feel the world ──────────────────
            sensors = read_robot_sensors()
            emotion.update_from_sensors(sensors)
            emotion.natural_decay()

            # ── 2. Choose expression ───────────────
            new_expression = mapper.update(emotion)
            ear_pos        = ears.pick_ear_position(emotion)
            eye_symbols    = eyes.pick_eyes(emotion)

            # ── 3. Move the face ───────────────────
            if new_expression and new_expression != current_expression:
                current_expression = new_expression
                servos.go_to_expression(current_expression)

                # Move ears to match
                servos.set_position("ear_left",  ear_pos["left"])
                servos.set_position("ear_right", ear_pos["right"])

            # ── 4. Idle micro-movement ─────────────
            # Every 5 seconds, do a tiny life-like movement
            if tick % 10 == 0:
                servos.idle_breathe()

            # ── 5. Print state ─────────────────────
            if tick % 20 == 0:
                print(
                    f"[{tick:05d}] {emotion.summary()} | "
                    f"face={current_expression} | "
                    f"ears={ear_pos['label']} | "
                    f"eyes={eye_symbols[0]}"
                )

            time.sleep(0.5)  # 2 ticks per second

    except KeyboardInterrupt:
        print("\n\n💤 Pucky is going to sleep...")
        servos.rest_all()
        print("Goodbye. 🌙\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
