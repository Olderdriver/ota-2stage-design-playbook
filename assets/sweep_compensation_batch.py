#!/usr/bin/env python3
"""Batch Cc/Rz transient sweep for the two-stage OTA using HSPICE .alter."""
import os
import sys
import tempfile

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path

import numpy as np

from hspice_common import MODEL_DIR, parse_print_table, run_hspice, spath

VDD = 1.8
VCM = 0.9
VIN_LOW = '0.75'
VIN_HIGH = '1.05'
TDELAY = '10n'
TRISE = '200p'
TFALL = '200p'
TON = '200n'
TPERIOD = '500n'
TSTEP = '100p'
TSTOP = '500n'


def _as_spice_cap_pf(value_pf):
    return f'{value_pf:g}p'


def _as_spice_res_kohm(value_kohm):
    return f'{value_kohm:g}k'


def build_tran_alter_netlist(base_params, sweep_points):
    first = sweep_points[0]
    lib = base_params['usage_lib']
    lines = []
    lines.append('* Two-Stage OTA - batch Cc/Rz transient sweep via .alter')
    lines.append(f".lib '{lib}' tt_mos_varactor")
    lines.append(f".param cc_val = {_as_spice_cap_pf(first['cc_pf'])}")
    lines.append(f".param rz_val = {_as_spice_res_kohm(first['rz_kohm'])}")
    lines.append(f"Vdd vdd 0 DC {base_params['vdd']}")
    lines.append(f"Vbp1 vdd vbp1 DC {base_params['vbp1_drop']}")
    lines.append(f"Vbp2 vdd vbp2 DC {base_params['vbp2_drop']}")
    lines.append(f"Vinp inp 0 PULSE({base_params['vin_low']} {base_params['vin_high']} {base_params['tdelay']} {base_params['trise']} {base_params['tfall']} {base_params['ton']} {base_params['period']})")
    lines.append('')
    lines.append('* Stage 1')
    lines.append(f"xm3 n1 n1 0 0 n18_ckt w={base_params['w_load_um']}u l={base_params['l_load_um']}u nfin={base_params['nfin_load']} nf=1 m={base_params['m_load']}")
    lines.append(f"xm4 n2 n1 0 0 n18_ckt w={base_params['w_load_um']}u l={base_params['l_load_um']}u nfin={base_params['nfin_load']} nf=1 m={base_params['m_load']}")
    lines.append(f"xm1 n1 out tail vdd p18_ckt w={base_params['w_in_um']}u l={base_params['l_in_um']}u nfin={base_params['nfin_in']} nf=1 m={base_params['m_in']}")
    lines.append(f"xm2 n2 inp tail vdd p18_ckt w={base_params['w_in_um']}u l={base_params['l_in_um']}u nfin={base_params['nfin_in']} nf=1 m={base_params['m_in']}")
    lines.append(f"xm5 tail vbp1 vdd vdd p18_ckt w={base_params['w_tail_um']}u l={base_params['l_tail_um']}u nfin={base_params['nfin_tail']} nf=1 m={base_params['m_tail']}")
    lines.append('* Stage 2')
    lines.append(f"xm6 out n2 0 0 n18_ckt w={base_params['w_stage2_um']}u l={base_params['l_stage2_um']}u nfin={base_params['nfin_stage2']} nf=1 m={base_params['m_stage2']}")
    lines.append(f"xm7 out vbp2 vdd vdd p18_ckt w={base_params['w_p2_um']}u l={base_params['l_p2_um']}u nfin={base_params['nfin_p2']} nf=1 m={base_params['m_p2']}")
    lines.append('Rz n2 rz rz_val')
    lines.append('Cc rz out cc_val')
    lines.append(f"Cl out 0 {base_params['cl']}")
    lines.append(f".tran {base_params['tstep']} {base_params['tstop']}")
    lines.append('.print tran v(inp) v(out) v(n2)')
    for point in sweep_points[1:]:
        lines.append('.alter')
        lines.append(f".param cc_val = {_as_spice_cap_pf(point['cc_pf'])}")
        lines.append(f".param rz_val = {_as_spice_res_kohm(point['rz_kohm'])}")
    lines.append('.end')
    return '\n'.join(lines)


def _split_column_blocks(names, arr):
    if arr is None or names is None or len(arr) == 0 or len(names) < 4:
        return []
    blocks = []
    col = 1
    while col + 2 < arr.shape[1]:
        blocks.append(arr[:, [0, col, col + 1, col + 2]])
        col += 3
    return blocks


