# Architecture and formats

LG Reverse Lab separates three activities: editing text on the computer, reconstructing an experimental image from a delta, and recording observations of USB media. None provides remote control of the LG over USB.

## File flow

```text
User-supplied original ROM
  ├─ prepare_catalogs.py → local catalogs → OSD editor → preview + manifests
  └─ firmware_patch.py + published delta → Clara native458.preview.bin

USB Scout on the computer
  → before inventory → media test on the LG → after inventory + observations
```

The reference image is 2,091,376 bytes with SHA-256 `27adf86b93e5e7347fbd7d12837e32a3394243a75e025d2b188e1afd5151c00a`. The parsers and delta target this specific image, not the entire HT306 family.

## Editor and local catalogs

`tools/prepare_catalogs.py` validates the source size, SHA-256, and XOR32 before interpreting the OSD directories. It generates `osd_strings.json` and `fontes.json` in `AUDITORIA_ROM/recursos_osd/`, including resource bounds and metadata needed by the editor. These files are derived from the ROM and remain outside the publication.

The source text directory contains 25 tables with 542 records each: 13,550 records in total. There are 15 fonts. Not every table can be treated as ordinary Unicode text; some language labels are inferences, and certain sequences use glyph banks or dynamic values.

The `LG_REVERSE_LAB_EDITOR/engine.py` engine checks the metadata against the ROM bounds and bytes. Allowed edits preserve the space reserved for each record and recalculate the XOR32 footer. In the supported Latin bank, a typed space is encoded as `@` (`0x40`), matching the source OSD text. A literal `@` is not an editing option.

The server uses the computer's loopback interface. `glyph_preview.py` reads glyphs from the supplied ROM and uses Pillow for the preview. Its palette is a reference; a PC-generated image does not establish the palette, timing, or video output on the device.

## Experimental Clara native458 delta

`tools/firmware_patch.py` uses the `lg-reverse-lab-xor-v1` format. The JSON contains the size, source, target, and delta hashes, metadata, and the XOR delta compressed with zlib and encoded as base64. Applying the patch requires the exact source; reversing it requires the exact target. Output is accepted only if its final hash matches the expected value. The writer creates a new file ending in `.preview.bin` and does not overwrite files.

The published delta reconstructs image `c5183ed34966bee321abaccd14f26d3236fcff20166dd97a54e94380cbfa86e1`. It does not contain a complete ROM, but it remains specific to proprietary firmware. Publishing the delta grants no rights to that firmware.

The Clara candidate retains the native engine and its drawing commands:

- Native window 12 at 720 × 458 with the factory palette.
- Two MTG crops for the top and bottom composition, drawn with native command `32`.
- Direct USB menu display, without the experimental cover that waited for an animation to finish.
- 403 unique MTGs; 15 fonts; font 0 with 434 glyphs in explicit RLE and read guards.
- Static WYS CORP opening and six preserved screensaver frames.

The change removes a display dependency observed in the code and preserves the Clara composition. This is a corrective hypothesis supported by PC tests; the visual result of this image on the LG still needs to be observed. The interface implements neither HTML, touch input, iOS blur, a GIF decoder, nor an animated opening during USB reading.

## Logical visibility and physical output

Marking a window as visible in software state does not establish that it reached the video output. Earlier tests did not execute the native `204AE` commit path; a computer compositor could display a window that the device had not necessarily sent to the screen.

The candidate review includes execution of this commit and MMIO writes in two video modes. This improves coverage of the display path, but it is still controlled execution on a computer. It does not measure the component signal, actual colors, timing, installed flash contents, or every peripheral's behavior.

## Scout

Scout runs on the computer using Python's standard library, with Tkinter for the graphical interface. It compares files by path, size, and hash where applicable, records manual observations, and exports a session ZIP. Optional capture and local summary features require additional setup.

The USB drive carries media and results. It is not a debugging channel: Scout does not read RAM, EEPROM, registers, or the LG's installed firmware, and does not inject commands or install an image. The screen and audio require external observation.
