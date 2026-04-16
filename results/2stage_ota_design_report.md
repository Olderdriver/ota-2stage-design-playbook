# Two-Stage OTA Design Report

## 1. Design Target

Target metrics requested by user:

- PSRR > 80 dB
- CMRR > 80 dB
- Open-loop gain > 80 dB
- Slew rate between 1 V/us and 5 V/us

## 2. Topology Choice

This delivery uses a two-stage Miller OTA instead of the repository's baseline 5T OTA. The 5T OTA flow was run first as a baseline and produced only about 39 dB open-loop gain, so it is structurally insufficient for the requested gain/PSRR/CMRR targets.

The delivered topology is:

- Stage 1: PMOS differential pair + NMOS mirror active load
- Stage 2: NMOS common-source second gain stage + PMOS current-source load
- Compensation: Miller capacitor between first-stage output and final output

## 3. Implemented Device Parameters

- VDD = 1.8 V
- VCM = 0.9 V
- VBP1 drop from VDD = 0.600 V
- VBP2 drop from VDD = 0.528 V
- L_IN = 0.18 um, NFIN_IN = 20
- L_LOAD = 0.24 um, NFIN_LOAD = 8
- L_TAIL = 0.24 um, NFIN_TAIL = 12
- L_STAGE2 = 0.24 um, NFIN_STAGE2 = 11
- L_P2 = 0.24 um, NFIN_P2 = 15
- Miller capacitor Cc = 3.5p
- Nulling resistor Rz = 6.8k
- Load capacitor CL = 8p

## 4. Design Intent

The first stage is reduced to a standard PMOS differential pair with an NMOS mirror load so the OTA can establish a valid DC operating point before any higher-gain cascode structure is reconsidered. The second stage uses an NMOS common-source device with a PMOS current-source load so the first-stage output common-mode can more naturally bias the second stage into a useful operating region. A series nulling resistor is added with the Miller capacitor to move the compensation zero away from the destabilizing right-half-plane behavior. Device lengths are pushed to the process limit to maximize output resistance, and larger compensation/load capacitors are used to intentionally slow the large-signal response toward the requested slew-rate band.
