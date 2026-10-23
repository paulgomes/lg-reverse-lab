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
        raise EngineError("O tamanho da imagem não é múltiplo de quatro bytes.")
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
    raise EngineError("Número inválido no catálogo OSD.")


def _diff(before: bytes, after: bytes) -> list[dict]:
    """Contiguous windows of bytes that actually differ, independently scanned."""
    _require(len(before) == len(after), "O patch alterou o tamanho da imagem.")
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
            raise EngineError(f"Não foi possível abrir a ROM e o catálogo local: {exc}") from exc
        _require(len(self._original) == EXPECTED_SIZE and sha256(self._original) == EXPECTED_SHA256,
                 "A ROM original não corresponde ao SHA-256 autorizado para este editor.")
        _require(xor32(self._original) == 0, "O checksum XOR32 da ROM original é inválido.")
        self._records: dict[tuple[int, int], dict] = {}
        self._languages = self._parse_and_validate(metadata)

    def _parse_and_validate(self, metadata: dict) -> list[dict]:
        """Derive addresses/run boundaries from ROM, then compare catalog claims."""
        b = self._original

        def u32(offset: int) -> int:
            _require(0 <= offset <= len(b) - 4, "Ponteiro OSD fora da imagem.")
            return struct.unpack_from("<I", b, offset)[0]

        _require(isinstance(metadata, dict), "Catálogo OSD inválido.")
        _require(metadata.get("rom_sha256") == EXPECTED_SHA256, "O catálogo pertence a outra ROM.")
        _require(b[TEXT_BASE:TEXT_BASE + 12] == b"MTKOSD0.100.", "Cabeçalho OSD inesperado.")
        directory = TEXT_BASE + u32(TEXT_BASE + 12)
        count = u32(directory)
        _require(count == 25, "Quantidade inesperada de idiomas na ROM.")
        _require(_number(metadata.get("base")) == TEXT_BASE and
                 _number(metadata.get("directory")) == directory and
                 metadata.get("language_count") == count and
                 metadata.get("records_total") == count * 542,
                 "O catálogo diverge do diretório OSD original.")
        languages = metadata.get("languages")
        _require(isinstance(languages, list) and len(languages) == count, "Lista de idiomas inválida.")
        heads = [TEXT_BASE + u32(directory + 4 + i * 4) for i in range(count)]
        payloads = [TEXT_BASE + u32(directory + 4 + count * 4 + i * 4) for i in range(count)]
        _require(heads == sorted(set(heads)) and heads[0] == TEXT_BASE + 16 and heads[-1] < directory,
                 "Limites das tabelas OSD inconsistentes.")
        parsed_languages = []
        occupied = []
        for language, head in enumerate(heads):
            meta = languages[language]
            _require(isinstance(meta, dict) and meta.get("index") == language,
                     "Índice de idioma incorreto no catálogo.")
            n = u32(head)
            _require(n == 542, "Quantidade inesperada de textos na ROM.")
            payload = head + 4 + n * 4
            limit = heads[language + 1] if language + 1 < count else directory
            _require(head < payload == payloads[language] < limit,
                     "Ponteiros de tabela e conteúdo OSD divergem.")
            offsets = [u32(head + 4 + i * 4) for i in range(n)]
            _require(offsets[0] == 0 and offsets == sorted(set(offsets)),
                     "Offsets OSD duplicados ou fora de ordem.")
            meta_records = meta.get("records")
            _require(isinstance(meta_records, list) and len(meta_records) == n and
                     meta.get("count") == n and _number(meta.get("head_offset")) == head and
                     _number(meta.get("payload_offset")) == payload,
                     "A tabela de idioma do catálogo diverge da ROM.")
            parsed_records = []
            for ident, off in enumerate(offsets):
                start = payload + off
                _require(payload <= start < limit, "Registro OSD fora de sua tabela.")
                total, cursor, accumulated, runs = b[start], start + 1, 0, []
                while accumulated < total or not runs:
                    _require(cursor + 2 <= limit, "Cabeçalho de corrida OSD truncado.")
                    run_count, bank = b[cursor:cursor + 2]
                    glyph_start = cursor + 2
                    cursor = glyph_start + run_count
                    accumulated += run_count
                    _require(cursor <= limit and accumulated <= total and
                             (run_count > 0 or total == 0), "Corrida OSD inválida.")
                    glyphs = b[glyph_start:cursor]
                    runs.append({"count": run_count, "bank": bank, "glyph_hex": glyphs.hex(),
                                 "ascii_font0": glyphs.decode("latin-1") if bank == 0 else None})
                _require(accumulated == total, "Tamanho das corridas OSD inconsistente.")
                if ident + 1 < n:
                    _require(cursor == payload + offsets[ident + 1], "Registro OSD sobreposto ou com lacuna.")
                projection = "".join(r["ascii_font0"] if r["bank"] == 0 else
                                     f"<bank{r['bank']}:{r['glyph_hex']}>" for r in runs)
                m = meta_records[ident]
                _require(isinstance(m, dict) and m.get("id") == ident and
                         _number(m.get("file_offset")) == start and
                         _number(m.get("end_exclusive")) == cursor and m.get("glyph_count") == total and
                         m.get("runs") == runs and m.get("text_font0_projection") == projection,
                         f"O catálogo diverge dos bytes originais: idioma {language}, texto {ident}.")
                editable = len(runs) == 1 and runs[0]["bank"] == 0 and total > 0
                reason = "" if editable else (
                    "Texto vazio" if total == 0 else "Texto com várias corridas ou outra fonte")
                if editable and 0xFF in bytes.fromhex(runs[0]["glyph_hex"]):
                    editable, reason = False, "Texto contém marcador dinâmico 0xFF"
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
                     "Fim de tabela OSD inconsistente.")
            parsed_languages.append({"index": language,
                                     "label": str(meta.get("label_inference", f"Idioma {language}")),
                                     "records": parsed_records})
        occupied.sort()
        _require(all(a[1] <= z[0] for a, z in zip(occupied, occupied[1:])),
                 "Há sobreposição entre registros OSD.")
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
            "constraints": "Uma corrida, fonte 0, texto Latin-1 imprimível sem 0xFF ou @ literal; espaço e preenchimento usam o glifo 0x40."
        }, ensure_ascii=False))

    def prepare_edit(self, edit: dict) -> dict:
        """Validate one edit without writing; JSON-ready bytes and record metadata."""
        _require(isinstance(edit, dict) and set(edit) == {"language", "id", "text"},
                 "Cada alteração aceita apenas language, id e text; caminhos e offsets são proibidos.")
        language, ident, text = edit["language"], edit["id"], edit["text"]
        _require(type(language) is int and type(ident) is int and isinstance(text, str),
                 "Idioma e ID devem ser números inteiros, e o texto deve ser uma string.")
        record = self._records.get((language, ident))
        _require(record is not None, "Idioma ou ID de texto inexistente.")
        _require(record["editable"], "Registro não editável: " + record["reason"])
        _require(bool(text) and text.isprintable(), "Use texto imprimível, sem controles ou quebras de linha.")
        _require("@" not in text,
                 "O símbolo @ literal não é suportado: o byte 0x40 representa espaço nesta OSD. Digite um espaço normal.")
        try:
            raw = text.replace(" ", "@").encode("latin-1")
        except UnicodeEncodeError as exc:
            raise EngineError("O texto precisa usar caracteres Latin-1.") from exc
        _require(0xFF not in raw, "O byte 0xFF é reservado a conteúdo dinâmico nesta OSD.")
        _require(len(raw) <= record["max_length"],
                 f"O texto excede o limite de {record['max_length']} caracteres deste registro.")
        raw = raw.ljust(record["max_length"], b"@")
        a, z = record["glyph_offset"], record["end_exclusive"]
        before = self._original[a:z]
        _require(self._original[record["offset"]:z].hex() == record["original_hex"] and
                 len(before) == len(raw) and a >= RESOURCES_START and z <= len(self._original) - 4,
                 "Os bytes ou limites originais da janela OSD são inválidos.")
        _require(raw != before, "A alteração não modifica os bytes originais.")
        return {"language": language, "id": ident, "id_hex": f"0x{ident:03X}",
                "original_text": record["text"], "original_raw_text": record["raw_text"],
                "requested_text": text, "stored_text": raw.decode("latin-1"),
                "stored_display_text": raw.decode("latin-1").replace("@", " "),
                "offset": a, "end_exclusive": z,
                "before_hex": before.hex(), "after_hex": raw.hex(),
                "record": dict(record)}

    def restore_bytes(self, preview: bytes, restore: dict) -> bytes:
        """Validate and apply a generated inverse patch in memory only."""
        _require(isinstance(preview, bytes) and isinstance(restore, dict), "Dados de restauração inválidos.")
        _require(len(preview) == EXPECTED_SIZE and restore.get("size") == EXPECTED_SIZE and
                 restore.get("source_sha256") == EXPECTED_SHA256 and
                 restore.get("preview_sha256") == sha256(preview), "Hash de restauração inválido.")
        patches = restore.get("inverse_patches")
        _require(isinstance(patches, list) and patches, "Patch inverso vazio.")
        restored = bytearray(preview)
        previous_end = -1
        for p in patches:
            _require(isinstance(p, dict) and type(p.get("offset")) is int,
                     "Janela de restauração inválida.")
            try:
                expected, original = bytes.fromhex(p["expected_hex"]), bytes.fromhex(p["restore_hex"])
            except (KeyError, TypeError, ValueError) as exc:
                raise EngineError("Bytes de restauração inválidos.") from exc
            start, end = p["offset"], p["offset"] + len(original)
            _require(len(expected) == len(original) > 0 and previous_end <= start < end <= len(preview),
                     "Janelas de restauração sobrepostas ou fora da imagem.")
            _require(bytes(restored[start:end]) == expected, "A janela a restaurar não coincide com o manifesto.")
            restored[start:end] = original
            previous_end = end
        result = bytes(restored)
        _require(result == self._original and sha256(result) == EXPECTED_SHA256,
                 "A restauração não recuperou a ROM original byte a byte.")
        return result

    def build(self, edits: list[dict]) -> dict:
        _require(isinstance(edits, list) and 1 <= len(edits) <= 13550,
                 "Escolha ao menos uma alteração de texto OSD.")
        _require(self.source_path.read_bytes() == self._original,
                 "A ROM original foi alterada após abrir o editor.")
        patched = bytearray(self._original)
        seen, changes, windows = set(), [], []
        for edit in edits:
            change = self.prepare_edit(edit)
            key = (change["language"], change["id"])
            _require(key not in seen, "O mesmo texto foi selecionado mais de uma vez.")
            seen.add(key)
            change.pop("record")
            a, z = change["offset"], change["end_exclusive"]
            windows.append((a, z))
            patched[a:z] = bytes.fromhex(change["after_hex"])
            changes.append(change)
        windows.sort()
        changes.sort(key=lambda change: (change["language"], change["id"]))
        _require(all(a[1] <= z[0] for a, z in zip(windows, windows[1:])), "Janelas de edição sobrepostas.")
        struct.pack_into("<I", patched, len(patched) - 4, xor32(patched[:-4]))
        output = bytes(patched)
        diff = _diff(self._original, output)
        allowed = windows + [(len(output) - 4, len(output))]
        _require(all(any(a <= d["offset"] and d["end_exclusive"] <= z for a, z in allowed) for d in diff),
                 "Foram detectadas alterações fora das janelas autorizadas.")
        _require(output[:RESOURCES_START] == self._original[:RESOURCES_START],
                 "O código 8051, ARM ou DSP foi alterado.")
        _require(len(output) == EXPECTED_SIZE and xor32(output) == 0, "Falha ao validar tamanho ou checksum.")
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
                 "A pasta do editor não pode redirecionar para outro local.")
        self.outputs_dir.mkdir(exist_ok=True)
        _require(self.outputs_dir.resolve() == self.editor_dir.resolve() / "outputs",
                 "A pasta outputs não pode redirecionar para outro local.")
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
            _require(not path.is_symlink(), "Um arquivo de saída não pode ser um link simbólico.")
            if path.exists():
                _require(path.read_bytes() == content, "Já existe um artefato diferente com o nome calculado.")
        for path, content in artifacts:
            if not path.exists():
                try:
                    with path.open("xb") as handle:
                        handle.write(content)
                except FileExistsError as exc:
                    raise EngineError("Outro processo criou o mesmo artefato durante a exportação.") from exc
        _require(all(path.read_bytes() == content for path, content in artifacts),
                 "A releitura dos artefatos exportados não coincide com o patch e os manifestos.")
        _require(self.source_path.read_bytes() == self._original, "A ROM original mudou durante a exportação.")
        return {"name": name, "sha256": digest, **paths, "validation": validation,
                "changes": changes, "raw_diff": diff, "restore_manifest": restore}
