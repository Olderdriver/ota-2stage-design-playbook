#!/usr/bin/env python3
"""Batch transient sweep for VBP2 and Cc to study large-signal response speed."""
import os
import sys
import tempfile

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path

import numpy as np

from hspice_common import MODEL_DIR, parse_print_table, run_hspice, spath


def _cap_pf(v):
    return f'{v:g}p'


def _res_k(v):
    return f'{v:g}k'


def _v(v):
    return f'{v:.4f}'


def build_netlist(base, points):
    first = points[0]
    lines = []
    lines.append('* Two-Stage OTA - VBP2/Cc sweep via .alter')
    lines.append(f".lib '{base['usage_lib']}' tt_mos_varactor")
    lines.append(f".param cc_val = {_cap_pf(first['cc_pf'])}")
    lines.append(f".param rz_val = {_res_k(first['rz_kohm'])}")
    lines.append(f".param vbp2_drop_val = {_v(first['vbp2_drop'])}")
    lines.append(f"Vdd vdd 0 DC {base['vdd']}")
    lines.append(f"Vbp1 vdd vbp1 DC {base['vbp1_drop']}")
    lines.append('Vbp2 vdd vbp2 DC vbp2_drop_val')
    lines.append(f"Vinp inp 0 PULSE({base['vin_low']} {base['vin_high']} {base['tdelay']} {base['trise']} {base['tfall']} {base['ton']} {base['period']})")
    lines.append('')
    lines.append('* Stage 1')
    lines.append(f"xm3 n1 n1 0 0 n18_ckt w={base['w_load_um']}u l={base['l_load_um']}u nfin={base['nfin_load']} nf=1 m={base['m_load']}")
    lines.append(f"xm4 n2 n1 0 0 n18_ckt w={base['w_load_um']}u l={base['l_load_um']}u nfin={base['nfin_load']} nf=1 m={base['m_load']}")
    lines.append(f"xm1 n1 out tail vdd p18_ckt w={base['w_in_um']}u l={base['l_in_um']}u nfin={base['nfin_in']} nf=1 m={base['m_in']}")
    lines.append(f"xm2 n2 inp tail vdd p18_ckt w={base['w_in_um']}u l={base['l_in_um']}u nfin={base['nfin_in']} nf=1 m={base['m_in']}")
    lines.append(f"xm5 tail vbp1 vdd vdd p18_ckt w={base['w_tail_um']}u l={base['l_tail_um']}u nfin={base['nfin_tail']} nf=1 m={base['m_tail']}")
    lines.append('* Stage 2')
    lines.append(f"xm6 out n2 0 0 n18_ckt w={base['w_stage2_um']}u l={base['l_stage2_um']}u nfin={base['nfin_stage2']} nf=1 m={base['m_stage2']}")
    lines.append(f"xm7 out vbp2 vdd vdd p18_ckt w={base['w_p2_um']}u l={base['l_p2_um']}u nfin={base['nfin_p2']} nf=1 m={base['m_p2']}")
    lines.append('Rz n2 rz rz_val')
    lines.append('Cc rz out cc_val')
    lines.append(f"Cl out 0 {base['cl']}")
    lines.append(f".tran {base['tstep']} {base['tstop']}")
    lines.append('.print tran v(inp) v(out) v(n2)')
    for p in points[1:]:
        lines.append('.alter')
        lines.append(f".param cc_val = {_cap_pf(p['cc_pf'])}")
        lines.append(f".param rz_val = {_res_k(p['rz_kohm'])}")
        lines.append(f".param vbp2_drop_val = {_v(p['vbp2_drop'])}")
    lines.append('.end')
    return '\n'.join(lines)


def _blocks(arr):
    blocks = []
    col = 1
    while col + 2 < arr.shape[1]:
        blocks.append(arr[:, [0, col, col + 1, col + 2]])
        col += 3
    return blocks


def _cross_time(t, y, target, start_idx=0):
    idx = np.where(y[start_idx:] >= target)[0]
    if len(idx) == 0:
        return None
    i = idx[0] + start_idx
    return float(t[i])


