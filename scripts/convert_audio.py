#!/usr/bin/env python3
"""Convert audio files to 16-bit WAV for optimal QLC+ sync.

QLC+'s Show Manager works best with 16-bit 44.1kHz WAV files.
MP3 works but WAV provides tighter synchronization with the
lighting timeline.

Requires: ffmpeg (brew install ffmpeg)
"""

import subprocess
import sys
import os


def convert_to_wav(input_path: str, output_path: str) -> None:
    """Convert any audio file to 16-bit 44.1kHz stereo WAV using ffmpeg."""
    if not os.path.isfile(input_path):
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    cmd = [
        "ffmpeg", "-i", input_path,
        "-acodec", "pcm_s16le",  # 16-bit PCM
        "-ar", "44100",           # 44.1kHz sample rate
        "-ac", "2",               # Stereo
        "-y",                     # Overwrite output
        output_path
    ]

    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        print("Error: ffmpeg not found. Install with: brew install ffmpeg",
              file=sys.stderr)
        sys.exit(1)

    print(f"Converted: {input_path} -> {output_path}")


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python convert_audio.py <input_file> <output.wav>")
        print("Example: python convert_audio.py song.mp3 audio/song.wav")
        sys.exit(1)

    convert_to_wav(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    main()
