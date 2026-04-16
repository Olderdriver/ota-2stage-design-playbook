#!/usr/bin/env python3
"""Batch sweep output load capacitance for slew tuning."""
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


def build_netlist(base, cl_values):
    first = cl_values[0]
    lines = []
    lines.append('* Two-Stage OTA - CL sweep via .alter')
    lines.append(f".lib '{base['usage_lib']}' tt_mos_varactor")
    lines.append(f".param cl_val = {_cap_pf(first)}")
    lines.append(f"Vdd vdd 0 DC {base['vdd']}")
    lines.append(f"Vbp1 vdd vbp1 DC {base['vbp1_drop']}")
    lines.append(f"Vbp2 vdd vbp2 DC {base['vbp2_drop']}")
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
    lines.append(f"Rz n2 rz {base['rz']}")
    lines.append(f"Cc rz out {base['cc']}")
    lines.append('Cl out 0 cl_val')
    lines.append(f".tran {base['tstep']} {base['tstop']}")
    lines.append('.print tran v(inp) v(out) v(n2)')
    for cl in cl_values[1:]:
        lines.append('.alter')
        lines.append(f".param cl_val = {_cap_pf(cl)}")
    lines.append('.end')
    return '\n'.join(lines)


def _blocks(arr):
    blocks = []
    col = 1
    while col + 2 < arr.shape[1]:
        blocks.append(arr[:, [0, col, col + 1, col + 2]])
        col += 3
    return blocks


def _analyze(arr, vin_low, vin_high):
    t, vin, vout, n2 = arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3]
    dvdt = np.diff(vout) / np.diff(t)
    step_idx = np.where(vin > (vin_low + vin_high) * 0.5)[0][0]
    fall_idx = np.where(np.diff(vin) < -0.1)[0][0] + 1
    rise95 = vin_low + 0.95 * (vin_high - vin_low)
    idx95 = np.where(vout[step_idx:] >= rise95)[0]
    idx95 = idx95[0] + step_idx if len(idx95) else None
    hold_ns = None if idx95 is None else (t[fall_idx] - t[idx95]) * 1e9
    return {
        'sr_pos_vus': float(np.max(dvdt)) * 1e-6,
        'sr_neg_vus': abs(float(np.min(dvdt))) * 1e-6,
        'hold_ns': hold_ns,
        'overshoot_v': float(np.max(vout) - vin_high),
        'n2_min_v': float(np.min(n2)),
    }


def _score(m):
    return (
        abs(m['sr_neg_vus'] - 5.0)
        + abs(m['sr_pos_vus'] - 5.0)
        + max(0.0, 100.0 - (m['hold_ns'] or 0.0)) / 20.0
        + abs(m['overshoot_v']) * 10.0
    )


def run_sweep(base, cl_values):
    netlist = build_netlist(base, cl_values)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sp', delete=False, encoding='utf-8') as f:
        f.write(netlist)
        tmp = f.name
    try:
        lis = run_hspice(tmp, 'batch_cl_sweep', timeout=600)
    finally:
        os.unlink(tmp)
    _, arr = parse_print_table(lis)
    results = []
    for cl, block in zip(cl_values, _blocks(arr)):
        m = _analyze(block, float(base['vin_low']), float(base['vin_high']))
        m['cl_pf'] = cl
        m['score'] = _score(m)
        results.append(m)
    for f in Path(lis).parent.glob('batch_cl_sweep*'):
        f.unlink(missing_ok=True)
    results.sort(key=lambda x: x['score'])
    print(f"{'CL':>5s} {'SR+':>5s} {'SR-':>5s} {'hold':>7s} {'Ovsh':>6s} {'N2min':>6s} {'score':>6s}")
    print('-' * 46)
    for r in results:
        print(f"{r['cl_pf']:5.1f} {r['sr_pos_vus']:5.2f} {r['sr_neg_vus']:5.2f} {r['hold_ns']:7.1f} {r['overshoot_v']:6.3f} {r['n2_min_v']:6.3f} {r['score']:6.2f}")
    return results


if __name__ == '__main__':
    base = dict(
        usage_lib=spath(MODEL_DIR / '12sfe_spice_v1p2_rev0_usage.lib'),
        vdd=1.8, vbp1_drop=0.600, vbp2_drop=0.528,
        cc='3p', rz='12k',
        vin_low='0.75', vin_high='1.05', tdelay='10n', trise='200p', tfall='200p', ton='200n', period='500n', tstep='100p', tstop='500n',
        w_in_um=0.154, l_in_um=0.18, nfin_in=20, m_in=1,
        w_load_um=0.154, l_load_um=0.24, nfin_load=8, m_load=1,
        w_tail_um=0.154, l_tail_um=0.24, nfin_tail=12, m_tail=1,
        w_stage2_um=0.154, l_stage2_um=0.24, nfin_stage2=11, m_stage2=4,
        w_p2_um=0.154, l_p2_um=0.24, nfin_p2=15, m_p2=4,
    )
    run_sweep(base, [8, 10, 12, 14, 16, 20, 24, 32])
