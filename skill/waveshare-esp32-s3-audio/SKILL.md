---
name: waveshare-esp32-s3-audio
description: >
  Reference for building/editing ESPHome configs on the Waveshare
  ESP32-S3-AUDIO-Board (ESP32-S3R8 smart-speaker devkit: ES8311 codec + NS4150B amp,
  ES7210 dual-mic ADC, TCA9555 I/O expander, 7x WS2812 ring, PCF85063 RTC, DVP camera
  and SPI LCD connectors). Use whenever working on this board (or the base/core.yaml in
  this repo): correct pinout, why the DAC must be forced I2S master, the mute/gain
  traps, the EXIO map, strapping pins, and which "official" sources are wrong.
---

# Waveshare ESP32-S3-AUDIO-Board: ESPHome working notes

Facts below are from Waveshare's **schematic v1.1** and their **own demo source**
(Arduino + ESP-IDF), cross-checked with a working ESPHome config. Where sources
conflict, that is stated. Don't paper over it.

Full detail and citations: `docs/HARDWARE.md` in this repo.

## Board

- **ESP32-S3R8** (bare chip), 240 MHz, **8 MB octal PSRAM**, **16 MB flash**.
- **ES8311** mono codec (DAC) into **NS4150B** Class-D amp into speaker (JST header).
- **ES7210** 4-ch ADC with **2 physical mics** (CH1/CH2). CH3 = AEC loopback.
- **TCA9555** I/O expander @ 0x20: amp enable + 3 buttons (+ LCD/cam/SD lines).
- **7x WS2812B** ring on GPIO38, driven directly over RMT, **not** via expander.
- **PCF85063** RTC @ 0x51. DVP camera + SPI/QSPI LCD connectors. USB-C. Li-ion header.
- Wi-Fi 2.4 GHz + BT 5 LE. ESP32-S3 has **no Bluetooth Classic**, so no A2DP.

ESPHome target: `board: esp32-s3-devkitc-1`, `variant: esp32s3`, `flash_size: 16MB`,
`framework: esp-idf`, `psram: {mode: octal, speed: 80MHz}`.

## Pinout (authoritative)

```
I2S (ONE shared bus):  MCLK=12  BCLK/SCLK=13  LRCK/WS=14   DIN=15 (mic)  DOUT=16 (spk)
I2C (one bus):         SDA=11   SCL=10        100 kHz confirmed working
LED ring WS2812:       DATA=38  (7 LEDs, RGB order, but verify: see gotchas)
BOOT button:           GPIO0 (active low).  RESET = hardware CHIP_PU, not readable.
SD (1-bit SDMMC):      CLK=40 CMD=42 D0=41   CS=EXIO3   (D1/D2 = NC)
LCD (use WIKI table):  CS=3 SCK=4 BL=5 SDA3=6 DC=7 MISO=8 MOSI=9  RST=EXIO0
Camera DVP:            D0=2 D1=17 D2=18 D3=39 D4=45 D5=46 D6=47 D7=48
                       VSYNC=21 HREF=1  PCLK/XCLK muxed 44/43 or 19/20  PWDN=EXIO5
USB:                   D-=19  D+=20        UART0: TX=43 RX=44
GPIO33-37:             UNUSABLE, taken by octal PSRAM (flash uses 26-32)
```

I2C addresses: **ES8311 0x18**, **ES7210 0x40**, **TCA9555 0x20**, **PCF85063 0x51**.

### TCA9555 EXIO map

```
0: LCD_RST     4: unknown          8:  PA_EN  (amp enable, ACTIVE HIGH)
1: TP_RST      5: CAM_PWDN (AL)    9:  Key1   (active low, 10k HW pull-up)
2: TP_INT      6: Camera_SEL  *    10: Key2   (active low)
3: SD_CS       7: USB/cam mux *    11: Key3   (active low)
                                   12-15: expansion header
* EXIO6/EXIO7: schematic and wiki/demo disagree on which does the mux.
  NEVER drive either. The wrong one kills USB and forces manual download mode.
```

The TCA9555 has **no reset pin** (schematic pin 1 is `INT#`).

## The one thing that defines this board: shared I2S clocks

ES8311 and ES7210 sit on the **same BCLK (13) / LRCK (14)**. Only one device may
drive them, and **ESPHome cannot run a single i2s_audio bus full-duplex**: a
microphone and a speaker on one bus each call `i2s_new_channel` on the port, and
the second fails at runtime with `Parent bus is busy` (the speaker then crackles).

The layout this firmware uses (ESPHome 2026.11.0+): **one full-duplex,
four-slot TDM bus owned by `aec_speexdsp`** (SpeexDSP echo canceller, from a
fork of matt123p/esphome-aec), which gives a real echo reference.