def _analyze_block(arr):
    time_s = arr[:, 0]
    vin = arr[:, 1]
    vout = arr[:, 2]
    vn2 = arr[:, 3]
    dvdt = np.diff(vout) / np.diff(time_s)
    sr_pos = float(np.max(dvdt)) if len(dvdt) else None
    sr_neg = float(np.min(dvdt)) if len(dvdt) else None
    high_level = float(np.max(vin))
    low_level = float(np.min(vin))
    high_idx = np.where(vin > 0.5 * (high_level + low_level))[0]
    low_idx = np.where(vin < 0.5 * (high_level + low_level))[0]
    vout_high = float(np.mean(vout[high_idx[-50:]])) if len(high_idx) else None
    vout_low = float(np.mean(vout[low_idx[-50:]])) if len(low_idx) else None
    overshoot = float(np.max(vout) - high_level)
    undershoot = float(low_level - np.min(vout))
    n2_min = float(np.min(vn2))
    return {
        'sr_pos_vus': sr_pos * 1e-6 if sr_pos is not None else None,
        'sr_neg_vus': abs(sr_neg) * 1e-6 if sr_neg is not None else None,
        'vout_high': vout_high,
        'vout_low': vout_low,
        'overshoot_v': overshoot,
        'undershoot_v': undershoot,
        'n2_min_v': n2_min,
    }


def _score(metrics):
    return (
        abs(metrics['overshoot_v']) * 6.0
        + max(0.0, 0.12 - metrics['n2_min_v']) * 8.0
        + abs(metrics['sr_pos_vus'] - 5.0) * 0.8
        + max(0.0, metrics['sr_neg_vus'] - 7.0) * 0.4
    )


def run_sweep(base_params, cc_values_pf, rz_values_kohm):
    sweep_points = [
        {'cc_pf': cc_pf, 'rz_kohm': rz_kohm}
        for cc_pf in cc_values_pf
        for rz_kohm in rz_values_kohm
    ]
    print(f"Batch sweep: {len(sweep_points)} transient points in one HSPICE run")
    netlist = build_tran_alter_netlist(base_params, sweep_points)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sp', delete=False, encoding='utf-8') as f:
        f.write(netlist)
        tmp = f.name
    try:
        lis = run_hspice(tmp, 'batch_comp_sweep', timeout=600)
    finally:
        os.unlink(tmp)

    parsed = parse_print_table(lis)
    names, arr = parsed if parsed else (None, None)
    blocks = _split_column_blocks(names, arr)
    results = []
    for point, block in zip(sweep_points, blocks):
        if block.shape[1] < 4:
            continue
        metrics = _analyze_block(block)
        metrics['cc_pf'] = point['cc_pf']
        metrics['rz_kohm'] = point['rz_kohm']
        metrics['score'] = _score(metrics)
        results.append(metrics)

    for f in Path(lis).parent.glob('batch_comp_sweep*'):
        f.unlink(missing_ok=True)

    results.sort(key=lambda x: x['score'])
    print(f"\n{'Cc(pF)':>6s} {'Rz(k)':>6s} {'SR+':>6s} {'SR-':>6s} {'Ovsh':>7s} {'N2min':>7s} {'Vhi':>7s} {'Score':>7s}")
    print('-' * 62)
    for r in results:
        print(f"{r['cc_pf']:6.2f} {r['rz_kohm']:6.2f} {r['sr_pos_vus']:6.2f} {r['sr_neg_vus']:6.2f} {r['overshoot_v']:7.3f} {r['n2_min_v']:7.3f} {r['vout_high']:7.3f} {r['score']:7.3f}")
    return results


if __name__ == '__main__':
    params = dict(
        usage_lib=spath(MODEL_DIR / '12sfe_spice_v1p2_rev0_usage.lib'),
        vdd=VDD,
        vbp1_drop=0.600,
        vbp2_drop=0.528,
        cl='8p',
        vin_low=VIN_LOW,
        vin_high=VIN_HIGH,
        tdelay=TDELAY,
        trise=TRISE,
        tfall=TFALL,
        ton=TON,
        period=TPERIOD,
        tstep=TSTEP,
        tstop=TSTOP,
        w_in_um=0.154, l_in_um=0.18, nfin_in=20, m_in=1,
        w_load_um=0.154, l_load_um=0.24, nfin_load=8, m_load=1,
        w_tail_um=0.154, l_tail_um=0.24, nfin_tail=12, m_tail=1,
        w_stage2_um=0.154, l_stage2_um=0.24, nfin_stage2=11, m_stage2=2,
        w_p2_um=0.154, l_p2_um=0.24, nfin_p2=15, m_p2=2,
    )
    cc_values = [1.5, 2.0, 2.5, 3.0, 4.0]
    rz_values = [4.7, 6.8, 9.4, 12.0, 18.0]
    run_sweep(params, cc_values, rz_values)
