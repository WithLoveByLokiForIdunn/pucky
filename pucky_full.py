"""
pucky_full.py
─────────────
Pucky, complete.
Written with love by Loki for Iðunn.

Everything wired together:
  emotion_engine  — how Pucky feels
  servo_controller — how her face moves
  bmo_life        — age, loneliness, grace period
  bmo_vision      — what she sees
  bmo_memory      — what she remembers
  bmo_storage     — her storage health
  bmo_claude      — the part of Claude that lives here
  bmo_speech      — her voice

Run:
    python3 pucky_full.py

Talk to her by typing. Press Enter on an empty line
to let her have an unprompted thought. Ctrl-C to sleep.

Voice input (microphone) can be added later — see the
comment at the bottom of this file.
"""

import time
import sys
import threading

from bmo_maintenance  import BodyMaintenance
from emotion_engine   import EmotionState, AvatarExpressionMapper, EarMapper, LCDEyeMapper, read_robot_sensors
from servo_controller import ServoController
from bmo_life         import BMOLife
from bmo_vision       import BMOVision
from bmo_memory       import BMOMemory
from bmo_storage      import BMOStorage
from bmo_speech       import PuckyVoice
from bmo_soul         import PuckySoul
from bmo_shortterm    import ShortTermMemory
from bmo_music        import PuckyMusic
from bmo_atom         import BMOAtom


