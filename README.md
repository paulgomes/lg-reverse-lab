# LG Reverse Lab

Independent research into the **LG HT306SU-A2**: a local OSD text editor, USB observation tools, and an experimental **Clara Biblioteca / WYS CORP** interface patch.

This repository contains code and a reversible delta. **It does not include the original ROM, a modified ROM ready to install, manuals, personal photos, the original GIF, or complete font and text catalogs.** You must supply your own original image, with the exact SHA-256 below, to reconstruct the preview locally.

## Current status

| Stage | Known result |
| --- | --- |
| Previous experimental firmware `f1c0a95eccb7…` on the device | Static WYS opening visible; USB menu and updater had no picture; audio remained normal, according to the user's report. |
| Corrective candidate `c5183ed34966…` on the PC | Passed 98 MCU cases, 29 ARM checks, and independent review; USB copy verified by reading it back. |
| Corrective candidate `c5183ed34966…` on the LG | **New physical test pending.** PC results do not establish the actual picture on the TV. |

The correction uses the native **720 × 458** window, the factory palette, and menu display that does not depend on the USB entry animation. It retains the Clara composition, with 403 unique MTG images and 15 fonts. The opening remains a static MPEG image; the six WYS screensaver frames were preserved. There is no GIF decoder or animated opening during USB reading.

[Hardware status](docs/hardware-status.md) · [Architecture](docs/architecture.md) · [Testing and limitations](docs/testing.md) · [Validation summary](reports/validation-summary.json) · [Knowledge graph](knowledge/graph.json)

## Available tools

- **`tools/firmware_patch.py`**: inspects, verifies, applies, and reverses the delta, always bound to exact input and output hashes. Writes only a new `.preview.bin` file.
- **`LG_REVERSE_LAB_EDITOR/`**: browses OSD text and generates previews of fixed-size edits, with a manifest and restoration data. Works with the supported original ROM; it is not a complete visual editor for the Clara firmware.
- **`tools/prepare_catalogs.py`**: rebuilds the editor's local catalogs from a user-supplied ROM, without executing firmware.
- **`USB_SCOUT/`**: creates sessions, compares inventories, and collects external observations. Runs on the computer; it does not control the LG or read its internal memory.
- **`lab/osd_parse.py`**: an OSD resource parser for local analysis.

## Get started without firmware

Use **Python 3.11 or later**. The commands below work in PowerShell and common shells with `git` and `python` available. Some installations name the executable `python3`.

```sh
git clone https://github.com/paulgomes/lg-reverse-lab.git
cd lg-reverse-lab
python tools/firmware_patch.py inspect patches/clara-native458-c5183ed34966.lgpatch.json
python -m unittest discover -s tests -p "test_*.py" -v
python -m unittest discover -s USB_SCOUT/tests -p "test_scout.py" -v
```

Delta inspection and the public tests with synthetic data require neither a ROM nor a connected device. Scout's graphical interface requires Python with **Tkinter**; the editor's font preview uses **Pillow**, declared in `requirements.txt`.

## Reconstruct the experimental preview

The delta accepts only this original image:

```text
Reference file: LG_HT306LD1_1107200.rom
Size: 2,091,376 bytes
SHA-256: 27adf86b93e5e7347fbd7d12837e32a3394243a75e025d2b188e1afd5151c00a
```

Place your copy of this ROM in the project root. The program verifies the contents by hash; renaming another ROM does not make it compatible.

```sh
python -c "from pathlib import Path; Path('local').mkdir(exist_ok=True)"
python tools/firmware_patch.py verify patches/clara-native458-c5183ed34966.lgpatch.json LG_HT306LD1_1107200.rom
python tools/firmware_patch.py apply patches/clara-native458-c5183ed34966.lgpatch.json LG_HT306LD1_1107200.rom local/clara-native458.preview.bin
```

The expected output has the same size and this SHA-256:

```text
c5183ed34966bee321abaccd14f26d3236fcff20166dd97a54e94380cbfa86e1
```

To reconstruct the input from that output and verify reversibility:

```sh
python tools/firmware_patch.py reverse patches/clara-native458-c5183ed34966.lgpatch.json local/clara-native458.preview.bin local/restored-original.preview.bin
```

The program does not overwrite existing files, access the device, or copy the preview to a USB drive. The `.preview.bin` suffix identifies a research output; **a correct hash and valid checksum do not guarantee that modified firmware will work on hardware**.

## Open the OSD editor

This optional step also requires the original ROM above. Derived catalogs are generated locally and excluded from Git.

```sh
python -m pip install -r requirements.txt
python tools/prepare_catalogs.py --rom LG_HT306LD1_1107200.rom
python tools/prepare_catalogs.py --rom LG_HT306LD1_1107200.rom --check
python LG_REVERSE_LAB_EDITOR/server.py --open
```

The browser opens the editor's local server. Outputs are saved in `LG_REVERSE_LAB_EDITOR/outputs/`, with change and restoration manifests. The preview palette is an estimated reference, not a measurement of the colors on the TV. Some language names are inferred from the resources and labeled accordingly.

## Record a test with Scout

Scout treats its installation folder as the inventory root. To observe a USB drive, use a copy of the `USB_SCOUT` folder on a dedicated drive; running the repository copy inventories that folder on the computer.

```sh
cd USB_SCOUT
python lg_scout.py --new
python lg_scout.py --snapshot before
```

After the media test and after returning the USB drive to the computer:

```sh
python lg_scout.py --snapshot after
python lg_scout.py --export
```

Without arguments, `python lg_scout.py` opens the graphical interface. The media verification feature uses five synthetic files included in `LG_TESTES`: three MP3 test signals and two JPEG color patterns. They contain no personal recordings or photos. `tools/generate_test_media.py` can regenerate them using FFmpeg and Pillow.

Inventories and exported files may contain personal filenames and notes: keep them local or review them before sharing.

## Testing on the device

This project provides neither an installer nor an update procedure without a visible picture. **Do not press PLAY based on memorized timing if the updater screen is black.** The update confirmation must be visible before any flashing. The known case uses component video; a diagnostic attempt using VIDEO OUT/AV, without a USB drive and outside an update, remains pending and does not guarantee that menus will return.

Useful contributions include reproducible analysis, parser fixes, and test results that distinguish PC execution, TV observation, and file identity. Read [Testing and limitations](docs/testing.md) before interpreting a preview as physical validation.

## Authorship and scope

Maintained by [paulgomes](https://github.com/paulgomes). An independent project with no LG affiliation or endorsement. This publication grants no license to third-party firmware or trademarks and declares no software license for the code. See [NOTICE.md](NOTICE.md).
