#!/usr/bin/env python3
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')

import tempfile
from pathlib import Path

import numpy as np

from hspice_common import MODEL_DIR, render_template, run_hspice, parse_print_table, spath

W_UM = 0.154
VDD = 1.8
VCM = 0.9
VBP1_DROP = 0.600
VBP2_DROP = 0.528

L_IN_UM = 0.18
L_LOAD_UM = 0.24
L_TAIL_UM = 0.24
L_STAGE2_UM = 0.24
L_P2_UM = 0.24

NFIN_IN = 20
NFIN_LOAD = 8
NFIN_TAIL = 12
NFIN_STAGE2 = 11
NFIN_P2 = 15

M_IN = 1
M_LOAD = 1
M_TAIL = 1
M_STAGE2 = 4
M_P2 = 4

CC = '3.5p'
RZ = '6.8k'
CL = '8p'

VCM_START = 0.55
VCM_STOP = 1.25
VCM_STEP = 0.01

FREQ_START = '1'
FREQ_STOP = '100G'

VIN_LOW = '0.75'
VIN_HIGH = '1.05'
TDELAY = '10n'
TRISE = '200p'
TFALL = '200p'
TON = '200n'
TPERIOD = '500n'
TSTEP = '100p'
TSTOP = '500n'

BASE_DIR = Path(__file__).resolve().parent
REF_DIR = BASE_DIR.parent / 'references'
DESIGN_REPORT = REF_DIR / '2stage_ota_design_report.md'
SIM_REPORT = REF_DIR / '2stage_ota_simulation_report.md'


def _geom():
    return dict(
        usage_lib=spath(MODEL_DIR / '12sfe_spice_v1p2_rev0_usage.lib'),
        vdd=VDD,
        vcm=VCM,
        vbp1_drop=VBP1_DROP,
        vbp2_drop=VBP2_DROP,
        cc=CC,
        rz=RZ,
        cl=CL,
        w_in_um=W_UM,
        l_in_um=L_IN_UM,
        nfin_in=NFIN_IN,
        m_in=M_IN,
        w_load_um=W_UM,
        l_load_um=L_LOAD_UM,
        nfin_load=NFIN_LOAD,
        m_load=M_LOAD,
        w_tail_um=W_UM,
        l_tail_um=L_TAIL_UM,
        nfin_tail=NFIN_TAIL,
        m_tail=M_TAIL,
        w_stage2_um=W_UM,
        l_stage2_um=L_STAGE2_UM,
        nfin_stage2=NFIN_STAGE2,
        m_stage2=M_STAGE2,
        w_p2_um=W_UM,
        l_p2_um=L_P2_UM,
        nfin_p2=NFIN_P2,
        m_p2=M_P2,
    )


def _run_one(tmpl_name, stem, **kw):
    text = render_template(tmpl_name, **kw)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sp', delete=False, encoding='utf-8') as f:
        f.write(text)
        tmp = f.name
    try:
        return run_hspice(tmp, stem, timeout=240)
    finally:
        os.unlink(tmp)


def _extract_ac(parsed):
    data = parsed[1] if parsed else None
    if data is None or data.shape[1] < 3:
        return None, None, None
    return data[:, 0], data[:, 1], data[:, 2]


_SUFFIX_SCALE = {
    't': 1e12,
    'g': 1e9,
    'meg': 1e6,
    'x': 1e6,
    'k': 1e3,
    'm': 1e-3,
    'u': 1e-6,
    'n': 1e-9,
    'p': 1e-12,
    'f': 1e-15,
    'a': 1e-18,
}


def _parse_spice_float(token):
    s = token.strip().lower()
    if s.endswith('meg'):
        return float(s[:-3]) * _SUFFIX_SCALE['meg']
    if s and s[-1].isalpha() and s[-1] != 'e':
        return float(s[:-1]) * _SUFFIX_SCALE[s[-1]]
    return float(s)


