# Waveshare ESP32-S3-AUDIO-Board: hardware reference

Pinout and gotchas for the [ESP32-S3-AUDIO-Board](https://www.waveshare.com/esp32-s3-audio-board.htm),
cross-checked against the sources below. Every value is attributed to its source.
Several sources contradict each other, including Waveshare's own documentation
against its own demo code; those conflicts are documented rather than resolved by
assumption.

| Tier | Source |
|---|---|
| **A** | [Schematic PDF v1.1](https://files.waveshare.com/wiki/ESP32-S3-AUDIO-Board/ESP32-S3-AUDIO-Board_1.1.pdf), ground truth for wiring. Text-extracted, so net/pin association is occasionally ambiguous. |
| **A** | [Official demo ZIP](https://files.waveshare.com/wiki/ESP32-S3-AUDIO-Board/ESP32-S3-AUDIO-Board-Demo.zip), Arduino + ESP-IDF. Ground truth for what firmware actually drives, **but it contains proven stale copy-paste from other boards.** |
| **B** | [Waveshare wiki](https://www.waveshare.com/wiki/ESP32-S3-AUDIO-Board), pinout tables. (Returns HTTP 403 to some fetchers; a browser User-Agent gets through.) |
| **B** | [sw3Dan's ESPHome config](https://github.com/sw3Dan/waveshare-s2-audio_esphome_voice), empirically working, so behavioural confirmation. |

## Board identity

| Item | Value |
|---|---|
| MCU | **ESP32-S3R8** (bare chip, not a module), dual-core LX7 @ 240 MHz |
| Flash | **16 MB**, W25Q128JVSI |
| PSRAM | **8 MB, octal**, in-package (the `R8` suffix). Runs at 80 MHz. |
| Radio | 2.4 GHz Wi-Fi b/g/n, BT 5 LE. Ceramic antenna + IPEX (resistor reflow) |
| Power | MP1605GTF-Z buck to 3.314 V, max 2 A |
| Audio | ES8311 codec (DAC) + NS4150B mono Class-D amp; ES7210 4-ch ADC (mics) |

ESPHome target: `board: esp32-s3-devkitc-1`, `variant: esp32s3`, `flash_size: 16MB`,
framework `esp-idf`.

## Audio: one shared I2S bus

**Confirmed by three independent sources** (wiki tables, the demo's `bsp_board.h`,
and the schematic nets). This is the most solid part of this document.

| Signal | GPIO | Direction |
|---|---|---|
| I2S **MCLK** | **GPIO12** | ESP32 to both codecs |
| I2S **BCLK / SCLK** | **GPIO13** | **shared** |
| I2S **LRCK / WS** | **GPIO14** | **shared** |
| I2S **DIN** (ES7210 to ESP) | **GPIO15** | in |
| I2S **DOUT** (ESP to ES8311) | **GPIO16** | out |

**The DAC and the ADC share one clock pair.** The wiki's ES8311 and ES7210
tables list the same MCLK/SCLK/LRCK; the schematic lands one net set on both
chips; and the demo opens a **single full-duplex I2S peripheral**
(`i2s_new_channel(&chan_cfg, &tx_handle, &rx_handle)`).

That single shared clock pair is what shapes the whole audio setup, see
[Shared I2S clocks](#shared-i2s-clocks) below.

## I2C: one bus, GPIO10/11

| Item | Value |
|---|---|
| **SDA** | **GPIO11** |
| **SCL** | **GPIO10** |
| Speed | 100 kHz confirmed working |

The schematic uses different net *names* (`ESP32_`, `EXIO_`, `RTC_`, `TP_`,
`TWI_` for the camera SCCB) but they all resolve to GPIO10/11. Schematic note:
*"can only be used for I2C, cannot be used for other functions."*

> ⚠️ The HA community thread on this board states *"SDA=10, SCL=11"*, which is
> **swapped** versus every official source.

| Device | Address |
|---|---|
| **ES8311** codec / DAC | **0x18** |
| **ES7210** ADC / mics | **0x40** |
| **TCA9555PWR** I/O expander | **0x20** |
| **PCF85063ATL** RTC | **0x51** |

## TCA9555 I/O expander (0x20)

**There is no reset pin.** The schematic's pin 1 is `INT#`; the part simply has
none.

| EXIO | Function | Used here |
|---|---|---|
| 0 | LCD_RST | - |
| 1 | TP_RST (touch reset) | - |
| 2 | TP_INT | - |
| 3 | SD_D3 / SD CS | - |
| 4 | **unknown**, no driver references it | - |
| 5 | CAM_PWDN (active low) | - |
| 6 | Camera_SEL (clock mux) | **do not drive** |
| 7 | USB/camera mux | **do not drive** |
| **8** | **PA_EN, amplifier enable, ACTIVE HIGH** | ✅ `amp_enable` |
| **9** | **Key1, active low** | ✅ volume down |
| **10** | **Key2, active low** | ✅ play/pause |
| **11** | **Key3, active low** | ✅ volume up |
| 12-15 | expansion header P1 | - |

Keys have **10 kΩ hardware pull-ups to 3V3**, so they are active low and need no
internal pull.

### "The keys are on 12, not 9/10/11": settled, they are on 9/10/11

sw3Dan's config carries `number: 9 # not '12' as schematics say!`. The map
**9/10/11 (keys) + 8 (PA_EN) is right**, confirmed twice over:

- Waveshare's **own driver code** reads exactly those:
  `Button_Driver.cpp` calls `Read_EXIO(TCA9555_EXIO9/10/11)` with
  `#define BUTTON_ACTIVE_LEVEL 0`, and `Audio_ES8311.cpp` has `Audio_PA_EN()`
  setting `TCA9555_EXIO8` true.
- sw3Dan arrived at the same map empirically, independently.

Whether the *schematic* really implies 12 could not be confirmed (PDF text
extraction loses the geometry, and `Key4`/`Key5` nets also appear near
`Extend_IO12..15`). It doesn't matter: code and practice agree.

### ⚠️ EXIO6 vs EXIO7: genuine unresolved conflict

The schematic carries explicit warnings naming **EXIO7**: driving it LOW
disables USB on GPIO19/20 *and forces manual download mode before every flash*;
driving it HIGH disables UART on GPIO43/44; **EXIO7 defaults HIGH**. But the
wiki and `Camera_Driver.cpp` attribute the identical function to **EXIO6**.

**Off-by-one, unresolved. For a voice build: never drive either.** Leaving both
alone keeps USB flashing alive.

## RGB LEDs

| Item | Value |
|---|---|
| GPIO | **GPIO38**, driven **directly over RMT**, *not* via the expander |
| Count | **7** (WS2812B-0807, U9-U14 + U19) |
| RGB order | **RGB** |

> On RGB vs GRB: two sources say RGB (the official demo's
> `LED_STRIP_COLOR_COMPONENT_FMT_RGB`, and sw3Dan's working config). But
> WS2812B is *conventionally* GRB, and Waveshare's own line contradicts its own
> trailing comment (`..._FMT_RGB, // The color order of the strip: GRB`).
> **Verify visually**: set pure red and check it isn't green.

## Microphones

**Two physical mics.** Per the schematic:

| ES7210 ch | Wired to |
|---|---|
| **MIC1, MIC2** | the two real microphones |
| **MIC3** | **AEC loopback**, the ES8311 speaker output, attenuated |
| MIC4 | nets exist, no source found, likely unused |

Corroboration: `MICBIAS12` biases **only** channels 1 and 2, i.e. only those two
have actual capsules.

> **Unresolved:** the demo declares its AFE input format as `"RMNM"`
> (slot0 = reference, slot1 = mic, slot2 = null, slot3 = mic), which does not
> reconcile with a naive MIC1 to slot0 mapping. Possibly ES7210 slot packing
> isn't 1:1, possibly copy-paste from a Korvo BSP. Verify before relying on it.

**Hardware AEC is not usable from stock ESPHome on this board.** The demo packs
4x16-bit channels into 2x32-bit I2S slots and unpacks them in software; ESPHome
does not. This firmware therefore takes the two real mics as a plain stereo
stream (`channel: left` gives one capsule) and relies on ESPHome's software
`noise_suppression_level` / `auto_gain` instead.

## Not used by this firmware

Kept for reference. This build is speaker + mics + ring + buttons only.

- **BOOT button**: GPIO0, active low. **RESET**: hardware `CHIP_PU`, not readable.
- **SD (1-bit SDMMC)**: CLK GPIO40, CMD GPIO42, D0 GPIO41, CS EXIO3. D1/D2 = NC.
- **LCD (18-pin FPC)**: CS GPIO3, SCK GPIO4, BL GPIO5, MOSI GPIO9, DC GPIO7,
  MISO GPIO8, SDA3 GPIO6; RST EXIO0, TP_RST EXIO1, TP_INT EXIO2.
  ⚠️ Use the **wiki** table for the LCD, not the IDF demo's `bsp_board.h`, which
  contradicts it (proven stale, see the battery note).
- **Camera (DVP, 24-pin FPC)**: D0 GPIO2, D1 GPIO17, D2 GPIO18, D3 GPIO39,
  D4 GPIO45, D5 GPIO46, D6 GPIO47, D7 GPIO48, VSYNC GPIO21, HREF GPIO1,
  PCLK/XCLK muxed GPIO44/43 or GPIO19/20, PWDN EXIO5.
- **USB**: D- GPIO19, D+ GPIO20. **UART0**: TX GPIO43, RX GPIO44.
- **RTC PCF85063ATL** @ 0x51 + 32.768 kHz crystal + backup battery header.
  The `RTC_INT` net exists but **where it terminates is unconfirmed**.
  sw3Dan's `rtc_int: 5` collides with CAM_PWDN and is unused in their own config.

### ⚠️ Battery ADC: conflicting sources, don't trust GPIO8

The schematic says **GPIO1** (behind 0 Ω jumpers R53/R78, sharing with CAM_HREF);
the Arduino demo says `BAT_ADC_PIN 8`. **The schematic is almost certainly right**:
GPIO8 on this board is LCD_SDA1/MISO, GPIO8 *is* the battery ADC on other
Waveshare S3 boards (classic copy-paste), and the same demo's LCD pins are
provably wrong too.

Either way, the schematic notes battery measurement is **not enabled by default**.
It needs a 0 Ω resistor soldered, **and doing so makes the camera unusable**.
Divider ratio is 3.0 (R2 200 k / R11 100 k). Treat battery monitoring as
unavailable.

## Gotchas

### Shared I2S clocks

ES8311 and ES7210 share BCLK/LRCK, so only one device may drive them. On top of
that, **ESPHome cannot run a single `i2s_audio` bus full-duplex**: a microphone
and a speaker on the same bus each call `i2s_new_channel` on the port, and the
second fails at runtime with `Parent bus is busy` (the speaker then crackles).

The layout this firmware uses, all on stock ESPHome components:

- **Two `i2s_audio` buses** (two I2S ports) over the shared GPIO13/14 (with
  `allow_other_uses`). The **mic bus is the I2S master**, the **speaker bus is a
  slave** reading its clock.
- The mic is always capturing for the wake word, so as master it drives
  BCLK/LRCK/MCLK **continuously** - exactly what a slave speaker and the ES8311
  need. It also gives the mic a correct-rate stream.
- The mic is pinned to **16-bit**: as master it sets the frame slot width, and
  the i2s_audio default is 32-bit, which against the 16-bit DAC produces noise.

The board's original ESPHome config (sw3Dan) instead made the **ES8311** the
master via a patched component (`force_master`, setting the codec's MSC bit).
That works, but it fed the ESP mic a wrong-rate stream that killed the wake word;
the ESP-mastered two-bus layout above avoids the patch entirely. See
`base/core.yaml` for the annotated config.

### ⚠️ Cold-boot failure of the ES7210 / LEDs: no verified fix

There is a [HA community thread](https://community.home-assistant.io/t/help-needed-waveshare-esp32-s3-audio-board-cold-boot-failure-of-es7210-mic-and-leds-tca9555/1009883)
reporting that the mic and LEDs don't come up on a cold boot, only after a
reset. **It is a single post with zero replies, a question rather than an
answer**, so no root cause or fix has been published for this board.

What its register dumps do establish:

| Device | Reg | Warm (works) | Cold (fails) |
|---|---|---|---|
| TCA9555 | 0x06 | `0x9C` | `0xFF` |
| ES7210 | 0x00 | `0x41` | `0x32` |
| ES7210 | 0x02 | `0xC1` | `0x02` |

TCA9555 regs 0x06/0x07 are the **direction registers**, power-on default
`0xFF` = all inputs. So the cold dump is just the un-configured power-on state,
and the warm one is what the previous firmware left behind, meaning **PA_EN
(EXIO8) is never driven, so the amp stays off.** Waveshare's own code fixes this
explicitly with `TCA9555PWR_Init(0x0000)` (all pins to output).

What that mechanism does **not** account for:

- **The LED symptom.** The ring is on GPIO38 over RMT, nowhere near the
  expander, so an expander direction register cannot keep it dark. (The
  reporter's "green LED" may be `LED1`, the hardware charge indicator, which
  firmware cannot control.)
- **The ES7210 registers.** The reporter states that replaying them did not
  help. Their other unsuccessful attempts were delays up to 1000 ms and bringing
  MCLK up before I2C.

**What this firmware does** (a mechanism-based mitigation, not a proven fix):
ESPHome's `tca9555` writes the direction registers itself, and the `amp_enable`
GPIO switch with `restore_mode: RESTORE_DEFAULT_ON` drives PA_EN at boot. This
matches sw3Dan's config, which is reported working.

### Amp idle hiss / turn-on pop

Waveshare's `Audio_Init()` orders it **codec first, amp second**
(`es8311_codec_init()` then `Audio_PA_EN()`), with a 50 ms delay after each
`Set_EXIO`. An amp left enabled at boot amplifies the undriven DAC line as a
faint hiss until the first playback. This firmware gates the amp instead:
`amp_enable` is `ALWAYS_OFF` at boot and the media_player `on_state` turns it on
when playback starts (then leaves it on, since the speaker holds the line at
clean silence via `timeout: never`).

### Strapping pins

ESP32-S3 straps are **GPIO0, GPIO3, GPIO45, GPIO46**.

| Pin | Board use | Risk |
|---|---|---|
| GPIO0 | BOOT button | fine, intended |
| GPIO3 | LCD_CS | floating by default; don't add strong pulls |
| **GPIO45** | CAM_D4 | ⚠️ must be **LOW at boot** (VDD_SPI = 3.3 V) |
| **GPIO46** | CAM_D5 | ⚠️ must be **LOW at boot** |

⚠️ **A camera plugged into J3 sits on two strapping pins.** If the module drives
them HIGH during reset the board may not boot, which is relevant even for a
voice-only build if a camera is left connected.

### GPIO33-37 do not exist for you

The octal PSRAM occupies **GPIO33-37** (on top of flash on GPIO26-32). No
Waveshare pinout table assigns them. Any config claiming to use them is wrong.

## Unresolved

Documented rather than guessed at:

1. **Battery ADC pin**: GPIO1 (schematic) vs GPIO8 (demo).
2. **EXIO6 vs EXIO7**: official sources contradict each other.
3. **ES7210 slot order**: wiring (CH3 = ref) vs demo's `"RMNM"`.
4. **EXIO4**: no known function.
5. **RTC_INT**: net exists, terminus unknown.
6. **RGB vs GRB**: verify with a pure-red test.
7. **I2C pull-ups**: resistors visible, nets not resolvable from the PDF text.
8. **Cold-boot fix**: none published.
