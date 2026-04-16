#!/usr/bin/env python3
"""
Batch VBP2_DROP sweep using HSPICE .alter — single process launch.

Usage:
    python sweep_vbp2_batch.py [lo_mv] [hi_mv] [step_mv]
    defaults: 515 555 1
"""
import os, sys, tempfile, re
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path
from hspice_common import MODEL_DIR, run_hspice, spath, _parse_spice_float

VDD = 1.8
VCM = 0.9


def build_alter_netlist(base_params, drop_values):
    """Build a single HSPICE netlist with .alter blocks for each VBP2_DROP."""
    lib = base_params['usage_lib']
    lines = []
    lines.append("* Two-Stage OTA — batch VBP2_DROP sweep via .alter")
    lines.append(f".lib '{lib}' tt_mos_varactor")
    lines.append(f".param vbp2_drop_val = {drop_values[0]:.4f}")
    lines.append(f"Vdd  vdd  0 DC {base_params['vdd']}")
    lines.append(f"Vinp inp  0 DC {base_params['vcm']}")
    lines.append(f"Vinn inn  0 DC {base_params['vcm']}")
    lines.append(f"Vbp1 vdd vbp1 DC {base_params['vbp1_drop']}")
    lines.append(f"Vbp2 vdd vbp2 DC vbp2_drop_val")
    lines.append("")
    lines.append("* Stage 1")
    lines.append(f"xm3 n1 n1 0 0 n18_ckt w={base_params['w_load_um']}u l={base_params['l_load_um']}u nfin={base_params['nfin_load']} nf=1 m={base_params['m_load']}")
    lines.append(f"xm4 n2 n1 0 0 n18_ckt w={base_params['w_load_um']}u l={base_params['l_load_um']}u nfin={base_params['nfin_load']} nf=1 m={base_params['m_load']}")
    lines.append(f"xm1 n1 inp tail vdd p18_ckt w={base_params['w_in_um']}u l={base_params['l_in_um']}u nfin={base_params['nfin_in']} nf=1 m={base_params['m_in']}")
    lines.append(f"xm2 n2 inn tail vdd p18_ckt w={base_params['w_in_um']}u l={base_params['l_in_um']}u nfin={base_params['nfin_in']} nf=1 m={base_params['m_in']}")
    lines.append(f"xm5 tail vbp1 vdd vdd p18_ckt w={base_params['w_tail_um']}u l={base_params['l_tail_um']}u nfin={base_params['nfin_tail']} nf=1 m={base_params['m_tail']}")
    lines.append("* Stage 2")
    lines.append(f"xm6 out n2 0 0 n18_ckt w={base_params['w_stage2_um']}u l={base_params['l_stage2_um']}u nfin={base_params['nfin_stage2']} nf=1 m={base_params['m_stage2']}")
    lines.append(f"xm7 out vbp2 vdd vdd p18_ckt w={base_params['w_p2_um']}u l={base_params['l_p2_um']}u nfin={base_params['nfin_p2']} nf=1 m={base_params['m_p2']}")
    lines.append(f"Rz n2 rz {base_params['rz']}")
    lines.append(f"Cc rz out {base_params['cc']}")
    lines.append(f"Cl out 0 {base_params['cl']}")
    lines.append(".op")
    for drop in drop_values[1:]:
        lines.append(f".alter")
        lines.append(f".param vbp2_drop_val = {drop:.4f}")
    lines.append(".end")
    return "\n".join(lines)


def parse_alter_results(lis_path, drop_values):
    """Parse Vout from each .alter run in a single .lis file."""
    content = Path(lis_path).read_text(encoding='utf-8', errors='replace')
    matches = re.findall(r'0:out\s*=\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?(?:meg|[a-zA-Z])?)', content, flags=re.IGNORECASE)
    results = []
    for i, drop in enumerate(drop_values):
        vout = _parse_spice_float(matches[i]) if i < len(matches) else None
        err = abs(vout - VCM) if vout is not None else 999
        results.append((drop, vout, err))
    return results


def run_sweep(base_params, lo_mv=515, hi_mv=555, step_mv=1):
    drop_values = [mv / 1000.0 for mv in range(lo_mv, hi_mv + 1, step_mv)]
    print(f"  Batch sweep: {len(drop_values)} points in ONE hspice run")
    print(f"  Range: VBP2_DROP = [{lo_mv/1000:.3f}, {hi_mv/1000:.3f}] V, step {step_mv} mV")

    netlist = build_alter_netlist(base_params, drop_values)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sp', delete=False, encoding='utf-8') as f:
        f.write(netlist)
        tmp = f.name
    try:
        lis = run_hspice(tmp, 'batch_vbp2_sweep', timeout=300)
    finally:
        os.unlink(tmp)

    results = parse_alter_results(lis, drop_values)

    for f in Path(lis).parent.glob('batch_vbp2_sweep*'):
        f.unlink(missing_ok=True)

    print(f"\n  {'drop':>6s}  {'Vout':>8s}  {'err':>8s}")
    print("  " + "-" * 30)
    best_drop, best_err, best_vout = None, 999, None
    for drop, vout, err in results:
        if vout is None:
            continue
        if err < best_err:
            best_err = err
            best_drop = drop
            best_vout = vout
        mark = ' <--' if err < 0.05 else ''
        print(f"  {drop:6.3f}  {vout:8.4f}  {err:8.4f}{mark}")

    if best_drop is not None:
        print(f"\n  Best: VBP2_DROP = {best_drop:.3f}  Vout = {best_vout:.4f}  err = {best_err:.4f}")
    else:
        print("\n  No valid operating point parsed.")
    return best_drop, results


if __name__ == '__main__':
    params = dict(
        usage_lib=spath(MODEL_DIR / '12sfe_spice_v1p2_rev0_usage.lib'),
        vdd=1.8, vcm=0.9, vbp1_drop=0.600,
        cc='1.5p', rz='9.4k', cl='8p',
        w_in_um=0.154, l_in_um=0.18, nfin_in=20, m_in=1,
        w_load_um=0.154, l_load_um=0.24, nfin_load=8, m_load=1,
        w_tail_um=0.154, l_tail_um=0.24, nfin_tail=12, m_tail=1,
        w_stage2_um=0.154, l_stage2_um=0.24, nfin_stage2=11, m_stage2=2,
        w_p2_um=0.154, l_p2_um=0.24, nfin_p2=15, m_p2=2,
    )
    lo = int(sys.argv[1]) if len(sys.argv) > 1 else 515
    hi = int(sys.argv[2]) if len(sys.argv) > 2 else 555
    step = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    run_sweep(params, lo, hi, step)
