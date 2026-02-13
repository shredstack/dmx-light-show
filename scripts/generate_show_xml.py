#!/usr/bin/env python3
"""Generate QLC+ show workspace files from beat analysis and fixture config.

Takes the JSON output from analyze_audio.py plus a fixture configuration
file and produces a valid .qxw (QLC+ workspace) XML file with:
- Fixture definitions patched to Universe 1
- Color scenes for each fixture
- Beat-synced chasers with BPM-derived timing
- A Show timeline with segments mapped to lighting looks
- A basic Virtual Console with a GO button and master slider

Usage:
    python generate_show_xml.py \\
        --analysis audio/song1_analysis.json \\
        --fixtures fixtures/example_generic_rgb.json \\
        --audio-path audio/song1.wav \\
        --output shows/song1_show.qxw \\
        --style energetic

Requires: Python 3.7+ (standard library only, no external dependencies)
"""

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET


# ---------------------------------------------------------------------------
# ID Allocator
# ---------------------------------------------------------------------------

class IDAllocator:
    """Manages unique integer IDs for QLC+ entities."""

    def __init__(self):
        self._next_fixture_id = 0
        self._next_function_id = 0

    def fixture_id(self) -> int:
        fid = self._next_fixture_id
        self._next_fixture_id += 1
        return fid

    def function_id(self) -> int:
        fid = self._next_function_id
        self._next_function_id += 1
        return fid


# ---------------------------------------------------------------------------
# Fixture Config Loader
# ---------------------------------------------------------------------------

def load_fixture_config(path: str) -> dict:
    """Load and validate the fixture configuration JSON."""
    with open(path) as f:
        config = json.load(f)

    if "fixtures" not in config or not config["fixtures"]:
        print("Error: Fixture config must contain a non-empty 'fixtures' list",
              file=sys.stderr)
        sys.exit(1)

    if "color_palette" not in config or not config["color_palette"]:
        print("Error: Fixture config must contain a non-empty 'color_palette'",
              file=sys.stderr)
        sys.exit(1)

    for fix in config["fixtures"]:
        for field in ("name", "manufacturer", "model", "mode",
                      "universe", "address", "channels", "channel_map"):
            if field not in fix:
                print(f"Error: Fixture '{fix.get('name', '?')}' missing "
                      f"field '{field}'", file=sys.stderr)
                sys.exit(1)

    return config


def load_analysis(path: str) -> dict:
    """Load the beat analysis JSON from analyze_audio.py."""
    with open(path) as f:
        analysis = json.load(f)

    for field in ("duration", "bpm", "beat_times", "segment_boundaries"):
        if field not in analysis:
            print(f"Error: Analysis JSON missing field '{field}'",
                  file=sys.stderr)
            sys.exit(1)

    return analysis


# ---------------------------------------------------------------------------
# Scene Generation
# ---------------------------------------------------------------------------

def make_fixture_val(channel_map: dict, color_rgb: list) -> str:
    """Build a FixtureVal string: 'ch,val,ch,val,...' for RGB channels.

    channel_map: {"red": 0, "green": 1, "blue": 2}
    color_rgb: [255, 0, 0]
    """
    pairs = []
    pairs.append(f"{channel_map['red']},{color_rgb[0]}")
    pairs.append(f"{channel_map['green']},{color_rgb[1]}")
    pairs.append(f"{channel_map['blue']},{color_rgb[2]}")
    return ",".join(pairs)


def generate_scenes(ids: IDAllocator, fixtures: list, fixture_ids: list,
                    palette: dict) -> list:
    """Generate Scene functions for each color applied to all fixtures.

    Returns a list of dicts: {id, name, color_name, element}
    """
    scenes = []
    for color_name, rgb in palette.items():
        func_id = ids.function_id()
        name = f"All {color_name.title()}"

        elem = ET.Element("Function", ID=str(func_id), Type="Scene",
                          Name=name)
        # Speed element (scenes have zero speed)
        speed = ET.SubElement(elem, "Speed",
                              FadeIn="0", FadeOut="0", Duration="0")

        for i, fix in enumerate(fixtures):
            fv = ET.SubElement(elem, "FixtureVal", ID=str(fixture_ids[i]))
            fv.text = make_fixture_val(fix["channel_map"], rgb)

        scenes.append({
            "id": func_id,
            "name": name,
            "color_name": color_name,
            "rgb": rgb,
            "element": elem,
        })

    return scenes


