# Setup Guide

Step-by-step instructions for setting up the DMX light show system on macOS.

## 1. Install QLC+

Download QLC+ from https://www.qlcplus.org/download — select the macOS build (Apple Silicon or Intel). Double-click the DMG and drag QLC+ to your Applications folder.

Alternatively, via Homebrew:
```bash
brew install --cask qlc+
```

**Note:** QLC+ v5 requires Apple Silicon. If you have an older Intel Mac, download v4 from the website instead.

## 2. macOS Driver Notes (Important)

QLC+ on macOS uses the **native USB interface (libFTDI)** — no additional drivers are needed.

**DO NOT install FTDI VCP (Virtual COM Port) drivers.** They will interfere with QLC+ and prevent DMX output. If VCP drivers are already installed, remove them. D2XX drivers are fine.

## 3. Verify USB-DMX Adapter

1. Plug the Jhoinrch USB-to-DMX adapter into your USB hub (or directly into a USB-C adapter)
2. Open QLC+ and go to the **Inputs/Outputs** tab
3. Look for the **DMX USB** plugin with a device named `FT232RNL USB UART` or similar
4. Check the **Output** checkbox for Universe 1
5. Click the device row — Protocol should show "Open DMX USB"
6. If not detected: click the configure button (wrench icon) and force the device type to **"Open TX"**

## 4. Physical Wiring

```
MacBook Pro → USB Hub → Jhoinrch USB-to-DMX → XLR daisy-chain to fixtures → DMX terminator (120 ohm)
```

- Connect fixtures in a **daisy chain** using XLR cables (3-pin)
- Each fixture passes DMX through to the next via its DMX OUT port
- Place a **120 ohm DMX terminator** on the last fixture's DMX OUT port
- The terminator prevents signal reflections and is especially important with budget adapters

## 5. Install Python Dependencies

The helper scripts require **Python 3.12** and a few libraries. Python 3.13+ is not yet supported by librosa's dependency chain (numba/llvmlite).

```bash
# Install Python 3.12 if you don't have it
brew install python@3.12

# Create a virtual environment with Python 3.12
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Activate the environment with `source .venv/bin/activate` each time you open a new terminal.

This installs:
- **librosa** — audio analysis (BPM, beat detection, segmentation)
- **numpy** — numerical computing (required by librosa)
- **soundfile** — audio file I/O

## 6. Install FFmpeg

FFmpeg is used by `convert_audio.py` to convert audio files to 16-bit WAV:

```bash
brew install ffmpeg
```

## 7. Test Your First DMX Output

1. Open QLC+ and verify your adapter appears in Inputs/Outputs (step 3)
2. Connect at least one DMX fixture and set its DMX address (usually via the fixture's built-in display or DIP switches)
3. In QLC+, go to the **Simple Desk** tab
4. Find the channel sliders corresponding to your fixture's address
5. Move the sliders — you should see the light respond
6. If using an RGB fixture: the first three channels are typically Red, Green, Blue

If Simple Desk works, your hardware chain is good and you're ready to start programming shows.

## Quick Reference: DMX Addressing

- DMX uses 512 channels per universe
- Each fixture occupies a contiguous block of channels starting at its **address**
- Example: A 3-channel RGB PAR at address 1 uses channels 1, 2, 3
- The next fixture should start at address 4 (or higher)
- Set fixture addresses on the fixtures themselves, then match in QLC+
