#!/usr/bin/env python3
"""Generate QLC+ show workspace files from beat analysis and fixture config.

Takes the JSON output from analyze_audio.py plus a fixture configuration
file and produces a valid .qxw (QLC+ workspace) XML file with:
- Fixture definitions patched to Universe 1
- Dynamically generated scenes with varied laser, motor, UV, and color combos
- Per-beat energy-driven lighting that responds to the music's dynamics
- Build-up ramps and blackout accents before drops
- Section-aware color palettes (not the same 10 colors every time)
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


# ---------------------------------------------------------------------------
# Scene Cache — creates unique scenes on demand, deduplicates identical combos
# ---------------------------------------------------------------------------

class SceneCache:
    """Creates and caches Scene functions by parameter tuple.

    Instead of pre-generating a fixed grid of scenes, this creates scenes
    on-the-fly as the timeline needs them and reuses identical combos.
    """

    def __init__(self, ids: IDAllocator, fixtures: list, fixture_ids: list):
        self.ids = ids
        self.fixtures = fixtures
        self.fixture_ids = fixture_ids
        self._cache = {}  # param tuple -> scene dict
        self.all_scenes = []

    def get_or_create(self, color_name: str, color_rgb: list,
                      motor_speed: int, laser_values: list,
                      strobe: int, uv: int, white: int) -> dict:
        key = (tuple(color_rgb), motor_speed, tuple(laser_values),
               strobe, uv, white)

        if key in self._cache:
            return self._cache[key]

        # Build a descriptive name
        laser_tag = "".join("1" if v > 0 else "0" for v in laser_values)
        name = f"{color_name} M{motor_speed} L{laser_tag} UV{uv}"
        if strobe:
            name += f" S{strobe}"
        if white:
            name += f" W{white}"

        scene = _build_scene(
            self.ids, name, self.fixtures, self.fixture_ids,
            color_rgb=color_rgb, motor_speed=motor_speed,
            laser_values=laser_values, strobe=strobe,
            strobe_rgb=color_rgb, uv=uv, white=white,
        )
        scene["rgb"] = list(color_rgb)
        scene["color_name"] = color_name

        self._cache[key] = scene
        self.all_scenes.append(scene)
        return scene


# ---------------------------------------------------------------------------
# Per-Beat Energy
# ---------------------------------------------------------------------------

def get_beat_energies(analysis: dict) -> list:
    """Get energy value (0.0-1.0) for each beat.

    Uses beat_energy from enhanced analysis if available,
    otherwise falls back to onset density around each beat.
    """
    beat_times = analysis.get("beat_times", [])

    if "beat_energy" in analysis and len(analysis["beat_energy"]) == len(beat_times):
        return list(analysis["beat_energy"])

    # Fallback: onset density in a one-beat window around each beat
    onset_times = analysis.get("onset_times", [])
    bpm = analysis["bpm"]
    window = 60.0 / bpm

    energies = []
    for bt in beat_times:
        count = sum(1 for t in onset_times if bt - window <= t < bt + window)
        energies.append(count)

    max_e = max(energies) if energies else 1
    if max_e > 0:
        return [e / max_e for e in energies]
    return [0.5] * len(beat_times)


def classify_energy(energy: float) -> int:
    """Classify normalized energy (0.0-1.0) into tier 1-5."""
    if energy < 0.2:
        return 1
    elif energy < 0.4:
        return 2
    elif energy < 0.6:
        return 3
    elif energy < 0.8:
        return 4
    else:
        return 5


# ---------------------------------------------------------------------------
# Section Color Palettes
# ---------------------------------------------------------------------------

# Colors that "feel" hot/energetic vs cool/chill
_HOT_COLORS = ["hot_pink", "magenta", "gold", "white", "coral", "rose"]
_COOL_COLORS = ["purple", "electric_blue", "lavender", "champagne"]


def assign_section_palettes(seg_bounds: list, seg_avg_energies: list,
                            palette: dict) -> list:
    """Assign 3-4 colors to each segment based on its energy character.

    High-energy segments get hot colors, low-energy get cool colors.
    Adjacent segments always get different subsets for contrast.
    """
    color_names = [name for name in palette.keys() if name != "off"]
    hot = [c for c in _HOT_COLORS if c in color_names]
    cool = [c for c in _COOL_COLORS if c in color_names]

    # Fallback if palette doesn't match our categories
    if not hot:
        hot = color_names
    if not cool:
        cool = color_names

    section_palettes = []
    prev_set = set()

    for i, energy in enumerate(seg_avg_energies):
        if energy > 0.6:
            pool = hot
        elif energy > 0.35:
            pool = color_names
        else:
            pool = cool

        n = min(4, len(pool))
        start = (i * 3) % len(pool)
        selected = [pool[(start + j) % len(pool)] for j in range(n)]

        # Ensure we don't repeat the exact same palette as the previous section
        if set(selected) == prev_set and len(pool) > n:
            start = (start + n) % len(pool)
            selected = [pool[(start + j) % len(pool)] for j in range(n)]

        prev_set = set(selected)
        section_palettes.append([(name, palette[name]) for name in selected])

    return section_palettes


# ---------------------------------------------------------------------------
# Laser Patterns & Feature Levels
# ---------------------------------------------------------------------------

# Each pattern: [green_laser_1, red_laser_2, blue_laser_3, red_laser_4]
_LASER_PATTERNS = {
    1: [[0, 0, 0, 0]],
    2: [[180, 0, 0, 0],
        [0, 0, 180, 0],
        [0, 180, 0, 0],
        [0, 0, 0, 180]],
    3: [[200, 200, 0, 0],
        [0, 0, 200, 200],
        [200, 0, 200, 0],
        [0, 200, 0, 200]],
    4: [[220, 220, 0, 220],
        [220, 0, 220, 220],
        [0, 220, 220, 220],
        [220, 220, 220, 0]],
    5: [[255, 255, 255, 255]],
}

_MOTOR_SPEEDS = {1: 0, 2: 60, 3: 130, 4: 190, 5: 245}
_UV_LEVELS = {1: 0, 2: 40, 3: 100, 4: 170, 5: 230}


def get_laser_pattern(tier: int, beat_idx: int) -> list:
    """Get laser values that alternate every 2 beats within the tier's patterns."""
    patterns = _LASER_PATTERNS[tier]
    return patterns[(beat_idx // 2) % len(patterns)]


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _find_segment(time: float, seg_bounds: list) -> int:
    """Return the segment index that contains the given time."""
    for i in range(len(seg_bounds) - 1):
        if seg_bounds[i] <= time < seg_bounds[i + 1]:
            return i
    return len(seg_bounds) - 2


# ---------------------------------------------------------------------------
# Show Timeline Generation
# ---------------------------------------------------------------------------

def generate_show_timeline(ids: IDAllocator, analysis: dict,
                           palette: dict, bpm: float, style: str,
                           fixtures: list, fixture_ids: list) -> dict:
    """Generate the Show function with per-beat dynamic scene selection.

    Key improvements over the old approach:
    - Per-beat energy drives laser, motor, UV, and color intensity on EVERY beat
    - Section-aware color palettes (2-4 colors per section, not all 10)
    - Build-up ramps before high-energy sections (gradual laser/motor increase)
    - Blackout accents before drops and as breathing breaks
    - Dynamic scene creation with caching (50-150+ unique scenes)

    Returns: {show_id, audio_id, elements, all_scenes}
    """
    duration_ms = int(analysis["duration"] * 1000)
    seg_bounds = sorted(analysis.get("segment_boundaries", []))
    onset_times = analysis.get("onset_times", [])
    beat_times = sorted(analysis.get("beat_times", []))

    if not seg_bounds or seg_bounds[0] > 0.5:
        seg_bounds = [0.0] + seg_bounds
    if seg_bounds[-1] < analysis["duration"] - 1.0:
        seg_bounds.append(analysis["duration"])

    # --- Per-beat energy ---
    beat_energies = get_beat_energies(analysis)

    # --- Per-segment average energy (for section palette assignment) ---
    seg_avg_energies = []
    for i in range(len(seg_bounds) - 1):
        beats_in_seg = [e for bt, e in zip(beat_times, beat_energies)
                        if seg_bounds[i] <= bt < seg_bounds[i + 1]]
        avg = sum(beats_in_seg) / len(beats_in_seg) if beats_in_seg else 0.5
        seg_avg_energies.append(avg)

    # --- Section color palettes ---
    section_palettes = assign_section_palettes(
        seg_bounds, seg_avg_energies, palette)

    # --- Scene cache ---
    scene_cache = SceneCache(ids, fixtures, fixture_ids)
    blackout = scene_cache.get_or_create("off", [0, 0, 0], 0,
                                          [0, 0, 0, 0], 0, 0, 0)

    # --- Style parameters ---
    style_color_rate = {"calm": 4, "moderate": 2, "energetic": 1, "dramatic": 2}
    base_beats_per_color = style_color_rate.get(style, 2)

    # --- Audio function ---
    audio_id = ids.function_id()
    audio_source = analysis.get("filepath", "audio/song.wav")
    audio_elem = ET.Element("Function", ID=str(audio_id), Type="Audio",
                            Name=os.path.basename(audio_source))
    ET.SubElement(audio_elem, "Source").text = audio_source

    # --- Show function ---
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

    # Track 1: Main Lights
    lights_track = ET.SubElement(show_elem, "Track", ID="1",
                                 Name="Main Lights",
                                 SceneID=str(blackout["id"]), isMute="0")

    # Pre-first-beat blackout
    first_beat_ms = int(beat_times[0] * 1000) if beat_times else 500
    if first_beat_ms > 50:
        ET.SubElement(lights_track, "ShowFunction",
                      ID=str(blackout["id"]),
                      StartTime="0", Duration=str(first_beat_ms),
                      Color="#000000")

    # --- Build-up / segment transition helpers ---

    def _beats_until_next_segment(beat_time: float) -> float:
        """How many beats until the next segment boundary."""
        for bound in seg_bounds:
            if bound > beat_time + 0.1:
                return (bound - beat_time) * bpm / 60.0
        return 999.0

    def _next_segment_is_hotter(beat_time: float) -> bool:
        """True if the segment after the next boundary is higher energy."""
        seg_idx = _find_segment(beat_time, seg_bounds)
        if seg_idx + 1 < len(seg_avg_energies):
            return seg_avg_energies[seg_idx + 1] > seg_avg_energies[seg_idx] * 1.3
        return False

    # --- Walk each beat and build the timeline ---

    color_counter = 0
    prev_seg_idx = -1

    for beat_idx in range(len(beat_times)):
        beat_time = beat_times[beat_idx]
        beat_ms = int(beat_time * 1000)

        # Duration to next beat (or end of song)
        if beat_idx + 1 < len(beat_times):
            next_beat_ms = int(beat_times[beat_idx + 1] * 1000)
        else:
            next_beat_ms = duration_ms
        beat_duration = next_beat_ms - beat_ms
        if beat_duration < 10:
            continue

        # Segment info
        seg_idx = _find_segment(beat_time, seg_bounds)
        energy = (beat_energies[beat_idx]
                  if beat_idx < len(beat_energies) else 0.5)
        tier = classify_energy(energy)

        # Reset color counter on segment change
        if seg_idx != prev_seg_idx:
            color_counter = 0
            prev_seg_idx = seg_idx

        # Section color palette for this beat
        if seg_idx < len(section_palettes):
            sec_pal = section_palettes[seg_idx]
        else:
            sec_pal = section_palettes[-1]

        # --- Build-up detection ---
        beats_to_seg = _beats_until_next_segment(beat_time)
        building_up = beats_to_seg <= 8 and _next_segment_is_hotter(beat_time)

        # Blackout accent: 1 beat of darkness right before a drop
        if building_up and beats_to_seg <= 1.5:
            ET.SubElement(lights_track, "ShowFunction",
                          ID=str(blackout["id"]),
                          StartTime=str(beat_ms),
                          Duration=str(beat_duration),
                          Color="#000000")
            color_counter += 1
            continue

        # Build-up ramp: gradually boost tier in the 8 beats before a drop
        if building_up:
            ramp = 1.0 - (beats_to_seg / 8.0)  # 0→1 as we approach
            tier = min(5, tier + int(ramp * 3))

        # Breathing blackout: 1 beat of dark every 32 beats in high-energy
        if (tier >= 4 and color_counter > 0
                and color_counter % 32 == 0):
            ET.SubElement(lights_track, "ShowFunction",
                          ID=str(blackout["id"]),
                          StartTime=str(beat_ms),
                          Duration=str(beat_duration),
                          Color="#000000")
            color_counter += 1
            continue

        # --- Transition blackout at segment boundaries ---
        # 2 beats of blackout when entering a new lower-energy segment
        if (color_counter < 2 and seg_idx > 0
                and seg_idx < len(seg_avg_energies)
                and seg_idx - 1 < len(seg_avg_energies)
                and seg_avg_energies[seg_idx] < seg_avg_energies[seg_idx - 1] * 0.7):
            ET.SubElement(lights_track, "ShowFunction",
                          ID=str(blackout["id"]),
                          StartTime=str(beat_ms),
                          Duration=str(beat_duration),
                          Color="#000000")
            color_counter += 1
            continue

        # --- Select color ---
        # High energy = change color every beat; low energy = hold longer
        color_rate = 1 if tier >= 4 else base_beats_per_color
        color_idx = (color_counter // color_rate) % len(sec_pal)
        color_name, color_rgb = sec_pal[color_idx]

        # --- Compute per-beat feature levels ---
        lasers = get_laser_pattern(tier, beat_idx)
        motor = _MOTOR_SPEEDS[tier]
        uv = _UV_LEVELS[tier]

        # White LED flash on accent beats in high-energy sections
        white = 200 if (tier >= 4 and beat_idx % 4 == 0) else 0

        # Strobe only on peak moments (tier 5, first 2 of every 8 beats)
        strobe = 150 if (tier == 5 and beat_idx % 8 < 2) else 0

        # --- Get or create the scene ---
        scene = scene_cache.get_or_create(
            color_name, color_rgb, motor, lasers, strobe, uv, white)

        r, g, b = color_rgb
        color_hex = f"#{r:02x}{g:02x}{b:02x}"

        ET.SubElement(lights_track, "ShowFunction",
                      ID=str(scene["id"]),
                      StartTime=str(beat_ms),
                      Duration=str(beat_duration),
                      Color=color_hex)

        color_counter += 1

    # End with blackout (2s fade out)
    end_start = max(0, duration_ms - 2000)
    ET.SubElement(lights_track, "ShowFunction",
                  ID=str(blackout["id"]),
                  StartTime=str(end_start), Duration="2000",
                  Color="#000000")

    # --- Track 2: Strobe Hits (onset clusters in high-energy regions) ---
    strobe_scene = scene_cache.get_or_create(
        "white", [255, 255, 255], 255, [255, 255, 255, 255], 150, 255, 255)

    strobe_track = ET.SubElement(show_elem, "Track", ID="2",
                                 Name="Strobe Hits",
                                 SceneID=str(strobe_scene["id"]),
                                 isMute="0")

    avg_beat_ms = int(60000 / bpm)
    last_strobe_end = 0

    for idx in range(len(onset_times) - 3):
        window_start = onset_times[idx]
        window_end = window_start + 0.5
        cluster_count = sum(1 for t in onset_times[idx:idx + 10]
                            if t < window_end)

        if cluster_count >= 4:
            s_idx = _find_segment(window_start, seg_bounds)
            if (s_idx < len(seg_avg_energies)
                    and seg_avg_energies[s_idx] > 0.5):
                start_ms = int(window_start * 1000)
                if start_ms >= last_strobe_end + avg_beat_ms:
                    ET.SubElement(strobe_track, "ShowFunction",
                                  ID=str(strobe_scene["id"]),
                                  StartTime=str(start_ms),
                                  Duration=str(avg_beat_ms),
                                  Color="#ffffff")
                    last_strobe_end = start_ms + avg_beat_ms

    return {
        "show_id": show_id,
        "audio_id": audio_id,
        "elements": [audio_elem, show_elem],
        "all_scenes": scene_cache.all_scenes,
        "blackout_scene": blackout,
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

    # Override audio path in analysis if provided
    if audio_path:
        analysis["filepath"] = audio_path

    # Show timeline — generates all scenes dynamically via SceneCache
    timeline = generate_show_timeline(ids, analysis, palette,
                                      analysis["bpm"], style,
                                      fixtures, fixture_ids)

    # Add all dynamically generated scenes to the engine
    for scene in timeline["all_scenes"]:
        engine.append(scene["element"])

    # Add audio and show functions
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
    blackout_scene = timeline["blackout_scene"]
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
    ET.SubElement(props, "GrandMaster", ChannelMode="Intensity",
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
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE Workspace>\n' + xml_body + "\n")


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
