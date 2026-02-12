# Troubleshooting

Common issues and their fixes.

## Audio Sync Drift

**Symptom:** Light cues gradually fall out of sync with the music during playback.

**Fixes:**
- Use **16-bit WAV** files (not 32-bit, not MP3). Convert with: `python scripts/convert_audio.py input.mp3 output.wav`
- Try the **start → stop → start** trick: quickly start playback, stop it, then start again. This resyncs QLC+'s audio engine.
- Close unnecessary applications to reduce CPU load
- macOS generally has better audio sync than Windows in QLC+

## Adapter Not Detected

**Symptom:** The Jhoinrch adapter is plugged in but doesn't appear in QLC+ Inputs/Outputs.

**Fixes:**
- **Check for VCP driver conflicts.** FTDI VCP (Virtual COM Port) drivers interfere with QLC+ on macOS. If installed, remove them. See the [QLC+ FAQ](https://www.qlcplus.org/forum/viewtopic.php?t=12277) question #3.
- Unplug the adapter, wait 5 seconds, replug, then restart QLC+
- Try a different USB port or connect directly (bypass the hub)
- In QLC+ Input/Output settings, click the wrench icon and force the device type to **"Open TX"**

## No DMX Output (Adapter Shows in QLC+)

**Symptom:** The adapter appears in QLC+ but fixtures don't respond.

**Fixes:**
- Verify the **Output checkbox** is checked for Universe 1 in Inputs/Outputs
- Confirm the fixture's physical DMX address matches what's patched in QLC+
- Test with **Simple Desk** — move sliders for your fixture's channel range
- Check XLR cable connections (DMX uses pins 2 and 3 for data)
- Ensure the last fixture has a **120 ohm DMX terminator**

## USB Hub Latency

**Symptom:** Intermittent DMX flicker or slow response.

**Fixes:**
- Connect the adapter directly to the MacBook via a simple USB-A to USB-C adapter (not a powered hub)
- If a hub is required, use a powered USB 3.0 hub

## Python Script Errors

### `Failed building wheel for llvmlite` during pip install
Librosa depends on numba/llvmlite, which don't support Python 3.13+ yet. Use Python 3.12:
```bash
brew install python@3.12
rm -rf .venv
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### `ModuleNotFoundError: No module named 'librosa'`
```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### `FileNotFoundError: ffmpeg not found`
```bash
brew install ffmpeg
```

### `librosa.beat.beat_track` returns unexpected type
Ensure you're using librosa >= 0.10.0. The return type changed in earlier versions. The script handles both scalar and array return values.

### Permission errors on macOS
If you get permission errors running scripts:
```bash
chmod +x scripts/*.py
```

## Fixtures Not Responding

**Symptom:** QLC+ shows output but lights don't change.

**Fixes:**
- **Address mismatch:** Double-check the fixture's physical address (DIP switches or display) matches the QLC+ patch. Remember: the fixture config JSON uses 1-indexed addresses (DMX convention), and QLC+ displays 1-indexed, but the XML internally is 0-indexed.
- **Channel count:** Ensure the fixture definition's channel count matches the fixture's actual mode. Many fixtures have multiple modes (3ch, 6ch, 8ch).
- **XLR wiring:** DMX uses 3-pin or 5-pin XLR. If using adapters between 3-pin and 5-pin, verify pin mapping.
- **Terminator:** A missing terminator on the last fixture can cause erratic behavior, especially with longer cable runs or more than 3-4 fixtures.

## QLC+ Crashes or Won't Open a File

- Keep backups of your `.qxw` files (QLC+ may reorder XML elements on save)
- If a generated file won't open, validate the XML: `python -c "import xml.etree.ElementTree as ET; ET.parse('shows/your_show.qxw')"`
- Try opening in a text editor to check for malformed XML
