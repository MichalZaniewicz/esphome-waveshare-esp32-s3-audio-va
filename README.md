# ESPHome Voice Assistant for the Waveshare ESP32-S3-AUDIO-Board

A **Home Assistant voice satellite** running on the
[Waveshare ESP32-S3-AUDIO-Board](https://www.waveshare.com/esp32-s3-audio-board.htm),
the little AI smart-speaker devkit with a dual-mic array, an ES8311 codec, three
buttons and a 7-LED RGB ring. Pure ESPHome, no custom C firmware: an always-on
core you pull as a package, plus one thin config file you actually edit.

> **Status: working on hardware.** Wake word, STT/TTS, clean playback and the LED
> ring are confirmed on-device. See [CHANGELOG.md](CHANGELOG.md) for the history.

## What it does

- **Voice assistant**: on-device wake word (`alexa`, `okay_nabu`) via
  `micro_wake_word`, the full Home Assistant Assist pipeline (STT / LLM / TTS),
  a wake beep and music ducking while it listens.
- **Simultaneous music and announcements**: a mixer speaker blends the media and
  announcement pipelines, so a doorbell announcement ducks the music instead of
  fighting it. Both are exposed to Music Assistant.
- **LED ring**: one state machine drives it. Boot, no-Wi-Fi, no-HA, listening,
  thinking, replying, timer counting, ringing, volume changed - each a distinct
  colour/effect. Brightness and the animation for the listening / thinking /
  replying phases are pickable from HA, from 16 effects: solid, pulses, breathe,
  wipe, scan, spinner, comet, twinkle, flicker, fireworks, fire, rainbows.
- **Timers**: set by voice, with an on-ring countdown and a "Next timer" sensor
  in HA. (A daily-alarm engine is present but its entities are hidden by default.)
- **Buttons**: the three onboard keys do volume down, play-pause, volume up.
- **Boot chime**: a short "ready" sound once the device connects to HA
  (toggleable, and it also settles the amp so the ring boots silent).
- **Tunable live from HA**: microphone mute, ES7210 mic gain, LED brightness and
  wake-word sensitivity are all entities, so there's no reflashing to tune it.

## Quick start

> Requires **ESPHome 2025.8.0+**.

1. Copy `secrets.example.yaml` to `secrets.yaml` and fill in your Wi-Fi. The
   native API is unencrypted by default; enable encryption in `base/core.yaml`
   if you want it (see the commented block there).
2. Copy **`waveshare-va.yaml`** next to it and edit the `substitutions:` at the
   top (device name, timezone, volume limits). That thin file is the only
   firmware file you keep. The core is **pulled from GitHub at compile time**,
   see its `packages:` block.
3. **First flash over USB**, then updates go wireless:
   ```
   esphome run waveshare-va.yaml
   ```
   Or drop both files into the ESPHome dashboard's `/config/esphome/` and hit
   Install.
4. In Home Assistant: the new ESPHome device appears, open **Configure** and
   assign an Assist pipeline.
5. Say "Alexa" (or "OK Nabu"). The ring should go violet.

To pull later changes: `esphome clean waveshare-va.yaml` (clears the package
cache), then `esphome run waveshare-va.yaml`.

## How the shared I2S bus is handled

The board wires the **ES8311 (DAC) and the ES7210 (ADC) to the same BCLK/LRCLK
pins**, and only one device can drive those clocks. ESPHome also cannot run a
single I2S bus full-duplex: a microphone and a speaker on one bus each try to
init the port, and the second fails with "Parent bus is busy".

The layout that works, all on **stock ESPHome components**:

- **Two I2S buses** (two ports) over the shared pins. The **mic bus is the I2S
  master**: it is always capturing for the wake word, so it drives BCLK/LRCLK/MCLK
  continuously. The **speaker bus is a slave** that reads the mic's clock, so it
  never needs a port of its own to master.
- The ES8311 and ES7210 are stock and slave to the mic's clock.
- The mic is pinned to **16-bit** (the i2s_audio default is 32-bit); since the
  mic is master it sets the frame's slot width, and a 32-bit frame against the
  16-bit DAC comes out as noise.

This gives simultaneous capture + playback with no custom component. The
annotated config is in the audio section of `base/core.yaml`.

## Repository layout

```
waveshare-va.yaml          # YOUR config: copy + edit this (pulls the rest from GitHub)
secrets.example.yaml       # copy to secrets.yaml
base/
  core.yaml                # the always-on core, pulled as a remote package
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
edit: mic gain, LED brightness, the ring animation per assistant phase
(Listening / Thinking / Replying effect), wake-word sensitivity, wake sound,
boot sound, microphone mute.

What lives in `waveshare-va.yaml`:

| Substitution | Default | What it does |
|---|---|---|
| `name` / `friendly_name` | `waveshare-va` | Device name. Changing it re-creates every entity in HA. |
| `posix_timezone` | `CET-1CEST,...` | Clock zone in POSIX form (the device has no IANA database). DST automatic. |
| `volume_min` / `volume_max` | `0.4` / `0.8` | Media player clamps, because the onboard amp distorts near the top. |
| `hidden_ssid` | `false` | `true` enables `fast_connect` for a hidden SSID. |

Pins and the audio format are substitutions too (in `base/core.yaml`), but you
should not need them unless you are porting to another board.

## Claude Code skill

This repo ships a [Claude Code](https://claude.com/claude-code) skill at
[`skill/waveshare-esp32-s3-audio/`](skill/waveshare-esp32-s3-audio/SKILL.md):
the pinout, the shared-I2S constraint, and the gotchas that cost real debugging
time. Install it user-wide so any session picks it up:

```bash
cp -r skill/waveshare-esp32-s3-audio ~/.claude/skills/
```

## Credits

- **[jensenbox](https://github.com/jensenbox/waveshare-esp32-s3-audio)**: the
  ESP-master I2S layout for this board that the audio setup is based on.
- **ESPHome**: everything the firmware is built out of.
- **[Home Assistant Voice PE](https://github.com/esphome/home-assistant-voice-pe)**:
  the sounds, and the phase/ducking model the LED state machine follows.
