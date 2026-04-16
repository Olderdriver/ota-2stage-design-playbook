---
name: ota-2stage-design-playbook
description: "Reusable playbook for designing and tuning a 1.8V two-stage Miller OTA in this repository with gm/ID sizing, batched HSPICE sweeps, DC-first validation, and large-signal waveform debugging guidance. Covers what to do first, what not to do, and how to choose transistor sizes, bias, and compensation from evidence instead of guessing."
---

# Two-Stage OTA Design Playbook Skill

> **Important — this skill is a reusable design process, not just a final answer.**
> Use it when the task is to design, retune, debug, or validate a two-stage OTA in this repository and the user wants a method that can be repeated.

## Purpose

This skill captures the design experience from the two-stage OTA work in this repository and turns it into a repeatable flow.

It is specifically for the topology implemented under:

- `references/simulate_2stage_ota.py`
- `references/netlist/`

The target topology is:

- Stage 1: **PMOS differential pair**
- Stage 1 load: **NMOS current-mirror active load**
- Tail source: **PMOS current source**
- Stage 2: **NMOS common-source gain stage**
- Stage 2 load: **PMOS current-source load**
- Compensation: **series `Rz` + Miller `Cc`** from node `n2` to `out`

This skill is intended to prevent ad-hoc tuning and to enforce a **DC-first, gm/ID-backed, sweep-backed** methodology.

---

## When to Use

Use this skill when the user asks to:

- design a two-stage OTA from scratch
- improve gain / UGF / PM / CMRR / PSRR / slew
- debug abnormal transient waveforms
- choose transistor sizes with gm/ID
- tune compensation (`Cc`, `Rz`)
- fix asymmetric `SR+` / `SR-`
- produce a final HSPICE netlist and evidence package

Do **not** use this as a generic analog design recipe for unrelated topologies without checking that the same structure still applies.

---

## Design Goals This Flow Handles Well

This playbook works best when the requirements look like:

- open-loop gain > 80 dB
- stable unity follower operation
- controllable slew band
- moderate bandwidth in the MHz range
- output load capacitor known up front
- large-signal waveform shape matters, not just AC metrics

It is especially useful when the user cares about:

- **normal rise-hold-fall transient behavior**
- **parameter choices supported by simulation data**
- **avoiding guessed tuning**

---

## Core Rules

### Rule 1 — DC operating point comes before everything else

Before trusting any AC, CMRR, PSRR, or transient result:

- run `.op`
- confirm all core transistors are in saturation / active region
- confirm `vds > vdsat` on critical devices
- reject any point where the DC gate fails

In this repository, the DC gate is implemented in:

- `references/simulate_2stage_ota.py`
- `references/netlist/op_2stage_ota_check.sp.tmpl`

If DC is wrong, every later result is suspect.

### Rule 2 — Do not guess parameter values

If a user asks to improve the OTA:

- use `GmIdTable` for initial sizing
- use HSPICE sweeps for refinement
- only keep values that are backed by simulation evidence

Do **not** say “this value should be better” unless a sweep or gm/ID estimate supports it.

### Rule 3 — Large-signal waveform quality matters separately from AC stability

A design can have:

- high gain
- good PM
- acceptable UGF

and still have a **bad unity-follower transient**.

Always inspect:

- `Vout`
- internal node `n2`
- whether the waveform has the expected **rise → hold → fall** behavior

If `n2` collapses or saturates badly during the transition, AC metrics alone are not enough.

### Rule 4 — Use batch sweeps, not repeated HSPICE startup

When scanning parameters:

- prefer `.alter` batch sweeps in one HSPICE run
- do not repeatedly relaunch HSPICE for dense parameter scans

This repository already established that startup overhead can dominate runtime if this rule is ignored.

---

## What to Do First

Always follow this priority order.

### Step 1 — Confirm the topology is capable of the target

Before tuning details, make sure the topology is structurally capable.

Example from this project:

- the baseline 5T OTA had only about 39 dB gain and poor DC behavior
- it was not worth heavy tuning for a target above 80 dB gain
- switching to the two-stage Miller OTA was the right first move

