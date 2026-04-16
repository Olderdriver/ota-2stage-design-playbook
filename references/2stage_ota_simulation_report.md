# Two-Stage OTA Simulation Report

## 1. Evidence Files

- DC operating-point log: `E:\analog_agent\ota_design_ai\.claude\skills\hspice\assets\logs\ota_2stage_op_check.lis`
- DC bias log: `E:\analog_agent\ota_design_ai\.claude\skills\hspice\assets\logs\ota_2stage_dc_bias.lis`
- AC open-loop log: `E:\analog_agent\ota_design_ai\.claude\skills\hspice\assets\logs\ota_2stage_ac_openloop.lis`
- Loop-gain log: `E:\analog_agent\ota_design_ai\.claude\skills\hspice\assets\logs\ota_2stage_ac_loopgain.lis`
- CMRR log: `E:\analog_agent\ota_design_ai\.claude\skills\hspice\assets\logs\ota_2stage_ac_cmrr.lis`
- PSRR+ log: `E:\analog_agent\ota_design_ai\.claude\skills\hspice\assets\logs\ota_2stage_ac_psrrp.lis`
- Slew log: `E:\analog_agent\ota_design_ai\.claude\skills\hspice\assets\logs\ota_2stage_tran_slew.lis`
- DC plot: `E:\analog_agent\ota_design_ai\.claude\skills\hspice\assets\plots\ota_2stage_dc_bias.png`
- AC plot: `E:\analog_agent\ota_design_ai\.claude\skills\hspice\assets\plots\ota_2stage_ac_bode.png`
- Rejection plot: `E:\analog_agent\ota_design_ai\.claude\skills\hspice\assets\plots\ota_2stage_rejection.png`
- Slew plot: `E:\analog_agent\ota_design_ai\.claude\skills\hspice\assets\plots\ota_2stage_tran_slew.png`

## 1.5 DC Check Gate

- DC Check status: `passed`
- DC Check reason: passed

## 2. Extracted Results

- Vout @ VCM=0.90 V: 0.915 V
- Vtail @ VCM=0.90 V: 1.365 V
- IVDD @ VCM=0.90 V: 75.642 uA
- Open-loop low-frequency gain: 93.852 dB
- Peak gain: 93.852 dB
- Unity-gain frequency: 7.707 MHz
- Loop phase margin: 98.769 deg
- Low-frequency CMRR: 88.801 dB
- Low-frequency PSRR+: 91.072 dB
- Positive slew rate: 5.000 V/us
- Negative slew rate: 12.000 V/us

## 3. Specification Check

- Gain > 80 dB: PASS
- CMRR > 100 dB: FAIL
- PSRR+ > 100 dB: FAIL
- Slew 1–5 V/us: PASS
