# Fixtures

This directory contains fixture configurations for the light show system.

## Finding Fixture Definitions for QLC+

QLC+ includes **800+ built-in fixture definitions**. Check if your fixture is already included:
1. Open QLC+ → Fixtures tab → click **+**
2. Browse by manufacturer and model

If your fixture isn't built in, check the **Open Fixture Library**:
https://open-fixture-library.org/

## Creating Custom Fixture Definitions

For unlisted fixtures, use the **QLC+ Fixture Editor** (a separate app bundled with QLC+):
1. Open Fixture Editor
2. Define the manufacturer, model, and mode
3. Add channels in order (e.g., Red, Green, Blue, Dimmer, Strobe)
4. Set channel capabilities (color, intensity, etc.)
5. Save as a `.qxf` file

## Fixture Configuration JSON (for the generate script)

The `generate_show_xml.py` script uses a simplified JSON format (not `.qxf`). See `example_generic_rgb.json` for the format:

```json
{
  "fixtures": [
    {
      "name": "PAR Left",
      "manufacturer": "Generic",
      "model": "Generic RGB",
      "mode": "3 Channel",
      "universe": 1,
      "address": 1,
      "channels": 3,
      "channel_map": {"red": 0, "green": 1, "blue": 2}
    }
  ],
  "color_palette": {
    "red": [255, 0, 0],
    "blue": [0, 0, 255]
  }
}
```

Fields:
- **universe** — DMX universe number (1-indexed, matching DMX convention)
- **address** — Starting DMX address (1-indexed)
- **channels** — Total channel count for this fixture
- **channel_map** — Maps color names to channel offsets (0-indexed within the fixture)
- **color_palette** — Named RGB colors used for scene generation

To use your own fixtures, copy `example_generic_rgb.json` and edit the values to match your hardware.