# ---------------------------------------------------------------------------
# Chaser Generation
# ---------------------------------------------------------------------------

def generate_chaser(ids: IDAllocator, name: str, scene_ids: list,
                    bpm: float, beats_per_step: int = 1,
                    fade_ms: int = 200) -> dict:
    """Generate a Chaser function that cycles through scenes on the beat.

    beats_per_step: how many beats each step holds (1 = every beat, 4 = every bar)
    """
    func_id = ids.function_id()
    step_duration_ms = int((60000 / bpm) * beats_per_step)

    elem = ET.Element("Function", ID=str(func_id), Type="Chaser", Name=name)
    ET.SubElement(elem, "Direction").text = "Forward"
    ET.SubElement(elem, "RunOrder").text = "Loop"
    ET.SubElement(elem, "SpeedModes", FadeIn="Common", FadeOut="Common",
                  Duration="Common")
    ET.SubElement(elem, "Speed", FadeIn=str(fade_ms), FadeOut=str(fade_ms),
                  Duration=str(step_duration_ms))

    for i, scene_id in enumerate(scene_ids):
        ET.SubElement(elem, "Step", Number=str(i),
                      FadeIn="0", Hold="0", FadeOut="0").text = str(scene_id)

    return {"id": func_id, "name": name, "element": elem}


# ---------------------------------------------------------------------------
# Energy Analysis
# ---------------------------------------------------------------------------

def compute_segment_energy(seg_start: float, seg_end: float,
                           onset_times: list) -> float:
    """Compute onset density (onsets per second) within a segment."""
    duration = seg_end - seg_start
    if duration <= 0:
        return 0.0
    count = sum(1 for t in onset_times if seg_start <= t < seg_end)
    return count / duration


# ---------------------------------------------------------------------------
# Show Timeline Generation
# ---------------------------------------------------------------------------

