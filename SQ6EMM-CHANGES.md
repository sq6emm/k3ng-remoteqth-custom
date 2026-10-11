# SQ6EMM rotator firmware changes

Base: K3NG rotator controller, OK1HRA fork, commit `d4b870f` ("interface rev.4 modify"), CODE_VERSION `2020.08.26.02`,
RemoteQTH Rotator Interface 4.0.3 (ATmega328P, Optiboot 4.4, FT232RQ), SPID RAU (pulses from the motor side, before the
self-locking slew drive; the controller sees 1 pulse per degree).

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

Wiring (from binary + schematic): D2 = INT0 pulse input (PULSE-CCW line), D8 CW relay, D9 CCW relay, D10 brake,
D11 PWM speed, A3/A4/A5 START/CCW/CW buttons (with LEDs), A6/A2 preset encoder (read via ADC), LCD 16x2 on D4-D7/D12/D13.

## 2. Problems found

1. `OPTION_PULSE_IGNORE_AMBIGUOUS_PULSES`: every pulse while the motor is not driven was discarded. After each stop the
   motor coasts (and turns the antenna through the slew drive) - those degrees were lost. Main cause of the drift.
2. Hard limit clamp: pulses beyond 0 / 360 were discarded.
3. `\A` did not set the pulse counter - calibration lost on the first pulse (only `\A` + `\Q` worked).
4. No debounce on the azimuth pulse input (reed contact), hardware RC only ~0.1 ms.
5. Counter (`volatile float`) read without disabling interrupts.
6. Position saved to EEPROM only every 30 s; the FTDI DTR line resets the controller whenever the port is opened.
7. A start in the opposite direction while the motor still coasts counted the coasting pulses in the new direction.
8. Several hard stops (REQUEST_KILL) besides the STOP commands; a second STOP during slow-down was a hard stop.

## 3. Changes (switchable in `rotator_features.h`)

`OPTION_SQ6EMM_PULSE_FIXES`
- coasting pulses counted in the last direction (`OPTION_PULSE_IGNORE_AMBIGUOUS_PULSES` disabled)
- ISR: level read, re-checked after `AZ_PULSE_STABLE_US` (300 us), guard `AZ_PULSE_DEBOUNCE_US` (2 ms), level tracking
- counting continues `AZ_PULSE_LIMIT_MARGIN` (15 deg) beyond start / start+capability
- a start in the opposite direction waits until no pulse for `AZ_PULSE_QUIET_MS` (300 ms)
- `\A` also sets the pulse counter (atomically); counter copied atomically in `read_azimuth()`
- raw azimuth keeps half degrees; GS-232 `C` reports the rounded value
- position saved to EEPROM `AZ_EEPROM_SAVE_AFTER_STOP_MS` (1 s) after every stop; `EEPROM.update()` (changed bytes only)
- `\?PD` diagnostics: `a` accepted edges, `r` rejected, `c` coasting, `h` held starts, `H`/`L` avg/min ms of the open/closed phase

`OPTION_SQ6EMM_PULSE_BOTH_EDGES`
- interrupt on both edges, 0.5 deg per edge (`AZIMUTH_TOLERANCE` 0.5 = "stop exactly on target", as before)

`OPTION_SQ6EMM_ALWAYS_SOFT`
- soft start always (slow start), soft stop everywhere: target reached (slow-down zone), button release, preset START
  button while rotating, manual limits (ramp starts `AZ_SOFT_LIMIT_ANTICIPATION` = 5 deg before the limit),
  operation timeout, second STOP during slow-down (continues ramping; from the target slow-down it switches to the timed ramp)
- immediate stop only for explicit STOP commands: GS-232 `S` and `A`, Easycom `SA`

Unchanged: EEPROM layout and magic number (111), all pins, speeds (X1-X4), display, buttons, encoder.

## 4. Verification before flashing

- compiles with arduino-cli 0.35.3 / AVR core 1.8.3 (avr-gcc 7.3.0): 30274 bytes flash (limit 32256 with Optiboot 512 B), 548 bytes RAM free
- ISR logic simulated (`tools-sim_isr.py`): 0.0 deg error after 360 deg for duty cycles 5-50 %, bounce 0.5-1.5 ms, EMI glitches

## 5. Flash / fallback

- new: `release/SQ6EMM-k3ng-2020.08.26.02-sq6emm1.hex`
- fallback: `release/ORIGINAL-app-only_20261011.hex` (backup without the bootloader area)
- `avrdude -p m328p -c arduino -b 115200 -P /dev/rotator -U flash:w:<hex>:i` (rotctld stopped); EEPROM is not touched (Optiboot 4.4)
