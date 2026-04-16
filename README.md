# OTA Two-Stage Design Playbook

This repository is a reusable design playbook for a **1.8 V two-stage Miller OTA** implemented with a **PMOS differential input pair**, **NMOS mirror load**, **NMOS second-stage gain device**, and **series `Rz + Cc` compensation**.

The goal of the project is not just to store a final netlist. It captures a repeatable, evidence-based design flow built around three ideas:

- **validate DC first** before trusting AC or transient results
- **use gm/ID sizing** to get physically reasonable starting points
- **use batch HSPICE sweeps** instead of guessing transistor sizes, bias, or compensation values

This makes the repository useful both as a delivered OTA result and as a working methodology for retuning or debugging similar two-stage OTA designs in the same environment.

## What this repository contains

The repository is organized around a design flow, simulation scripts, and generated results.

### Core documents

- `SKILL.md` - the main playbook, written as a reusable engineering workflow
- `Design_flow.md` - a Chinese reading version of the same design logic and lessons learned

### Design and simulation references

- `references/simulate_2stage_ota.py` - main end-to-end simulation driver for DC, AC, and transient checks
- `references/design_gmoverid.py` - gm/ID sizing API with cached lookup-table generation
- `references/netlist/*.sp.tmpl` - HSPICE template netlists for OP, DC bias, open-loop gain, CMRR, PSRR, and transient slew analysis
- `references/2stage_ota_design_report.md` - design summary and selected final parameters

### Batch sweep utilities

The `assets/` directory contains sweep helpers and shared HSPICE utilities, including:

- `assets/hspice_common.py`
- `assets/sweep_vbp2_batch.py`
- `assets/sweep_vbp2_cc_batch.py`
- `assets/sweep_compensation_batch.py`
- `assets/sweep_comp_srneg_batch.py`
- `assets/sweep_stage2_drive_batch.py`
- `assets/sweep_srneg_batch.py`
- `assets/sweep_cl_batch.py`

These scripts are intended to reduce simulator startup overhead by scanning multiple operating points efficiently.

### Generated outputs

The `results/` directory contains artifacts from a successful run, including:

- `results/2stage_ota_design_report.md`
- `results/final_netlist/final_2stage_ota.sp`
- `results/final_netlist/final_2stage_ota_tran.sp`
- `results/logs/`
- `results/plots/`

## Target OTA topology

This playbook is written for the topology used by the scripts in this repository:

- Stage 1: **PMOS differential pair**
- Stage 1 load: **NMOS current-mirror active load**
- Tail source: **PMOS current source**
- Stage 2: **NMOS common-source gain stage**
- Stage 2 load: **PMOS current-source load**
- Compensation: **series `Rz + Cc` Miller network** from the first-stage node to the output

It is not a generic analog cookbook for arbitrary OTA architectures. If you change topology or move to a different process, you should expect to rebuild the sizing and sweep flow.

## Design intent and method

The repository formalizes a specific tuning strategy:

1. **Check whether the topology is structurally capable** of the required gain and stability.
2. **Fix the testbench first** if the stimulus or operating range is unrealistic.
3. **Establish a valid DC operating point** before using AC or transient results.
4. **Use gm/ID sizing** to get a sensible first pass for transistor dimensions and current levels.
5. **Refine with HSPICE sweeps** for bias, compensation, and large-signal behavior.
6. **Inspect both `Vout` and internal node `n2`**, because acceptable AC metrics do not guarantee a healthy unity-follower transient.

The documentation in this repo repeatedly emphasizes that waveform quality, slew behavior, and DC validity must be checked together rather than optimized one metric at a time.

## Environment and prerequisites

This repository is tied to a real HSPICE-based design environment. Before running the scripts, you need the following:

- **Python 3**
- **NumPy**
- **Synopsys HSPICE**
- A compatible **model library / PDK deck** available under a path expected by the scripts

### HSPICE path

`assets/hspice_common.py` currently hardcodes the simulator path as:

```text
C:\synopsys\Hspice_S-2021.09\WIN64\hspice.com
```

If your installation lives elsewhere, update `HSPICE_EXE` in `assets/hspice_common.py` before running any simulation flow.

### Model library path

The scripts expect a model library under one of these locations:

- `models/hspice`
- `gmoverid-hspice/models/hspice`

The main simulation flow references the file:

```text
12sfe_spice_v1p2_rev0_usage.lib
```