def generate_show_timeline(ids: IDAllocator, analysis: dict,
                           scenes: list, palette: dict,
                           bpm: float, style: str) -> dict:
    """Generate the Show function with tracks and timeline placements.

    Returns: {show_id, audio_id, elements: [show_elem, audio_elem],
              chasers: [chaser dicts]}
    """
    duration_ms = int(analysis["duration"] * 1000)
    seg_bounds = sorted(analysis.get("segment_boundaries", []))
    onset_times = analysis.get("onset_times", [])

    # Ensure we have at least start and end boundaries
    if not seg_bounds or seg_bounds[0] > 0.5:
        seg_bounds = [0.0] + seg_bounds
    if seg_bounds[-1] < analysis["duration"] - 1.0:
        seg_bounds.append(analysis["duration"])

    # Filter out colors we don't want in rotation (keep 'off' for blackout only)
    rotation_colors = [s for s in scenes if s["color_name"] != "off"]
    blackout_scene = next((s for s in scenes if s["color_name"] == "off"), None)

    # Style parameters
    style_params = {
        "calm":      {"beats_per_step": 4, "fade_ms": 500, "energy_threshold": 5.0},
        "moderate":  {"beats_per_step": 2, "fade_ms": 300, "energy_threshold": 3.0},
        "energetic": {"beats_per_step": 1, "fade_ms": 150, "energy_threshold": 2.0},
        "dramatic":  {"beats_per_step": 2, "fade_ms": 400, "energy_threshold": 2.5},
    }
    params = style_params.get(style, style_params["moderate"])

    # Generate chasers for different energy levels
    chasers = []

    # High-energy chaser: fast color cycling (every beat)
    high_colors = rotation_colors[:4] if len(rotation_colors) >= 4 else rotation_colors
    high_chaser = generate_chaser(
        ids, "Fast Color Cycle",
        [s["id"] for s in high_colors],
        bpm, beats_per_step=1, fade_ms=100
    )
    chasers.append(high_chaser)

    # Medium-energy chaser: moderate cycling (every 2 beats)
    med_colors = rotation_colors[1:5] if len(rotation_colors) >= 5 else rotation_colors
    med_chaser = generate_chaser(
        ids, "Medium Color Cycle",
        [s["id"] for s in med_colors],
        bpm, beats_per_step=2, fade_ms=params["fade_ms"]
    )
    chasers.append(med_chaser)

    # Low-energy chaser: slow cycling (every 4 beats / 1 bar)
    low_colors = rotation_colors[2:6] if len(rotation_colors) >= 6 else rotation_colors
    low_chaser = generate_chaser(
        ids, "Slow Color Fade",
        [s["id"] for s in low_colors],
        bpm, beats_per_step=4, fade_ms=500
    )
    chasers.append(low_chaser)

    # Audio function
    audio_id = ids.function_id()
    audio_source = analysis.get("filepath", "audio/song.wav")
    audio_elem = ET.Element("Function", ID=str(audio_id), Type="Audio",
                            Name=os.path.basename(audio_source))
    ET.SubElement(audio_elem, "Source").text = audio_source

    # Show function
    show_id = ids.function_id()
    show_elem = ET.Element("Function", ID=str(show_id), Type="Show",
                           Name="Generated Light Show")
    ET.SubElement(show_elem, "TimeDivision", Type="BPM_4_4",
                  BPM=str(int(bpm)))

    # Track 0: Audio
    audio_track = ET.SubElement(show_elem, "Track", ID="0", Name="Audio",
                                SceneID="4294967295", isMute="0")
    ET.SubElement(audio_track, "ShowFunction", ID=str(audio_id),
                  StartTime="0", Duration=str(duration_ms))

    # Track 1: Main Lights — place chasers at segment boundaries
    # Use the first scene as the track's bound scene
    bound_scene_id = scenes[0]["id"] if scenes else 0
    lights_track = ET.SubElement(show_elem, "Track", ID="1",
                                 Name="Main Lights",
                                 SceneID=str(bound_scene_id), isMute="0")

    # Place a blackout at the very start (500ms)
    if blackout_scene:
        ET.SubElement(lights_track, "ShowFunction",
                      ID=str(blackout_scene["id"]),
                      StartTime="0", Duration="500",
                      Color="#000000")

    # Map segments to chasers based on energy
    for i in range(len(seg_bounds) - 1):
        seg_start = seg_bounds[i]
        seg_end = seg_bounds[i + 1]
        seg_start_ms = int(seg_start * 1000)
        seg_duration_ms = int((seg_end - seg_start) * 1000)

        if seg_duration_ms < 500:
            continue  # Skip very short segments

        energy = compute_segment_energy(seg_start, seg_end, onset_times)

        # Select chaser based on energy level
        if energy > params["energy_threshold"]:
            chaser = high_chaser
            color_hex = "#ff4444"
        elif energy > params["energy_threshold"] * 0.6:
            chaser = med_chaser
            color_hex = "#44aaff"
        else:
            chaser = low_chaser
            color_hex = "#44ff44"

        # Offset past the initial blackout
        start = max(seg_start_ms, 500)
        duration = seg_duration_ms - max(0, 500 - seg_start_ms)
        if duration < 500:
            continue

        ET.SubElement(lights_track, "ShowFunction",
                      ID=str(chaser["id"]),
                      StartTime=str(start),
                      Duration=str(duration),
                      Color=color_hex)

    # End with blackout (2s fade out)
    if blackout_scene:
        end_start = max(0, duration_ms - 2000)
        ET.SubElement(lights_track, "ShowFunction",
                      ID=str(blackout_scene["id"]),
                      StartTime=str(end_start), Duration="2000",
                      Color="#000000")

    return {
        "show_id": show_id,
        "audio_id": audio_id,
        "elements": [audio_elem, show_elem],
        "chasers": chasers,
    }


# ---------------------------------------------------------------------------
# Workspace Builder
# ---------------------------------------------------------------------------

