# Changelog

## [Unreleased]

### Changed
- **Play/Pause silences a ringing timer or alarm.** While a timer or alarm is
  ringing, the Play/Pause key stops it instead of toggling playback. It works
  even with the microphone muted, when the wake word cannot be used. The rest
  of the time the key still does play/pause.

## [1.1.1] - 2026-10-02

Tagged `v1.1.1`; the example config now pins this tag.

### Changed
- **One wake word threshold slider instead of two.** *Wake word threshold*
  replaces *Wake word 1 threshold* and *Wake word 2 threshold*, which only
  covered the `alexa` and `okay_nabu` slots. In **Custom** sensitivity the single
  slider applies to whichever wake word is active, including Hey Jarvis and Hey
  Mycroft. On first boot it starts at the active model's default cutoff. The two
  old entities become unavailable in Home Assistant and can be deleted.

## [1.1.0] - 2026-10-02

Feature release: more wake words, a night mode, tunable wake word thresholds
and a CI build. Tagged `v1.1.0`; the example config now pins this tag. Requires
ESPHome 2026.8.0 or newer.

### Added
- **Two more wake words: Hey Jarvis and Hey Mycroft**, next to Alexa and Okay
  Nabu. The active one is picked with the **Wake word** select on the device
  page in Home Assistant. Models that are not selected are not loaded, so they
  cost flash only. Giving each satellite its own wake word avoids the
  `duplicate_wake_up_detected` beep-and-nothing when two satellites on one Home
  Assistant instance hear the same word.
- **Night mode.** A **Night mode** switch dims the ring to the new **Night LED
  Ring Brightness** slider and skips the wake beep and the boot chime. Replies,
  timers and the alarm are unaffected.
- **CI build.** A GitHub Actions workflow compiles the firmware with the latest
  ESPHome release on every push and pull request (`ci/build.yaml` builds the
  core from the working tree).
- The mic gain restored from flash at boot is now logged
  (`[MIC] restored ES7210 gain -> ... dB`).
- **Per-wake-word threshold sliders.** A new **Custom** option in *Wake word
  sensitivity* hands control to two sliders, *Wake word 1 threshold* (`alexa`
  slot) and *Wake word 2 threshold* (`okay_nabu` slot), from 0.50 to 0.99. On
  first boot they start at each model's default cutoff. This makes a custom
  wake word model tunable without editing the firmware.
- **Opt-in deep sleep** on a long press of the BOOT button (GPIO0), behind the
  `enable_deep_sleep` substitution (off by default).

### Changed
- **Wake word sensitivity presets are relative to each model's default
  cutoff** instead of fixed values tuned for the stock models, so they stay
  sensible after swapping a model. *Moderately sensitive* is the default minus
  0.16, *Very sensitive* the default minus 0.29. With the stock `alexa` model,
  *Very sensitive* is now 0.61 instead of 0.50 (`okay_nabu` is effectively
  unchanged).
- **The Restart button is enabled by default** in Home Assistant. On a device
  that was already added to Home Assistant the entity stays disabled, because
  Home Assistant remembers the earlier default; enable it once from the device
  page.
- **Minimum ESPHome version is now 2026.8.0.** The LED ring uses
  `channel_colors` in place of `rgb_order`, which ESPHome deprecated and will
  remove in 2027.3.0.
- **Mic gain slider moves in 3 dB steps, 0 to 36 dB** (was 1.5 dB steps up to
  37.5 dB). The ES7210 gain register only has 3 dB resolution below 33 dB, so
  every second slider position did nothing. A saved off-grid value keeps
  working until the slider is next moved.
- **Wake word sensitivity presets apply to every wake word model**, not only
  `alexa` and `okay_nabu`.

## [1.0.1] - 2026-09-20

Patch release fixing the mic gain control. Tagged `v1.0.1`; the example config
now pins this tag.

