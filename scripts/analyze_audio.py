#!/usr/bin/env python3
"""Analyze audio files for BPM, beat positions, and song structure.

Detects tempo, individual beat timestamps, onset/accent positions,
and structural segment boundaries (verse/chorus/bridge transitions).
Outputs a JSON file used by generate_show_xml.py to create
beat-synced QLC+ show files.

Requires: pip install librosa numpy soundfile
"""

import json
import sys
import os


def analyze_audio(filepath: str) -> dict:
    """Detect BPM, beats, onsets, and segments from an audio file."""
    import librosa
    import numpy as np

    print(f"Loading: {filepath}")
    y, sr = librosa.load(filepath)

    # BPM and beat detection
    print("Detecting tempo and beats...")
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)

    # Onset detection (accent/transient hits)
    print("Detecting onsets...")
    onset_frames = librosa.onset.onset_detect(y=y, sr=sr)
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)

    # Structural segmentation using MFCC-based clustering
    print("Detecting song structure...")
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=12)
    bound_frames = librosa.segment.agglomerative(mfcc, k=8)
    bound_times = librosa.frames_to_time(bound_frames, sr=sr)

    # Per-beat energy (RMS) — allows the show generator to vary intensity
    # on every single beat rather than per-segment
    print("Computing per-beat energy...")
    rms = librosa.feature.rms(y=y)[0]
    rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr)
    beat_rms = np.interp(beat_times, rms_times, rms)
    rms_max = beat_rms.max()
    if rms_max > 0:
        beat_energy = beat_rms / rms_max
    else:
        beat_energy = beat_rms

    # Per-beat spectral brightness — high values indicate bright/harsh
    # sounds (cymbals, synth stabs), low values indicate bass/warm sounds
    cent = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    cent_times = librosa.frames_to_time(np.arange(len(cent)), sr=sr)
    beat_cent = np.interp(beat_times, cent_times, cent)
    cent_max = beat_cent.max()
    if cent_max > 0:
        beat_brightness = beat_cent / cent_max
    else:
        beat_brightness = beat_cent

    # Handle librosa versions where tempo may be an array
    bpm = float(tempo) if not hasattr(tempo, '__len__') else float(tempo[0])

    result = {
        "filepath": filepath,
        "duration": float(librosa.get_duration(y=y, sr=sr)),
        "bpm": bpm,
        "beat_times": [float(t) for t in beat_times],
        "onset_times": [float(t) for t in onset_times],
        "segment_boundaries": [float(t) for t in bound_times],
        "beat_energy": [round(float(e), 4) for e in beat_energy],
        "beat_brightness": [round(float(b), 4) for b in beat_brightness],
    }
    return result


def update_playlist(filepath: str, bpm: float, duration: float) -> None:
    """Update bpm and duration_seconds in playlist.json for the matching song."""
    audio_dir = os.path.dirname(os.path.abspath(filepath))
    playlist_path = os.path.join(audio_dir, "playlist.json")
    if not os.path.isfile(playlist_path):
        return

    audio_filename = os.path.basename(filepath)

    with open(playlist_path, "r") as f:
        playlist = json.load(f)

    updated = False
    for song in playlist.get("songs", []):
        if song.get("file") == audio_filename:
            song["bpm"] = round(bpm, 1)
            song["duration_seconds"] = round(duration, 1)
            updated = True
            break

    if updated:
        with open(playlist_path, "w") as f:
            json.dump(playlist, f, indent=2)
            f.write("\n")
        print(f"  Updated playlist.json: bpm={round(bpm, 1)}, duration_seconds={round(duration, 1)}")
    else:
        print(f"  Warning: No matching entry for '{audio_filename}' in playlist.json")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python analyze_audio.py <audio_file>")
        print("Example: python analyze_audio.py audio/song1.wav")
        print()
        print("Output: <audio_file_without_ext>_analysis.json")
        sys.exit(1)

    filepath = sys.argv[1]
    if not os.path.isfile(filepath):
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    result = analyze_audio(filepath)

    output_path = filepath.rsplit(".", 1)[0] + "_analysis.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"\nAnalysis complete:")
    print(f"  BPM: {result['bpm']:.1f}")
    print(f"  Duration: {result['duration']:.1f}s")
    print(f"  Beats: {len(result['beat_times'])}")
    print(f"  Onsets: {len(result['onset_times'])}")
    print(f"  Segments: {len(result['segment_boundaries'])}")
    print(f"  Saved to: {output_path}")

    update_playlist(filepath, result["bpm"], result["duration"])


if __name__ == "__main__":
    main()
