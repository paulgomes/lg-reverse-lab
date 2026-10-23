"""Offline, hash-bound reversible XOR patches. No firmware or device is bundled."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import zlib

FORMAT = 'lg-reverse-lab-xor-v1'
MAX_IMAGE_BYTES = 16 * 1024 * 1024


class PatchError(ValueError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_patch(before: bytes, after: bytes, metadata: dict | None = None) -> dict:
    if not before or len(before) != len(after) or len(before) > MAX_IMAGE_BYTES:
        raise PatchError('Images must have the same nonzero size, up to 16 MiB.')
    delta = bytes(a ^ b for a, b in zip(before, after))
    return {
        'format': FORMAT, 'image_bytes': len(before),
        'source_sha256': sha256(before), 'target_sha256': sha256(after),
        'delta_sha256': sha256(delta), 'encoding': 'zlib+base64',
        'changed_bytes': sum(a != b for a, b in zip(before, after)),
        'metadata': metadata or {},
        'delta': base64.b64encode(zlib.compress(delta, 9)).decode('ascii'),
    }


def decode_delta(patch: dict) -> bytes:
    size = patch.get('image_bytes')
    if patch.get('format') != FORMAT or patch.get('encoding') != 'zlib+base64':
        raise PatchError('Unsupported patch format.')
    if type(size) is not int or not 0 < size <= MAX_IMAGE_BYTES:
        raise PatchError('Invalid image size.')
    try:
        packed = base64.b64decode(patch['delta'], validate=True)
        decoder = zlib.decompressobj()
        delta = decoder.decompress(packed, size + 1)
    except (KeyError, TypeError, ValueError, zlib.error) as exc:
        raise PatchError('Invalid compressed delta.') from exc
    if (len(delta) != size or not decoder.eof or decoder.unused_data
            or decoder.unconsumed_tail):
        raise PatchError('Truncated, oversized or trailing delta data.')
    if sha256(delta) != patch.get('delta_sha256'):
        raise PatchError('Delta SHA-256 mismatch.')
    return delta


def apply_patch(source: bytes, patch: dict, reverse: bool = False) -> bytes:
    delta = decode_delta(patch)
    expected_input = patch.get('target_sha256' if reverse else 'source_sha256')
    expected_output = patch.get('source_sha256' if reverse else 'target_sha256')
    if len(source) != len(delta) or sha256(source) != expected_input:
        raise PatchError('Input image does not match the exact required SHA-256.')
    output = bytes(a ^ b for a, b in zip(source, delta))
    if sha256(output) != expected_output:
        raise PatchError('Output SHA-256 mismatch.')
    return output


def write_new(path: Path, data: bytes) -> None:
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    inspect = sub.add_parser('inspect', help='Verify delta and show metadata; no ROM needed.')
    inspect.add_argument('patch', type=Path)
    for command in ('apply', 'reverse', 'verify'):
        p = sub.add_parser(command)
        p.add_argument('patch', type=Path)
        p.add_argument('input', type=Path)
        if command != 'verify':
            p.add_argument('output', type=Path, help='New .preview.bin file; never overwritten.')
    args = parser.parse_args()
    try:
        patch = json.loads(args.patch.read_text(encoding='utf-8'))
        decode_delta(patch)
        if args.command == 'inspect':
            print(json.dumps({k: v for k, v in patch.items() if k != 'delta'}, indent=2))
            return
        result = apply_patch(args.input.read_bytes(), patch, reverse=args.command == 'reverse')
        if args.command != 'verify':
            if not args.output.name.endswith('.preview.bin'):
                raise PatchError('Research output must end with .preview.bin.')
            write_new(args.output, result)
        print(json.dumps({'verified': True, 'sha256': sha256(result), 'bytes': len(result),
                          'output_written': args.command != 'verify',
                          'device_accessed': False, 'physical_validation': False}))
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(1, f'Error: {exc}\n')


if __name__ == '__main__':
    main()