def _analyze(arr, vin_low, vin_high):
    t = arr[:, 0]
    vin = arr[:, 1]
    vout = arr[:, 2]
    n2 = arr[:, 3]
    step_idx = np.where(vin > (vin_low + vin_high) * 0.5)[0]
    fall_idx = np.where(np.diff(vin) < -0.1)[0]
    t_step = float(t[step_idx[0]]) if len(step_idx) else None
    t_fall = float(t[fall_idx[0] + 1]) if len(fall_idx) else None
    rise_95_target = vin_low + 0.95 * (vin_high - vin_low)
    t95 = _cross_time(t, vout, rise_95_target, step_idx[0] if len(step_idx) else 0)
    hold_ns = None if (t95 is None or t_fall is None) else (t_fall - t95) * 1e9
    dvdt = np.diff(vout) / np.diff(t)
    return {
        'sr_pos_vus': float(np.max(dvdt)) * 1e-6,
        'sr_neg_vus': abs(float(np.min(dvdt))) * 1e-6,
        't95_ns': None if t95 is None or t_step is None else (t95 - t_step) * 1e9,
        'hold_ns': hold_ns,
        'overshoot_v': float(np.max(vout) - vin_high),
        'n2_min_v': float(np.min(n2)),
        'vout_at_fall': float(vout[np.argmin(np.abs(t - t_fall))]) if t_fall is not None else None,
    }


def _score(m):
    hold_pen = max(0.0, 40.0 - (m['hold_ns'] or 0.0)) / 10.0
    rise_pen = max(0.0, (m['t95_ns'] or 1e9) - 120.0) / 20.0
    ov_pen = abs(m['overshoot_v']) * 10.0
    n2_pen = max(0.0, 0.12 - m['n2_min_v']) * 10.0
    return hold_pen + rise_pen + ov_pen + n2_pen


def run_sweep(base, cc_values_pf, vbp2_values, rz_kohm):
    points = [
        {'cc_pf': cc, 'vbp2_drop': vbp2, 'rz_kohm': rz_kohm}
        for cc in cc_values_pf for vbp2 in vbp2_values
    ]
    netlist = build_netlist(base, points)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sp', delete=False, encoding='utf-8') as f:
        f.write(netlist)
        tmp = f.name
    try:
        lis = run_hspice(tmp, 'batch_vbp2_cc_sweep', timeout=600)
    finally:
        os.unlink(tmp)
    parsed = parse_print_table(lis)
    _, arr = parsed
    results = []
    for p, block in zip(points, _blocks(arr)):
        m = _analyze(block, float(base['vin_low']), float(base['vin_high']))
        m.update(p)
        m['score'] = _score(m)
        results.append(m)
    for f in Path(lis).parent.glob('batch_vbp2_cc_sweep*'):
        f.unlink(missing_ok=True)
    results.sort(key=lambda x: x['score'])
    print(f"{'Cc':>5s} {'VBP2':>6s} {'t95':>7s} {'hold':>7s} {'SR+':>5s} {'Ovsh':>6s} {'N2min':>6s} {'score':>6s}")
    print('-' * 56)
    for r in results:
        print(f"{r['cc_pf']:5.2f} {r['vbp2_drop']:6.3f} {r['t95_ns']:7.1f} {r['hold_ns']:7.1f} {r['sr_pos_vus']:5.1f} {r['overshoot_v']:6.3f} {r['n2_min_v']:6.3f} {r['score']:6.2f}")
    return results


if __name__ == '__main__':
    base = dict(
        usage_lib=spath(MODEL_DIR / '12sfe_spice_v1p2_rev0_usage.lib'),
        vdd=1.8, vbp1_drop=0.600, cl='8p',
        vin_low='0.75', vin_high='1.05', tdelay='10n', trise='200p', tfall='200p', ton='200n', period='500n', tstep='100p', tstop='500n',
        w_in_um=0.154, l_in_um=0.18, nfin_in=20, m_in=1,
        w_load_um=0.154, l_load_um=0.24, nfin_load=8, m_load=1,
        w_tail_um=0.154, l_tail_um=0.24, nfin_tail=12, m_tail=1,
        w_stage2_um=0.154, l_stage2_um=0.24, nfin_stage2=11, m_stage2=2,
        w_p2_um=0.154, l_p2_um=0.24, nfin_p2=15, m_p2=2,
    )
    run_sweep(base, [2.5, 3.0, 4.0, 5.5], [0.500, 0.514, 0.528, 0.542], 12.0)