- The **ESP is the I2S master**; ES8311 and ES7210 are stock drivers and slave
  to it. The ES7210 runs with `tdm: true` (stock since 2026.11.0; ESP32 and
  ESP32-S2 have no TDM and are rejected).
- Each 16 kHz frame carries the four ES7210 inputs in and the DAC samples out
  on the same clock. **Measured slot map on this board: slots 0 and 2 = mics,
  slot 1 = MIC3 speaker loopback, slot 3 = dead.**
- The canceller processes **one** mic slot (`microphone_slots`), half the cost
  of two, which matters on the S3.

```yaml
audio_adc:
  - platform: es7210
    id: adc_mic
    bits_per_sample: 16bit
    sample_rate: 16000
    tdm: true
    channel_gains: [24db, 24db, 30db, 0db]   # MIC3 = loopback, boosted
audio_dac:
  - platform: es8311
    id: es8311_dac
    bits_per_sample: 16bit
    sample_rate: 16000
    use_mclk: true
aec_speexdsp:
  id: aec
  audio_adc: adc_mic
  i2s_port: 0
  tdm_slots: 4
  microphone_slots: [0]
  reference_source: analog_slot
  reference_slot: 1
  tx_slots: [0, 1]
  frame_size: 128
  filter_length: 512
  playback_buffer: 500ms
microphone:
  - { platform: aec_speexdsp, id: i2s_mics, aec_speexdsp_id: aec }
speaker:
  - platform: aec_speexdsp
    id: aec_speaker
    aec_speexdsp_id: aec
    audio_dac: es8311_dac          # without it HA volume/mute do nothing
```

**Fallback without AEC (stock `i2s_audio` only):** two buses over the shared
pins, the **mic bus as master** (always capturing, so the clock never stops),
the speaker bus as a slave (`i2s_mode: secondary`), and the mic pinned to
**16-bit** (the 32-bit default doubles the bit clock and playback becomes
noise). Do **not** make the ES8311 the master via a `force_master`-style
patch: a codec-mastered clock feeds the ESP mic a wrong-rate stream and kills
the wake word.

### AEC gotchas

- **The MIC3 loopback is weak on this board** (about -50 dBFS for a TTS reply at
  0 dB gain, so the canceller removed nothing). Boost MIC3 to ~30 dB and keep
  `playback_gain_db` around -12 so the reference does not clip.
- **ESP32-S3 FFT needs 16-byte aligned buffers.** Upstream SpeexDSP got 4-byte
  aligned memory and the S3 SIMD FFT overwrote heap headers: a stalled API
  ("Timeout waiting for DeviceInfoResponse"), then `LoadProhibited` in
  `tlsf_walk_pool`. The pinned fork allocates with `heap_caps_aligned_alloc(16)`.
- **Internal RAM is the limit.** Frame 256 / filter 1024 left ~10 KB free and
  crash-looped; frame 128 / filter 512 (32 ms tail) leaves ~65 KB, DSP load
  ~25%.
- **The canceller's playback ring defaults to 4 s**, which made ducking, "stop"
  and barge-in act ~4 s late. Set `playback_buffer: 500ms`.
- **Mic gain: write MIC1/MIC2 registers (0x43/0x44) directly.**
  `set_mic_gain()` also moves MIC3, the reference. Stock `set_channel_gain()`
  does reach the hardware after setup, but each call reprograms all four
  channels and briefly powers down every PGA, the reference included.

## Gotchas that cost real time

- **`microphone.mute` is the correct mute.** It makes the Microphone hand every
  consumer a zero-filled buffer (`set_mute_state` in `microphone.h`), so the wake
  word hears real silence and the stream never restarts. **Do not "mute" by
  setting ES7210 gain to 0**, because 0 dB is *unity* gain, not silence. There
  are also `microphone.unmute` and the `microphone.is_muted` condition.
- **ES7210 gain caps at 37.5 dB**, not 42. `set_mic_gain()` does
  `clamp<float>(gain, MIN, MAX)` and the register steps are 3 dB up to 33 dB,
  then 34.5/36/37.5. A slider promising more than 37.5 is lying to the user.
- **Template switch triggers fire during `setup()`**, at `setup_priority
  HARDWARE - 2`, i.e. **before** the mic/mWW components exist, whenever
  `restore_mode` isn't `DISABLED` (`TemplateSwitch::setup()` calls
  `turn_on()`/`turn_off()`, which fires the trigger). If a switch's
  `on_turn_on`/`turn_on_action` touches audio components, guard it with an
  `init_in_progress`-style flag and apply the real state from `on_boot`
  (priority -100). **The same applies to a template `select` with
  `restore_value: true`**: it replays the saved option during `setup()` and
  fires `on_value` before the light/RMT and voice_assistant exist. An
  `on_value` that repaints the ring (`control_leds`) then paints an effect on
  an uninitialised strip and crash-loops the board into safe mode. Guard the
  `on_value` with the same `init_in_progress` check.
