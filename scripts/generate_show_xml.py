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

def make_fixture_val(channel_map: dict, color_rgb: list,
                     motor_speed: int = 0, laser_values: list = None,
                     strobe: int = 0, strobe_rgb: list = None,
                     uv: int = 0, white: int = 0) -> str:
    """Build a FixtureVal string: 'ch,val,ch,val,...' for a fixture's channels.

    Supports two channel_map formats:

    Legacy 3-channel RGB:
        {"red": 0, "green": 1, "blue": 2}

    Extended multi-channel (e.g. KeoBin L2800 18CH):
        Named channels mapped to 0-indexed offsets. Color, laser, motor,
        strobe, UV, and white values are all set explicitly.

    Parameters:
        color_rgb:    [R, G, B] for magic ball LEDs
        motor_speed:  0-255 for laser_motors channel
        laser_values: [green, red, blue, red] for the 4 laser channels, or None for all off
        strobe:       0-255 for strobe channel (0=off, 1-4=on, 5-29=random, 30-255=speed)
        strobe_rgb:   [R, G, B] for strobe LED color, or None to match color_rgb
        uv:           0-255 for led_violet_light
        white:        0-255 for magic_ball_white_1
    """
    if laser_values is None:
        laser_values = [0, 0, 0, 0]
    if strobe_rgb is None:
        strobe_rgb = color_rgb

    # Legacy 3-channel RGB format
    if set(channel_map.keys()) == {"red", "green", "blue"}:
        pairs = []
        pairs.append(f"{channel_map['red']},{color_rgb[0]}")
        pairs.append(f"{channel_map['green']},{color_rgb[1]}")
        pairs.append(f"{channel_map['blue']},{color_rgb[2]}")
        return ",".join(pairs)

    # Extended channel map — set each channel explicitly
    r, g, b = color_rgb[0], color_rgb[1], color_rgb[2]
    laser_idx = 0
    pairs = []
    for name, offset in sorted(channel_map.items(), key=lambda x: x[1]):
        if name == "special_channel":
            pairs.append(f"{offset},0")  # MUST stay 0-30 for DMX control
        elif "laser" in name and name != "laser_motors":
            val = laser_values[laser_idx] if laser_idx < len(laser_values) else 0
            laser_idx += 1
            pairs.append(f"{offset},{val}")
        elif name == "laser_motors":
            pairs.append(f"{offset},{motor_speed}")
        elif name == "magic_ball_white_1":
            pairs.append(f"{offset},{white}")
        elif name == "strobe" and "led" not in name:
            pairs.append(f"{offset},{strobe}")
        elif "strobe_led" in name:
            if "red" in name:
                pairs.append(f"{offset},{strobe_rgb[0]}")
            elif "green" in name:
                pairs.append(f"{offset},{strobe_rgb[1]}")
            elif "blue" in name:
                pairs.append(f"{offset},{strobe_rgb[2]}")
            else:
                pairs.append(f"{offset},0")
        elif name == "led_violet_light":
            pairs.append(f"{offset},{uv}")
        elif "red" in name:
            pairs.append(f"{offset},{r}")
        elif "green" in name:
            pairs.append(f"{offset},{g}")
        elif "blue" in name or "blu" in name:
            pairs.append(f"{offset},{b}")
        else:
            pairs.append(f"{offset},0")

    return ",".join(pairs)


def _build_scene(ids: IDAllocator, name: str, fixtures: list,
                  fixture_ids: list, **fixture_val_kwargs) -> dict:
    """Helper to build a single Scene element with the given fixture values."""
    func_id = ids.function_id()
    elem = ET.Element("Function", ID=str(func_id), Type="Scene", Name=name)
    ET.SubElement(elem, "Speed", FadeIn="0", FadeOut="0", Duration="0")

    for i, fix in enumerate(fixtures):
        fv = ET.SubElement(elem, "FixtureVal", ID=str(fixture_ids[i]))
        fv.text = make_fixture_val(fix["channel_map"], **fixture_val_kwargs)

    return {"id": func_id, "name": name, "element": elem}