def _parse_dc_bias_log(lis_path):
    lines = Path(lis_path).read_text(encoding='utf-8', errors='replace').splitlines()

    def _collect_after(header_prefix, ncols):
        for i, line in enumerate(lines):
            if line.strip().lower().startswith(header_prefix):
                rows = []
                j = i + 2
                while j < len(lines):
                    s = lines[j].strip()
                    if not s or s in {'x', 'y'} or s.startswith('*'):
                        if rows and (not s or s == 'y' or s.startswith('*')):
                            break
                        j += 1
                        continue
                    parts = s.split()
                    if len(parts) >= ncols:
                        try:
                            rows.append([_parse_spice_float(x) for x in parts[:ncols]])
                        except ValueError:
                            if rows:
                                break
                    elif rows:
                        break
                    j += 1
                if rows:
                    return np.array(rows, dtype=float)
        return None

    voltages = _collect_after('volt', 5)
    currents = _collect_after('volt         current', 2)
    if voltages is None:
        return None, None, None, None, None

    vcm = voltages[:, 1]
    v1 = voltages[:, 2]
    vout = voltages[:, 3]
    vtail = voltages[:, 4]
    ivdd = currents[:, 1] if currents is not None else None
    if ivdd is not None and len(ivdd) != len(vcm):
        ivdd = None
    return vcm, v1, vout, vtail, np.abs(ivdd) if ivdd is not None else None


def _parse_op_devices(lis_path):
    lines = Path(lis_path).read_text(encoding='utf-8', errors='replace').splitlines()
    devices = {}
    current = []
    in_mos = False

    def _flush(block):
        if not block:
            return
        headers = None
        elements = None
        values = []
        for line in block:
            s = line.strip()
            if not s:
                continue
            if s.startswith('subckt'):
                headers = s.split()[1:]
                continue
            if s.startswith('element'):
                elements = s.split()[1:]
                continue
            if s.startswith('model'):
                continue
            parts = s.split()
            if len(parts) < 2 or headers is None:
                continue
            metric = parts[0].lower()
            vals = parts[1:]
            if len(vals) == len(headers):
                values.append((metric, vals))
        if headers is None:
            return
        for idx, name in enumerate(headers):
            entry = devices.setdefault(name.lower(), {})
            if elements and idx < len(elements):
                entry['element'] = elements[idx].lower()
            for metric, vals in values:
                entry[metric] = vals[idx]

    for line in lines:
        s = line.strip().lower()
        if s.startswith('**** mosfets'):
            in_mos = True
            current = []
            continue
        if in_mos and s.startswith('******'):
            _flush(current)
            break
        if in_mos:
            if s.startswith('subckt') and current:
                _flush(current)
                current = [line]
            else:
                current.append(line)
    if in_mos and current:
        _flush(current)
    return devices


def _device_passes_dc(name, dev):
    region = dev.get('region', '').lower()
    try:
        vds = abs(_parse_spice_float(dev.get('vds', 'nan')))
        vdsat = abs(_parse_spice_float(dev.get('vdsat', 'nan')))
    except ValueError:
        return False, {'device': name, 'reason': 'parse_error', 'region': dev.get('region'), 'vds': dev.get('vds'), 'vdsat': dev.get('vdsat')}
    region_ok = region.startswith('saturat') or region.startswith('active')
    headroom_ok = np.isfinite(vds) and np.isfinite(vdsat) and (vds > vdsat)
    passed = region_ok and headroom_ok
    return passed, {
        'device': name,
        'region': dev.get('region'),
        'vds': vds,
        'vdsat': vdsat,
        'region_ok': region_ok,
        'headroom_ok': headroom_ok,
    }


def _run_dc_check(lis_path):
    core_devices = ['xm1', 'xm2', 'xm3', 'xm4', 'xm5', 'xm6', 'xm7']
    devices = _parse_op_devices(lis_path)
    by_element = {
        dev.get('element', '').split(':')[-1]: dev
        for dev in devices.values()
        if dev.get('element')
    }
    details = []
    failed = []
    missing = []
    for name in core_devices:
        dev = devices.get(name) or by_element.get(name.replace('x', ''))
        if dev is None:
            missing.append(name)
            continue
        passed, info = _device_passes_dc(name, dev)
        details.append(info)
        if not passed:
            failed.append(info)
    status = 'passed' if not failed and not missing else 'failed'
    reason = None
    if missing:
        reason = f'missing devices: {", ".join(missing)}'
    elif failed:
        reason = '; '.join(
            f"{d['device']} region={d['region']} vds={d['vds']:.4g} vdsat={d['vdsat']:.4g}"
            for d in failed
        )
    return {
        'status': status,
        'failed': failed,
        'details': details,
        'missing': missing,
        'reason': reason,
    }


