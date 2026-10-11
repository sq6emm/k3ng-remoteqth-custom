# k3ng-remoteqth-custom

Customised K3NG rotator controller firmware for the **RemoteQTH Rotator Interface 4.0.3** (ATmega328P / Optiboot)
driving a **SPID RAU** azimuth rotator with motor-side pulse sensing (1 pulse per degree), as used at SQ6EMM.

Based on:
- [K3NG Rotator Controller](https://github.com/k3ng/k3ng_rotator_controller) by Anthony Good, K3NG (GPL-3.0)
- [OK1HRA fork](https://github.com/ok1hra/k3ng_rotator_controller), commit `d4b870f` ("interface rev.4 modify"), CODE_VERSION `2020.08.26.02`

## What is different

- **No more position drift with pulse sensors**: coasting pulses after a stop are counted (the slew drive cannot be
  back-driven), no reversal while coasting, counting continues past the 0/360 limits, `\A` really sets the position,
  position saved to EEPROM after every stop.
- **Both pulse edges counted** (0.5 deg steps with a 1 pulse/deg sensor), robust against contact bounce and EMI
  (stability check + guard + level tracking, verified in simulation and with a 848 deg drift test: 0 lost pulses).
- **Always soft start and soft stop** (also for short moves); only explicit STOP commands (GS-232 `S`/`A`) stop immediately.
- **Stall guard**: motor switched off if no pulses arrive while driven.
- **Preset encoder** on A6/A2 sampled by the ADC interrupt with per-channel debounce; 1 deg per click; no wrap-around.
- Diagnostics: `\?PD` (pulse/encoder counters, contact duty cycle), `\?PE` (encoder states, raw ADC).
- Splash screen `K3NG/SQ6EMM` + version.

All changes are behind `OPTION_SQ6EMM_*` switches in `rotator_features.h`; settings are at the end of
`rotator_settings.h`. Full details, test results and version history: **[SQ6EMM-CHANGES.md](SQ6EMM-CHANGES.md)**.
The first commit of this repository is the reconstructed *original* configuration of the unit
(see [RECONSTRUCTED-CONFIG.diff](RECONSTRUCTED-CONFIG.diff)).

## Build

Arduino AVR core 1.8.3 (avr-gcc 7.3.0), LiquidCrystal 1.0.7, board **Arduino Nano (ATmega328P)**:

```
arduino-cli compile --fqbn arduino:avr:nano:cpu=atmega328 --libraries ./libraries ./k3ng_rotator_controller
```

> **Flash size limit: 30720 bytes (application must end at or below 0x7800).** The fuses reserve a 2 kB boot section
> even though Optiboot is only 512 bytes; anything above 0x7800 is silently not written. Check the size before flashing.

## Flash

```
avrdude -p m328p -c arduino -P /dev/rotator -b 115200 -U flash:w:k3ng_rotator_controller.ino.hex:i
```
Stop anything holding the serial port (e.g. `rotctld`) first. The EEPROM (calibration, range, position) is not touched.

## License

GPL-3.0, as the original K3NG code. See [LICENSE](LICENSE).
