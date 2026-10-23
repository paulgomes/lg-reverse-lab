# Hardware test status

**The Clara native458 candidate `c5183ed34966…` does not yet have physical confirmation of a visible picture on the LG.** Passing computer tests and verifying a USB copy are separate from installing the image and observing the result on the TV.

## Available evidence

| Image | Evidence source | Result and limitation |
| --- | --- | --- |
| Initial text and resource modifications | User reports and photos | Changed text and visual identity appeared on the device; audio, pause, resume, volume, and Settings were reported working at the corresponding stages. This does not validate later versions. |
| `757ee81bad98…` | Earlier physical test associated with this image | USB menu visible, with an unsuitable layout; the WYS image during reading remained static. |
| `f1c0a95eccb7…` | Most recent physical report | Static WYS CORP opening visible, USB menu and updater black, music normal. The user reported updating without a picture using memorized timing; this must not be repeated as a procedure. |
| `c5183ed34966…` | Native computer tests, independent review, and USB copy readback | Checks passed; **physical test of the correction pending**. |

The hash of the file copied to USB is not a readout of the LG's flash chip. An association between an image and a physical report must not be presented as confirmation of the installed hash.

## Corrective candidate identity

```text
Original source:
27adf86b93e5e7347fbd7d12837e32a3394243a75e025d2b188e1afd5151c00a

Clara native458 candidate:
c5183ed34966bee321abaccd14f26d3236fcff20166dd97a54e94380cbfa86e1

Size of each image: 2,091,376 bytes
```

The correction restores the native window, palette, and USB display contracts while preserving the Clara design. It removes the wait for the experimental animation before making the menu visible. This mechanism has not been shown to be the only cause of the physical defect.

## Opening and animation

The opening is a static MPEG image. The candidate does not play a GIF at startup or start an animation during USB detection. The six WYS screensaver frames were preserved, but this does not prove that the entire sequence will work in every device state.

## Next evidence needed

The user reported a YPbPr component video connection. One possible diagnostic step, **outside any update and without a USB drive**, is to test the yellow VIDEO OUT with a compatible AV input and check whether Settings becomes visible. This alternative has not been confirmed and does not guarantee picture recovery.

Before any further flashing, update instructions must be visible. **If the updater is black, do not remove the USB drive or press PLAY based on memorized timing.** This repository does not provide a blind update sequence.

Future validation should record the file used, cable and video mode, opening, USB while stopped and playing, item selection, queue, Settings, pause/resume, volume, and updater screen. Remove personal information from photos or videos before publication.
