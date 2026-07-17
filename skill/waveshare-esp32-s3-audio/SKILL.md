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

# Waveshare ESP32-S3-AUDIO-Board — ESPHome working notes

Facts below are from Waveshare's **schematic v1.1** and their **own demo source**
(Arduino + ESP-IDF), cross-checked with a working ESPHome config. Where sources
conflict, that is stated — don't paper over it.

Full detail + citations: `docs/HARDWARE.md` in this repo.

## Board

- **ESP32-S3R8** (bare chip), 240 MHz, **8 MB octal PSRAM**, **16 MB flash**.
- **ES8311** mono codec (DAC) → **NS4150B** Class-D amp → speaker (JST header).
- **ES7210** 4-ch ADC → **2 physical mics** (CH1/CH2). CH3 = AEC loopback.
- **TCA9555** I/O expander @ 0x20: amp enable + 3 buttons (+ LCD/cam/SD lines).
- **7× WS2812B** ring on GPIO38, driven directly over RMT (**not** via expander).
- **PCF85063** RTC @ 0x51. DVP camera + SPI/QSPI LCD connectors. USB-C. Li-ion header.
- Wi-Fi 2.4 GHz + BT 5 LE. ESP32-S3 has **no Bluetooth Classic** → no A2DP.

ESPHome target: `board: esp32-s3-devkitc-1`, `variant: esp32s3`, `flash_size: 16MB`,
`framework: esp-idf`, `psram: {mode: octal, speed: 80MHz}`.

## Pinout (authoritative)

```
I2S (ONE shared bus):  MCLK=12  BCLK/SCLK=13  LRCK/WS=14   DIN=15 (mic)  DOUT=16 (spk)
I2C (one bus):         SDA=11   SCL=10        100 kHz confirmed working
LED ring WS2812:       DATA=38  (7 LEDs, RGB order - but verify, see gotchas)
BOOT button:           GPIO0 (active low).  RESET = hardware CHIP_PU, not readable.
SD (1-bit SDMMC):      CLK=40 CMD=42 D0=41   CS=EXIO3   (D1/D2 = NC)
LCD (use WIKI table):  CS=3 SCK=4 BL=5 SDA3=6 DC=7 MISO=8 MOSI=9  RST=EXIO0
Camera DVP:            D0=2 D1=17 D2=18 D3=39 D4=45 D5=46 D6=47 D7=48
                       VSYNC=21 HREF=1  PCLK/XCLK muxed 44/43 or 19/20  PWDN=EXIO5
USB:                   D-=19  D+=20        UART0: TX=43 RX=44
GPIO33-37:             UNUSABLE - octal PSRAM (flash uses 26-32)
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
  NEVER drive either - the wrong one kills USB and forces manual download mode.
```

The TCA9555 has **no reset pin** (schematic pin 1 is `INT#`).

## The one thing that defines this board: shared I2S clocks

ES8311 and ES7210 sit on the **same BCLK (13) / LRCK (14)**. Only one device may
drive them. ESPHome models in and out as two `i2s_audio` buses — if the ESP32
were primary on both, two I2S peripherals would fight over the same lines.

**Stock ESPHome's `es8311` always configures the codec as I2S slave and has no
way to change that.** Hence the patched component in `components/es8311/`:

- `force_master: true` → sets the ES8311's **MSC bit (reg 0x00 bit 6)** so the
  *codec* drives BCLK/LRCK from the ESP32's MCLK (GPIO12).
- `mclk_multiple: 256` → fixes the MCLK/BCLK divider maths.

So the working shape is:

```yaml
audio_dac:
  - platform: es8311           # from components/, NOT upstream
    force_master: true
    use_mclk: true
    mclk_multiple: 256
microphone:
  - platform: i2s_audio
    i2s_mode: secondary        # ESP is never the master
speaker:
  - platform: i2s_audio
    i2s_mode: secondary        # ditto
i2s_audio:                     # both buses declare 13/14 with:
  #   allow_other_uses: true
```

**Check before assuming this is still needed:** if upstream ESPHome ever gains
`force_master`, the whole `external_components:` block and `components/` folder
should be deleted. As of July 2026 upstream does not have it.

## Gotchas that cost real time

