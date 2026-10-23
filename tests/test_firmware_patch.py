import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('firmware_patch', Path(__file__).resolve().parents[1] / 'tools/firmware_patch.py')
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


class FirmwarePatchTests(unittest.TestCase):
    def setUp(self):
        self.source = bytes(range(256)) * 8
        self.target = self.source[:30] + b'CLARA' + self.source[35:-4] + b'WYS!'
        self.patch = p.make_patch(self.source, self.target)

    def test_round_trip(self):
        self.assertEqual(p.apply_patch(self.source, self.patch), self.target)
        self.assertEqual(p.apply_patch(self.target, self.patch, reverse=True), self.source)

    def test_wrong_image_rejected(self):
        with self.assertRaises(p.PatchError):
            p.apply_patch(b'?' * len(self.source), self.patch)

    def test_wrong_output_hash_rejected(self):
        patch = copy.deepcopy(self.patch)
        patch['target_sha256'] = '0' * 64
        with self.assertRaises(p.PatchError):
            p.apply_patch(self.source, patch)

    def test_bad_delta_rejected(self):
        patch = copy.deepcopy(self.patch)
        patch['delta_sha256'] = '0' * 64
        with self.assertRaises(p.PatchError):
            p.decode_delta(patch)

    def test_truncated_compression_rejected(self):
        patch = copy.deepcopy(self.patch)
        packed = p.base64.b64decode(patch['delta'])
        patch['delta'] = p.base64.b64encode(packed[:-2]).decode()
        with self.assertRaises(p.PatchError):
            p.decode_delta(patch)

    def test_expansion_bound(self):
        patch = copy.deepcopy(self.patch)
        patch['image_bytes'] = 1
        with self.assertRaises(p.PatchError):
            p.decode_delta(patch)

    def test_never_overwrites(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'result.preview.bin'
            p.write_new(out, self.source)
            with self.assertRaises(FileExistsError):
                p.write_new(out, self.target)
            self.assertEqual(out.read_bytes(), self.source)

    def test_published_patch_is_experimental(self):
        root = Path(__file__).resolve().parents[1]
        patch = p.json.loads((root / 'patches/clara-native458-c5183ed34966.lgpatch.json').read_text())
        self.assertEqual(len(p.decode_delta(patch)), 2091376)
        self.assertFalse(patch['metadata']['hardware_validated'])
        self.assertEqual(patch['target_sha256'], 'c5183ed34966bee321abaccd14f26d3236fcff20166dd97a54e94380cbfa86e1')


if __name__ == '__main__':
    unittest.main()
