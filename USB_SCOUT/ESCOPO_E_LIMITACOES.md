# LG Reverse Lab — USB Scout 0.1

## Actual architecture and demonstrated capabilities

`Windows laptop (Python 3 + optional Ollama) ↔ FAT32 USB drive ↔ LG HT306SU-A2`

The arrow to the LG represents **media and file transport**, not a control connection or remote execution. According to the supplied owner's manual, the LG firmware supports USB media formatted as FAT16/FAT32, and its USB port **cannot be connected to a PC**. The HDMI interface is an **output**.

**The agent is not a copy of ChatGPT and does not run inside the LG.** It is an external tool for local collection, observation logging, deterministic analysis of changes on the USB drive, and optional text summaries through Ollama. It neither makes EEPROM editing decisions nor issues service commands.

## Sources and confidence

- `LG_HT306LD1_1107200.rom`: SHA-256 verified against the file attached to the chat: `27adf86b93e5e7347fbd7d12837e32a3394243a75e025d2b188e1afd5151c00a`, size 2,091,376 bytes; **not included in this package**.
- LG HT306SU manual (P/NO MFL66983891): page 8 describes FAT16/FAT32 USB and states that USB connection to a PC is unsupported; page 14 shows HDMI OUT; page 16 shows AUX L/R input.
- `RELATORIO-ENGENHARIA-REVERSA.md`: mentions `.ROM`, `.EPM`, and `.HEX` and interprets routines; those claims **still require an independent disassembly audit**.

## What it does

1. Validates hashes of three stereo MP3 test files and two JPEGs. The MP3s use 44.1 kHz and 128 kbit/s, within the manual's documented limits.
2. Creates an identified session on the USB drive.
3. Records before/after USB inventories, comparing new, removed, and modified files.
4. Saves manual notes and evidence (photos, video, audio); can capture a webcam frame and five seconds of laptop microphone audio **only after a click**, with optional dependencies.
5. Generates a ZIP containing a JSON manifest, inventories, comparisons, and observations for later sharing with ChatGPT.
6. Optionally summarizes observations with a local model accessed through `127.0.0.1:11434` (Ollama). The program makes no remote model calls.

## What it does not do

- Read the LG's EEPROM, RAM, registers, HDMI logs, or infrared communication.
- Execute code on the LG through USB.
- Modify or install firmware; it contains no `.ROM`, `.EPM`, or `.HEX` files.
- Automatically extract knowledge from everything the LG does. USB changes appear only if the LG **writes files**, such as through its normal recording function; screen and audio responses require human observation or externally captured media.
- Provide capabilities equivalent to GPT-6, even when using an LLM through Ollama.

## Possible future development

Future versions could add controlled continuous camera capture to observe the LG display, audio spectrum analysis, and, if a compatible IR transmitter is available, control actions through a local API with limited permissions. Each feature requires its own hardware and safety testing.