def generate_scenes(ids: IDAllocator, fixtures: list, fixture_ids: list,
                    palette: dict) -> dict:
    """Generate Scene functions in multiple categories using all fixture features.

    Returns a dict with keys:
        "party"   — full party scenes (motor + lasers + UV + colors)
        "calm"    — calm scenes (slow motor + colors + low UV)
        "drop"    — drop/peak scenes (strobe + lasers + bright colors + white)
        "blackout" — single blackout scene
        "all"     — flat list of all scene dicts
    """
    party_scenes = []
    calm_scenes = []
    drop_scenes = []
    blackout_scene = None

    for color_name, rgb in palette.items():
        if color_name == "off":
            # Blackout: everything off
            blackout_scene = _build_scene(
                ids, "Blackout", fixtures, fixture_ids,
                color_rgb=[0, 0, 0])
            blackout_scene["color_name"] = "off"
            blackout_scene["rgb"] = [0, 0, 0]
            continue

        # --- Full party scene ---
        party = _build_scene(
            ids, f"Party {color_name.replace('_', ' ').title()}",
            fixtures, fixture_ids,
            color_rgb=rgb,
            motor_speed=180,
            laser_values=[220, 220, 220, 220],
            strobe=0,
            uv=128,
            white=0,
        )
        party["color_name"] = color_name
        party["rgb"] = rgb
        party_scenes.append(party)

        # --- Calm scene ---
        calm = _build_scene(
            ids, f"Calm {color_name.replace('_', ' ').title()}",
            fixtures, fixture_ids,
            color_rgb=rgb,
            motor_speed=80,
            laser_values=[0, 0, 0, 0],
            strobe=0,
            uv=60,
            white=0,
        )
        calm["color_name"] = color_name
        calm["rgb"] = rgb
        calm_scenes.append(calm)

        # --- Drop/peak scene ---
        drop = _build_scene(
            ids, f"Drop {color_name.replace('_', ' ').title()}",
            fixtures, fixture_ids,
            color_rgb=rgb,
            motor_speed=220,
            laser_values=[255, 255, 255, 255],
            strobe=150,
            strobe_rgb=rgb,
            uv=200,
            white=255,
        )
        drop["color_name"] = color_name
        drop["rgb"] = rgb
        drop_scenes.append(drop)

    all_scenes = party_scenes + calm_scenes + drop_scenes
    if blackout_scene:
        all_scenes.append(blackout_scene)

    return {
        "party": party_scenes,
        "calm": calm_scenes,
        "drop": drop_scenes,
        "blackout": blackout_scene,
        "all": all_scenes,
    }


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

def generate_strobe_scene(ids: IDAllocator, fixtures: list,
                          fixture_ids: list, color_rgb: list,
                          strobe_speed: int = 150) -> dict:
    """Generate a short strobe hit scene for beat drops."""
    return _build_scene(
        ids, "Strobe Hit", fixtures, fixture_ids,
        color_rgb=color_rgb,
        motor_speed=255,
        laser_values=[255, 255, 255, 255],
        strobe=strobe_speed,
        strobe_rgb=color_rgb,
        uv=255,
        white=255,
    )


def _find_segment(time: float, seg_bounds: list) -> int:
    """Return the segment index that contains the given time."""
    for i in range(len(seg_bounds) - 1):
        if seg_bounds[i] <= time < seg_bounds[i + 1]:
            return i
    return len(seg_bounds) - 2  # last segment