- **`microphone.mute` is the correct mute.** It makes the Microphone hand every
  consumer a zero-filled buffer (`set_mute_state` in `microphone.h`) — the wake
  word hears real silence, the stream never restarts. **Do not "mute" by setting
  ES7210 gain to 0** — 0 dB is *unity* gain, not silence. There are also
  `microphone.unmute` and the `microphone.is_muted` condition.
- **ES7210 gain caps at 37.5 dB**, not 42. `set_mic_gain()` does
  `clamp<float>(gain, MIN, MAX)` and the register steps are 3 dB up to 33 dB,
  then 34.5/36/37.5. A slider promising more than 37.5 is lying to the user.
- **Template switch triggers fire during `setup()`**, at `setup_priority
  HARDWARE - 2` — i.e. **before** the mic/mWW components exist — whenever
  `restore_mode` isn't `DISABLED` (`TemplateSwitch::setup()` calls
  `turn_on()`/`turn_off()`, which fires the trigger). If a switch's
  `on_turn_on`/`turn_on_action` touches audio components, guard it with an
  `init_in_progress`-style flag and apply the real state from `on_boot`
  (priority -100).
- **`channels:` on `voice_assistant`/`micro_wake_word` is NOT a channel count.**
  It is a `MicrophoneSource`, and `channels` is a **list of channel indices**
  (`cv.ensure_list(cv.int_range(0, 7))`, default `0`). With `channel: left` on
  the mic you have a 1-channel stream, so `0` is the only valid index. Assist
  does not accept a stereo source.
- **Hardware AEC is not reachable from stock ESPHome here.** The demo packs
  4×16-bit ADC channels into 2×32-bit I2S slots and unpacks in software; ESPHome
  doesn't. Use `noise_suppression_level` / `auto_gain` instead. (And the demo's
  declared slot order `"RMNM"` doesn't reconcile with the schematic's wiring —
  unresolved.)
- **Cold-boot: mic + LEDs sometimes don't come up until a reset.** Reported on
  the HA forum in **a single post with zero replies — no published root cause or
  fix.** The TCA9555 direction registers defaulting to `0xFF` (all inputs) would
  leave PA_EN undriven, which ESPHome's `tca9555` + a `RESTORE_DEFAULT_ON` GPIO
  switch on EXIO8 addresses — but that does **not** explain the LED symptom (the
  ring is on GPIO38/RMT, not the expander), and the reporter says replaying
  registers didn't help. Don't claim this is solved.
- **Strapping: GPIO45 (CAM_D4) and GPIO46 (CAM_D5) must be LOW at boot.** A
  camera left plugged into J3 sits on both and can stop the board booting — even
  on a voice-only build. GPIO3 (LCD_CS) is also a strap; don't add strong pulls.
- **Waveshare's demo source contains stale copy-paste from other boards.** Proven:
  its `bsp_board.h` LCD pins contradict the wiki's LCD table, and its
  `BAT_ADC_PIN 8` contradicts the schematic's GPIO1 (GPIO8 is LCD_MISO here).
  **Prefer the wiki + schematic over the demo for pin tables**; prefer the demo
  for *behaviour* (which EXIO gets driven, init order).
- **The HA forum thread swaps I2C**: it says SDA=10/SCL=11. It's SDA=11, SCL=10.
- **RGB vs GRB**: the demo says RGB and its own trailing comment says GRB;
  WS2812B is conventionally GRB. Two sources favour `rgb_order: RGB` — but
  confirm with a pure-red test before trusting either.
- **Amp pop**: Waveshare init order is codec first, amp second
  (`es8311_codec_init()` → `Audio_PA_EN()`), 50 ms after each EXIO write. A
  `RESTORE_DEFAULT_ON` amp switch has no such ordering — suspect this if power-up
  pops.
- **Battery monitoring is effectively unavailable**: the divider needs a 0 Ω
  resistor soldered (depopulated by default) and **enabling it kills the camera**.
  Ratio 3.0. Pin is GPIO1 per schematic (not GPIO8 — that's stale demo code).

## Validating without flashing

ESPHome is the real validator, but `scripts/validate.py` in this repo catches
YAML syntax, unresolved `${substitutions}` and duplicate component ids offline.
Note when writing such tooling: an `id:` under a **dotted key** (`script.execute`,
`light.turn_on`, `mixer_speaker.apply_ducking`) is a *reference*, not a
declaration — component declarations never sit under a dotted key.

`scripts/esplog.py` streams device logs over the native API (reads the API key
out of `secrets.yaml`), which beats the dashboard's log view for boot-time races.
