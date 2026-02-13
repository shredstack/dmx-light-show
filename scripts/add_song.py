#!/usr/bin/env python3
"""Add a song to the playlist, analyze it, and generate its light show.

Automates the full pipeline:
1. Copy/convert audio to audio/ as 16-bit WAV (if not already there)
2. Add entry to playlist.json
3. Run beat/BPM analysis (updates playlist.json with detected BPM/duration)
4. Generate QLC+ show file

Usage:
    python scripts/add_song.py <wav_file> --artist "Artist" --title "Song Title"
    python scripts/add_song.py song.mp3 --artist "Avicii" --title "Levels" --style dramatic

Supports .wav files directly and .mp3/.flac/.ogg files (auto-converted via ffmpeg).
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
AUDIO_DIR = os.path.join(PROJECT_DIR, "audio")
SHOWS_DIR = os.path.join(PROJECT_DIR, "shows")
PLAYLIST_PATH = os.path.join(AUDIO_DIR, "playlist.json")
DEFAULT_FIXTURES = os.path.join(PROJECT_DIR, "fixtures", "keobin_l2800.json")


def make_song_id(artist: str, title: str) -> str:
    """Derive a song ID like 'artist__song_title' from artist and title."""
    def slugify(text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^\w\s]", "", text)
        text = re.sub(r"\s+", "_", text)
        return text

    return f"{slugify(artist)}__{slugify(title)}"


def ensure_wav_in_audio_dir(input_path: str, song_id: str) -> str:
    """Ensure a 16-bit WAV exists in audio/. Returns the WAV filename."""
    wav_filename = f"{song_id}.wav"
    wav_path = os.path.join(AUDIO_DIR, wav_filename)

    ext = os.path.splitext(input_path)[1].lower()

    if ext == ".wav":
        # Copy WAV directly if it's not already in the audio dir
        abs_input = os.path.abspath(input_path)
        if abs_input != os.path.abspath(wav_path):
            print(f"Copying {input_path} -> {wav_path}")
            shutil.copy2(input_path, wav_path)
        else:
            print(f"WAV already in place: {wav_path}")
    else:
        # Convert non-WAV formats using convert_audio.py
        print(f"Converting {input_path} -> {wav_path}")
        convert_script = os.path.join(SCRIPT_DIR, "convert_audio.py")
        subprocess.run(
            [sys.executable, convert_script, input_path, wav_path],
            check=True,
        )

    return wav_filename


def add_to_playlist(song_id: str, title: str, artist: str, wav_filename: str) -> None:
    """Add a new song entry to playlist.json (skips if already present)."""
    with open(PLAYLIST_PATH, "r") as f:
        playlist = json.load(f)

    # Check for duplicates
    for song in playlist.get("songs", []):
        if song.get("id") == song_id:
            print(f"Song '{song_id}' already in playlist.json — skipping add.")
            return

    entry = {
        "id": song_id,
        "title": title,
        "artist": artist,
        "file": wav_filename,
        "bpm": 0.0,
        "duration_seconds": 0.0,
        "analysis_file": f"{song_id}_analysis.json",
        "show_file": f"../shows/{song_id}_show.qxw",
        "notes": "",
    }

    playlist["songs"].append(entry)

    with open(PLAYLIST_PATH, "w") as f:
        json.dump(playlist, f, indent=2)
        f.write("\n")

    print(f"Added '{artist} - {title}' to playlist.json")


def run_analysis(wav_filename: str) -> str:
    """Run analyze_audio.py on the WAV file. Returns the analysis JSON path."""
    wav_path = os.path.join(AUDIO_DIR, wav_filename)
    analyze_script = os.path.join(SCRIPT_DIR, "analyze_audio.py")

    print(f"\n--- Analyzing {wav_filename} ---")
    subprocess.run(
        [sys.executable, analyze_script, wav_path],
        check=True,
    )

    analysis_path = wav_path.rsplit(".", 1)[0] + "_analysis.json"
    return analysis_path


def generate_show(analysis_path: str, wav_filename: str, song_id: str,
                  style: str, fixtures: str) -> str:
    """Run generate_show_xml.py to create the QLC+ show. Returns the .qxw path."""
    wav_path = os.path.join(AUDIO_DIR, wav_filename)
    output_path = os.path.join(SHOWS_DIR, f"{song_id}_show.qxw")
    generate_script = os.path.join(SCRIPT_DIR, "generate_show_xml.py")

    print(f"\n--- Generating show ({style}) ---")
    subprocess.run(
        [
            sys.executable, generate_script,
            "--analysis", analysis_path,
            "--fixtures", fixtures,
            "--audio-path", wav_path,
            "--output", output_path,
            "--style", style,
        ],
        check=True,
    )

    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add a song and generate its light show."
    )
    parser.add_argument("audio_file", help="Path to audio file (.wav, .mp3, .flac, .ogg)")
    parser.add_argument("--artist", required=True, help="Artist name")
    parser.add_argument("--title", required=True, help="Song title")
    parser.add_argument(
        "--style",
        default="energetic",
        choices=["calm", "moderate", "energetic", "dramatic"],
        help="Show style (default: energetic)",
    )
    parser.add_argument(
        "--fixtures",
        default=DEFAULT_FIXTURES,
        help="Fixture config JSON (default: fixtures/keobin_l2800.json)",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.audio_file):
        print(f"Error: File not found: {args.audio_file}", file=sys.stderr)
        sys.exit(1)

    song_id = make_song_id(args.artist, args.title)
    print(f"Song ID: {song_id}")

    # Step 1: Get WAV into audio/
    wav_filename = ensure_wav_in_audio_dir(args.audio_file, song_id)

    # Step 2: Add to playlist
    add_to_playlist(song_id, args.title, args.artist, wav_filename)

    # Step 3: Analyze audio (also updates playlist.json with BPM/duration)
    analysis_path = run_analysis(wav_filename)

    # Step 4: Generate show
    show_path = generate_show(
        analysis_path, wav_filename, song_id, args.style, args.fixtures
    )

    print(f"\n{'='*50}")
    print(f"Done! Song '{args.artist} - {args.title}' is ready.")
    print(f"  Playlist:  {PLAYLIST_PATH}")
    print(f"  Analysis:  {analysis_path}")
    print(f"  Show file: {show_path}")
    print(f"\nOpen in QLC+:")
    print(f"  open {show_path}")


if __name__ == "__main__":
    main()
