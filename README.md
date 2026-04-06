# OBS Floating Control Bar

A lightweight always-on-top floating control widget for OBS Studio that lets you start, stop, pause and resume recordings without alt-tabbing out of your game or full-screen application. The widget is completely invisible to OBS and any screen capture source.

---

## The Problem

OBS Studio is powerful but it does not have a built-in floating control bar. If you record gameplay or tutorials on a single monitor, your only options are:

- Use the OBS window directly, which means it shows up in your recording
- Set up hotkeys and memorise them
- Alt-tab out of your game every time you want to stop recording

Other screen recorders like Icecream and Aiseesoft have had floating overlay controls for years. OBS users have been asking for this since at least 2023 with no native solution shipped.

This project fills that gap.

---

## The Solution

A slim pill-shaped widget built in Python that floats above all windows, is invisible to OBS via the Win32 `SetWindowDisplayAffinity` flag, and controls OBS directly through its built-in WebSocket API.

**Key features:**

- Start, stop, pause and resume recording with one click
- Live timer showing elapsed recording time (turns red when recording, orange when paused)
- Connection status indicator (green = connected to OBS, red = disconnected)
- Completely invisible to OBS Display Capture, Window Capture and all other capture sources
- Draggable anywhere on screen
- Configurable WebSocket host, port and password via the settings panel
- No hotkey configuration needed in OBS
- No admin rights required
- Compiled to a single `.exe` with no runtime dependencies

---

## How It Works

### Invisible to OBS

The widget calls `SetWindowDisplayAffinity(hwnd, 0x00000011)` immediately after the window is created. This is the same Win32 flag used by Discord overlays and screen annotation tools. It tells the Windows Desktop Window Manager to exclude the window from any capture or screenshot, including OBS.

### Controlling OBS

OBS Studio ships with a WebSocket server (v5) built in since version 28. The widget connects to it over a standard TCP socket, performs the WebSocket handshake manually, authenticates if a password is set, and sends JSON-formatted requests directly to OBS.

The four requests used are:

| Action | OBS WebSocket Request |
|---|---|
| Start recording | `StartRecord` |
| Stop recording | `StopRecord` |
| Pause recording | `PauseRecord` |
| Resume recording | `ResumeRecord` |

No third-party libraries are used for the WebSocket connection. The entire client is implemented in pure Python stdlib using `socket`, `hashlib`, `base64`, `struct` and `json`.

### Why Not Hotkeys

The original implementation used the `keyboard` Python library to fire global hotkeys at OBS. Keystroke logging confirmed the library was not emitting any keys at all when targeting complex 4-key modifier combinations like `Ctrl+Shift+Alt+F9`.

The second attempt used `SendInput` via `ctypes`, the correct Win32 API for injecting synthetic keystrokes globally. This also failed silently. The reason is Windows UIPI (User Interface Privilege Isolation). OBS typically runs at a higher integrity level than a normal Python process. Windows silently discards any `SendInput` call from a lower-privilege process targeting a higher-privilege window. There is no error code and no log entry. The keystrokes simply disappear.

Attempting to self-elevate the Python process via `ShellExecuteW` with the `runas` verb caused a separate issue where the elevated tkinter window lost proper input and rendering behaviour on certain Windows configurations.

The WebSocket approach bypasses all of this entirely. It is a network connection, not a simulated input event, so privilege levels are irrelevant.

---

## Setup

### 1. Enable the OBS WebSocket Server

Open OBS Studio and go to:

**Tools > WebSocket Server Settings**

- Check **Enable WebSocket server**
- Port: `4455` (default, change if needed)
- Optionally set a password
- Click OK

### 2. Run the Controller

**Option A: Run from source**

```
python obs_controller.py
```

Python 3.8 or higher required. No pip installs needed.

**Option B: Build a standalone exe**

Double-click `build.bat`. It will install PyInstaller if needed and produce `dist/OBS Controller.exe`.

---

## Usage

When the widget launches, the small dot on the left edge shows connection status:

- Red dot: not connected to OBS (check that WebSocket server is enabled)
- Green dot: connected and ready

Click **START** to begin recording. The timer starts counting and the dot turns red.

Click **PAUSE** to pause. The dot turns orange and the timer freezes.

Click **RESUME** to continue. Timer resumes.

Click **STOP** to end the recording. Everything resets.

Click **⚙** to open settings and change the WebSocket host, port or password. Click **SAVE and RECONNECT** to apply.

Click **✕** to close the widget.

The widget is draggable by clicking and holding anywhere on the pill and moving it to any position on screen.

---

## Why the Demo Photos Look Like That

The widget is invisible to screen capture by design. Attempting to record a demo video resulted in a screen recording with no widget visible at all. The demo photos were taken with a phone camera pointed at the monitor. The video demo was captured using a different method to show the widget controlling OBS in real time.

---

## Technical Details

| Item | Detail |
|---|---|
| Language | Python 3.8+ |
| UI framework | tkinter |
| OBS API | WebSocket v5 (OBS 28+) |
| WebSocket client | Pure stdlib, no external deps |
| Capture exclusion | Win32 SetWindowDisplayAffinity |
| Build tool | PyInstaller (onefile, noconsole) |
| External pip deps | None at runtime |

---

## Requirements

- Windows 10 or Windows 11
- OBS Studio 28 or newer (for WebSocket v5 support)
- Python 3.8 or newer (only needed if running from source)

---

## File Structure

```
obs widget/
  obs_controller.py   main application
  build.bat           builds standalone exe via PyInstaller
  dist/
    OBS Controller.exe  compiled standalone executable
```

---

## Related

- OBS Studio: https://obsproject.com
- OBS WebSocket v5 protocol reference: https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md
- Original OBS forum thread requesting floating controls: https://obsproject.com/forum/threads/floating-control-bar-for-obs-studio-while-recording.170955/
