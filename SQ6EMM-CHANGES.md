# SQ6EMM rotator firmware changes

Current release: **ver 6** (`release/SQ6EMM-k3ng-2020.08.26.02-ver6.hex`, 27078 bytes, flashed and verified 2026-10-11 20:13 UTC).

Base: K3NG rotator controller, OK1HRA fork, commit `d4b870f` ("interface rev.4 modify"), CODE_VERSION `2020.08.26.02`.
Hardware: RemoteQTH Rotator Interface 4.0.3 (ATmega328P, Optiboot 4.4, FT232RQ with DTR auto-reset), SPID RAU
(pulses from the motor side, before the self-locking slew drive; the controller sees 1 pulse per degree).
Controller is attached to `rpi5-server` (`/dev/rotator`), driven by `rotctld -m 603` (GS-232B).

## 1. Reconstructed original configuration (commit `c960e5e`)

Recovered from the flash backup of 2026-10-11 (89.8 % of instruction words identical; the pulse ISR identical):

| Setting | Repository | Unit |
|---|---|---|
| position sensor | `FEATURE_AZ_POSITION_POTENTIOMETER` | `FEATURE_AZ_POSITION_PULSE_INPUT` |
| `AZ_POSITION_PULSE_DEG_PER_PULSE` | 0.5 | 1.0 |
| `OPTION_PULSE_IGNORE_AMBIGUOUS_PULSES` | off | on |
| `AZIMUTH_TOLERANCE` | 3.0 | 1.0 |
| `SLOW_DOWN_BEFORE_TARGET_AZ` | 10.0 | 3.0 |
| `AZ_MANUAL_ROTATE_CW_LIMIT` | 535 | 360 |
| start / capability defaults | 180 / 450 | 0 / 360 (EEPROM holds 0 / 360) |

Wiring (binary + schematic): D2 = INT0 pulse input (PULSE-CCW line, 10k pull-up, 1k/100n/1k + BAV99), D3 = INT1 (PULSE-CW,
unused), D8 CW relay, D9 CCW relay, D10 brake, D11 PWM speed (Q4 fitted), A3/A4/A5 START/CCW/CW buttons (LEDs on
D10/D9/D8), A6/A2 preset encoder (channels A/B, 1k pull-up, 1k series, 100 nF = only 0.1 ms filter), LCD 16x2 on
D4-D7/D12/D13, AREF from a resistor divider (external reference).

## 2. Problems found

1. `OPTION_PULSE_IGNORE_AMBIGUOUS_PULSES`: every pulse while the motor was not driven was discarded. After each stop the
   motor coasts (and turns the antenna through the slew drive) - those degrees were lost. Main cause of the drift.
2. Hard limit clamp: pulses beyond 0 / 360 were discarded.
3. `\A` did not set the pulse counter - calibration lost on the first pulse (only `\A` + `\Q` worked).
4. No debounce on the azimuth pulse input (reed contact).
5. Counter (`volatile float`) read without disabling interrupts.
6. Position saved to EEPROM only every 30 s; the FTDI DTR line resets the controller whenever the port is opened.
7. A start in the opposite direction while the motor still coasts counted the coasting pulses in the new direction.
8. Several hard stops (REQUEST_KILL); a second STOP during slow-down was a hard stop.
9. Slow-down zone was only entered from NORMAL speed: short moves reached the target inside the start ramp and were
   switched off at almost full speed (overshoot 0.5-1 deg, found in the drift test).
10. Preset encoder on A6 (analog-only) polled via `analogRead()` once per main loop; +5 deg acceleration; wrap-around
    0 <-> 360. `analogReference(EXTERNAL)` was only set in an unused function, so A6/A2 were read with the AVcc reference
    while a divider drives AREF.

## 3. Changes (switches in `rotator_features.h`, settings in `rotator_settings.h`)

`OPTION_SQ6EMM_PULSE_FIXES`
- coasting pulses counted in the last direction (`OPTION_PULSE_IGNORE_AMBIGUOUS_PULSES` disabled)
- ISR: level read and re-checked after `AZ_PULSE_STABLE_US` (300 us), guard `AZ_PULSE_DEBOUNCE_US` (2 ms), level tracking
- counting continues `AZ_PULSE_LIMIT_MARGIN` (15 deg) beyond start / start+capability
- a start in the opposite direction waits until no pulse for `AZ_PULSE_QUIET_MS` (300 ms)
- `\A` also sets the pulse counter (atomically); counter copied atomically in `read_azimuth()`
- raw azimuth keeps half degrees; GS-232 `C` reports the rounded value (`\?AZ` gives the decimal value)
- position saved to EEPROM `AZ_EEPROM_SAVE_AFTER_STOP_MS` (1 s) after every stop; `EEPROM.update()` (changed bytes only)
- stall guard: motor driven but no pulse for `AZ_STALL_NO_PULSE_MS` (1.5 s), armed after `AZ_STALL_ARM_MS` (3 s) -> off
- `\?PD`: `a` accepted edges, `r` rejected, `c` coasting, `h` held starts, `s` stalls, `e/i/k` encoder transitions /
  invalid / clicks, `H`/`L` avg/min ms of the open/closed contact phase

`OPTION_SQ6EMM_PULSE_BOTH_EDGES`
- interrupt on both edges, 0.5 deg per edge (`AZIMUTH_TOLERANCE` 0.5 = "stop exactly on target", as before)

`OPTION_SQ6EMM_ALWAYS_SOFT`
- soft start always; soft stop everywhere: target reached, button release, preset START while rotating, manual limits
  (ramp starts `AZ_SOFT_LIMIT_ANTICIPATION` = 5 deg before the limit), operation timeout, second STOP during slow-down
