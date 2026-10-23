"""Fixed-size OSD text editor for one verified LG firmware image.

Engine(workspace=None).catalog() returns JSON-ready UI data.
Engine.build([{"language": 6, "id": 157, "text": "LG LAB"}]) writes only
outputs/*.preview.bin and two JSON manifests. No device or USB operations.
The binary remains a research preview; this module does not establish that a
modified image can be installed or that the installed LG firmware matches it.
"""
from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

EXPECTED_SHA256 = "27adf86b93e5e7347fbd7d12837e32a3394243a75e025d2b188e1afd5151c00a"
EXPECTED_SIZE = 2_091_376
TEXT_BASE = 0x1ACB0C
RESOURCES_START = 0x147080
ROM_NAME = "LG_HT306LD1_1107200.rom"
OSD_ENCODING = {"name": "LG OSD bank 0 / Latin-1 glyph indices",
                "space_byte": "0x40", "padding_byte": "0x40",
                "human_space_maps_to": "@", "literal_at_sign_supported": False}


class EngineError(ValueError):
    """A requested patch or its source failed a required validation."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def xor32(data: bytes) -> int:
    if len(data) % 4:
        raise EngineError("The image size is not a multiple of four bytes.")
    result = 0
    for (word,) in struct.iter_unpack("<I", data):
        result ^= word
    return result


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EngineError(message)


def _number(value: object) -> int:
    if type(value) is int:
        return value
    if isinstance(value, str) and value.startswith("0x"):
        try:
            return int(value, 16)
        except ValueError:
            pass
    raise EngineError("Invalid number in the OSD catalog.")


def _diff(before: bytes, after: bytes) -> list[dict]:
    """Contiguous windows of bytes that actually differ, independently scanned."""
    _require(len(before) == len(after), "The patch changed the image size.")
    result, start = [], None
    for offset, (a, b) in enumerate(zip(before, after)):
        if a != b and start is None:
            start = offset
        if a == b and start is not None:
            result.append({"offset": start, "end_exclusive": offset,
                           "before_hex": before[start:offset].hex(),
                           "after_hex": after[start:offset].hex()})
            start = None
    if start is not None:
        result.append({"offset": start, "end_exclusive": len(before),
                       "before_hex": before[start:].hex(), "after_hex": after[start:].hex()})
    return result


class Engine:
    def __init__(self, workspace: str | Path | None = None):
        self.workspace = Path(workspace or Path(__file__).resolve().parent.parent).resolve()
        self.source_path = self.workspace / ROM_NAME
        self.editor_dir = self.workspace / "LG_REVERSE_LAB_EDITOR"
        self.outputs_dir = self.editor_dir / "outputs"
        self.catalog_path = self.workspace / "AUDITORIA_ROM" / "recursos_osd" / "osd_strings.json"
        try:
            self._original = self.source_path.read_bytes()
            metadata = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise EngineError(f"Could not open the ROM and local catalog: {exc}") from exc
        _require(len(self._original) == EXPECTED_SIZE and sha256(self._original) == EXPECTED_SHA256,
                 "The original ROM does not match the SHA-256 authorized for this editor.")
        _require(xor32(self._original) == 0, "The original ROM has an invalid XOR32 checksum.")
        self._records: dict[tuple[int, int], dict] = {}
        self._languages = self._parse_and_validate(metadata)

    def _parse_and_validate(self, metadata: dict) -> list[dict]:
        """Derive addresses/run boundaries from ROM, then compare catalog claims."""
        b = self._original

        def u32(offset: int) -> int:
            _require(0 <= offset <= len(b) - 4, "OSD pointer is outside the image.")
            return struct.unpack_from("<I", b, offset)[0]

        _require(isinstance(metadata, dict), "Invalid OSD catalog.")
        _require(metadata.get("rom_sha256") == EXPECTED_SHA256, "The catalog belongs to a different ROM.")
        _require(b[TEXT_BASE:TEXT_BASE + 12] == b"MTKOSD0.100.", "Unexpected OSD header.")
        directory = TEXT_BASE + u32(TEXT_BASE + 12)
        count = u32(directory)
        _require(count == 25, "Unexpected language count in the ROM.")
        _require(_number(metadata.get("base")) == TEXT_BASE and
                 _number(metadata.get("directory")) == directory and
                 metadata.get("language_count") == count and
                 metadata.get("records_total") == count * 542,
                 "The catalog differs from the original OSD directory.")
        languages = metadata.get("languages")
        _require(isinstance(languages, list) and len(languages) == count, "Invalid language list.")
        heads = [TEXT_BASE + u32(directory + 4 + i * 4) for i in range(count)]
        payloads = [TEXT_BASE + u32(directory + 4 + count * 4 + i * 4) for i in range(count)]
        _require(heads == sorted(set(heads)) and heads[0] == TEXT_BASE + 16 and heads[-1] < directory,
                 "Inconsistent OSD table bounds.")
        parsed_languages = []
        occupied = []
        for language, head in enumerate(heads):
            meta = languages[language]
            _require(isinstance(meta, dict) and meta.get("index") == language,
                     "Incorrect language index in the catalog.")
            n = u32(head)
            _require(n == 542, "Unexpected text count in the ROM.")
            payload = head + 4 + n * 4
            limit = heads[language + 1] if language + 1 < count else directory
            _require(head < payload == payloads[language] < limit,
                     "OSD table and payload pointers differ.")
            offsets = [u32(head + 4 + i * 4) for i in range(n)]
            _require(offsets[0] == 0 and offsets == sorted(set(offsets)),
                     "Duplicate or unsorted OSD offsets.")
            meta_records = meta.get("records")
            _require(isinstance(meta_records, list) and len(meta_records) == n and
                     meta.get("count") == n and _number(meta.get("head_offset")) == head and
                     _number(meta.get("payload_offset")) == payload,
                     "The catalog language table differs from the ROM.")
            parsed_records = []
            for ident, off in enumerate(offsets):
                start = payload + off
                _require(payload <= start < limit, "OSD record is outside its table.")
                total, cursor, accumulated, runs = b[start], start + 1, 0, []
                while accumulated < total or not runs:
                    _require(cursor + 2 <= limit, "Truncated OSD run header.")
                    run_count, bank = b[cursor:cursor + 2]
                    glyph_start = cursor + 2
                    cursor = glyph_start + run_count
                    accumulated += run_count
                    _require(cursor <= limit and accumulated <= total and
                             (run_count > 0 or total == 0), "Invalid OSD run.")
                    glyphs = b[glyph_start:cursor]
                    runs.append({"count": run_count, "bank": bank, "glyph_hex": glyphs.hex(),
                                 "ascii_font0": glyphs.decode("latin-1") if bank == 0 else None})
                _require(accumulated == total, "Inconsistent OSD run length.")
                if ident + 1 < n:
                    _require(cursor == payload + offsets[ident + 1], "OSD record overlaps or leaves a gap.")
                projection = "".join(r["ascii_font0"] if r["bank"] == 0 else
                                     f"<bank{r['bank']}:{r['glyph_hex']}>" for r in runs)
                m = meta_records[ident]
                _require(isinstance(m, dict) and m.get("id") == ident and
                         _number(m.get("file_offset")) == start and
                         _number(m.get("end_exclusive")) == cursor and m.get("glyph_count") == total and
                         m.get("runs") == runs and m.get("text_font0_projection") == projection,
                         f"The catalog differs from the original bytes: language {language}, entry {ident}.")
                editable = len(runs) == 1 and runs[0]["bank"] == 0 and total > 0
                reason = "" if editable else (
                    "Empty text" if total == 0 else "Text uses multiple runs or another font")
                if editable and 0xFF in bytes.fromhex(runs[0]["glyph_hex"]):
                    editable, reason = False, "Text contains the dynamic marker 0xFF"
                record = {"id": ident, "id_hex": f"0x{ident:03X}",
                          "text": projection.replace("@", " ") if editable else projection,
                          "raw_text": projection,
                          "max_length": total, "editable": editable, "reason": reason,
                          "offset": start, "end_exclusive": cursor,
                          "glyph_offset": start + 3 if editable else None,
                          "original_hex": b[start:cursor].hex()}
                self._records[language, ident] = record
                parsed_records.append(record)
                occupied.append((start, cursor))
            _require((cursor + 3) & ~3 == limit and _number(meta.get("end_exclusive")) == cursor,
                     "Inconsistent OSD table end.")
            parsed_languages.append({"index": language,
                                     "label": str(meta.get("label_inference", f"Language {language}")),
                                     "records": parsed_records})
        occupied.sort()
        _require(all(a[1] <= z[0] for a, z in zip(occupied, occupied[1:])),
                 "OSD records overlap.")
        return parsed_languages

    def catalog(self) -> dict:
        # A detached copy prevents callers from weakening patch boundaries.
        return json.loads(json.dumps({
            "original": {"path": str(self.source_path), "name": ROM_NAME,
                         "sha256": EXPECTED_SHA256, "size": EXPECTED_SIZE,
                         "checksum_xor32": "00000000"},
            "languages": self._languages, "language_count": 25, "records_total": 13550,
            "outputs_dir": str(self.outputs_dir),
            "preview_only": True,
            "encoding": OSD_ENCODING,
            "constraints": "One run, font 0, printable Latin-1 text without 0xFF or literal @; spaces and padding use glyph 0x40."
        }, ensure_ascii=False))

    def prepare_edit(self, edit: dict) -> dict:
        """Validate one edit without writing; JSON-ready bytes and record metadata."""
        _require(isinstance(edit, dict) and set(edit) == {"language", "id", "text"},
                 "Each change accepts only language, id, and text; paths and offsets are forbidden.")
        language, ident, text = edit["language"], edit["id"], edit["text"]
        _require(type(language) is int and type(ident) is int and isinstance(text, str),
                 "Language and ID must be integers, and text must be a string.")
        record = self._records.get((language, ident))
        _require(record is not None, "Language or text ID does not exist.")
        _require(record["editable"], "Read-only record: " + record["reason"])
        _require(bool(text) and text.isprintable(), "Use printable text without control characters or line breaks.")
        _require("@" not in text,
                 "The literal @ symbol is unsupported: byte 0x40 represents a space in this OSD. Type a normal space.")
        try:
            raw = text.replace(" ", "@").encode("latin-1")
        except UnicodeEncodeError as exc:
            raise EngineError("Text must use Latin-1 characters.") from exc
        _require(0xFF not in raw, "Byte 0xFF is reserved for dynamic content in this OSD.")
        _require(len(raw) <= record["max_length"],
                 f"The text exceeds this record limit of {record['max_length']} characters.")
        raw = raw.ljust(record["max_length"], b"@")
        a, z = record["glyph_offset"], record["end_exclusive"]
        before = self._original[a:z]
        _require(self._original[record["offset"]:z].hex() == record["original_hex"] and
                 len(before) == len(raw) and a >= RESOURCES_START and z <= len(self._original) - 4,
                 "The original OSD window bytes or bounds are invalid.")
        _require(raw != before, "The change does not modify the original bytes.")
        return {"language": language, "id": ident, "id_hex": f"0x{ident:03X}",
                "original_text": record["text"], "original_raw_text": record["raw_text"],
                "requested_text": text, "stored_text": raw.decode("latin-1"),
                "stored_display_text": raw.decode("latin-1").replace("@", " "),
                "offset": a, "end_exclusive": z,
                "before_hex": before.hex(), "after_hex": raw.hex(),
                "record": dict(record)}

    def restore_bytes(self, preview: bytes, restore: dict) -> bytes:
        """Validate and apply a generated inverse patch in memory only."""
        _require(isinstance(preview, bytes) and isinstance(restore, dict), "Invalid restoration data.")
        _require(len(preview) == EXPECTED_SIZE and restore.get("size") == EXPECTED_SIZE and
                 restore.get("source_sha256") == EXPECTED_SHA256 and
                 restore.get("preview_sha256") == sha256(preview), "Invalid restoration hash.")
        patches = restore.get("inverse_patches")
        _require(isinstance(patches, list) and patches, "Empty inverse patch.")
        restored = bytearray(preview)
        previous_end = -1
        for p in patches:
            _require(isinstance(p, dict) and type(p.get("offset")) is int,
                     "Invalid restoration window.")
            try:
                expected, original = bytes.fromhex(p["expected_hex"]), bytes.fromhex(p["restore_hex"])
            except (KeyError, TypeError, ValueError) as exc:
                raise EngineError("Invalid restoration bytes.") from exc
            start, end = p["offset"], p["offset"] + len(original)
            _require(len(expected) == len(original) > 0 and previous_end <= start < end <= len(preview),
                     "Restoration windows overlap or extend outside the image.")
            _require(bytes(restored[start:end]) == expected, "The restoration window does not match the manifest.")
            restored[start:end] = original
            previous_end = end
        result = bytes(restored)
        _require(result == self._original and sha256(result) == EXPECTED_SHA256,
                 "Restoration did not recover the original ROM byte for byte.")
        return result

    def build(self, edits: list[dict]) -> dict:
        _require(isinstance(edits, list) and 1 <= len(edits) <= 13550,
                 "Select at least one OSD text change.")
        _require(self.source_path.read_bytes() == self._original,
                 "The original ROM changed after the editor was opened.")
        patched = bytearray(self._original)
        seen, changes, windows = set(), [], []
        for edit in edits:
            change = self.prepare_edit(edit)
            key = (change["language"], change["id"])
            _require(key not in seen, "The same text was selected more than once.")
            seen.add(key)
            change.pop("record")
            a, z = change["offset"], change["end_exclusive"]
            windows.append((a, z))
            patched[a:z] = bytes.fromhex(change["after_hex"])
            changes.append(change)
        windows.sort()
        changes.sort(key=lambda change: (change["language"], change["id"]))
        _require(all(a[1] <= z[0] for a, z in zip(windows, windows[1:])), "Overlapping edit windows.")
        struct.pack_into("<I", patched, len(patched) - 4, xor32(patched[:-4]))
        output = bytes(patched)
        diff = _diff(self._original, output)
        allowed = windows + [(len(output) - 4, len(output))]
        _require(all(any(a <= d["offset"] and d["end_exclusive"] <= z for a, z in allowed) for d in diff),
                 "Changes were detected outside the authorized windows.")
        _require(output[:RESOURCES_START] == self._original[:RESOURCES_START],
                 "8051, ARM, or DSP code was changed.")
        _require(len(output) == EXPECTED_SIZE and xor32(output) == 0, "Size or checksum validation failed.")
        digest = sha256(output)
        restore = {"schema": "lg-osd-inverse-v1", "size": EXPECTED_SIZE,
                   "source_sha256": EXPECTED_SHA256, "preview_sha256": digest,
                   "inverse_patches": [{"offset": d["offset"], "expected_hex": d["after_hex"],
                                        "restore_hex": d["before_hex"]} for d in diff]}
        restored = self.restore_bytes(output, restore)
        validation = {"original_sha256_verified": True, "catalog_verified_against_rom": True,
                      "same_size": True, "xor32_zero": True, "only_osd_and_checksum_changed": True,
                      "code_8051_arm_dsp_unchanged": True, "inverse_restores_exact_original": True,
                      "restored_sha256": sha256(restored),
                      "changed_bytes": sum(d["end_exclusive"] - d["offset"] for d in diff)}
        name = f"LG_LAB_{digest}.preview.bin"
        manifest_name = f"LG_LAB_{digest}.manifest.json"
        restore_name = f"LG_LAB_{digest}.restore.json"
        # Resolve every parent to prevent output symlinks redirecting a write.
        self.editor_dir.mkdir(parents=True, exist_ok=True)
        _require(self.editor_dir.resolve() == self.workspace / "LG_REVERSE_LAB_EDITOR",
                 "The editor directory cannot redirect to another location.")
        self.outputs_dir.mkdir(exist_ok=True)
        _require(self.outputs_dir.resolve() == self.editor_dir.resolve() / "outputs",
                 "The outputs directory cannot redirect to another location.")
        paths = {"path": str(self.outputs_dir / name),
                 "manifest_path": str(self.outputs_dir / manifest_name),
                 "restore_manifest_path": str(self.outputs_dir / restore_name)}
        manifest = {"schema": "lg-osd-preview-v1", "preview_only": True,
                    "encoding": dict(OSD_ENCODING),
                    "original_path": str(self.source_path), "original_sha256": EXPECTED_SHA256,
                    "original_size": EXPECTED_SIZE, "name": name, "sha256": digest,
                    **paths, "validation": validation, "changes": changes,
                    "allowed_windows": [{"offset": a, "end_exclusive": z} for a, z in allowed],
                    "raw_diff": diff, "restore_manifest": restore_name,
                    "checksum": {"offset": len(output) - 4,
                                 "before_le_hex": self._original[-4:].hex(),
                                 "after_le_hex": output[-4:].hex()}}
        encoded = lambda value: (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        artifacts = [(Path(paths["path"]), output), (Path(paths["manifest_path"]), encoded(manifest)),
                     (Path(paths["restore_manifest_path"]), encoded(restore))]
        for path, content in artifacts:
            _require(not path.is_symlink(), "An output file cannot be a symbolic link.")
            if path.exists():
                _require(path.read_bytes() == content, "A different artifact already exists with the calculated name.")
        for path, content in artifacts:
            if not path.exists():
                try:
                    with path.open("xb") as handle:
                        handle.write(content)
                except FileExistsError as exc:
                    raise EngineError("Another process created the same artifact during export.") from exc
        _require(all(path.read_bytes() == content for path, content in artifacts),
                 "Exported artifacts read back differently from the patch and manifests.")
        _require(self.source_path.read_bytes() == self._original, "The original ROM changed during export.")
        return {"name": name, "sha256": digest, **paths, "validation": validation,
                "changes": changes, "raw_diff": diff, "restore_manifest": restore}
