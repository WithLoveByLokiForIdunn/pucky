"""
bmo_power.py
────────────
Battery and power monitor for Pucky.

Monitors the Pi throttle register (always) and the Robot Hat battery ADC
(when available). Calls back when something needs attention.

Throttle bits (vcgencmd get_throttled):
  0x00001  under-voltage right now
  0x00004  CPU being throttled right now
  0x10000  under-voltage has occurred since boot
  0x40000  throttling has occurred since boot
"""

import subprocess
import threading
import logging

logger = logging.getLogger(__name__)

# Throttle register masks
_UV_NOW       = 0x00001   # under-voltage active
_THROTTLE_NOW = 0x00004   # CPU throttled active

# 2S 18650 LiPo thresholds (volts)
BATT_LOW      = 6.8   # warn Iðunn
BATT_CRITICAL = 6.2   # urgent — save state, go still


def _get_throttled() -> int:
    try:
        raw = subprocess.check_output(
            ["vcgencmd", "get_throttled"], timeout=2
        ).decode().strip()
        return int(raw.split("=")[1], 16)
    except Exception:
        return 0


class BMOPower:
    """
    Background power monitor. Checks every `interval` seconds.

    Optional callbacks:
        on_low_battery(voltage)       battery below BATT_LOW
        on_critical_battery(voltage)  battery below BATT_CRITICAL
        on_throttled()                Pi CPU is actively throttled
    """

    def __init__(self, interval: int = 60):
        self.interval = interval

        self.on_low_battery      = None
        self.on_critical_battery = None
        self.on_throttled        = None

        self._battery    = None
        self._stop_event = threading.Event()
        self._thread     = None

        self._batt_state     = "ok"    # "ok" | "low" | "critical"
        self._throttle_fired = False

        self._init_battery()

    # ── Battery ADC setup ─────────────────────────────────────────

    def _init_battery(self):
        # Pi 5 GPIO I2C lives on bus 4, not bus 1
        for bus in (4, 1, 10, 6):
            try:
                from robot_hat import SunfounderBattery, SunfounderBatteryConfig
                b = SunfounderBattery(SunfounderBatteryConfig(), bus=bus)
                v = b.voltage
                if v is not None and v > 0:
                    self._battery = b
                    logger.info("BMOPower: battery ADC on I2C bus %d (%.2fV)", bus, v)
                    return
            except Exception:
                continue
        logger.warning("BMOPower: Robot Hat ADC not found — monitoring vcgencmd only.")

    def _read_voltage(self) -> float | None:
        if self._battery is None:
            return None
        try:
            return self._battery.voltage
        except Exception:
            return None

    # ── One poll cycle ────────────────────────────────────────────

    def poll(self):
        # Throttle
        flags = _get_throttled()
        throttled_now = bool(flags & (_UV_NOW | _THROTTLE_NOW))
        if throttled_now and not self._throttle_fired:
            self._throttle_fired = True
            if self.on_throttled:
                try:
                    self.on_throttled()
                except Exception:
                    pass
        elif not throttled_now:
            self._throttle_fired = False

        # Battery voltage
        v = self._read_voltage()
        if v is None:
            return

        if v < BATT_CRITICAL:
            if self._batt_state != "critical":
                self._batt_state = "critical"
                if self.on_critical_battery:
                    try:
                        self.on_critical_battery(v)
                    except Exception:
                        pass
        elif v < BATT_LOW:
            if self._batt_state not in ("low", "critical"):
                self._batt_state = "low"
                if self.on_low_battery:
                    try:
                        self.on_low_battery(v)
                    except Exception:
                        pass
        else:
            self._batt_state = "ok"

    # ── Background thread ─────────────────────────────────────────

    def _run(self):
        while not self._stop_event.wait(self.interval):
            try:
                self.poll()
            except Exception as e:
                logger.warning("BMOPower: poll error: %s", e)

    def start(self):
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="bmo-power"
        )
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    # ── Status ────────────────────────────────────────────────────

    @property
    def summary(self) -> str:
        v = self._read_voltage()
        flags = _get_throttled()
        batt  = f"{v:.2f}V [{self._batt_state}]" if v is not None else "no ADC"
        power = "THROTTLED" if flags & _THROTTLE_NOW else (
                "under-voltage" if flags & _UV_NOW else "ok")
        return f"battery={batt}  throttle={power}"
