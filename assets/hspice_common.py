#!/usr/bin/env python3
"""Shared utilities for the HSPICE example package."""

from __future__ import annotations

import subprocess
import sys
import re
from pathlib import Path

import numpy as np


BASE_DIR = Path(__file__).resolve().parent
NETLIST_DIR = BASE_DIR / 'netlist'
LOG_DIR = BASE_DIR / 'logs'
PLOT_DIR = BASE_DIR / 'plots'
MODEL_DIR = BASE_DIR.parent.parent / 'models' / 'hspice'
if not MODEL_DIR.is_dir():
    MODEL_DIR = BASE_DIR.parent.parent / 'gmoverid-hspice' / 'models' / 'hspice'
for _d in (LOG_DIR, PLOT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

HSPICE_EXE = Path(r'C:\synopsys\Hspice_S-2021.09\WIN64\hspice.com')


def spath(p: Path) -> str:
    return str(p).replace('\\', '/')


def check_hspice():
    if not HSPICE_EXE.exists():
        sys.exit(f'HSPICE not found at {HSPICE_EXE}')
    print(f'  HSPICE: {HSPICE_EXE}')


def render_template(tmpl_name: str, **kw) -> str:
    text = (NETLIST_DIR / tmpl_name).read_text(encoding='utf-8')
    return text.format(**kw)


def run_hspice(netlist: Path, stem: str, timeout: int = 120) -> Path:
    lis = LOG_DIR / f'{stem}.lis'
    out_root = LOG_DIR / stem
    cmd = [str(HSPICE_EXE), '-i', str(Path(netlist).resolve()), '-o', str(out_root.resolve())]
    kwargs = dict(capture_output=True, text=True, timeout=timeout, cwd=str(MODEL_DIR))
    if sys.platform == 'win32':
        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
    proc = subprocess.run(cmd, **kwargs)
    if not lis.exists():
        raise RuntimeError((proc.stdout or '') + '\n' + (proc.stderr or ''))
    return lis


_FLOAT_RE = re.compile(r'^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?[a-zA-Z]?$')


_SUFFIX_SCALE = {
    't': 1e12,
    'g': 1e9,
    'meg': 1e6,
    'k': 1e3,
    'm': 1e-3,
    'u': 1e-6,
    'n': 1e-9,
    'p': 1e-12,
    'f': 1e-15,
    'a': 1e-18,
    # HSPICE may emit `x` as the compact 1e6 suffix in print tables
    # (for example `1.00000x` = 1 MHz), even though bare `x` on its own line
    # is also used as a table marker and must be skipped separately below.
    'x': 1e6,
}


def _parse_spice_float(token: str) -> float:
    s = token.strip()
    if not s:
        raise ValueError('empty token')
    lower = s.lower()
    if lower.endswith('meg'):
        return float(lower[:-3]) * _SUFFIX_SCALE['meg']
    if lower[-1].isalpha() and lower[-1] not in {'e'}:
        return float(lower[:-1]) * _SUFFIX_SCALE[lower[-1]]
    return float(lower)


def parse_print_table(lis_path: Path):
    lines = lis_path.read_text(encoding='utf-8', errors='replace').splitlines()
    blocks = []

    def _dedupe_names(raw_names):
        # HSPICE can print repeated node names on the second header row, e.g.
        # `freq volt db volt phase` + `drain drain`. Preserve both columns by
        # uniquifying names before accumulation instead of collapsing them.
        counts = {}
        unique = []
        for name in raw_names:
            idx = counts.get(name, 0)
            unique.append(name if idx == 0 else f'{name}_{idx + 1}')
            counts[name] = idx + 1
        return unique

    i = 0
    while i < len(lines):
        lead = lines[i].lstrip().lower()
        if (lead.startswith('volt') or lead.startswith('time') or lead.startswith('freq')) and i + 1 < len(lines):
            header1 = lines[i].split()
            header2 = lines[i + 1].split()
            names = [header1[0].lower()]
            names.extend(tok.lower() for tok in header2)
            names = _dedupe_names(names)
            rows = []
            i += 2
            while i < len(lines):
                s = lines[i].strip()
                if not s:
                    i += 1
                    continue
                if s in {'x', 'y'}:
                    if s == 'y':
                        break
                    i += 1
                    continue
                if s.startswith('*') or s.startswith('******'):
                    break
                parts = s.split()
                if len(parts) >= len(names) and _FLOAT_RE.match(parts[0]):
                    rows.append([_parse_spice_float(x) for x in parts[:len(names)]])
                i += 1
            if rows:
                blocks.append((names, np.array(rows, dtype=float)))
        i += 1

    if not blocks:
        return None

    merged_names, merged_arr = blocks[0]
    for names, arr in blocks[1:]:
        same_sweep = (
            names
            and merged_names
            and names[0] == merged_names[0]
            and arr.shape[0] == merged_arr.shape[0]
            and np.allclose(arr[:, 0], merged_arr[:, 0])
        )
        if same_sweep:
            merged_names = merged_names + names[1:]
            merged_arr = np.column_stack([merged_arr, arr[:, 1:]])

    return merged_names, merged_arr