def build_workspace(fixture_config: dict, analysis: dict,
                    audio_path: str, style: str) -> ET.Element:
    """Assemble the complete QLC+ workspace XML."""
    ids = IDAllocator()

    fixtures = fixture_config["fixtures"]
    palette = fixture_config["color_palette"]

    # Root element (QLC+ 4.x format)
    workspace = ET.Element("Workspace",
                           CurrentWindow="VirtualConsole")

    # Creator info
    creator = ET.SubElement(workspace, "Creator")
    ET.SubElement(creator, "Name").text = "Q Light Controller Plus"
    ET.SubElement(creator, "Version").text = "4.14.3"
    ET.SubElement(creator, "Author").text = "dmx-light-show-generator"

    # Engine
    engine = ET.SubElement(workspace, "Engine")

    # Input/Output map
    io_map = ET.SubElement(engine, "InputOutputMap")
    ET.SubElement(io_map, "Universe", Name="Universe 1", ID="0")

    # Fixtures — convert 1-indexed DMX addresses to 0-indexed for XML
    fixture_ids = []
    for fix in fixtures:
        fid = ids.fixture_id()
        fixture_ids.append(fid)

        fix_elem = ET.SubElement(engine, "Fixture")
        ET.SubElement(fix_elem, "Manufacturer").text = fix["manufacturer"]
        ET.SubElement(fix_elem, "Model").text = fix["model"]
        ET.SubElement(fix_elem, "Mode").text = fix["mode"]
        ET.SubElement(fix_elem, "Universe").text = str(fix["universe"] - 1)
        ET.SubElement(fix_elem, "Address").text = str(fix["address"] - 1)
        ET.SubElement(fix_elem, "Channels").text = str(fix["channels"])
        ET.SubElement(fix_elem, "Name").text = fix["name"]
        ET.SubElement(fix_elem, "ID").text = str(fid)

    # Scenes
    scenes = generate_scenes(ids, fixtures, fixture_ids, palette)
    for scene in scenes:
        engine.append(scene["element"])

    # Override audio path in analysis if provided
    # QLC+ resolves paths relative to the .qxw file, so adjust accordingly
    if audio_path:
        analysis["filepath"] = audio_path

    # Show timeline (includes chasers, audio function, and show function)
    timeline = generate_show_timeline(ids, analysis, scenes, palette,
                                      analysis["bpm"], style)

    for chaser in timeline["chasers"]:
        engine.append(chaser["element"])

    for elem in timeline["elements"]:
        engine.append(elem)

    # Virtual Console (QLC+ 4.x format)
    vc = ET.SubElement(workspace, "VirtualConsole")

    def _vc_appearance(parent, frame_style="None", fg="Default",
                       bg="Default", font="Default"):
        """Add a QLC+ 4.x Appearance block."""
        app = ET.SubElement(parent, "Appearance")
        ET.SubElement(app, "FrameStyle").text = frame_style
        ET.SubElement(app, "ForegroundColor").text = fg
        ET.SubElement(app, "BackgroundColor").text = bg
        ET.SubElement(app, "BackgroundImage").text = "None"
        ET.SubElement(app, "Font").text = font

    # Root frame (wraps the entire VC)
    frame = ET.SubElement(vc, "Frame", Caption="")
    _vc_appearance(frame, frame_style="None")
    ET.SubElement(frame, "WindowState", Visible="False",
                  X="0", Y="0", Width="1920", Height="1080")
    ET.SubElement(frame, "AllowChildren").text = "True"
    ET.SubElement(frame, "AllowResize").text = "True"
    ET.SubElement(frame, "ShowHeader").text = "False"
    ET.SubElement(frame, "ShowEnableButton").text = "True"
    ET.SubElement(frame, "Collapsed").text = "False"
    ET.SubElement(frame, "Disabled").text = "False"

    # GO button
    go_btn = ET.SubElement(frame, "Button", Icon="", Caption="GO")
    ET.SubElement(go_btn, "Function", ID=str(timeline["show_id"]))
    ET.SubElement(go_btn, "Action").text = "Toggle"
    ET.SubElement(go_btn, "Intensity", Adjust="False").text = "100"
    ET.SubElement(go_btn, "WindowState", Visible="False",
                  X="10", Y="10", Width="150", Height="150")
    _vc_appearance(go_btn, fg="4294967295", bg="4278233600")

    # Master slider (Level mode controlling all fixture channels)
    slider = ET.SubElement(frame, "Slider", Caption="Master",
                           WidgetStyle="Slider",
                           InvertedAppearance="false")
    ET.SubElement(slider, "WindowState", Visible="False",
                  X="200", Y="10", Width="60", Height="200")
    _vc_appearance(slider)
    sm = ET.SubElement(slider, "SliderMode",
                       ValueDisplayStyle="Percentage",
                       Monitor="false")
    sm.text = "Level"
    level = ET.SubElement(slider, "Level", LowLimit="0", HighLimit="255",
                          Value="255")
    for i, fid in enumerate(fixture_ids):
        for ch in range(fixtures[i]["channels"]):
            ET.SubElement(level, "Channel",
                          Fixture=str(fid)).text = str(ch)

    # Blackout button
    blackout_scene = next((s for s in scenes if s["color_name"] == "off"),
                          None)
    if blackout_scene:
        bo_btn = ET.SubElement(frame, "Button", Icon="",
                               Caption="BLACKOUT")
        ET.SubElement(bo_btn, "Function", ID=str(blackout_scene["id"]))
        ET.SubElement(bo_btn, "Action").text = "Toggle"
        ET.SubElement(bo_btn, "Intensity", Adjust="False").text = "100"
        ET.SubElement(bo_btn, "WindowState", Visible="False",
                      X="10", Y="180", Width="150", Height="80")
        _vc_appearance(bo_btn, fg="4294967295", bg="4278190080")

    # Properties (required by QLC+ 4.x)
    props = ET.SubElement(vc, "Properties")
    ET.SubElement(props, "Size", Width="1920", Height="1080")
    gm = ET.SubElement(props, "GrandMaster", ChannelMode="Intensity",
                       ValueMode="Reduce", SliderMode="Normal")

    return workspace