def _interp_at(x, y, x0):
    if x is None or y is None or len(x) == 0:
        return None
    return float(np.interp(x0, x, y))


def _ugf_phase_margin(freq, gain_db, phase_deg):
    if freq is None or gain_db is None or phase_deg is None or len(freq) < 2:
        return None, None
    idx = np.where(gain_db <= 0.0)[0]
    if len(idx) == 0:
        return None, None
    i = int(idx[0])
    if i == 0:
        ugf = float(freq[0])
        phase = float(phase_deg[0])
    else:
        x1 = np.log10(freq[i - 1])
        x2 = np.log10(freq[i])
        y1 = float(gain_db[i - 1])
        y2 = float(gain_db[i])
        frac = 0.0 if y1 == y2 else (0.0 - y1) / (y2 - y1)
        log_ugf = x1 + frac * (x2 - x1)
        ugf = float(10 ** log_ugf)
        phase = float(phase_deg[i - 1] + frac * (phase_deg[i] - phase_deg[i - 1]))
    wrapped = ((phase + 180.0) % 360.0) - 180.0
    if wrapped > 90.0:
        wrapped -= 360.0
    return ugf, float(180.0 + wrapped)


def _db_phase_to_complex(gain_db, phase_deg):
    mag = np.power(10.0, np.asarray(gain_db, dtype=float) / 20.0)
    phase_rad = np.deg2rad(np.asarray(phase_deg, dtype=float))
    return mag * (np.cos(phase_rad) + 1j * np.sin(phase_rad))


def _closed_loop_to_loop_gain(gain_db, phase_deg):
    if gain_db is None or phase_deg is None:
        return None, None
    h = _db_phase_to_complex(gain_db, phase_deg)
    denom = 1.0 + h
    tiny = np.abs(denom) < 1e-18
    denom = np.where(tiny, 1e-18 + 0j, denom)
    t = -h / denom
    t_mag = np.maximum(np.abs(t), 1e-30)
    t_gain_db = 20.0 * np.log10(t_mag)
    t_phase_deg = np.rad2deg(np.angle(t))
    return t_gain_db, t_phase_deg


def _slew_rate(time_s, vout):
    if time_s is None or vout is None or len(time_s) < 2:
        return None, None
    dvdt = np.diff(vout) / np.diff(time_s)
    sr_pos = float(np.max(dvdt))
    sr_neg = float(np.min(dvdt))
    return sr_pos, sr_neg


