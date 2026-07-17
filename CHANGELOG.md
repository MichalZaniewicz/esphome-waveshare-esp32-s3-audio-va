# Changelog

## [0.1.0] — 2026-07-17

First cut. A working single-file config for the Waveshare ESP32-S3-AUDIO-Board,
restructured into a core package + a thin user config, with the patched
`es8311` component brought in-tree so nothing depends on an upstream repo that
has gone quiet.

### Added
- `base/core.yaml` — the always-on core: ES8311 speaker, ES7210 dual mic,
  on-device wake word (`alexa` + `okay_nabu`), the HA Assist pipeline,
  music/announcement mixing with ducking, the 7×WS2812 status ring state
  machine, the three onboard buttons, voice timers and an alarm clock.
- `waveshare-va.yaml` — thin user config; pulls the core from GitHub at compile
  time, so it is the only file you keep.
- `components/es8311/` — vendored fork of ESPHome's `es8311` adding
  `force_master` + `mclk_multiple`. Origin, credits and the licensing situation:
  `components/es8311/README.md`.
- `docs/HARDWARE.md` — board pinout and the I2C device map.
- `skill/waveshare-esp32-s3-audio/` — Claude Code skill: pinout + gotchas.
- `scripts/validate.py` — offline YAML check (syntax, substitutions, duplicate
  ids) so a typo does not cost a dashboard round trip.
- `scripts/esplog.py` — stream device logs over the native API.

### Fixed
Bugs carried over from the config this started as:

- **The mic was stopped on every boot.** The `diag_disable_mic` check was
  inverted: with the switch in its default OFF position `on_boot` ran
  `micro_wake_word.stop` + `microphone.stop_capture`. It only ever recovered
  because `on_client_connected` restarted the wake word — so the switch also
  did not actually work, in either direction.
- **"Microphone Mute" did not mute.** It dropped the ES7210 gain to `0.0f`,
  but 0 dB is *unity* gain, not silence — the mic kept hearing the room and only
  the wake-word handler ignored it. It now uses ESPHome's own `microphone.mute`,
  which hands every consumer a zero-filled buffer, so the wake word hears actual
  silence with no I2S restart.
- **A test sound fired on every LED repaint during boot.** A leftover
  `id(play_sound).execute(1, id(wake_word_triggered_sound)); //TEST` sat in the
  `init_in_progress` branch of `control_leds`.
- **Wake word sensitivity did nothing.** The select only set cutoffs on
  `okay_nabu`, while the primary wake word is `alexa`. It now sets both.
- **Mic gain slider promised 42 dB.** The ES7210 caps at 37.5 dB and the driver
  silently clamps, so the top third of the slider was a lie. Range is now
  0–37.5 dB in 1.5 dB steps (the chip's real granularity), and the boot value in
  `audio_adc` matches the number entity instead of contradicting it (24 dB vs a
  32 dB global).
- **The API encryption key was hard-coded in the config.** It now comes from
  `!secret api_encryption_key`.
- **The `time:` block was half-commented-out**, leaving `id: rtc` dangling under
  `platform: homeassistant`. Cleaned up; PCF85063 support is not in this build.
- **Two `on_boot: priority: -100` blocks** ran in an order nobody had chosen.
  Merged into one.

### Changed
- All pins, audio format and the HA-facing values are `substitutions:` with
  documented defaults, instead of literals scattered through the file.
- `${mic_channel_${which_mic}}` nested-substitution trickery replaced with two
  plainly named knobs, `mic_channel` (the I2S slot) and `mic_va_channel` (the
  index handed to Assist). These are genuinely different things and the old
  names implied they were the same one.
- Dropped dead substitutions (`i2s_bits_per_sample`, `i2s_mode_speaker`,
  `rtc_int`, `mic_channel_2`) and the now-unused `mic_gain_saved` global.
- Timezone is a `posix_timezone` substitution rather than a hard-coded `UTC0`.

### Known / untested
- The mute and diagnostics switch rework is **not yet verified on hardware**.
- Cold-boot reliability of the ES7210 + TCA9555 is a reported issue on this
  board; see `docs/HARDWARE.md`.