# ---------------------------------------------------------------------------
# XML Output
# ---------------------------------------------------------------------------

def prettify_xml(element: ET.Element) -> str:
    """Return a pretty-printed XML string with the DOCTYPE declaration."""
    ET.indent(element, space=" ")
    xml_body = ET.tostring(element, encoding="unicode", xml_declaration=False,
                           short_empty_elements=True)
    return '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE Workspace>\n' + xml_body + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a QLC+ show workspace from beat analysis data."
    )
    parser.add_argument("--analysis", required=True,
                        help="Path to beat analysis JSON (from analyze_audio.py)")
    parser.add_argument("--fixtures", required=True,
                        help="Path to fixture configuration JSON")
    parser.add_argument("--output", required=True,
                        help="Output .qxw file path")
    parser.add_argument("--audio-path", default=None,
                        help="Audio file path to embed in the show "
                             "(overrides path in analysis JSON)")
    parser.add_argument("--style", default="moderate",
                        choices=["calm", "moderate", "energetic", "dramatic"],
                        help="Show style affecting color change speed and "
                             "energy thresholds (default: moderate)")

    args = parser.parse_args()

    # Load inputs
    print(f"Loading analysis: {args.analysis}")
    analysis = load_analysis(args.analysis)

    print(f"Loading fixtures: {args.fixtures}")
    fixture_config = load_fixture_config(args.fixtures)

    # Build workspace
    print(f"Generating show (style: {args.style})...")
    workspace = build_workspace(fixture_config, analysis,
                                args.audio_path, args.style)

    # Write output
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    xml_str = prettify_xml(workspace)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(xml_str)

    print(f"\nGenerated: {args.output}")
    print(f"  Fixtures: {len(fixture_config['fixtures'])}")
    print(f"  Colors: {len(fixture_config['color_palette'])}")
    print(f"  BPM: {analysis['bpm']:.1f}")
    print(f"  Duration: {analysis['duration']:.1f}s")
    print(f"  Segments: {len(analysis.get('segment_boundaries', []))}")
    print(f"\nOpen in QLC+ to preview and refine the show.")


if __name__ == "__main__":
    main()
