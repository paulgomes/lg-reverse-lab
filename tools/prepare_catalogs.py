#!/usr/bin/env python3
"""Rebuild the editor's local JSON catalogs from a user-supplied HT306 ROM.

Only Python's standard library is needed. No ROM bytes, extracted glyph images,
font files, icons, or MPEG pictures are bundled with this tool. The generated
JSON contains firmware-derived text and metadata and should remain local.

This is an independently implemented, bounded parser for this exact image. It
does not execute firmware, modify the source, access devices, or flash anything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent
ROM_NAME = "LG_HT306LD1_1107200.rom"
EXPECTED_SHA256 = "27adf86b93e5e7347fbd7d12837e32a3394243a75e025d2b188e1afd5151c00a"
EXPECTED_SIZE = 2_091_376
VISUAL_BASE = 0x1470C0
TEXT_BASE = 0x1ACB0C
PREVIEW_PALETTE = [[20, 80, 150, 255], [0, 0, 0, 0],
                   [0, 0, 0, 255], [255, 255, 255, 255]]
LANGUAGE_LABELS = [
    "English", "Korean (glyph-based inference)",
    "Sparse Simplified Chinese / DRM (glyph-based inference)",
    "French", "Spanish", "German", "Portuguese", "Italian", "Dutch",
    "Hungarian", "Polish", "Russian (glyph-based inference)", "Swedish",
    "Czech", "Greek (glyph-based inference)",
    "Traditional Chinese (glyph-based inference)",
    "Japanese (glyph-based inference)",
    "Persian / whole-word glyphs (inference)",
    "Thai / whole-word glyphs (inference)", "Vietnamese", "Turkish",
    "Indonesian", "Brazilian Portuguese (text inference)", "Romanian", "Slovak",
]


class CatalogError(ValueError):
    """The image or one of its declared resource boundaries is invalid."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CatalogError(message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def align4(value: int) -> int:
    return (value + 3) & ~3


class Reader:
    def __init__(self, data: bytes):
        self.data = data

    def span(self, start: int, size: int, limit: int | None = None) -> bytes:
        end = start + size
        ceiling = len(self.data) if limit is None else limit
        require(0 <= start <= end <= ceiling <= len(self.data),
                f"Out-of-bounds resource read: {start:#x}..{end:#x}")
        return self.data[start:end]

    def u8(self, at: int, limit: int | None = None) -> int:
        return self.span(at, 1, limit)[0]

    def u16(self, at: int, limit: int | None = None) -> int:
        return int.from_bytes(self.span(at, 2, limit), "little")

    def u32(self, at: int, limit: int | None = None) -> int:
        return int.from_bytes(self.span(at, 4, limit), "little")


