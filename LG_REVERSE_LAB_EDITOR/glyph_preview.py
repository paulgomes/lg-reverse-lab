"""Render extracted firmware glyphs. Palette is a documented reference only."""
from functools import lru_cache
from io import BytesIO
import hashlib
import json
from pathlib import Path
from PIL import Image


class GlyphPreview:
    def __init__(self, workspace, original, expected_sha):
        if hashlib.sha256(original).hexdigest() != expected_sha:
            raise ValueError('A imagem usada pela prévia não corresponde à fonte verificada.')
        self.raw = original
        resources = Path(workspace) / 'AUDITORIA_ROM' / 'recursos_osd'
        meta = json.loads((resources / 'fontes.json').read_text(encoding='utf-8'))
        strings = json.loads((resources / 'osd_strings.json').read_text(encoding='utf-8'))
        if meta['rom_sha256'] != expected_sha or strings['rom_sha256'] != expected_sha:
            raise ValueError('As fontes extraídas pertencem a outra imagem.')
        self.fonts = meta['fonts']
        self.banks = meta['bank_map']
        self.records = {(lang['index'], rec['id']): rec
                        for lang in strings['languages'] for rec in lang['records']}
        self.palette = [tuple(color) for color in meta['preview_palette']]

    @lru_cache(maxsize=4096)
    def glyph(self, bank, value):
        if value == 255:
            return Image.new('RGBA', (10, 18), (255, 150, 30, 255))
        mapping = self.banks[str(bank)]
        font = self.fonts[mapping['font_index']]
        glyph = font['glyphs'][mapping['glyph_base'] + value]
        start, end = int(glyph['start'], 16), int(glyph['end_exclusive'], 16)
        if not (int(font['start'], 16) <= start < end <= int(font['end_exclusive'], 16)):
            raise ValueError('Glifo fora dos limites da fonte.')
        if not glyph['complete']:
            return Image.new('RGBA', (glyph['width'], font['height']), (255, 150, 30, 255))
        nibbles = [n for b in self.raw[start:end] for n in (b >> 4, b & 15)]
        pos, pixels = 0, []
        count_needed = glyph['raster_width'] * font['height']
        while len(pixels) < count_needed:
            code = nibbles[pos]
            pos += 1
            if code < 4:
                code = code * 16 + nibbles[pos]
                pos += 1
                if code < 16:
                    code = code * 16 + nibbles[pos]
                    pos += 1
                    if code < 64:
                        code = code * 16 + nibbles[pos]
                        pos += 1
            run, color = code >> 2, code & 3
            if not run:
                run = count_needed - len(pixels)
            pixels.extend([self.palette[color]] * min(run, count_needed - len(pixels)))
        bitmap = Image.new('RGBA', (glyph['raster_width'], font['height']))
        bitmap.putdata(pixels)
        return bitmap.crop((0, 0, glyph['width'], font['height']))

    def compose(self, language, ident, text=None):
        rec = self.records[(language, ident)]
        runs = rec['runs'] if text is None else [{'bank': 0, 'glyph_hex': text.encode('latin-1').hex()}]
        glyphs = [self.glyph(run['bank'], code)
                  for run in runs for code in bytes.fromhex(run['glyph_hex'])]
        width = max(1, sum(g.width for g in glyphs))
        height = max((g.height for g in glyphs), default=18)
        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        x = 0
        for g in glyphs:
            image.alpha_composite(g, (x, height - g.height))
            x += g.width
        return image

    def png(self, language, ident, text=None):
        image = self.compose(language, ident, text)
        # These colors do not assert the palette selected by the installed LG.
        canvas = Image.new('RGBA', (image.width + 24, image.height + 20), '#29384f')
        canvas.alpha_composite(image, (12, 10))
        canvas = canvas.resize((canvas.width * 3, canvas.height * 3), Image.Resampling.NEAREST)
        out = BytesIO()
        canvas.convert('RGB').save(out, format='PNG')
        return out.getvalue()