def generate_show_timeline(ids: IDAllocator, analysis: dict,
                           scene_groups: dict, palette: dict,
                           bpm: float, style: str,
                           fixtures: list, fixture_ids: list) -> dict:
    """Generate the Show function with beat-synced scene placements.

    Instead of free-running chasers, places individual scenes at actual
    beat timestamps from the audio analysis so lighting changes land
    precisely on the music's beats.

    Returns: {show_id, audio_id, elements: [show_elem, audio_elem],
              extra_scenes: [scene dicts]}
    """
    duration_ms = int(analysis["duration"] * 1000)
    seg_bounds = sorted(analysis.get("segment_boundaries", []))
    onset_times = analysis.get("onset_times", [])
    beat_times = sorted(analysis.get("beat_times", []))

    # Ensure we have at least start and end boundaries
    if not seg_bounds or seg_bounds[0] > 0.5:
        seg_bounds = [0.0] + seg_bounds
    if seg_bounds[-1] < analysis["duration"] - 1.0:
        seg_bounds.append(analysis["duration"])

    party_scenes = scene_groups["party"]
    calm_scenes = scene_groups["calm"]
    drop_scenes = scene_groups["drop"]
    blackout_scene = scene_groups["blackout"]

    # Style parameters — beats_per_step controls how many beats a scene
    # holds before cycling to the next color
    style_params = {
        "calm":      {"beats_per_step": 4, "energy_threshold": 5.0},
        "moderate":  {"beats_per_step": 2, "energy_threshold": 3.0},
        "energetic": {"beats_per_step": 1, "energy_threshold": 2.0},
        "dramatic":  {"beats_per_step": 2, "energy_threshold": 2.5},
    }
    params = style_params.get(style, style_params["moderate"])

    # Compute energy for each segment
    segment_energies = []
    for i in range(len(seg_bounds) - 1):
        energy = compute_segment_energy(seg_bounds[i], seg_bounds[i + 1],
                                        onset_times)
        segment_energies.append(energy)

    # Classify each segment's energy level and detect drops
    # "drop" = high energy AND significantly higher than previous segment
    seg_levels = []  # "drop", "high", "med", "low"
    for i, energy in enumerate(segment_energies):
        is_drop = (i > 0 and energy > params["energy_threshold"]
                   and energy > segment_energies[i - 1] * 1.5)
        if is_drop:
            seg_levels.append("drop")
        elif energy > params["energy_threshold"]:
            seg_levels.append("high")
        elif energy > params["energy_threshold"] * 0.6:
            seg_levels.append("med")
        else:
            seg_levels.append("low")

    # Map energy levels to scene lists and color-change rate
    level_config = {
        "drop": {"scenes": drop_scenes,  "beats_per_step": 1},
        "high": {"scenes": party_scenes, "beats_per_step": 1},
        "med":  {"scenes": party_scenes, "beats_per_step": params["beats_per_step"]},
        "low":  {"scenes": calm_scenes,  "beats_per_step": params["beats_per_step"] * 2},
    }

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

    # Track 1: Main Lights — place scenes at actual beat times
    bound_scene_id = party_scenes[0]["id"] if party_scenes else 0
    lights_track = ET.SubElement(show_elem, "Track", ID="1",
                                 Name="Main Lights",
                                 SceneID=str(bound_scene_id), isMute="0")

    # Place a blackout before the first beat
    first_beat_ms = int(beat_times[0] * 1000) if beat_times else 500
    if blackout_scene and first_beat_ms > 50:
        ET.SubElement(lights_track, "ShowFunction",
                      ID=str(blackout_scene["id"]),
                      StartTime="0", Duration=str(first_beat_ms),
                      Color="#000000")

    # Walk through every beat and place scenes synced to actual beat times.
    # Track which scene we're on per-level so color cycling is smooth.
    scene_counters = {"drop": 0, "high": 0, "med": 0, "low": 0}
    beat_counter = 0  # counts beats within current energy level
    prev_level = None

    for beat_idx in range(len(beat_times)):
        beat_time = beat_times[beat_idx]
        beat_ms = int(beat_time * 1000)

        # Duration until next beat (or end of song)
        if beat_idx + 1 < len(beat_times):
            next_beat_ms = int(beat_times[beat_idx + 1] * 1000)
        else:
            next_beat_ms = duration_ms
        beat_duration = next_beat_ms - beat_ms

        if beat_duration < 10:
            continue

        # Determine energy level for this beat
        seg_idx = _find_segment(beat_time, seg_bounds)
        level = seg_levels[seg_idx] if seg_idx < len(seg_levels) else "med"

        # Reset beat counter when energy level changes
        if level != prev_level:
            beat_counter = 0
            prev_level = level

        config = level_config[level]
        scenes = config["scenes"]
        bps = config["beats_per_step"]

        if not scenes:
            continue

        # Advance to next scene every N beats
        if beat_counter % bps == 0:
            scene_counters[level] = (scene_counters[level] + 1) % len(scenes)

        scene = scenes[scene_counters[level]]
        beat_counter += 1

        # Color hex for timeline visualization in QLC+
        r, g, b = scene["rgb"]
        color_hex = f"#{r:02x}{g:02x}{b:02x}"

        ET.SubElement(lights_track, "ShowFunction",
                      ID=str(scene["id"]),
                      StartTime=str(beat_ms),
                      Duration=str(beat_duration),
                      Color=color_hex)

    # End with blackout (2s fade out)
    if blackout_scene:
        end_start = max(0, duration_ms - 2000)
        ET.SubElement(lights_track, "ShowFunction",
                      ID=str(blackout_scene["id"]),
                      StartTime=str(end_start), Duration="2000",
                      Color="#000000")

    # Track 2: Strobe Hits — short strobe bursts at onset clusters
    strobe_scene = generate_strobe_scene(
        ids, fixtures, fixture_ids, [255, 255, 255], strobe_speed=150)
    extra_scenes = [strobe_scene]

    strobe_track = ET.SubElement(show_elem, "Track", ID="2",
                                  Name="Strobe Hits",
                                  SceneID=str(strobe_scene["id"]),
                                  isMute="0")

    # Find onset clusters (4+ onsets within 0.5s) in high-energy segments
    avg_beat_ms = int(60000 / bpm)
    strobe_dur_ms = avg_beat_ms
    last_strobe_end = 0

    for idx in range(len(onset_times) - 3):
        window_start = onset_times[idx]
        window_end = window_start + 0.5
        cluster_count = sum(1 for t in onset_times[idx:idx + 10]
                            if t < window_end)

        if cluster_count >= 4:
            seg_idx = _find_segment(window_start, seg_bounds)
            if seg_idx < len(segment_energies) and \
               segment_energies[seg_idx] > params["energy_threshold"] * 0.8:
                start_ms = int(window_start * 1000)
                if start_ms >= last_strobe_end + avg_beat_ms:
                    ET.SubElement(strobe_track, "ShowFunction",
                                  ID=str(strobe_scene["id"]),
                                  StartTime=str(start_ms),
                                  Duration=str(strobe_dur_ms),
                                  Color="#ffffff")
                    last_strobe_end = start_ms + strobe_dur_ms

    return {
        "show_id": show_id,
        "audio_id": audio_id,
        "elements": [audio_elem, show_elem],
        "extra_scenes": extra_scenes,
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

    # Scenes (categorized: party, calm, drop, blackout)
    scene_groups = generate_scenes(ids, fixtures, fixture_ids, palette)
    for scene in scene_groups["all"]:
        engine.append(scene["element"])

    # Override audio path in analysis if provided
    # QLC+ resolves paths relative to the .qxw file, so adjust accordingly
    if audio_path:
        analysis["filepath"] = audio_path

    # Show timeline (includes chasers, audio function, show function, strobe track)
    timeline = generate_show_timeline(ids, analysis, scene_groups, palette,
                                      analysis["bpm"], style,
                                      fixtures, fixture_ids)

    for scene in timeline.get("extra_scenes", []):
        engine.append(scene["element"])

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
    blackout_scene = scene_groups["blackout"]
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
