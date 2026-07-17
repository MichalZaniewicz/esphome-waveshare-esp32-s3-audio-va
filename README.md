# ESPHome Voice Assistant for the Waveshare ESP32-S3-AUDIO-Board

A **Home Assistant voice satellite** running on the
[Waveshare ESP32-S3-AUDIO-Board](https://www.waveshare.com/esp32-s3-audio-board.htm) —
the little AI smart-speaker devkit with a dual-mic array, an ES8311 codec, three
buttons and a 7-LED RGB ring. Pure ESPHome, no custom C firmware: an always-on
core you pull as a package, plus one thin config file you actually edit.

> **Status: early.** The firmware is a working config cleaned up and
> restructured, not a polished release. See [CHANGELOG.md](CHANGELOG.md) for
> what is fixed and what is still untested on hardware.

## What it does

- **Voice assistant** — on-device wake word (`alexa`, `okay_nabu`) via
  `micro_wake_word`, the full Home Assistant Assist pipeline (STT / LLM / TTS),
  a wake beep and music ducking while it listens.
- **Simultaneous music + announcements** — a mixer speaker blends the media and
  announcement pipelines, so a doorbell announcement ducks the music instead of
  fighting it. Both are exposed to Music Assistant.
- **Say "stop"** — a `stop` wake word is armed only while a long TTS reply is
  playing, so you can cut the assistant off mid-sentence.
- **LED ring** — one state machine drives it: boot, no-Wi-Fi, no-HA, listening,
  thinking, replying, timer ticking, alarm ringing, volume changed. Colour is
  settable from HA (`set_led_color` action).
- **Timers and an alarm clock** — voice timers with an on-ring countdown, plus a
  daily alarm that can play a sound, fire an HA event, or both.
- **Buttons** — the three onboard keys do volume down / play-pause / volume up.
- **Diagnostics** — a real microphone mute, a "disable mic" switch, live ES7210
  gain, LED brightness and wake-word sensitivity, all as HA entities. No
  reflashing to tune the thing.

## Why this repo exists

The board wires the **ES8311 (DAC) and the ES7210 (ADC) to the same I2S clock
pins**. Only one device can drive those clocks, and ESPHome's stock `es8311`
cannot be made the I2S master — which means no capture and playback at once,
i.e. no wake word while music plays.

[sw3Dan](https://github.com/sw3Dan) solved this with a patched `es8311`
(`force_master` + `mclk_multiple`) in
[`waveshare-s2-audio_esphome_voice`](https://github.com/sw3Dan/waveshare-s2-audio_esphome_voice).
That work is the reason this board is usable at all, and it is
**gratefully vendored here** — the origin repo has gone quiet, and depending on
someone else's `external_components:` URL for a board that does not boot without
it is not a plan. Full credits and the licensing position:
[`components/es8311/README.md`](components/es8311/README.md).

Those two options are still absent from upstream ESPHome (checked against
`esphome/dev`, July 2026). **Upstreaming them would make this folder
disappear** — see the component README.

## Quick start

> Requires **ESPHome 2025.8.0+**.

1. Copy `secrets.example.yaml` → `secrets.yaml` and fill in your Wi-Fi and a
   freshly generated API encryption key.
2. Copy **`waveshare-va.yaml`** next to it and edit the `substitutions:` at the
   top (device name, timezone, volume limits). That thin file is the only
   firmware file you keep — the core and the patched component are **pulled from
   GitHub at compile time** (see its `packages:` block).
3. **First flash over USB**, then updates go wireless:
   ```
   esphome run waveshare-va.yaml
   ```
   Or drop both files into the ESPHome dashboard's `/config/esphome/` and hit
   Install.
4. In Home Assistant: the new ESPHome device appears → **Configure** → assign an
   Assist pipeline.
5. Say "Alexa" (or "OK Nabu"). The ring should go violet.

To pull later changes: `esphome clean waveshare-va.yaml` (clears the package
cache), then `esphome run waveshare-va.yaml`.

## Repository layout

```
waveshare-va.yaml          # YOUR config: copy + edit this (pulls the rest from GitHub)
secrets.example.yaml       # copy to secrets.yaml
base/
  core.yaml                # the always-on core, pulled as a remote package
components/
  es8311/                  # vendored patched DAC component (force_master, mclk_multiple)
docs/
  HARDWARE.md              # pinout, I2C map, gotchas
scripts/
  validate.py              # offline YAML check (syntax, substitutions, duplicate ids)
  esplog.py                # stream device logs over the native API
skill/
  waveshare-esp32-s3-audio/  # Claude Code skill: pinout + hard-won gotchas
```

## Configuration

Everything worth changing day to day is a Home Assistant entity, not a config
edit: mic gain, LED brightness, wake-word sensitivity, wake sound, alarm time
and action, mute.

What lives in `waveshare-va.yaml`:

| Substitution | Default | What it does |
|---|---|---|
| `name` / `friendly_name` | `waveshare-va` | Device name. Changing it re-creates every entity in HA. |
| `posix_timezone` | `CET-1CEST,...` | Clock zone in POSIX form (the device has no IANA database). DST automatic. |
| `volume_min` / `volume_max` | `0.4` / `0.8` | Media player clamps — the onboard amp distorts near the top. |
| `hidden_ssid` | `false` | `true` enables `fast_connect` for a hidden SSID. |

Pins and the audio format are substitutions too (in `base/core.yaml`), but you
should not need them unless you are porting to another board.

## Claude Code skill

This repo ships a [Claude Code](https://claude.com/claude-code) skill at
[`skill/waveshare-esp32-s3-audio/`](skill/waveshare-esp32-s3-audio/SKILL.md) —
the pinout, the shared-I2S constraint, and the gotchas that cost real debugging
time. Install it user-wide so any session picks it up:

```bash
cp -r skill/waveshare-esp32-s3-audio ~/.claude/skills/
```

## Credits

- **[sw3Dan](https://github.com/sw3Dan)** — the `es8311` `force_master` patch
  and the original board config this started from.
- **ESPHome** — the `es8311` component itself (`@kroimon`, `@kahrendt`) and
  everything else.
- **[Home Assistant Voice PE](https://github.com/esphome/home-assistant-voice-pe)** —
  the sounds, and the phase/ducking model the LED state machine follows.