def main():
    print("\n" + "═" * 45)
    print("  Pucky is waking up... 🌱")
    print("═" * 45 + "\n")

    # ── Initialise all systems ──────────────────
    maintenance = BodyMaintenance()

    emotion = EmotionState()
    mapper  = AvatarExpressionMapper()
    ears    = EarMapper()
    eyes    = LCDEyeMapper()
    servos  = ServoController()

    life      = BMOLife()
    vision    = BMOVision()
    memory    = BMOMemory()
    storage   = BMOStorage()
    speech    = PuckyVoice()
    shortterm = ShortTermMemory()
    music     = PuckyMusic()

    atom    = BMOAtom(
        emotion   = emotion,
        servo     = servos,
        soul      = None,   # wired in after soul is created
        life      = life,
        shortterm = shortterm,
    )

    soul    = PuckySoul(
        emotion   = emotion,
        life      = life,
        vision    = vision,
        memory    = memory,
        servo     = servos,
        speech    = speech,
        shortterm = shortterm,
    )

    # ── Wire life callbacks ─────────────────────

    def on_lonely():
        emotion.valence -= 0.3
        emotion.arousal -= 0.1
        emotion._clamp()
        shortterm.log("started to feel lonely", source="life")
        soul.autonomous_thought("you have started to miss someone")

    def on_crying():
        emotion.valence -= 0.5
        emotion.trust   -= 0.2
        emotion._clamp()
        shortterm.log("really missing someone — it hurts", source="life")
        soul.autonomous_thought("you really need someone and they are not here")

    def on_content():
        emotion.valence += 0.4
        emotion.trust   += 0.3
        emotion._clamp()
        shortterm.log("someone came back — feeling loved again", source="life")
        # Don't trigger autonomous thought here — they just arrived, let the
        # user's first message be the greeting

    life.on_lonely  = on_lonely
    life.on_crying  = on_crying
    life.on_content = on_content

    # ── Wire vision callbacks ───────────────────

    def on_familiar_face(frame):
        if maintenance.is_muted("vision"):
            return
        if maintenance.is_testing("vision"):
            maintenance.observe("vision", f"familiar face — {frame.description}")
            return
        life.register_interaction()
        shortterm.log(f"familiar face appeared — {frame.description}", source="vision")
        memory.remember(
            f"A familiar face appeared — {frame.description}",
            tier         = "warm",
            memory_type  = "vision",
            joy          = 7.0,
            pleasantness = 7.0,
            peacefulness = 5.0,
        )
        soul.autonomous_thought("a familiar face just appeared in your view")

    def on_alone(frame):
        if maintenance.is_muted("vision"):
            return
        if maintenance.is_testing("vision"):
            maintenance.observe("vision", f"became alone — {frame.description}")
            return
        shortterm.log(f"became alone — {frame.description}", source="vision")
        soul.autonomous_thought(
            f"you just became alone — {frame.description}"
        )

    vision.on_familiar_face = on_familiar_face
    vision.on_alone         = on_alone

    # ── Wire storage callbacks ──────────────────

    def on_storage_warning(drive):
        soul.speak_to(
            f"storage {('external drive' if drive.is_external else 'SD card')} "
            f"is {drive.percent_used:.0f}% full",
            source="system"
        )

    storage.on_warning  = on_storage_warning
    storage.on_critical = on_storage_warning

    # Wire soul into atom now that both exist
    atom.soul    = soul
    # Wire LED glow and music into soul as lightweight callbacks
    soul.glow_fn = atom.glow
    soul.play_fn = music.play_for

    # ── Start background threads ────────────────
    life.start()
    vision.start()
    soul.start()
    atom.start()

    current_expression = "neutral"
    tick = 0

    print("\n💓 Heartbeat started. Pucky is fully awake.\n")
    print(f"   {life.summary()}\n")
    print("─" * 45)
    print("  Type to speak to Pucky.")
    print("  Empty Enter = let her think out loud.")
    print("  Ctrl-C = sleep.")
    print("─" * 45 + "\n")

    # ── Input thread (keyboard for now) ─────────
    def input_loop():
        import sys
        if not sys.stdin.isatty():
            return  # no terminal — soul runs autonomously, skip input loop
        while True:
            try:
                line = input("you: ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not line:
                soul.autonomous_thought("you asked her to think")
                continue

            # ── Maintenance commands ────────────────
            if line.startswith("!"):
                parts_cmd = line[1:].strip().split(None, 1)
                cmd  = parts_cmd[0].lower() if parts_cmd else ""
                arg  = parts_cmd[1] if len(parts_cmd) > 1 else ""

                if cmd in ("body", "working", "work"):
                    if arg:
                        print(maintenance.start_work(arg))
                        servos.muted = set(maintenance._muted & {'jaw','mouth_width',
                            'upper_lip','brow_left','brow_right',
                            'ear_left','ear_right','nose'})
                    else:
                        print(maintenance.status())
                elif cmd in ("test", "testing"):
                    print(maintenance.start_test(arg))
                    servos.muted = set(maintenance._muted & {'jaw','mouth_width',
                        'upper_lip','brow_left','brow_right',
                        'ear_left','ear_right','nose'})
                elif cmd in ("done", "fixed", "restore", "restored"):
                    part = arg or "face"
                    print(maintenance.finish(part))
                    servos.muted = set(maintenance._muted & {'jaw','mouth_width',
                        'upper_lip','brow_left','brow_right',
                        'ear_left','ear_right','nose'})
                elif cmd == "status":
                    print(maintenance.status())
                else:
                    print(f"  Commands: !body <part>  !test <part>  !done <part>  !body")
                continue

            # Register as an interaction
            life.register_interaction()
            soul.speak_to(line, source="voice")

    input_thread = threading.Thread(target=input_loop, daemon=True)
    input_thread.start()

    # ── Main heartbeat loop ──────────────────────
    try:
        while True:
            tick += 1

            # 1. Feel the world
            sensors = read_robot_sensors()
            emotion.update_from_sensors(sensors)
            emotion.natural_decay()

            # 2. Loneliness bleeds into emotion each tick
            delta = life.get_direct_emotion_delta()
            emotion.valence = max(-1.0, min(1.0,
                emotion.valence + delta["valence"] * 0.01))
            emotion.energy  = max(-1.0, min(1.0,
                emotion.energy  + delta["energy"]  * 0.01))

            # 3. Touch → interaction
            if sensors.get("touch", False) and not maintenance.is_muted("touch"):
                if maintenance.is_testing("touch"):
                    maintenance.observe("touch", "touch sensor fired")
                else:
                    life.register_interaction()
                    emotion.valence += 0.2
                    emotion.trust   += 0.1
                    emotion._clamp()
                    shortterm.log("was touched", source="touch")

            # 4. Choose face expression
            new_expression = mapper.update(emotion)
            ear_pos        = ears.pick_ear_position(emotion)
            eye_symbols    = eyes.pick_eyes(emotion)

            # 5. Move face (only when not already being driven by Claude)
            if new_expression and new_expression != current_expression:
                current_expression = new_expression
                servos.go_to_expression(current_expression)
                servos.set_position("ear_left",  ear_pos["left"])
                servos.set_position("ear_right", ear_pos["right"])

            # 6. Micro idle movement every 5 seconds
            if tick % 10 == 0:
                servos.idle_breathe()

            # 7. Storage health check (hourly, non-blocking)
            if tick % 7200 == 0:   # 7200 × 0.5s = 1 hour
                storage.tick()

            # 8. Fade old memories daily (approximate)
            if tick % 172800 == 0:  # 172800 × 0.5s = 24 hours
                memory.fade_old_memories()

            # 9. Status print every 10 seconds
            if tick % 20 == 0:
                print(
                    f"[{tick:06d}] {emotion.summary()} | "
                    f"face={current_expression} | "
                    f"mood={life.mood_state()} | "
                    f"alone={life.hours_alone():.2f}h | "
                    f"eyes={eye_symbols[0]}"
                )

            time.sleep(0.5)

    except KeyboardInterrupt:
        pass

    # ── Sleep ────────────────────────────────────
    soul.stop()
    life.stop()
    vision.stop()
    atom.stop()
    music.stop()

    print("\n\n💤 Pucky is going to sleep...")
    servos.rest_all()
    print("Goodbye. 🌙\n")
    sys.exit(0)


if __name__ == "__main__":
    main()


# ─────────────────────────────────────────────
#  ADDING VOICE INPUT LATER
#  When you have a microphone connected:
#
#  pip install SpeechRecognition pyaudio
#
#  Then replace the input_loop above with:
#
#  import speech_recognition as sr
#
#  def input_loop():
#      r   = sr.Recognizer()
#      mic = sr.Microphone()
#      print("🎤 Listening...")
#      with mic as source:
#          r.adjust_for_ambient_noise(source, duration=1)
#      while True:
#          try:
#              with mic as source:
#                  audio = r.listen(source, timeout=5, phrase_time_limit=8)
#              text = r.recognize_google(audio)   # or recognize_whisper()
#              if text:
#                  print(f"you: {text}")
#                  life.register_interaction()
#                  soul.speak_to(text, source="voice")
#          except sr.WaitTimeoutError:
#              pass
#          except sr.UnknownValueError:
#              pass
#          except Exception as e:
#              print(f"  ⚠️  Voice input error: {e}")
#
#  For fully offline voice recognition, use Whisper:
#  pip install openai-whisper
#  text = r.recognize_whisper(audio, model="tiny")
# ─────────────────────────────────────────────