- **`channels:` on `voice_assistant`/`micro_wake_word` is NOT a channel count.**
  If you wrap the mic (`microphone: { microphone: id, channels: N }`) it is a
  `MicrophoneSource` and `channels` is a **list of channel indices**
  (`cv.ensure_list(cv.int_range(0, 7))`, default `0`), not a count. This firmware
  just passes the mic directly (`microphone: i2s_mics`) and lets it default, so
  the wrapper isn't used - simplest, and Assist won't take a stereo source anyway.
- **The vendor demo's slot order `"RMNM"`** (slot0 = reference) does not match
  what this board delivers in ESPHome's TDM mode (slot 1 = reference). Measure
  with per-slot level sensors instead of trusting the demo.
- **Cold-boot: mic + LEDs sometimes don't come up until a reset.** Reported on
  the HA forum in **a single post with zero replies, with no published root cause
  or fix.** The TCA9555 direction registers defaulting to `0xFF` (all inputs)
  would leave PA_EN undriven, which ESPHome's `tca9555` + a `RESTORE_DEFAULT_ON`
  GPIO switch on EXIO8 addresses. But that does **not** explain the LED symptom
  (the ring is on GPIO38/RMT, not the expander), and the reporter says replaying
  registers didn't help. Don't claim this is solved.
- **Strapping: GPIO45 (CAM_D4) and GPIO46 (CAM_D5) must be LOW at boot.** A
  camera left plugged into J3 sits on both and can stop the board booting, even
  on a voice-only build. GPIO3 (LCD_CS) is also a strap, so don't add strong
  pulls.
- **Waveshare's demo source contains stale copy-paste from other boards.** Proven:
  its `bsp_board.h` LCD pins contradict the wiki's LCD table, and its
  `BAT_ADC_PIN 8` contradicts the schematic's GPIO1 (GPIO8 is LCD_MISO here).
  **Prefer the wiki + schematic over the demo for pin tables**; prefer the demo
  for *behaviour* (which EXIO gets driven, init order).
- **The HA forum thread swaps I2C**: it says SDA=10/SCL=11. It's SDA=11, SCL=10.
- **RGB vs GRB**: the demo says RGB and its own trailing comment says GRB, while
  WS2812B is conventionally GRB. Two sources favour `channel_colors: RGB`, but
  confirm with a pure-red test before trusting either.
- **Idle-amp hiss at boot.** The amp (PA_EN on EXIO8) enabled at boot amplifies
  the undriven DAC line as a faint hiss until the first playback (after which the
  i2s speaker, `timeout: never`, holds the line at clean silence). Fix by gating
  the amp: `restore_mode: ALWAYS_OFF`, then turn it on from the media_player
  `on_state` when playback starts and leave it on. **Do not** try to fix this by
  playing a boot sound through the media player - a standalone boot announcement
  leaves `media_player.is_announcing` stuck true, and `on_wake_word_detected`
  then only ever stops that phantom announcement instead of starting Assist
  (wake word detected, nothing happens).
- **HTTPS-only Home Assistant stalls the pipeline.** If HA serves port 8123 over
  HTTPS with a certificate that does not cover the LAN address the device reaches
  it by, every announcement/TTS fetch fails certificate verification and the
  device holds in `STREAMING_MICROPHONE` with no `Starting STT by VAD` line. In
  the log this is **identical** to a too-tight `vad` threshold; the tell is
  `esp-x509-crt-bundle: Failed to verify certificate` /
  `mbedtls_ssl_handshake returned -0x3000` / `Connection failed, sock < 0`. The
  fix is HA-side, not firmware: set the HA Internal URL to `http://<ip>:8123`, or
  terminate TLS at a reverse proxy and keep HA's own `http:` server plain.
- **Battery monitoring is effectively unavailable**: the divider needs a 0 Ω
  resistor soldered (depopulated by default) and **enabling it kills the camera**.
  Ratio 3.0. Pin is GPIO1 per schematic, not GPIO8, which is stale demo code.

## Validating without flashing

ESPHome is the real validator, but `scripts/validate.py` in this repo catches
YAML syntax, unresolved `${substitutions}` and duplicate component ids offline.
Note when writing such tooling: an `id:` under a **dotted key** (`script.execute`,
`light.turn_on`, `mixer_speaker.apply_ducking`) is a *reference*, not a
declaration. Component declarations never sit under a dotted key.

`scripts/esplog.py` streams device logs over the native API (reads the API key
out of `secrets.yaml`), which beats the dashboard's log view for boot-time races.