def _write_design_report():
    REF_DIR.mkdir(parents=True, exist_ok=True)
    text = (
        "# Two-Stage OTA Design Report\n\n"
        "## 1. Design Target\n\n"
        "Target metrics requested by user:\n\n"
        "- PSRR > 100 dB\n"
        "- CMRR > 100 dB\n"
        "- Open-loop gain > 80 dB\n"
        "- Slew rate between 1 V/us and 5 V/us\n\n"
        "## 2. Topology Choice\n\n"
        "This delivery uses a two-stage Miller OTA instead of the repository's baseline 5T OTA. "
        "The 5T OTA flow was run first as a baseline and produced only about 39 dB open-loop gain, "
        "so it is structurally insufficient for the requested gain/PSRR/CMRR targets.\n\n"
        "The delivered topology is:\n\n"
        "- Stage 1: PMOS differential pair + NMOS mirror active load\n"
        "- Stage 2: NMOS common-source second gain stage + PMOS current-source load\n"
        "- Compensation: Miller capacitor between first-stage output and final output\n\n"
        "## 3. Implemented Device Parameters\n\n"
        f"- VDD = {VDD:.1f} V\n"
        f"- VCM = {VCM:.1f} V\n"
        f"- VBP1 drop from VDD = {VBP1_DROP:.3f} V\n"
        f"- VBP2 drop from VDD = {VBP2_DROP:.3f} V\n"
        f"- L_IN = {L_IN_UM:.2f} um, NFIN_IN = {NFIN_IN}\n"
        f"- L_LOAD = {L_LOAD_UM:.2f} um, NFIN_LOAD = {NFIN_LOAD}\n"
        f"- L_TAIL = {L_TAIL_UM:.2f} um, NFIN_TAIL = {NFIN_TAIL}\n"
        f"- L_STAGE2 = {L_STAGE2_UM:.2f} um, NFIN_STAGE2 = {NFIN_STAGE2}\n"
        f"- L_P2 = {L_P2_UM:.2f} um, NFIN_P2 = {NFIN_P2}\n"
        f"- Miller capacitor Cc = {CC}\n"
        f"- Nulling resistor Rz = {RZ}\n"
        f"- Load capacitor CL = {CL}\n\n"
        "## 4. Design Intent\n\n"
        "The first stage is reduced to a standard PMOS differential pair with an NMOS mirror load so the OTA can establish a valid DC operating point before any higher-gain cascode structure is reconsidered. "
        "The second stage uses an NMOS common-source device with a PMOS current-source load so the first-stage output common-mode can more naturally bias the second stage into a useful operating region. A series nulling resistor is added with the Miller capacitor to move the compensation zero away from the destabilizing right-half-plane behavior. Device lengths are "
        "pushed to the process limit to maximize output resistance, and larger compensation/load capacitors are "
        "used to intentionally slow the large-signal response toward the requested slew-rate band.\n"
    )
    DESIGN_REPORT.write_text(text, encoding='utf-8')


def _write_sim_report(result):
    def fmt(value, scale=1.0, unit=''):
        if value is None:
            return 'N/A'
        return f'{value * scale:.3f} {unit}'.strip()

    text = (
        "# Two-Stage OTA Simulation Report\n\n"
        "## 1. Evidence Files\n\n"
        f"- DC operating-point log: `{result['logs']['op']}`\n"
        f"- DC bias log: `{result['logs']['dc']}`\n"
        f"- AC open-loop log: `{result['logs']['ac']}`\n"
        f"- Loop-gain log: `{result['logs']['loop']}`\n"
        f"- CMRR log: `{result['logs']['cmrr']}`\n"
        f"- PSRR+ log: `{result['logs']['psrrp']}`\n"
        f"- Slew log: `{result['logs']['tran']}`\n"
        f"- DC plot: `{result['plots']['dc']}`\n"
        f"- AC plot: `{result['plots']['ac']}`\n"
        f"- Rejection plot: `{result['plots']['rejection']}`\n"
        f"- Slew plot: `{result['plots']['tran']}`\n\n"
        "## 1.5 DC Check Gate\n\n"
        f"- DC Check status: `{result['dc_check']['status']}`\n"
        f"- DC Check reason: {result['dc_check']['reason'] or 'passed'}\n\n"
        "## 2. Extracted Results\n\n"
        f"- Vout @ VCM={VCM:.2f} V: {fmt(result['dc']['bias_at_vcm']['vout'], 1.0, 'V')}\n"
        f"- Vtail @ VCM={VCM:.2f} V: {fmt(result['dc']['bias_at_vcm']['vtail'], 1.0, 'V')}\n"
        f"- IVDD @ VCM={VCM:.2f} V: {fmt(result['dc']['bias_at_vcm']['ivdd'], 1e6, 'uA')}\n"
        f"- Open-loop low-frequency gain: {fmt(result['ac']['dc_gain0_db'], 1.0, 'dB')}\n"
        f"- Peak gain: {fmt(result['ac']['peak_gain_db'], 1.0, 'dB')}\n"
        f"- Unity-gain frequency: {fmt(result['loop']['ugf_hz'], 1e-6, 'MHz')}\n"
        f"- Loop phase margin: {fmt(result['loop']['phase_margin_deg'], 1.0, 'deg')}\n"
        f"- Low-frequency CMRR: {fmt(result['cmrr']['cmrr0_db'], 1.0, 'dB')}\n"
        f"- Low-frequency PSRR+: {fmt(result['psrrp']['psrr0_db'], 1.0, 'dB')}\n"
        f"- Positive slew rate: {fmt(result['tran']['sr_pos'], 1e-6, 'V/us')}\n"
        f"- Negative slew rate: {fmt(abs(result['tran']['sr_neg']) if result['tran']['sr_neg'] is not None else None, 1e-6, 'V/us')}\n\n"
        "## 3. Specification Check\n\n"
        f"- Gain > 80 dB: {'PASS' if (result['ac']['peak_gain_db'] is not None and result['ac']['peak_gain_db'] > 80.0) else 'FAIL'}\n"
        f"- CMRR > 100 dB: {'PASS' if (result['cmrr']['cmrr0_db'] is not None and result['cmrr']['cmrr0_db'] > 100.0) else 'FAIL'}\n"
        f"- PSRR+ > 100 dB: {'PASS' if (result['psrrp']['psrr0_db'] is not None and result['psrrp']['psrr0_db'] > 100.0) else 'FAIL'}\n"
        f"- Slew 1–5 V/us: {'PASS' if (result['tran']['sr_pos'] is not None and 1e6 <= result['tran']['sr_pos'] <= 5e6) else 'FAIL'}\n"
    )
    SIM_REPORT.write_text(text, encoding='utf-8')