def font_rle_status(raw: bytes, pixels: int) -> dict:
    """Count the bounded four-level, MS-nibble-first, two-bit color RLE.

    Zero-length runs fill the remaining raster. Old terminal glyphs can have an
    incomplete stream; preserve that fact instead of claiming an invented tail.
    No raster pixels need to be retained to generate the metadata catalog.
    """
    pos = consumed = zero_fills = 0

    def nibble() -> int:
        nonlocal pos
        index = pos
        if index >= len(raw) * 2:
            raise IndexError
        pos += 1
        byte = raw[index // 2]
        return byte >> 4 if index % 2 == 0 else byte & 15

    try:
        while consumed < pixels:
            code = nibble()
            if code < 4:
                code = code * 16 + nibble()
                if code < 16:
                    code = code * 16 + nibble()
                    if code < 64:
                        code = code * 16 + nibble()
            count = code >> 2
            if count == 0:
                count = pixels - consumed
                zero_fills += 1
            consumed += min(count, pixels - consumed)
    except IndexError:
        pass
    return {"complete": consumed == pixels, "missing_pixels": pixels - consumed,
            "nibbles_consumed": pos, "zero_count_fills": zero_fills}


def parse_fonts(r: Reader) -> dict:
    directory = VISUAL_BASE + r.u32(VISUAL_BASE + 12)
    require(VISUAL_BASE < directory < TEXT_BASE, "Invalid visual directory")
    require(r.u32(directory) == 15, "Expected 15 fonts")
    starts = [VISUAL_BASE + r.u32(directory + 4 + 4 * i) for i in range(15)]
    require(starts == sorted(set(starts)), "Invalid font pointer order")
    require(r.u32(directory + 64) == 372, "Expected 372 original icons")
    first_icon = VISUAL_BASE + r.u32(directory + 68)
    require(VISUAL_BASE < starts[0] < starts[-1] < first_icon < directory,
            "Invalid font resource boundaries")
    fonts, bank_map, bank = [], {}, 0
    for index, start in enumerate(starts):
        limit = starts[index + 1] if index < 14 else first_icon
        require(r.span(start, 4, limit) == b"FON\x01", "Unexpected FON signature")
        require(r.u8(start + 6, limit) == 2 and r.u8(start + 9, limit) == 0,
                "Unsupported font encoding")
        count, height = r.u16(start + 7, limit), r.u8(start + 10, limit)
        require(0 < count <= 4096 and 0 < height <= 255, "Invalid font dimensions")
        widths = r.span(start + 11, count, limit)
        require(min(widths) > 0, "Zero-width glyph is unsupported")
        offset_table = start + align4(11 + count)
        offsets = [r.u32(offset_table + 4 * g, limit) for g in range(count + 1)]
        data_start = start + r.u16(start + 4, limit) + 1
        require(data_start == offset_table + 4 * (count + 1),
                "Font data pointer does not match offset table")
        require(offsets[0] == 0 and offsets == sorted(offsets),
                "Invalid glyph offset order")
        glyphs = []
        for glyph, width in enumerate(widths):
            at, nominal_end = data_start + offsets[glyph], data_start + offsets[glyph + 1]
            # Directory bounds take precedence over old terminal offset entries.
            end = limit if glyph + 1 == count else min(nominal_end, limit)
            require(data_start <= at < end <= limit, "Glyph outside font boundary")
            raster_width = align4(width)
            glyphs.append({"index": glyph, "width": width, "raster_width": raster_width,
                           "start": hex(at), "end_exclusive": hex(end),
                           "terminal_pointer_outside_font": nominal_end > limit,
                           "terminal_pointer": hex(nominal_end),
                           **font_rle_status(r.span(at, end - at, limit), raster_width * height)})
        logical_banks = []
        # The firmware advances banks in groups of 250 glyphs, not 256.
        for base in range(0, count, 250):
            bank_map[str(bank)] = {"font_index": index, "glyph_base": base}
            logical_banks.append(bank)
            bank += 1
        fonts.append({"index": index, "start": hex(start), "end_exclusive": hex(limit),
                      "count": count, "height": height, "max_width": max(widths),
                      "data_start": hex(data_start), "logical_banks": logical_banks,
                      "complete_glyphs": sum(g["complete"] for g in glyphs), "glyphs": glyphs})
    return {"rom_sha256": EXPECTED_SHA256, "directory": hex(directory),
            "bank_map": bank_map, "preview_palette": PREVIEW_PALETTE, "fonts": fonts}


def parse_strings(r: Reader, font_catalog: dict) -> dict:
    require(r.span(TEXT_BASE, 12) == b"MTKOSD0.100.", "Unexpected OSD signature")
    directory = TEXT_BASE + r.u32(TEXT_BASE + 12)
    require(TEXT_BASE < directory < len(r.data) - 4, "Invalid OSD directory")
    require(r.u32(directory) == 25, "Expected 25 language tables")
    heads = [TEXT_BASE + r.u32(directory + 4 + 4 * i) for i in range(25)]
    payloads = [TEXT_BASE + r.u32(directory + 104 + 4 * i) for i in range(25)]
    require(heads == sorted(set(heads)) and heads[0] == TEXT_BASE + 16 and heads[-1] < directory,
            "Invalid language table order")
    languages, roundtrips = [], []
    for language, head in enumerate(heads):
        limit = heads[language + 1] if language < 24 else directory
        count = r.u32(head, limit)
        require(count == 542, "Expected 542 records in each language")
        payload = head + 4 + count * 4
        require(payload == payloads[language] and head < payload < limit,
                "Language payload pointer mismatch")
        offsets = [r.u32(head + 4 + 4 * i, limit) for i in range(count)]
        require(offsets[0] == 0 and offsets == sorted(set(offsets)), "Invalid string offset order")
        records, rebuilt_payload = [], bytearray()
        for ident, offset in enumerate(offsets):
            at = payload + offset
            boundary = payload + offsets[ident + 1] if ident + 1 < count else limit
            require(payload <= at < boundary <= limit, "Invalid string boundary")
            total, cursor, accumulated, runs = r.u8(at, boundary), at + 1, 0, []
            dynamic = False
            while accumulated < total or not runs:
                run_count, bank = r.span(cursor, 2, boundary)
                cursor += 2
                glyphs = r.span(cursor, run_count, boundary)
                cursor += run_count
                accumulated += run_count
                require(accumulated <= total and (run_count > 0 or total == 0),
                        "Invalid OSD string run")
                mapping = font_catalog["bank_map"].get(str(bank))
                require(mapping is not None, "String uses an unknown font bank")
                font_count = font_catalog["fonts"][mapping["font_index"]]["count"]
                for value in glyphs:
                    if value == 255:
                        dynamic = True
                    else:
                        require(mapping["glyph_base"] + value < font_count,
                                "String glyph index outside font")
                runs.append({"count": run_count, "bank": bank, "glyph_hex": glyphs.hex(),
                             "ascii_font0": glyphs.decode("latin-1") if bank == 0 else None})
            require(accumulated == total and (cursor == boundary or ident + 1 == count),
                    "OSD record overlap or gap")
            projection = "".join(run["ascii_font0"] if run["bank"] == 0 else
                                 f"<bank{run['bank']}:{run['glyph_hex']}>" for run in runs)
            record = {"file_offset": hex(at), "end_exclusive": hex(cursor), "glyph_count": total,
                      "runs": runs, "text_font0_projection": projection,
                      "id": ident, "id_hex": f"0x{ident:03X}"}
            if dynamic:
                record["render_issues"] = ["dynamic byte 0xFF; value not evaluated"]
            rebuilt = bytes([total]) + b"".join(
                bytes([run["count"], run["bank"]]) + bytes.fromhex(run["glyph_hex"]) for run in runs)
            require(rebuilt == r.span(at, cursor - at, boundary), "String round-trip mismatch")
            require(len(rebuilt_payload) == offset, "Rebuilt string offset mismatch")
            rebuilt_payload.extend(rebuilt)
            records.append(record)
        require(align4(cursor) == limit, "Language table alignment mismatch")
        rebuilt_table = struct.pack("<I", count) + struct.pack(f"<{count}I", *offsets) + rebuilt_payload
        original_table = r.span(head, cursor - head, limit)
        require(rebuilt_table == original_table, "Language table round-trip mismatch")
        roundtrips.append({"language": language, "records": count, "start": hex(head),
                           "end_exclusive": hex(cursor), "bytes": len(rebuilt_table),
                           "sha256_original": sha256(original_table),
                           "sha256_serialized_from_records": sha256(rebuilt_table), "byte_exact": True,
                           "alignment_padding_excluded_bytes": limit - cursor})
        languages.append({"index": language, "label_inference": LANGUAGE_LABELS[language],
                          "head_offset": hex(head), "payload_offset": hex(payload),
                          "end_exclusive": hex(cursor), "count": count,
                          "all_record_boundaries_verified": True, "records": records})
    return {"rom_sha256": EXPECTED_SHA256, "base": hex(TEXT_BASE), "directory": hex(directory),
            "language_count": len(languages), "records_total": 25 * 542,
            "byte_exact_roundtrips": roundtrips, "languages": languages}


def build_catalogs(data: bytes) -> dict[str, dict]:
    require(len(data) == EXPECTED_SIZE, f"Expected {EXPECTED_SIZE} source bytes")
    require(sha256(data) == EXPECTED_SHA256, "Source SHA-256 does not match the supported original ROM")
    checksum = 0
    for (word,) in struct.iter_unpack("<I", data):
        checksum ^= word
    require(checksum == 0, "Invalid source XOR32 checksum")
    reader = Reader(data)
    fonts = parse_fonts(reader)
    return {"osd_strings.json": parse_strings(reader, fonts), "fontes.json": fonts}


def write_json(path: Path, content: dict) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(content, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=ROOT / ROM_NAME,
                        help="user-supplied original ROM (must match the documented SHA-256)")
    parser.add_argument("--output", type=Path, default=ROOT / "AUDITORIA_ROM" / "recursos_osd",
                        help="local generated-catalog directory")
    parser.add_argument("--force", action="store_true", help="replace existing local catalogs")
    parser.add_argument("--check", action="store_true", help="verify existing JSON catalogs without writing")
    args = parser.parse_args(argv)
    try:
        source = args.rom.resolve(strict=True)
        data = source.read_bytes()
        catalogs = build_catalogs(data)
        output = args.output.resolve()
        paths = [output / name for name in catalogs]
        require(all(path != source for path in paths), "Output cannot replace the source ROM")
        if args.check:
            for name, content in catalogs.items():
                actual = json.loads((output / name).read_text(encoding="utf-8"))
                require(actual == content, f"Existing catalog differs: {name}")
        else:
            require(args.force or not any(path.exists() for path in paths),
                    "Catalogs already exist; use --check to verify or --force to replace")
            output.mkdir(parents=True, exist_ok=True)
            for name, content in catalogs.items():
                write_json(output / name, content)
        require(sha256(source.read_bytes()) == EXPECTED_SHA256, "Source changed during processing")
        fonts = catalogs["fontes.json"]["fonts"]
        print(json.dumps({"status": "checked" if args.check else "created",
                          "source_sha256": EXPECTED_SHA256, "output": str(output),
                          "languages": 25, "records": 13550, "fonts": len(fonts),
                          "glyphs": sum(font["count"] for font in fonts),
                          "incomplete_glyphs": sum(font["count"] - font["complete_glyphs"] for font in fonts),
                          "source_unchanged": True, "firmware_executed": False}, ensure_ascii=False))
        return 0
    except (CatalogError, OSError, ValueError) as error:
        print(f"Catalog preparation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
