# Testing, evidence, and limitations

There are two separate sets: the executable tests published with the tools and the native checks performed during firmware research. The former run in a clean copy of this repository; the latter depend on local artifacts not distributed here.

## Public tests without a ROM or device

From the repository root, with Python 3.11 or later:

```sh
python -m unittest discover -s tests -p "test_*.py" -v
python -m unittest discover -s USB_SCOUT/tests -p "test_scout.py" -v
```

The patch tests use synthetic images to check reversibility, incompatible input rejection, hashes, invalid compressed data, and refusal to overwrite. They also check the published delta and its experimental status. This is not equivalent to executing the firmware.

Scout's non-graphical tests check inventories, comparisons, sessions, and exports using temporary data. Selecting `test_scout.py` avoids opening a Tk window during automated execution. Simulated data from these tests is not an observation of the LG.

## Optional tests with the original source

Supply the original ROM locally with the SHA-256 documented in the README, then generate the catalogs:

```sh
python tools/prepare_catalogs.py --rom LG_HT306LD1_1107200.rom
python tools/prepare_catalogs.py --rom LG_HT306LD1_1107200.rom --check
python -m unittest discover -s LG_REVERSE_LAB_EDITOR -p "test_engine.py" -v
```

These tests check the text engine against the original image, including concrete edits, checksums, bounds, and restoration. They are not a visual test of the complete Clara candidate. The ROM and derived catalogs remain local.

Trying Scout's graphical interface requires an environment with Tkinter and a graphical session. The media verification feature uses the five synthetic files included in `USB_SCOUT/LG_TESTES`: three MP3s and two JPEGs. They can be regenerated with `tools/generate_test_media.py`, FFmpeg, and Pillow; they are not personal research media.

## Native458 candidate checks

In the research environment, target candidate `c5183ed34966bee321abaccd14f26d3236fcff20166dd97a54e94380cbfa86e1` passed **98 MCU cases, 29 ARM checks, independent review, and USB copy verification by readback**. The [public validation summary](../reports/validation-summary.json) records these results. The full emulation setup, ROMs, and private reports are not part of this public package; the test commands above do not reproduce this native validation suite.

The review included preservation of declared regions, patch reconstruction and reversal, resource bounds, drawing commands, and execution of the native display commit in two video modes. Resource problems found during preparation were corrected or rejected before copying the candidate.

## What these results do not establish

- A window in the logical visibility list is not proof of video output. The review now includes native commit `204AE` and its MMIO writes, but this still runs on a computer.
- Preview PNGs do not measure device colors. The represented palette and scene composition may be estimated.
- A valid checksum and the expected SHA-256 establish file identity and consistency, not physical compatibility, recoverability, or operation in every state.
- Reading back the USB drive does not confirm installed flash contents or mean that the agent updated the LG.
- Screensaver animation does not imply GIF support at startup or during USB reading.

The most recent physical test of the previous firmware had black USB and updater screens, with normal audio. The corrective candidate is still awaiting a new observation of the device. See [Hardware test status](hardware-status.md).

## Reporting a result

Provide the hash of the file used, device model, cable type, video mode when known, reproducible steps, and observed behavior. Distinguish the PC picture, USB file copy, completed update, and picture observed on the TV. Do not attach dumps, manuals, complete catalogs, or personal photos to a report without reviewing their contents and distribution.

If update instructions are not visible, stop the flashing attempt. Do not use a PLAY or USB removal sequence based on memorized timing.