- slow-down zone also entered from the start ramp (short moves), starting PWM clamped to
  `AZ_INITIALLY_IN_SLOW_DOWN_PWM` (100) .. `AZ_SLOW_DOWN_PWM_START` (200); floor `AZ_SLOW_DOWN_PWM_STOP` 64
  (20 stalled the motor from standstill)
- immediate stop only for explicit STOP commands: GS-232 `S` and `A`, Easycom `SA`

`OPTION_SQ6EMM_ENCODER_ADC`
- preset encoder sampled by the ADC interrupt (A6/A2 alternately, ~4.8 kHz each), external AREF reference
- per-channel hysteresis (`SQ6EMM_ENC_LOW` 300 / `SQ6EMM_ENC_HIGH` 700) and debounce (`SQ6EMM_ENC_STABLE_SAMPLES` 5 = ~1 ms)
- quadrature decoding, 4 transitions per click (`SQ6EMM_ENC_TRANSITIONS_PER_CLICK`), skipped state = double step
- 1 deg per click, 10 deg per click when 5 clicks within 150 ms; target clamped to 0..360 (no wrap-around)
- `SQ6EMM_ENC_REVERSE` swaps the direction; `\?PE` shows the last 32 encoder states + raw ADC A6/A2

`OPTION_SQ6EMM_NO_GRID_CMDS`
- `\?CG \?GC \?GT \?BG \?BC` removed (unused by Hamlib/GS-232; frees ~4 kB incl. the float trig library)

Splash screen: `K3NG/SQ6EMM` / `Rotator ` + `SQ6EMM_VERSION` (currently "ver 6").

Unchanged: EEPROM layout and magic number (111), pins, speeds (X1-X4 via `w X1`..`w X4`), display, buttons.

## 4. Flash size limit - IMPORTANT

The application area ends at **0x7800 (30720 bytes)**. Optiboot itself is only 512 bytes at 0x7E00, but the fuses
reserve a 2 kB boot section; writes into 0x7800-0x7DFF are silently ignored. A 31060-byte build (first sq6emm4) was
written incompletely (verify mismatch at 0x7800) and the controller stopped responding until sq6emm3 was flashed back.
Always check that the hex ends at or below 0x7800, and flash with an automatic fallback (see section 6).

## 5. Verification

- ISR logic simulated (`tools-sim_isr.py`): 0.0 deg error after 360 deg for duty cycles 5-50 %, bounce, EMI glitches
- contact duty measured: closed ~77 % of each degree (half steps ~0.77 / 0.23 deg, each pair exactly 1 deg)
- drift test (sq6emm1): 51 moves, 848 deg, 1696 edges = exactly 2/deg, 0 rejected; Sky Tower check -0.14 deg after the test
- short/long moves (sq6emm3+): 15/15 exactly on target, no coasting past target, no stalls; 1 deg ~1.2 s, 5 deg ~3 s, 100 deg ~25 s
- slew drive backlash: ~0.26 deg direction-dependent offset at Sky Tower (mechanical, below resolution)
- buttons CW/CCW: soft start, soft stop on release; START with encoder target moves to the target

## 6. Flash procedure (on rpi5-server)

```
sudo -n pkill -x rotctld
podman run --rm --device /dev/ttyUSB1 --group-add keep-groups -v $PWD/release:/r:Z rotator-avrdude:local \
  -p m328p -c arduino -P /dev/ttyUSB1 -b 115200 -U flash:w:/r/<file>.hex:i
# check "<N> bytes of flash verified"; otherwise flash the previous release immediately
sudo -n setsid -f /usr/bin/rotctld -m 603 -r /dev/rotator </dev/null >/dev/null 2>&1   # detach, or ssh hangs
```
EEPROM is never touched (Optiboot 4.4 cannot read or write it): calibration, start/capability and position survive.
Fallback to the unmodified unit firmware: `release/ORIGINAL-app-only_20261011.hex`.

## 7. Preset encoder - hardware defect (open)

With ver 6 the encoder signals are clean (debounced) but not decodable: A2 always falls first in both directions and the
same complete sequence (A2 down, A6 down, A6 up, A2 up) occurs for CW and CCW clicks. The direction is not in the
signal -> the encoder is worn/defective. Replace with an EC11-type encoder, 24 pulses / 24 detents, 6 mm shaft, ~25 mm
(pins A-C-B + housing). ver 6 is ready for it; set `SQ6EMM_ENC_REVERSE` if the direction comes out swapped.
Until then the encoder target only takes effect with START, so it is harmless if not used.

## 8. Version history

| Version | Size | Status | Content |
|---|---|---|---|
| original | 28.3 kB | backup | reconstructed config (section 1) |
| sq6emm1 | 30274 B | superseded | pulse fixes, both edges, soft stop, `\?PD` |
| sq6emm2 | 30324 B | **do not use** | slow-down from start ramp with PWM floor 20 - stalled on short moves |
| sq6emm3 | 30540 B | good | floor 64, start-in-zone 100, stall guard |
| sq6emm4 (31060 B) | - | **too big, failed** | first ADC encoder attempt (exceeded 0x7800) |
| sq6emm4 | 26750 B | good | ADC encoder, grid commands removed |
| sq6emm5 / 5d | 26776 / 27048 B | superseded | encoder thresholds; `\?PE` diagnostics |
| **ver 6** | **27078 B** | **current** | per-channel encoder debounce, direction switch |