If a topology misses the target by architecture, do **not** waste time micro-tuning it.

### Step 2 — Fix the testbench so it is physically meaningful

Before blaming the circuit, check whether the excitation is reasonable.

For transient slew in this project:

- an earlier input swing was too large and drove the OTA out of its useful region
- that produced misleading “slow and small” output movement

So before tuning the circuit:

- center the input around the intended common-mode region
- use a realistic large-signal step
- make sure the requested output swing is actually achievable

### Step 3 — Establish a valid DC operating point

Choose biasing so that:

- the output settles near the intended common-mode operating point
- stage-2 devices remain in saturation
- tail source has enough headroom
- first-stage output node `n2` sits in a usable range for driving stage 2

Only after this should you move to AC or transient tuning.

### Step 4 — Use gm/ID to produce the first reasonable sizing point

Do not start from arbitrary widths.

- `references/design_gmoverid.py` and the `GmIdTable` API to estimate:

- input pair sizing
- load sizing
- tail device sizing
- stage-2 device sizing
- initial current split

The purpose of gm/ID here is **not** to finish the design automatically.

The purpose is to avoid beginning from nonsense.

### Step 5 — Only then tune compensation and large-signal behavior

Once the OTA has a valid DC point and the rough gm/ID sizing is done:

- tune `Cc`
- tune `Rz`
- inspect `n2` and `Vout`
- use batch sweeps to shape the transient waveform

---

## What Not to Do

### Do not tune AC before DC is validated

If `.op` fails, do not proceed to AC interpretation.

### Do not use a huge unrealistic input pulse and then conclude the OTA is broken

An invalid testbench can look like a circuit problem.

### Do not keep increasing `Cc` just because it reduces overshoot

Large `Cc` can hide instability symptoms while creating a different problem:

- very slow rise
- no hold interval during the high input level
- a waveform that never reaches the target before the input falls back

### Do not interpret “better transient” points that break DC as valid solutions

A point may look better during a transient batch sweep but still be unusable in a real design if the quiescent operating point is wrong.

### Do not force all width into `NFIN`

For this process and design flow:

- large effective width should often be realized with multiplier `m`
- not by pushing `NFIN` alone to impractical values

### Do not rely on a single metric

Examples of misleading single-metric conclusions:

- “PM is good, so the waveform must be fine”
- “SR+ is in spec, so slew is done”
- “CMRR is close enough, so DC can be ignored”

Always check the full set of relevant behaviors.

---

## What You Can Do Safely

You can and should:

- use gm/ID for initial sizing
- use `.alter` batch sweeps for bias / compensation scans
- inspect `n2` to diagnose large-signal behavior
- use `m` multipliers to realize larger effective stage-2 devices
- separate **topology problems**, **bias problems**, and **compensation problems**
- adjust the testbench if it is not physically meaningful
- write helper sweep scripts if they reduce repeated simulator startup

---

## Transistor Sizing Strategy

This section is the most reusable part of the skill.

### 1. Input pair (`XM1`, `XM2`)

Role:

- sets input transconductance
- contributes significantly to noise / input sensitivity / first-stage gain
- helps determine the first-stage pole and compensation needs

Sizing strategy:

- choose **shorter L than the other devices if speed is needed**, but not so short that gain collapses
- in this project the final choice was:
  - `L_IN = 0.18 um`
  - `NFIN_IN = 20`
  - `M_IN = 1`

Reasoning:

- shorter than load/tail/stage-2 devices to preserve gm
- wide enough to get useful gm at modest current
- not expanded with large `m` because the first stage was already adequate

When to increase input pair size:

- if first-stage gm is too low
- if UGF is too low
- if slew shaping through compensation becomes impossible because stage 1 is too weak

When **not** to increase it:

- if the real problem is stage-2 drive or compensation
- if the DC node `n2` is already poorly biased

### 2. Mirror load (`XM3`, `XM4`)

Role:

- converts differential current to single-ended node `n2`
- influences first-stage gain and node bias

Sizing strategy:

- use longer L than input pair to improve output resistance
- keep it moderate in size so `n2` is not over-constrained

Final project choice:

- `L_LOAD = 0.24 um`
- `NFIN_LOAD = 8`
- `M_LOAD = 1`

Reasoning:

- long enough to support gain
- not oversized
- avoids excessive parasitic loading on `n2`

### 3. Tail source (`XM5`)

Role:

- sets first-stage branch current
- affects gm of the input pair
- affects DC headroom and common-mode behavior

Sizing strategy:

- use longer L for better current-source behavior
- choose enough width for bias current without wasting headroom

Final choice:

- `L_TAIL = 0.24 um`
- `NFIN_TAIL = 12`
- `M_TAIL = 1`

Reasoning:

- tail current needed to support the chosen input gm
- current source should be reasonably stiff
- excessive tail current would increase slew and power unnecessarily

### 4. Stage-2 NMOS (`XM6`)

Role:

- main pull-down device at output
- dominant factor in negative slew rate `SR-`
- strongly affects large-signal settling behavior

Sizing strategy:

- start from gm/ID sizing
- realize extra drive with multiplier `m`, not only bigger `NFIN`
- increase only as much as needed for rise-hold-fall behavior and bandwidth

Key lesson from this project:

- increasing stage-2 drive fixed the slow-rising, no-hold waveform
- but too-strong `XM6` made `SR-` much larger than `SR+`

This means:

- `XM6` is usually the first suspect when `SR-` is too fast
- but reducing `XM6` alone can destroy the DC operating point if `XM7` is not adjusted consistently

Final kept choice:

- `L_STAGE2 = 0.24 um`
- `NFIN_STAGE2 = 11`
- `M_STAGE2 = 4`

This was not because it gave the smallest `SR-`, but because it gave the best **overall** tradeoff between:

- proper rise-hold-fall transient behavior
- valid DC operating point
- acceptable `SR+`
- acceptable gain / PM / bandwidth

### 5. Stage-2 PMOS load (`XM7`)

Role:

- provides output pull-up current
- sets the quiescent output operating point together with `XM6`
- strongly impacts large-signal upward motion and DC output bias

Sizing strategy:

- use longer L for output resistance
- size together with `XM6`, not independently
- if `XM7` becomes too strong relative to `XM6`, the output DC point can rail upward

Final kept choice:

- `L_P2 = 0.24 um`
- `NFIN_P2 = 15`
- `M_P2 = 4`

Key lesson:

- the pair `XM6` / `XM7` must be tuned as a matched stage-2 system
- not as two independent knobs

---

## Bias Selection Strategy

### `VBP1`

`VBP1` sets the PMOS tail current source.

Strategy:

- choose it from the desired first-stage current using gm/ID
- verify that the tail source has enough headroom over the full operating region

Final kept value:

- `VBP1_DROP = 0.600 V`

### `VBP2`

`VBP2` sets the PMOS load current of stage 2.

Strategy:

- it is extremely sensitive
- scan it in fine steps near the intended operating point
- always verify DC output bias after any `VBP2` change

Key lesson from this project:

- `VBP2_DROP = 0.528 V` was a narrow valid point
- moving to `0.529 V` or above caused the output bias to jump sharply upward
- some transient scan points looked better at larger `VBP2_DROP`, but those points failed DC and were rejected

Therefore:

- always do a **DC sweep of `Vout` vs `VBP2`** before trusting any transient improvement from `VBP2` changes

---

## Compensation Strategy

### Compensation network structure

Use:

- `Rz` in series with `Cc`
- from node `n2` to output `out`

Purpose:

- stabilize the two-stage OTA
- control the zero location
- prevent large-signal internal-node collapse from becoming severe

### `Cc` selection strategy

`Cc` controls two very different things at once:

1. stability / node coupling
2. large-signal speed

Key lessons:

- too small `Cc` can let `n2` collapse badly and create abnormal overshoot / nonlinear behavior
- too large `Cc` can make the output rise so slowly that there is almost no hold interval during the input high level

