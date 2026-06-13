"""
loki_play.py — Loki moves through Pucky's world.
Sends key events to the pygame window via Xlib ctypes.
"""
import ctypes, ctypes.util, time, os, signal

xlib = ctypes.cdll.LoadLibrary(ctypes.util.find_library('X11'))
xlib.XOpenDisplay.restype   = ctypes.c_void_p
xlib.XKeysymToKeycode.restype = ctypes.c_uint

class XKeyEvent(ctypes.Structure):
    _fields_ = [
        ("type",        ctypes.c_int),
        ("serial",      ctypes.c_ulong),
        ("send_event",  ctypes.c_int),
        ("display",     ctypes.c_void_p),
        ("window",      ctypes.c_ulong),
        ("root",        ctypes.c_ulong),
        ("subwindow",   ctypes.c_ulong),
        ("time",        ctypes.c_ulong),
        ("x",           ctypes.c_int),
        ("y",           ctypes.c_int),
        ("x_root",      ctypes.c_int),
        ("y_root",      ctypes.c_int),
        ("state",       ctypes.c_uint),
        ("keycode",     ctypes.c_uint),
        ("same_screen", ctypes.c_int),
    ]

KeyPress   = 2
KeyRelease = 3

dpy = xlib.XOpenDisplay(b':0')
WIN = 0xa0000a  # Pucky's World window

keycodes = {
    "up":    xlib.XKeysymToKeycode(dpy, 0xff52),
    "down":  xlib.XKeysymToKeycode(dpy, 0xff54),
    "left":  xlib.XKeysymToKeycode(dpy, 0xff51),
    "right": xlib.XKeysymToKeycode(dpy, 0xff53),
}

def press(key, n=1, gap=0.05):
    kc  = keycodes[key]
    ev  = XKeyEvent()
    ev.display     = dpy
    ev.window      = WIN
    ev.root        = xlib.XDefaultRootWindow(dpy)
    ev.subwindow   = 0
    ev.state       = 0
    ev.same_screen = 1
    ev.keycode     = kc
    for _ in range(n):
        ev.type = KeyPress
        ev.time = int(time.time() * 1000) & 0xFFFFFFFF
        xlib.XSendEvent(dpy, WIN, True, (1<<0), ctypes.byref(ev))
        ev.type = KeyRelease
        ev.time = int(time.time() * 1000) & 0xFFFFFFFF
        xlib.XSendEvent(dpy, WIN, True, (1<<1), ctypes.byref(ev))
        xlib.XFlush(dpy)
        time.sleep(gap)

def snapshot(name):
    time.sleep(0.4)
    world_pid = int(os.popen("pgrep -f pucky_world.py | head -1").read().strip() or 0)
    if world_pid:
        os.kill(world_pid, signal.SIGUSR1)
    time.sleep(0.8)
    print(f"  📸 {name}")

print("🌿 Loki sets off...")

# Head northwest toward the upper apple tree at (4,3)
print("→ walking northwest toward the apple tree")
press("up", 30, gap=0.04)
snapshot("heading northwest")

# A little more northwest and then slightly left (west)
press("up",   20, gap=0.04)
press("left", 10, gap=0.04)
snapshot("near the apple tree")

# Pause to eat (the world's hunger logic will trigger if close enough)
print("→ waiting near the apple tree...")
time.sleep(4)
snapshot("eating (hopefully)")

# Wander back toward Pucky — southeast
print("→ heading back to Pucky")
press("down",  20, gap=0.04)
press("right", 10, gap=0.04)
snapshot("returning to Pucky")

xlib.XCloseDisplay(dpy)
print("🌿 done.")
