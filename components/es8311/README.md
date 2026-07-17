# es8311 (patched): vendored component

This is **not** original work. It is ESPHome's built-in `es8311` audio_dac
component with two options added. It lives here because upstream ESPHome does
not have those options (checked against `esphome/dev`, 2026-07) and the board
does not work without them.

## What the patch adds

| Option | Default | Why it exists |
|---|---|---|
| `force_master: true` | `false` | Makes the **ES8311 the I2S master** (it drives BCLK/LRCLK) while the ESP32 and the ES7210 both stay slaves. The board wires the DAC and the ADC to the *same* clock pins, so exactly one device may generate them. Without this you cannot capture and play at the same time, i.e. no wake word during music. |
| `mclk_multiple: 256` | `256` | Fixes the MCLK/BCLK ratio maths so the codec's clock divider matches what the ESP32 actually emits on the MCLK pin. |

Everything else is stock upstream behaviour.

## Where it came from

1. **Upstream ESPHome**: `esphome/components/es8311`, original authors
   `@kroimon` and `@kahrendt` (per `CODEOWNERS`).
2. **The patch**: by **[sw3Dan](https://github.com/sw3Dan)**, published in
   [`sw3Dan/waveshare-s2-audio_esphome_voice`](https://github.com/sw3Dan/waveshare-s2-audio_esphome_voice).
   Vendored here from `main` @ commit of 2026-06-24.

## Keeping it in sync

`force_master` + `mclk_multiple` would be useful to any board that shares I2S
clocks between a codec and an ADC (the Espressif Korvo boards do the same), so
they belong upstream. If ESPHome ever gains them, **delete this folder** and the
`external_components:` block in `base/core.yaml`, and set both options directly
on the stock component.

To diff against upstream:

```bash
curl -sL https://raw.githubusercontent.com/esphome/esphome/dev/esphome/components/es8311/audio_dac.py -o /tmp/upstream_audio_dac.py
diff -u /tmp/upstream_audio_dac.py audio_dac.py
```