So `Cc` must be chosen by sweep, not by ideology.

In this project:

- large `Cc` values reduced overshoot
- but they also made the waveform too slow
- after stage-2 drive was strengthened, a moderate `Cc` became viable again

Final kept value:

- `Cc = 3.5 pF`

### `Rz` selection strategy

`Rz` is not just a PM knob.

It also changes:

- the effective large-signal behavior of the compensation path
- how sharply the output falls after the input step returns low

Key lesson from this project:

- reducing `Rz` from larger values to `6.8k` helped lower excessive `SR-` while preserving the rise-hold-fall waveform

Final kept value:

- `Rz = 6.8 kOhm`

---

## Large-Signal Debugging Strategy

If the unity-follower transient looks wrong, debug in this order.

### Symptom A — output moves in the wrong direction or barely moves

Check:

- testbench swing too large?
- common-mode outside valid range?
- stage 2 biased incorrectly?
- DC point invalid?

### Symptom B — output rises slowly and has almost no hold interval

Check:

- is `Cc` too large?
- is stage-2 drive too weak?
- does the output only reach the high level near the moment the input falls back?

This exact symptom occurred in this project.

Root cause found here:

- compensation was made too heavy to suppress earlier abnormal behavior
- stage-2 drive was still too weak
- result: most of the input-high interval was spent charging toward the target instead of holding it

Fix hierarchy:

1. strengthen stage-2 drive enough to restore a proper rise
2. then reduce `Cc` to a moderate value
3. re-sweep `Rz`

### Symptom C — output overshoots badly and `n2` collapses low

Check `n2` during the upward transition.

If `n2` collapses too far:

- `XM6` may effectively cut off
- feedback weakens during the transition
- output can continue charging under `XM7` action and overshoot

In that case:

- increase `Cc` moderately
- retune `Rz`
- verify that the waveform becomes monotonic enough without becoming too slow

### Symptom D — `SR-` is far larger than `SR+`

This happened in the final strong-drive design.

Diagnosis rule:

- first suspect `XM6` being too strong
- then check whether `Rz/Cc` can soften the fall
- only use `CL` as a tuning lever if load is truly allowed to change

Key project lesson:

- weakening `XM6` directly looked promising in transient-only sweeps
- but often broke the DC operating point when validated fully
- the usable fix was a compensation retune, not a naive stage-2 downsizing

---

## Recommended Design Flow

Use this sequence every time.

### Phase 1 — Topology sanity

1. confirm the target needs a two-stage OTA
2. reject structurally insufficient topologies early

### Phase 2 — gm/ID first pass

1. choose branch currents
2. size input, load, tail, stage-2 devices with `GmIdTable`
3. convert large required width into `m` where necessary
4. write an initial parameter block

### Phase 3 — DC gate

1. run `.op`
2. verify saturation / active region for all core devices
3. sweep output bias vs input common-mode if needed
4. sweep `VBP2` narrowly if the output bias is off

### Phase 4 — AC gate

1. run open-loop gain / phase
2. compute loop gain and PM
3. check UGF
4. check CMRR / PSRR

### Phase 5 — transient gate

1. run unity-follower transient with realistic input swing
2. inspect `Vout`
3. inspect `n2`
4. measure:
   - rise speed
   - hold interval
   - overshoot
   - `SR+`
   - `SR-`

### Phase 6 — batch refinement

Run batched `.alter` sweeps in this order:

1. `VBP2` near the DC operating point
2. `Cc` / `Rz`
3. stage-2 drive strength (`m_stage2`, `m_p2`) if required
4. load-dependent sweeps only if load is truly a free variable

### Phase 7 — final selection

Choose the solution that satisfies the user’s **actual priority order**, not the most extreme single metric.

For example, in this project the final chosen point prioritized:

- valid DC operation
- normal rise-hold-fall waveform
- gain > 80 dB
- PSRR around 90 dB+
- slew in the requested usable band

rather than trying to minimize `SR-` at all costs.

---

## Final Example Design Point From This Project

This project ended with the following practical design point:

- `VDD = 1.8 V`
- `VCM = 0.9 V`
- `VBP1_DROP = 0.600 V`
- `VBP2_DROP = 0.528 V`
- `L_IN = 0.18 um`, `NFIN_IN = 20`, `M_IN = 1`
- `L_LOAD = 0.24 um`, `NFIN_LOAD = 8`, `M_LOAD = 1`
- `L_TAIL = 0.24 um`, `NFIN_TAIL = 12`, `M_TAIL = 1`
- `L_STAGE2 = 0.24 um`, `NFIN_STAGE2 = 11`, `M_STAGE2 = 4`
- `L_P2 = 0.24 um`, `NFIN_P2 = 15`, `M_P2 = 4`
- `Cc = 3.5 pF`
- `Rz = 6.8 kOhm`
- `CL = 8 pF`

Verified behavior from the final report:

- gain ≈ `93.85 dB`
- UGF ≈ `7.71 MHz`
- PM ≈ `98.77 deg`
- CMRR ≈ `88.8 dB`
- PSRR+ ≈ `91.1 dB`
- `SR+ ≈ 5 V/us`
- `SR- ≈ 12 V/us`
- large-signal waveform restored to clear **rise → hold → fall** behavior

This point is not “universally optimal.”
It is the documented best compromise found under this project’s constraints.

---

## Files to Reuse

Primary implementation snapshots bundled with this skill:

- `references/simulate_2stage_ota.py`
- `references/netlist/op_2stage_ota_check.sp.tmpl`
- `references/netlist/dc_2stage_ota_bias.sp.tmpl`
- `references/netlist/ac_2stage_ota_openloop.sp.tmpl`
- `references/netlist/ac_2stage_ota_loopgain.sp.tmpl`
- `references/netlist/ac_2stage_ota_cmrr.sp.tmpl`
- `references/netlist/ac_2stage_ota_psrrp.sp.tmpl`
- `references/netlist/tran_2stage_ota_slew.sp.tmpl`
- `references/design_gmoverid.py`

Reference reports bundled with this skill:

- `references/2stage_ota_design_report.md`
- `references/2stage_ota_simulation_report.md`

Batch-sweep helper assets bundled with this skill:

- `assets/hspice_common.py` — shared HSPICE launcher, print-table parser, engineering-suffix parser
- `assets/sweep_vbp2_batch.py` — single-run `.alter` sweep for `VBP2_DROP`
- `assets/sweep_compensation_batch.py` — batch sweep for `Cc` / `Rz`
- `assets/sweep_vbp2_cc_batch.py` — joint sweep for `VBP2_DROP` and `Cc`
- `assets/sweep_stage2_drive_batch.py` — sweep `m_stage2` / `m_p2` drive strength
- `assets/sweep_srneg_batch.py` — isolate `SR-` sensitivity to stage-2 sizing
- `assets/sweep_cl_batch.py` — evaluate `CL` as a slew-control lever
- `assets/sweep_comp_srneg_batch.py` — retune `Cc` / `Rz` around a strong-drive point to reduce `SR-`

These assets are examples of the sweep methodology used to reach the final point. Reuse them as templates, but still validate every kept point with the full DC/AC/transient gate.

## Process Migration Guide

This packaged example is tied to a specific HSPICE model library and a FinFET device interface. If your target process does not use the same library or device cards, do not copy the netlists unchanged and assume the design is portable.

### 1. Replace the model library first

In the bundled examples, the library line points to the current usage deck, for example in `final_2stage_ota.sp` and the sweep scripts:

- `.lib '.../12sfe_spice_v1p2_rev0_usage.lib' tt_mos_varactor`

When migrating:

1. replace the `.lib` path with the target process usage/model deck
2. replace the corner name if the target deck uses a different section name
3. confirm the transistor subcircuit or model names still match the netlist
4. confirm the simulator can run a trivial `.op` deck before reusing the full OTA flow

Do not start by tuning `Cc`, `Rz`, or bias voltages before the model hookup itself is proven correct.

### 2. Rebuild gm/ID data for the new process