### Fixed
- **Mic gain slider snapped back to its old value in Home Assistant.** The
  `Mic gain (ES7210)` number had a `set_action` but was not `optimistic`, so the
  new value was never published back. The ES7210 was reprogrammed correctly (the
  device log showed the new gain), but HA kept displaying the previous value and
  reset the slider on the next visit. The number now publishes its state after
  every change.
- **A saved mic gain was not applied to the ES7210 after a reboot.** A template
  number restores its value from flash in `setup()` and publishes it, but does
  not run `set_action`, so HA showed the saved gain while the codec started at
  the default from `audio_adc`. `on_boot` (priority -100) now pushes the restored
  value to the ES7210. `set_mic_gain()` is safe to call there because the driver
  stores the value even before its own setup completes.

## [1.0.0] - 2026-07-18

First stable release. The full voice assistant is confirmed on hardware, the
regressions found during bring-up testing are fixed, and the project ships with
complete documentation and a wiki. Tagged `v1.0.0`; the example config pins this
tag so a build is reproducible instead of tracking a moving `main`.

### Fixed
- **Boot loop into safe mode after selecting a ring effect.** The three
  effect selects restore their saved option during `setup()` (at HARDWARE
  priority), which fired `on_value` and ran the LED state machine before the
  light/RMT and voice_assistant were initialised, painting an effect on an
  uninitialised strip and crashing the boot. The `on_value` is now gated on
  `init_in_progress` (cleared by `on_boot` at priority -100), so it only runs
  once setup is complete; a live effect change from HA still repaints the ring.

### Changed
- **Boot chime is now a bundled sound, not the wake-word beep.**
  `base/sounds/startup.mp3` (16 kHz mono, ~11 KB) plays on connect to HA and is
  swappable through the `boot_sound_file` substitution (any URL or local
  MP3/FLAC/WAV; the media player decodes all three).

### Removed
- **The Flicker ring effect** (weak visually); 15 effects remain.

## [0.2.0] - 2026-07-18

First on-hardware bring-up. The full voice assistant works: on-device wake word,
STT/intent/TTS, clean playback, no boot hiss - all on stock ESPHome components.

### Changed
- **Audio reworked to two I2S buses with the mic as master; the patched es8311
  and `force_master` are gone.** The board shares BCLK/LRCLK between the DAC and
  ADC, and ESPHome can't run one bus full-duplex (the speaker hits "Parent bus
  is busy"). Two buses over the shared pins, with the always-capturing mic
  mastering the clock and the speaker slaving to it, gives simultaneous capture
  and playback on stock components. The mic is pinned to 16-bit so its master
  frame matches the DAC (a 32-bit frame played back as noise).
- **The amplifier is gated on playback** (`ALWAYS_OFF` at boot, turned on by the
  media_player `on_state`) to remove the idle hiss the always-on amp produced
  before the first playback.
- **API encryption dropped** (LAN-only device); `secrets.yaml` is now just Wi-Fi.
  Re-enable it via the commented block in `base/core.yaml` if you want it.
- **Timers are visible in HA** (the "Next timer" / "Next timer name" sensors are
  no longer `disabled_by_default`).
- **Boot chime**: a short "ready" sound plays once the device connects to HA,
  played after the mic (I2S master) is clocking so the slave speaker can output
  it. New `boot_sound` switch toggles it. The sound ships with the repo
  (`base/sounds/startup.mp3`, 16 kHz mono) and is swappable via the
  `boot_sound_file` substitution (any URL or local MP3/FLAC/WAV).

### Added
- **Per-phase ring animation, pickable from HA.** New "Listening effect",
  "Thinking effect" and "Replying effect" selects choose the animation for those
  voice-assistant phases (the phase colour stays fixed). 15 effects to choose
  from: solid, three pulses, Breathe, Wipe, Scan, Spinner, Comet, Twinkle,
  Random Twinkle, Fireworks, Fire, and two rainbows. Breathe / Spinner /
  Comet / Fire are custom `addressable_lambda` effects.

### Fixed
- **The Pulse LED effects showed a solid colour instead of pulsing.** Their
  `update_interval` (16 ms) was shorter than the transition (300-1000 ms);
  `update_interval` is how often the pulse flips its brightness target, so it
  flipped faster than the brightness could move. Now ~2x the transition, with
  30-100% min/max brightness.
