# Programming Guide

How to create music-synchronized light shows using QLC+ and the helper scripts.

## Concepts Overview

| Concept | What It Does |
|---------|-------------|
| **Fixture** | A light with a defined channel map (e.g., ch1=Red, ch2=Green, ch3=Blue) |
| **Scene** | A static snapshot of channel values — one "look" |
| **Chaser** | A sequence of scenes played in order with timing |
| **Collection** | Groups multiple functions to fire simultaneously |
| **Show** | A timeline where functions are placed at specific timestamps, synced to audio |
| **Virtual Console** | Customizable control panel with buttons and sliders for live operation |

## Step 1: Patch Your Fixtures

In QLC+ **Fixtures** tab:

1. Click **+** to add a fixture
2. Select manufacturer/model (QLC+ includes 800+ built-in definitions)
3. Set the DMX **address** and **universe** (Universe 1)
4. Give it a descriptive name (e.g., "PAR Left", "Moving Head Center")

Example patch for a basic 3-PAR setup:

| Fixture | Type | DMX Address | Channels |
|---------|------|-------------|----------|
| PAR Left | Generic RGB | 1 | 1-3 |
| PAR Center | Generic RGB | 4 | 4-6 |
| PAR Right | Generic RGB | 7 | 7-9 |

## Step 2: Create Base Scenes

Scenes are the building blocks of your show. Create scenes for:

- **Color states:** All Red, All Blue, All Green, Warm White, Cool White
- **Blackout:** All channels at 0 (essential for clean starts/stops)
- **Intensity levels:** Full brightness, 75%, 50%, 25%
- **Special looks:** Single-fixture highlights, split colors (left=red, right=blue)

To create a scene:
1. Go to the **Functions** tab, click **+** → **Scene**
2. Select the fixtures to include
3. Set channel values using the sliders
4. Name it descriptively (e.g., "All Red", "Left Blue Right Green")

## Step 3: Create Chasers

Chasers sequence through scenes with timing:

1. Go to **Functions** → **+** → **Chaser**
2. Add scenes as steps
3. Set **Duration** to match your music's beat:
   - At 120 BPM: 1 beat = 500ms, 1 bar = 2000ms
   - At 128 BPM: 1 beat = 469ms, 1 bar = 1875ms
   - Formula: `beat_ms = 60000 / BPM`
4. Set **Fade In/Out** for smooth or sharp transitions

Common chasers:
- **Color chase:** R → G → B → W cycling across fixtures
- **Rainbow sweep:** Smooth color transitions every bar
- **Intensity pulse:** Fade up/down matching the beat
- **Strobe burst:** Quick on/off (use short durations, 50-100ms)

## Step 4: Program in Show Manager

The **Show Manager** is where you sync lights to music:

1. Open the **Show Manager** tab
2. Create a new Show (click **+**)
3. Add an **Audio track** — drag in your WAV file
4. The waveform displays on the timeline as your visual guide
5. Add **Sequence tracks** for lighting
6. Drag scenes, chasers, or collections onto the timeline
7. Align them to visible peaks and transients in the waveform
8. Set fade times on each item for smooth transitions

### Sync Tips

- **"Trust the waveform"** — align your cues to visible peaks in the audio waveform
- **Start/Stop/Start workaround:** On first play, quickly start → stop → start the show to sync the audio engine (known QLC+ quirk)
- **macOS has better sync than Windows** for QLC+ shows
- Use **Collections** to trigger multiple effects at the same beat
- Diagonal lines in the timeline show fades; vertical lines show step boundaries

## Step 5: Using the Python Scripts

For automated show generation, use the three-step pipeline:

### Convert audio to WAV
```bash
python scripts/convert_audio.py input.mp3 audio/song.wav
```

### Analyze the audio
```bash
python scripts/analyze_audio.py audio/song.wav
# Outputs: audio/song_analysis.json
```

### Generate a QLC+ show
```bash
python scripts/generate_show_xml.py \
    --analysis audio/song_analysis.json \
    --fixtures fixtures/example_generic_rgb.json \
    --audio-path audio/song.wav \
    --output shows/song_show.qxw \
    --style energetic
```

Style options: `calm`, `moderate`, `energetic`, `dramatic`

Open the generated `.qxw` in QLC+ to preview and refine.

## Step 6: Multi-Song Shows

### Option A: Single Timeline (best for fixed playlists)
- Place all audio files end-to-end on one audio track
- Program all lighting on the same timeline
- Pros: seamless transitions
- Cons: editing one song shifts everything after it

### Option B: Cue List (best for live/flexible sets)
- Create individual Shows per song
- Build a **Cue List** widget on the Virtual Console
- Each cue triggers one song's Show function
- Pros: reorder/skip songs freely
- Cons: small gap between songs

### Option C: Hybrid
- Use a Cue List for song-level triggering
- Each cue fires a **Collection** containing both the audio and lighting functions

## Step 7: Virtual Console

Build an operator-friendly control panel in the **Virtual Console** tab:

| Widget | Purpose |
|--------|---------|
| **Cue List** | Playlist navigation (Go/Next/Previous) |
| **Speed Dial** | BPM tap for live beat-matching |
| **Slider** | Grand master intensity control |
| **Button Grid** | Quick-fire scenes (Blackout, All White, Strobe) |
| **Audio Triggers** | Map frequency bands to fixture groups for reactive effects |