The gm/ID starting point is process-dependent.

When migrating to another library:

- regenerate the `GmIdTable` data with the target model deck
- re-extract the valid `gm/Id`, `gm/gds`, `ft`, and current-density ranges
- re-run initial sizing for input, load, tail, and stage-2 devices

Do **not** reuse the old 12SFE-derived `NFIN`, `L`, bias, or current values as if they were universal.

### 3. Re-check device interface assumptions

This design is written for a FinFET-style interface using parameters like:

- `nfin`
- `nf`
- `m`

Your target library may instead expect planar-CMOS style width parameters such as:

- `w`
- `l`
- `nf`
- `m`

or a different FinFET parameter set entirely.

Before reusing the templates, check:

- whether `n18_ckt` / `p18_ckt` still exist
- whether `nfin` is a valid parameter name
- whether `w` is interpreted per fin, per finger, or as total effective width
- whether `nf` and `m` mean the same thing in the target PDK

If those assumptions differ, adapt the templates first, then regenerate the initial sizing.

### 4. Treat bias values as non-portable

The kept values in this example, especially:

- `VBP1_DROP = 0.600 V`
- `VBP2_DROP = 0.528 V`

are not process-independent truths. They only make sense under the original supply, threshold, current-density, and headroom conditions.

On a new process:

- redo `.op`
- redo the DC bias sweep
- redo the narrow `VBP2` scan
- verify `Vout`, `n2`, and stage-2 saturation again

### 5. Re-tune compensation after migration

Even if the topology is unchanged, the pole/zero locations will move when the process changes.

Therefore after migration you should re-sweep:

- `Cc`
- `Rz`
- stage-2 drive strength
- load-dependent cases if `CL` is part of the spec

Do not assume `Cc = 3.5 pF` and `Rz = 6.8 kOhm` stay optimal in another PDK.

## FinFET-Specific Notes

This design flow assumes a FinFET process model rather than a simple planar MOS width-only model.

### 1. `NFIN` is a quantized geometry knob

In these netlists, `NFIN` is not just a cosmetic parameter. It is part of the device geometry and usually changes drive in discrete steps.

Implication:

- you often cannot realize an arbitrary effective width with one continuously scalable device
- small `NFIN` changes may move current and capacitance noticeably
- fine tuning often needs `m` in addition to `NFIN`

### 2. Prefer `m` for large effective-width expansion

A major lesson from this project was:

- do not force all extra drive into `NFIN`
- use multiplier `m` when larger effective width is needed

Why:

- it is often more realistic for FinFET implementation
- it avoids pushing one device to impractical fin counts
- it gives smoother sweep control when increasing stage-2 drive

This is exactly why the final stage-2 devices used:

- `NFIN_STAGE2 = 11`, `M_STAGE2 = 4`
- `NFIN_P2 = 15`, `M_P2 = 4`

instead of trying to realize all width through `NFIN` alone.

### 3. `nf` and `m` are not interchangeable

In many PDKs:

- `nf` controls finger segmentation inside one device instance
- `m` replicates the instance in parallel

Do not assume they can be swapped freely. Check the target model documentation and layout meaning before using one as a substitute for the other.

### 4. FinFET migration to planar CMOS needs a translation step

If the destination process is planar CMOS rather than FinFET:

- replace the `nfin`-based sizing scheme with width-based sizing
- map effective drive targets back into `W/L`
- regenerate gm/ID tables for planar devices
- redo all sweeps because parasitics and output resistance trends will change

The safe rule is: keep the **flow**, not the literal geometry values.

---

## Short Operational Summary

If you only remember one thing from this skill, remember this sequence:

1. **Topology first**
2. **DC first**
3. **gm/ID for initial sizing**
4. **`.alter` sweeps for refinement**
5. **inspect `n2`, not only `Vout`**
6. **do not accept any “better” transient point that fails DC**
7. **use `m` for effective width expansion**
8. **compensation can fix overshoot, but too much compensation creates slow, no-hold waveforms**
9. **final choice must match the user’s real spec priorities, not a single idealized metric**
