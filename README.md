# DMX Light Show

Music-synchronized DMX light show system using QLC+ on macOS, controlled via a Jhoinrch USB-to-DMX adapter.

## What This Does

- Converts audio files to QLC+-compatible 16-bit WAV format
- Analyzes music for BPM, beat positions, and song structure
- Programmatically generates QLC+ show files with lighting cues synced to the music
- Provides templates and guides for manual show programming in QLC+

## Quick Start

### 1. Install prerequisites

Using Makefile (recommended):
```bash
make install

# OR

make reinstall
```

Then activate:
```bash
source .venv/bin/activate
```

More manual setup:
```bash
# QLC+ 4.14.3 (the DMX control software)
# IMPORTANT: Do NOT install via Homebrew — `brew install --cask qlc+` installs
# QLC+ 5.x which has a broken Virtual Console. Use 4.14.3 from qlcplus.org:
# https://www.qlcplus.org/downloads/4.14.3/
# Download the DMG for your architecture (x86_64 or arm64) and install to /Applications.

# Python 3.12 + virtual environment (3.13+ not yet supported by librosa/numba)
brew install python@3.12
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# FFmpeg (for audio conversion)
brew install ffmpeg
```

See [docs/SETUP.md](docs/SETUP.md) for full hardware and software setup instructions.

### 2. Prepare audio

```bash
# Convert to 16-bit WAV (best sync with QLC+)
python3 scripts/convert_audio.py mp3_audio_files/<my_song>.mp3 audio/<my_song>.wav
```

### 3. Analyze the music

```bash
python3 scripts/analyze_audio.py audio/song.wav
# Outputs: audio/song_analysis.json (BPM, beats, segments)
```

### 4. Generate a light show

```bash
python scripts/generate_show_xml.py \
    --analysis audio/<song>_analysis.json \
    --fixtures fixtures/example_generic_rgb.json \
    --audio-path audio/<song>.wav \
    --output shows/<song>_show.qxw \
    --style energetic
```

### 5. Open in QLC+

Open the generated `.qxw` file in QLC+. Switch to **Operate mode** (Ctrl+F12), then press the GO button on the Virtual Console to play the show. Refine the timeline manually in Show Manager (switch back to Design mode with Ctrl+F12).

```bash
open shows/<song>_show.qxw

# For example:
open shows/pitbull__time_of_our_lives_show.qxw
```

You will need to map the inputs/outputs every time you re-open a show in QLC+. Make sure you select the DMX USB plugin as the Output. Click on FT232R USB then click the Tools symbol. Make sure the Mode is "Open TX".

## Project Structure

```
dmx-light-show/
├── README.md                           # This file
├── first_light_show_spec.md            # Full technical specification
├── requirements.txt                    # Python dependencies
├── fixtures/                           # Fixture configurations
│   ├── README.md                       # Fixture setup guide
│   └── example_generic_rgb.json        # Example 3-PAR RGB config
├── audio/                              # Music files (excluded from git)
│   └── playlist.json                   # Playlist metadata template
├── shows/                              # QLC+ workspace files
│   ├── README.md                       # Show file guide
│   └── main-show.qxw                   # Empty workspace template
├── scripts/                            # Helper scripts
│   ├── convert_audio.py                # MP3/FLAC → 16-bit WAV
│   ├── analyze_audio.py                # BPM & beat detection
│   └── generate_show_xml.py            # Auto-generate QLC+ shows
└── docs/
    ├── SETUP.md                        # Hardware & software setup
    ├── PROGRAMMING_GUIDE.md            # How to program light cues
    └── TROUBLESHOOTING.md              # Common issues & fixes
```

## Hardware Required

- **Computer:** MacBook Pro (macOS)
- **USB-DMX adapter:** Jhoinrch USB-to-DMX (ASIN: B0D5YN6PMG), FT232RNL chip
- **DMX fixtures:** RGB PAR cans, moving heads, LED bars, or any DMX512 fixture
- **Cabling:** XLR cables (3-pin) for daisy-chaining fixtures
- **Terminator:** 120 ohm DMX terminator for the last fixture in the chain

## Documentation

- [Setup Guide](docs/SETUP.md) — Hardware wiring, software installation, adapter verification
- [Programming Guide](docs/PROGRAMMING_GUIDE.md) — Scenes, chasers, Show Manager, music sync
- [Troubleshooting](docs/TROUBLESHOOTING.md) — Audio drift, adapter issues, fixture debugging
- [Fixtures README](fixtures/README.md) — Fixture definitions and JSON config format
- [Shows README](shows/README.md) — Working with QLC+ workspace files

## Show Styles

The `generate_show_xml.py` script supports four styles that control how aggressively lights change:

| Style | Description |
|-------|-------------|
| `calm` | Slow color fades, changes every 4 beats |
| `moderate` | Balanced color cycling, changes every 2 beats |
| `energetic` | Fast color switching on every beat |
| `dramatic` | Medium pace with longer fades for contrast |
