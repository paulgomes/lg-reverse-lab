"""Generate original sine-tone MP3 and color-bar JPEG files for USB Scout.

Requires Pillow and an ffmpeg executable on PATH. No recordings or photos used.
"""
from __future__ import annotations
import argparse
import math
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import wave

from PIL import Image, ImageDraw, ImageFont

RATE = 44100
SECONDS = 8


def generate(output: Path) -> None:
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise RuntimeError('ffmpeg was not found on PATH.')
    names = ['01_LEFT_CHANNEL.mp3', '02_RIGHT_CHANNEL.mp3',
             '03_ALTERNATING_CHANNELS.mp3', '04_COLOR_BARS.jpg',
             '05_COLOR_GRID.jpg']
    if any((output / name).exists() for name in names):
        raise FileExistsError('A test-media destination already exists; choose a new folder.')
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        for mode, name in enumerate(names[:3]):
            samples = bytearray()
            for sample in range(RATE * SECONDS):
                t = sample / RATE
                envelope = min(1.0, t / .02, (SECONDS - t) / .02)
                tone = round(0.12 * 32767 * envelope * math.sin(2 * math.pi * 440 * t))
                channel = mode if mode < 2 else int(t) % 2
                samples.extend(struct.pack('<hh', tone if channel == 0 else 0,
                                           tone if channel == 1 else 0))
            source = Path(temporary) / f'tone-{mode}.wav'
            with wave.open(str(source), 'wb') as stream:
                stream.setnchannels(2)
                stream.setsampwidth(2)
                stream.setframerate(RATE)
                stream.writeframes(samples)
            subprocess.run([ffmpeg, '-nostdin', '-v', 'error', '-n', '-i', str(source),
                            '-map_metadata', '-1', '-codec:a', 'libmp3lame', '-b:a', '128k',
                            str(output / name)], check=True)
    colors = ['#ffffff', '#ffff00', '#00ffff', '#00ff00', '#ff00ff', '#ff0000', '#0000ff']
    font = ImageFont.load_default(size=36)
    for index, name in enumerate(names[3:]):
        image = Image.new('RGB', (1280, 720), '#17202c')
        draw = ImageDraw.Draw(image)
        for bar, color in enumerate(colors):
            x = 40 + bar * 170
            draw.rectangle((x, 170, x + 169, 580), fill=color)
        if index:
            for x in range(40, 1230, 20):
                draw.line((x, 200, x, 550), fill='#222222', width=2)
        draw.text((40, 55), f'LG Reverse Lab | USB Scout | Test {index + 1}', fill='white', font=font)
        draw.text((40, 625), 'Synthetic media generated from code. No personal photos.', fill='white', font=font)
        image.save(output / name, quality=90, exif=b'')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'USB_SCOUT/LG_TESTES')
    generate(parser.parse_args().output)
