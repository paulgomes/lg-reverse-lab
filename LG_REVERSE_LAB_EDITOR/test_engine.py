"""Product-fixture verification; run: python -m unittest -v test_engine.py."""
import copy
import functools
import hashlib
import json
import operator
import struct
import tempfile
import unittest
from pathlib import Path

from engine import Engine, EngineError, EXPECTED_SHA256, ROM_NAME


WORKSPACE = Path(__file__).resolve().parent.parent


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = Engine(WORKSPACE)
        cls.original = (WORKSPACE / ROM_NAME).read_bytes()
        cls.catalog_bytes = (WORKSPACE / "AUDITORIA_ROM/recursos_osd/osd_strings.json").read_bytes()

    def sandbox(self):
        temporary = tempfile.TemporaryDirectory(prefix="lg_osd_engine_")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / ROM_NAME).write_bytes(self.original)
        folder = root / "AUDITORIA_ROM/recursos_osd"
        folder.mkdir(parents=True)
        (folder / "osd_strings.json").write_bytes(self.catalog_bytes)
        return root

    def test_three_programa_edits_exact_product_image_and_inverse(self):
        root = self.sandbox()
        engine = Engine(root)
        edits = [{"language": 6, "id": ident, "text": "LG LAB"} for ident in (157, 223, 289)]
        built = engine.build(edits)
        preview = Path(built["path"]).read_bytes()
        # An independent product fixture: concrete known glyph addresses and
        # checksum using a separate reduction, rather than reusing engine code.
        expected = bytearray(self.original)
        starts = (0x1B6FE0, 0x1B714F, 0x1B73C1)
        for start in starts:
            self.assertEqual(self.original[start:start + 8], b"Programa")
            expected[start:start + 8] = b"LG@LAB@@"
        checksum = functools.reduce(operator.xor, struct.unpack(f"<{(len(expected) - 4) // 4}I", expected[:-4]))
        expected[-4:] = struct.pack("<I", checksum)
        self.assertEqual(preview, bytes(expected))
        self.assertEqual(len(preview), len(self.original))
        self.assertEqual(functools.reduce(operator.xor, struct.unpack(f"<{len(preview) // 4}I", preview)), 0)
        self.assertEqual(preview[:0x147080], self.original[:0x147080])
        actual_positions = {i for i, (a, b) in enumerate(zip(self.original, preview)) if a != b}
        permitted = set(range(len(preview) - 4, len(preview)))
        for start in starts:
            permitted.update(range(start, start + 8))
        self.assertTrue(actual_positions <= permitted)
        self.assertEqual(built["validation"]["changed_bytes"], len(actual_positions))
        self.assertEqual(hashlib.sha256(preview).hexdigest(), built["sha256"])
        self.assertTrue(Path(built["path"]).name.endswith(".preview.bin"))
        self.assertEqual(Path(built["path"]).parent, root / "LG_REVERSE_LAB_EDITOR/outputs")
        self.assertEqual(set(p.name for p in Path(built["path"]).parent.iterdir()),
                         {Path(built[k]).name for k in ("path", "manifest_path", "restore_manifest_path")})
        saved_inverse = json.loads(Path(built["restore_manifest_path"]).read_text(encoding="utf-8"))
        saved_manifest = json.loads(Path(built["manifest_path"]).read_text(encoding="utf-8"))
        self.assertEqual(saved_manifest["encoding"]["space_byte"], "0x40")
        self.assertEqual(saved_manifest["encoding"]["padding_byte"], "0x40")
        self.assertEqual(saved_manifest["changes"][0]["stored_text"], "LG@LAB@@")
        self.assertEqual(saved_manifest["changes"][0]["stored_display_text"], "LG LAB  ")
        self.assertEqual(engine.restore_bytes(preview, saved_inverse), self.original)
        self.assertEqual((root / ROM_NAME).read_bytes(), self.original)
        self.assertEqual(hashlib.sha256((root / ROM_NAME).read_bytes()).hexdigest(), EXPECTED_SHA256)
        self.assertEqual(engine.build(edits)["path"], built["path"], "Identical build must be reproducible")
        self.assertEqual(engine.build(list(reversed(edits)))["path"], built["path"],
                         "Edit order must not change artifacts for the same binary result")
        corrupt = bytearray(preview)
        corrupt[0] ^= 1
        with self.assertRaises(EngineError):
            engine.restore_bytes(bytes(corrupt), saved_inverse)
        overlap = copy.deepcopy(saved_inverse)
        overlap["inverse_patches"].insert(1, copy.deepcopy(overlap["inverse_patches"][0]))
        with self.assertRaises(EngineError):
            engine.restore_bytes(preview, overlap)

    def test_prepare_and_catalog_cannot_mutate_engine_boundaries(self):
        catalog = self.engine.catalog()
        self.assertEqual(len(catalog["languages"]), 25)
        self.assertEqual(sum(len(l["records"]) for l in catalog["languages"]), 13550)
        prepared = self.engine.prepare_edit({"language": 6, "id": 157, "text": "LG LAB"})
        prepared["record"]["glyph_offset"] = 0
        catalog["languages"][6]["records"][157]["glyph_offset"] = 0
        fresh = self.engine.prepare_edit({"language": 6, "id": 157, "text": "LG LAB"})
        self.assertEqual(fresh["offset"], 0x1B6FE0)
        self.assertEqual(fresh["after_hex"], b"LG@LAB@@".hex())
        self.assertEqual(fresh["stored_text"], "LG@LAB@@")
        self.assertEqual(fresh["stored_display_text"], "LG LAB  ")

    def test_canonical_human_spaces_and_unchanged_existing_osd_space(self):
        catalog = self.engine.catalog()
        record = catalog["languages"][6]["records"][97]
        self.assertEqual(record["raw_text"], "Apagar@Tudo")
        self.assertEqual(record["text"], "Apagar Tudo")
        self.assertEqual(catalog["encoding"]["space_byte"], "0x40")
        # Typing the displayed original must recreate the same original bytes,
        # and therefore remain an unchanged edit rather than rewriting spaces.
        with self.assertRaisesRegex(EngineError, "does not modify"):
            self.engine.prepare_edit({"language": 6, "id": 97, "text": record["text"]})
        with self.assertRaisesRegex(EngineError, "literal @ symbol"):
            self.engine.prepare_edit({"language": 6, "id": 97, "text": record["raw_text"]})
        prepared = self.engine.prepare_edit({"language": 6, "id": 97, "text": "LG LAB"})
        self.assertEqual(prepared["before_hex"], b"Apagar@Tudo".hex())
        self.assertEqual(prepared["after_hex"], b"LG@LAB@@@@@".hex())
        self.assertEqual(prepared["original_text"], "Apagar Tudo")
        self.assertEqual(prepared["original_raw_text"], "Apagar@Tudo")
        self.assertEqual(prepared["stored_display_text"], "LG LAB     ")

    def test_reject_invalid_text_and_uneditable_runs(self):
        cases = [
            {"language": 6, "id": 157, "text": "LONGER THAN EIGHT"},
            {"language": 6, "id": 157, "text": "ABC\n"},
            {"language": 6, "id": 157, "text": ""},
            {"language": 6, "id": 157, "text": "\u2603"},
            {"language": 6, "id": 157, "text": "\u00ff"},
            {"language": 6, "id": 157, "text": "Programa"},
            {"language": 0, "id": 0, "text": "EMPTY"},
            {"language": 0, "id": 310, "text": "MIXED"},
            {"language": True, "id": 157, "text": "BOOLEAN"},
            {"language": 25, "id": 157, "text": "BAD"},
            {"language": 6, "id": 542, "text": "BAD"},
            {"language": 6, "id": 157, "text": "BAD", "offset": 0},
            {"language": 6, "id": 157, "text": "BAD", "path": "../../LG_HT306.NEW.ROM"},
        ]
        wrong_font = next((l["index"], r["id"]) for l in self.engine._languages
                          for r in l["records"]
                          if not r["editable"] and r["max_length"] > 0 and r["id"] != 310)
        cases.append({"language": wrong_font[0], "id": wrong_font[1], "text": "BAD"})
        for edit in cases:
            with self.subTest(edit=edit), self.assertRaises(EngineError):
                self.engine.prepare_edit(edit)

    def test_reject_zero_duplicate_edits_and_output_overwrite(self):
        root = self.sandbox()
        engine = Engine(root)
        edit = {"language": 6, "id": 157, "text": "LG LAB"}
        for edits in ([], [edit, edit], "../../output.rom"):
            with self.subTest(edits=edits), self.assertRaises(EngineError):
                engine.build(edits)
        self.assertFalse((root / "LG_REVERSE_LAB_EDITOR/outputs").exists())
        built = engine.build([edit])
        Path(built["path"]).write_bytes(b"unrelated existing contents")
        with self.assertRaises(EngineError):
            engine.build([edit])
        self.assertEqual(Path(built["path"]).read_bytes(), b"unrelated existing contents")

    def test_reject_source_hash_and_mutation_after_load(self):
        root = self.sandbox()
        bad_source = bytearray(self.original)
        bad_source[0] ^= 1
        (root / ROM_NAME).write_bytes(bad_source)
        with self.assertRaises(EngineError):
            Engine(root)
        (root / ROM_NAME).write_bytes(self.original)
        engine = Engine(root)
        (root / ROM_NAME).write_bytes(bad_source)
        with self.assertRaises(EngineError):
            engine.build([{"language": 6, "id": 157, "text": "LG LAB"}])
        self.assertFalse((root / "LG_REVERSE_LAB_EDITOR/outputs").exists())

    def test_catalog_cannot_redirect_osd_patch_to_code_or_false_bytes(self):
        for mode in ("outside", "glyphs", "overlap", "font"):
            with self.subTest(mode=mode):
                root = self.sandbox()
                data = json.loads(self.catalog_bytes)
                record = data["languages"][6]["records"][157]
                if mode == "outside":
                    record["file_offset"], record["end_exclusive"] = "0x1000", "0x100b"
                elif mode == "glyphs":
                    record["runs"][0]["glyph_hex"] = "0000000000000000"
                elif mode == "overlap":
                    record["file_offset"] = data["languages"][6]["records"][156]["file_offset"]
                else:
                    record["runs"][0]["bank"] = 1
                (root / "AUDITORIA_ROM/recursos_osd/osd_strings.json").write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaises(EngineError):
                    Engine(root)


if __name__ == "__main__":
    unittest.main()