That means this repository is currently configured for a specific FinFET process environment. Reusing the flow in another PDK requires updating the model setup and, in practice, regenerating the gm/ID data and re-running sweeps.

## Installation

At minimum, install Python dependencies and make sure HSPICE plus the model deck are available.

Example:

```bash
pip install numpy
```

No `requirements.txt` is currently provided in this repository, so dependency setup is manual.

## How to use

### 1. Run the main verification flow

The primary entry point is:

```bash
python references/simulate_2stage_ota.py
```

This script defines the current OTA geometry, bias conditions, compensation values, stimulus parameters, and analysis ranges directly in the file. It then renders the HSPICE templates, runs simulations, parses `.lis` results, and writes reports/artifacts.

From the file contents, the current built-in operating point includes:

- `VDD = 1.8 V`
- `VCM = 0.9 V`
- `VBP1_DROP = 0.600 V`
- `VBP2_DROP = 0.528 V`
- `Cc = 3.5p`
- `Rz = 6.8k`
- `CL = 8p`

and the selected stage dimensions are encoded directly in the script.

### 2. Use gm/ID sizing as the starting point

The gm/ID API lives in:

```bash
python references/design_gmoverid.py
```

In practice, this file is intended more as a reusable sizing API than as a standalone end-user CLI. It exposes `GmIdTable`, which builds cached sweep data and supports sizing from:

- target `gm/ID`
- target `f_t`
- target `gm·ro`

The cache is stored under the log/cache structure created by the gm/ID flow.

### 3. Run focused batch sweeps

When you need to retune a specific part of the design, use the batch scripts under `assets/`. Based on their filenames, they are organized around the main sensitive knobs in this design:

- `sweep_vbp2_batch.py` - refine the stage-2 bias point
- `sweep_vbp2_cc_batch.py` - co-sweep bias and compensation
- `sweep_compensation_batch.py` - refine `Cc` and `Rz`
- `sweep_stage2_drive_batch.py` - adjust stage-2 drive strength
- `sweep_srneg_batch.py` and `sweep_comp_srneg_batch.py` - investigate negative-slew behavior
- `sweep_cl_batch.py` - explore load-capacitance effects

These sweeps are especially useful because this design is sensitive to compensation and stage-2 balance, and because repeated single-run HSPICE startup is expensive.

## Outputs you should expect

After a successful run, the repository is structured to produce:

- rendered or final HSPICE netlists
- `.lis` simulator logs
- markdown design/simulation summaries
- plots for AC, DC, and transient analysis

The current checked-in result set can be found under `results/`, with the final netlist in:

```text
results/final_netlist/final_2stage_ota.sp
```

## Important design lessons captured here

This project records several strong constraints that matter when you reuse the flow:

- **DC correctness is a gate**, not a nice-to-have. If the operating point is wrong, later metrics are not trustworthy.
- **`VBP2` is highly sensitive**. Small changes can move the output bias dramatically.
- **Good phase margin does not guarantee a good transient waveform**.
- **Internal node `n2` must be inspected**, not just the final output.
- **Increasing stage-2 strength can improve waveform shape but worsen slew asymmetry**.
- **Use multiplier `m` where appropriate instead of unrealistically pushing all effective width into `NFIN`**.

The repo is therefore best understood as a practical design notebook turned into an executable playbook.

## Repository map

```text
.
├─ SKILL.md
├─ Design_flow.md
├─ assets/
│  ├─ hspice_common.py
│  └─ sweep_*.py
├─ references/
│  ├─ design_gmoverid.py
│  ├─ simulate_2stage_ota.py
│  ├─ 2stage_ota_design_report.md
│  └─ netlist/
├─ results/
│  ├─ 2stage_ota_design_report.md
│  ├─ final_netlist/
│  ├─ logs/
│  └─ plots/
└─ chroma/
```

## Known limitations

- The flow is currently **Windows-oriented** because the HSPICE executable path is hardcoded for a Windows installation.
- The repository does **not** currently provide a packaged dependency file such as `requirements.txt`.
- The scripts are **process-specific** and depend on the expected model library layout.
- Some parameter values and conclusions are valid only for the current FinFET environment and should not be blindly transferred to another technology.

## Recommended reading order

If you are new to the repository, read in this order:

1. `README.md`
2. `SKILL.md`
3. `Design_flow.md`
4. `references/2stage_ota_design_report.md`
5. `references/simulate_2stage_ota.py`

That sequence gives you the high-level method first, then the detailed design logic, then the script-level implementation.