def simulate_all():
    _write_design_report()
    geom = _geom()

    lis_op = _run_one('op_2stage_ota_check.sp.tmpl', 'ota_2stage_op_check', **geom)
    dc_check = _run_dc_check(lis_op)

    lis_dc = _run_one(
        'dc_2stage_ota_bias.sp.tmpl',
        'ota_2stage_dc_bias',
        vcm_start=VCM_START,
        vcm_stop=VCM_STOP,
        vcm_step=VCM_STEP,
        **geom,
    )
    vcm, v1, vout, vtail, ivdd = _parse_dc_bias_log(lis_dc)

    lis_ac = lis_loop = lis_cmrr = lis_psrrp = lis_tran = None
    freq = gain_db = phase_deg = None
    loop_freq = loop_gain_db = loop_phase_deg = None
    loop_resp_db = loop_resp_phase_deg = None
    ugf_hz = phase_margin_deg = None
    freq_cm = gain_cm_db = phase_cm = cmrr_db = None
    freq_ps = gain_ps_db = phase_ps = psrrp_db = None
    time_s = vin = vout_tr = sr_pos = sr_neg = None

    if dc_check['status'] == 'passed':
        lis_ac = _run_one('ac_2stage_ota_openloop.sp.tmpl', 'ota_2stage_ac_openloop', fstart=FREQ_START, fstop=FREQ_STOP, **geom)
        freq, gain_db, phase_deg = _extract_ac(parse_print_table(lis_ac))

        lis_loop = _run_one('ac_2stage_ota_loopgain.sp.tmpl', 'ota_2stage_ac_loopgain', fstart=FREQ_START, fstop=FREQ_STOP, **geom)
        loop_freq, loop_resp_db, loop_resp_phase_deg = _extract_ac(parse_print_table(lis_loop))
        loop_gain_db, loop_phase_deg = _closed_loop_to_loop_gain(loop_resp_db, loop_resp_phase_deg)
        ugf_hz, phase_margin_deg = _ugf_phase_margin(loop_freq, loop_gain_db, loop_phase_deg)

        lis_cmrr = _run_one('ac_2stage_ota_cmrr.sp.tmpl', 'ota_2stage_ac_cmrr', fstart=FREQ_START, fstop=FREQ_STOP, **geom)
        freq_cm, gain_cm_db, phase_cm = _extract_ac(parse_print_table(lis_cmrr))
        cmrr_db = gain_db - gain_cm_db if gain_db is not None and gain_cm_db is not None else None

        lis_psrrp = _run_one('ac_2stage_ota_psrrp.sp.tmpl', 'ota_2stage_ac_psrrp', fstart=FREQ_START, fstop=FREQ_STOP, **geom)
        freq_ps, gain_ps_db, phase_ps = _extract_ac(parse_print_table(lis_psrrp))
        psrrp_db = gain_db - gain_ps_db if gain_db is not None and gain_ps_db is not None else None

        lis_tran = _run_one(
            'tran_2stage_ota_slew.sp.tmpl',
            'ota_2stage_tran_slew',
            vin_low=VIN_LOW,
            vin_high=VIN_HIGH,
            tdelay=TDELAY,
            trise=TRISE,
            tfall=TFALL,
            ton=TON,
            period=TPERIOD,
            tstep=TSTEP,
            tstop=TSTOP,
            **geom,
        )
        parsed_tr = parse_print_table(lis_tran)
        tr = parsed_tr[1] if parsed_tr else None
        if tr is not None and tr.shape[1] >= 3:
            time_s = tr[:, 0]
            vin = tr[:, 1]
            vout_tr = tr[:, 2]
        sr_pos, sr_neg = _slew_rate(time_s, vout_tr)

    result = {
        'params': {
            'VDD': VDD, 'VCM': VCM, 'VBP1_DROP': VBP1_DROP, 'VBP2_DROP': VBP2_DROP, 'CC': CC, 'RZ': RZ, 'CL': CL,
            'NFIN_IN': NFIN_IN, 'NFIN_LOAD': NFIN_LOAD, 'NFIN_TAIL': NFIN_TAIL,
            'NFIN_STAGE2': NFIN_STAGE2, 'NFIN_P2': NFIN_P2,
            'L_IN_UM': L_IN_UM, 'L_LOAD_UM': L_LOAD_UM, 'L_TAIL_UM': L_TAIL_UM,
            'L_STAGE2_UM': L_STAGE2_UM, 'L_P2_UM': L_P2_UM,
        },
        'dc': {
            'vcm': vcm, 'v1': v1, 'vout': vout, 'vtail': vtail, 'ivdd': ivdd,
            'bias_at_vcm': {
                'v1': _interp_at(vcm, v1, VCM),
                'vout': _interp_at(vcm, vout, VCM),
                'vtail': _interp_at(vcm, vtail, VCM),
                'ivdd': _interp_at(vcm, ivdd, VCM),
            },
        },
        'dc_check': dc_check,
        'ac': {
            'freq': freq, 'gain_db': gain_db, 'phase_deg': phase_deg,
            'dc_gain0_db': float(gain_db[0]) if gain_db is not None else None,
            'peak_gain_db': float(np.max(gain_db)) if gain_db is not None else None,
        },
        'loop': {
            'freq': loop_freq,
            'resp_db': loop_resp_db,
            'resp_phase_deg': loop_resp_phase_deg,
            'gain_db': loop_gain_db,
            'phase_deg': loop_phase_deg,
            'ugf_hz': ugf_hz, 'phase_margin_deg': phase_margin_deg,
        },
        'cmrr': {
            'freq': freq_cm, 'gain_db': gain_cm_db, 'phase_deg': phase_cm, 'cmrr_db': cmrr_db,
            'cmrr0_db': float(cmrr_db[0]) if cmrr_db is not None else None,
        },
        'psrrp': {
            'freq': freq_ps, 'gain_db': gain_ps_db, 'phase_deg': phase_ps, 'psrr_db': psrrp_db,
            'psrr0_db': float(psrrp_db[0]) if psrrp_db is not None else None,
        },
        'tran': {
            'time_s': time_s, 'vin': vin, 'vout': vout_tr, 'sr_pos': sr_pos, 'sr_neg': sr_neg,
        },
        'logs': {
            'op': str(lis_op), 'dc': str(lis_dc), 'ac': str(lis_ac) if lis_ac else 'SKIPPED (DC OP Failed)', 'loop': str(lis_loop) if lis_loop else 'SKIPPED (DC OP Failed)', 'cmrr': str(lis_cmrr) if lis_cmrr else 'SKIPPED (DC OP Failed)', 'psrrp': str(lis_psrrp) if lis_psrrp else 'SKIPPED (DC OP Failed)', 'tran': str(lis_tran) if lis_tran else 'SKIPPED (DC OP Failed)',
        },
        'plots': {},
        'reports': {'design': str(DESIGN_REPORT), 'simulation': str(SIM_REPORT)},
    }
    return result, _write_sim_report