- Compile-time issues found during bring-up: a quoted `mclk_multiple`
  substitution (string vs the int a `cv.one_of` wants), a `template select`
  missing its `options:`, `select` `.state` -> `current_option()`, the dead
  microWakeWord model URLs (404), and a `/` in a switch name.

### Removed
- **The `stop` wake word.** This board has no usable hardware AEC, so the mic
  hears the device's own TTS far louder than the user; "stop" is detected only
  weakly and too late to be useful.
- **The daily-alarm entities** (Alarm time / Alarm on / Alarm action), the
  device-clock text sensor, and the diagnostic mic-disable switch are now
  `internal:` (hidden from HA). The logic stays; the clutter is gone.
- The dead "Mute and unmute sound" switch and its unused sound files.
- `components/es8311/` and the `external_components:` block - no longer needed.

## [0.1.0] - 2026-07-17

First cut. A working single-file config for the Waveshare ESP32-S3-AUDIO-Board,
restructured into a core package + a thin user config, with the patched
`es8311` component brought in-tree so nothing depends on an upstream repo that
has gone quiet.

### Added
- `base/core.yaml`: the always-on core with ES8311 speaker, ES7210 dual mic,
  on-device wake word (`alexa` + `okay_nabu`), the HA Assist pipeline,
  music/announcement mixing with ducking, the 7x WS2812 status ring state
  machine, the three onboard buttons, voice timers and an alarm clock.
- `waveshare-va.yaml`: thin user config. Pulls the core from GitHub at compile
  time, so it is the only file you keep.
- `components/es8311/`: vendored fork of ESPHome's `es8311` adding
  `force_master` + `mclk_multiple`. Origin, credits and the licensing situation
  are in the README.
- `docs/HARDWARE.md`: board pinout and the I2C device map.
- `skill/waveshare-esp32-s3-audio/`: Claude Code skill with pinout + gotchas.
- `scripts/validate.py`: offline YAML check (syntax, substitutions, duplicate
  ids) so a typo does not cost a dashboard round trip.
- `scripts/esplog.py`: stream device logs over the native API.

### Fixed
Bugs carried over from the config this started as:

- **The mic was stopped on every boot.** The `diag_disable_mic` check was
  inverted: with the switch in its default OFF position `on_boot` ran
  `micro_wake_word.stop` + `microphone.stop_capture`. It only ever recovered
  because `on_client_connected` restarted the wake word, so the switch also did
  not actually work, in either direction.
- **"Microphone Mute" did not mute.** It dropped the ES7210 gain to `0.0f`,
  but 0 dB is *unity* gain, not silence. The mic kept hearing the room and only
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
  0 to 37.5 dB in 1.5 dB steps (the chip's real granularity), and the boot value
  in `audio_adc` matches the number entity instead of contradicting it (24 dB vs
  a 32 dB global).
- **The API encryption key was hard-coded in the config.** It now comes from
  `!secret api_encryption_key`.
- **The `time:` block was half-commented-out**, leaving `id: rtc` dangling under
  `platform: homeassistant`. Cleaned up. PCF85063 support is not in this build.
- **Two `on_boot: priority: -100` blocks** ran in an order nobody had chosen.
  Merged into one.

### Changed
- All pins, audio format and the HA-facing values are `substitutions:` with
  documented defaults, instead of literals scattered through the file.
- `${mic_channel_${which_mic}}` nested-substitution trickery replaced with two
  plainly named knobs: `mic_channel` (the I2S slot) and `mic_va_channel` (the
  index handed to Assist). These are genuinely different things and the old
  names implied they were the same one.
- Dropped dead substitutions (`i2s_bits_per_sample`, `i2s_mode_speaker`,
  `rtc_int`, `mic_channel_2`) and the now-unused `mic_gain_saved` global.
- Timezone is a `posix_timezone` substitution rather than a hard-coded `UTC0`.
