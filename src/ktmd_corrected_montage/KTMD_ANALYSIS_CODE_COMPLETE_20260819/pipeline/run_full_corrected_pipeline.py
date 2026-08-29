#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import io
import itertools
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy import signal, stats
from scipy.io import loadmat
from scipy.ndimage import gaussian_filter, label, find_objects
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).parent))
from run_ktmd_state_v2 import (
    combine_stats, fit_operator, module_membership, signature,
)
from run_cross_day import load_day, keys, AWAKE

TARGETS = [
    ('Kin2', '20110513'), ('Kin2', '20110524'), ('Kin2', '20110525'),
    ('Su', '20110523'), ('Su', '20110526'), ('Su', '20110527'),
]
DATES_BY_ANIMAL = {
    'Kin2': ['20110513', '20110524', '20110525'],
    'Su': ['20110523', '20110526', '20110527'],
}
METRICS = ['Q', 'Cspec', 'Aspec', 'Deff_frac', 'Gpair', 'Oorg', 'top_share', 'WMI']
EXPECTED_DIRECTION = {
    'Q': 'increase', 'Cspec': 'increase', 'Aspec': 'decrease',
    'Deff_frac': 'decrease', 'Gpair': 'decrease', 'Oorg': 'decrease',
    'top_share': 'increase', 'WMI': 'increase',
}
STATE_LABELS = {
    'AwakeEyesOpened': 'EO', 'AwakeEyesClosed': 'EC', 'Anesthetized': 'AN',
    'RecoveryEyesClosed': 'REC', 'RecoveryEyesOpened': 'REO',
}
COMPACT_FILES = [
    'block_plan.csv', 'bipolar_pairs.csv', 'awake_scale.npy', 'awake_scale_qc.csv',
    'block_sufficient_stats.npz', 'ridge_cv.csv', 'model_fit.csv',
    'candidate_signatures.csv', 'candidate_sets.csv', 'crossfit_ratios.csv',
    'summary.json', 'full_awake_module_labels.npy',
    'RAW_ARCHIVE_PROVENANCE.json',
]
FS = 200.0
LAG = 5
SOS_HP = signal.butter(4, 4.0, btype='highpass', fs=FS, output='sos')
SOS_DELTA = signal.butter(4, [0.5, 4.0], btype='bandpass', fs=FS, output='sos')


def log(msg: str) -> None:
    print(msg, flush=True)


def sha256_path(path: Path, block: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        while True:
            b = f.read(block)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def gmean(values: Iterable[float]) -> float:
    a = np.asarray(list(values), dtype=float)
    a = a[np.isfinite(a) & (a > 0)]
    return float(np.exp(np.mean(np.log(a)))) if len(a) else np.nan


def load_expected(assets: Path) -> dict[str, dict]:
    obj = json.loads((assets / 'expected_master_index.json').read_text(encoding='utf-8'))
    return {a['original_name']: a for a in obj['archives']}


def target_filename(animal: str, date: str) -> str:
    return f'{date}KTMD_Anesthesia+and+Sleep_{animal}_Toru+Yanagawa_mat_ECoG128.zip'


def validate_raw_provenance(record: dict, expected_rec: dict, animal: str, date: str) -> None:
    """Reject placeholders, duplicated days, and mismatched raw archives."""
    expected_name = target_filename(animal, date)
    required = {
        'animal','date','expected_archive_name','expected_archive_sha256',
        'actual_archive_sha256','expected_archive_size_bytes','actual_archive_size_bytes',
        'manifest_original_name','manifest_original_sha256','part_count',
        'verified_part_count','dataset_root_name','pipeline_version',
    }
    missing = required - set(record)
    if missing:
        raise RuntimeError(f'{animal} {date}: raw provenance missing {sorted(missing)}')
    checks = {
        'animal': str(record['animal']) == animal,
        'date': str(record['date']) == date,
        'expected_name': record['expected_archive_name'] == expected_name,
        'manifest_name': record['manifest_original_name'] == expected_name,
        'expected_sha': record['expected_archive_sha256'] == expected_rec['original_sha256'],
        'actual_sha': record['actual_archive_sha256'] == expected_rec['original_sha256'],
        'manifest_sha': record['manifest_original_sha256'] == expected_rec['original_sha256'],
        'expected_size': int(record['expected_archive_size_bytes']) == int(expected_rec['original_size_bytes']),
        'actual_size': int(record['actual_archive_size_bytes']) == int(expected_rec['original_size_bytes']),
        'part_count': int(record['part_count']) == len(expected_rec['parts']),
        'verified_part_count': int(record['verified_part_count']) == len(expected_rec['parts']),
        'root_identity': animal.lower() in str(record['dataset_root_name']).lower() and date in str(record['dataset_root_name']),
        'pipeline_version': str(record['pipeline_version']).startswith('v4-provenance-locked'),
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise RuntimeError(f'{animal} {date}: raw provenance failed {failed}: {record}')


def _manifest_records(path: Path) -> list[dict]:
    try:
        obj = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return []
    if isinstance(obj, dict) and 'original_name' in obj and 'parts' in obj:
        return [obj]
    if isinstance(obj, dict) and isinstance(obj.get('files'), list):
        return [x for x in obj['files'] if isinstance(x, dict) and 'original_name' in x]
    if isinstance(obj, dict) and isinstance(obj.get('archives'), list):
        return [x for x in obj['archives'] if isinstance(x, dict) and 'original_name' in x]
    return []


def locate_split_root(configured: Path) -> Path:
    candidates: list[Path] = []
    if configured.exists():
        candidates.append(configured)
    for base in [Path('/content/drive/MyDrive'), Path('/content/ktmd_shared_parts'), Path('/content')]:
        if not base.exists():
            continue
        for p in base.rglob('manifest.json'):
            candidates.append(p.parent)
        for p in base.rglob('MASTER_INDEX.json'):
            candidates.append(p.parent)
    # Prefer the shallowest directory containing at least five target manifests/folders.
    roots: list[Path] = []
    for c in candidates:
        for parent in [c, *c.parents[:4]]:
            if parent.exists() and parent not in roots:
                roots.append(parent)
    scored = []
    for root in roots:
        score = 0
        for animal, date in TARGETS:
            name = target_filename(animal, date)
            if any(name == rec.get('original_name') for p in root.rglob('*.json') for rec in _manifest_records(p)):
                score += 1
            elif list(root.rglob(f'{date}KTMD*{animal}*.zip.parts')):
                score += 1
        if score:
            scored.append((score, -len(root.parts), root))
    if not scored:
        raise FileNotFoundError(
            f'No split-archive root found. Configured path was {configured}. '
            'Make sure the split folder is in MyDrive or that the public Drive fallback completed.'
        )
    scored.sort(reverse=True, key=lambda x: (x[0], x[1]))
    root = scored[0][2]
    log(f'[SPLIT ROOT] {root} ({scored[0][0]}/6 targets recognized)')
    return root


def find_manifest_and_parts(split_root: Path, animal: str, date: str, expected: dict) -> tuple[dict, Path]:
    name = target_filename(animal, date)
    # Fast path: archive-specific .zip.parts directory.
    hits = list(split_root.rglob(f'{date}KTMD*{animal}*.zip.parts'))
    for folder in hits:
        mp = folder / 'manifest.json'
        if mp.exists():
            for rec in _manifest_records(mp):
                if rec.get('original_name') == name:
                    return rec, folder
    # General path: inspect manifests and infer part folder.
    for mp in list(split_root.rglob('manifest.json')) + list(split_root.rglob('MASTER_INDEX.json')):
        for rec in _manifest_records(mp):
            if rec.get('original_name') != name:
                continue
            candidates = [
                mp.parent,
                mp.parent / f'{name}.parts',
                mp.parent / name.replace('.zip', '.zip.parts'),
                mp.parent / Path(str(rec.get('original_relative_path', ''))).name.replace('.zip', '.zip.parts'),
            ]
            for folder in candidates:
                if folder.exists() and all((folder / p['name']).exists() for p in rec['parts']):
                    return rec, folder
            # Last resort: find the first part and require all other parts beside it.
            first = rec['parts'][0]['name']
            for fp in split_root.rglob(first):
                folder = fp.parent
                if all((folder / p['name']).exists() for p in rec['parts']):
                    return rec, folder
    raise FileNotFoundError(f'Could not locate all parts for {name} under {split_root}')


def reassemble_archive(manifest: dict, parts_dir: Path, local_zip: Path, expected_rec: dict) -> dict:
    local_zip.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(local_zip) + '.tmp')
    h = hashlib.sha256()
    total = 0
    with tmp.open('wb') as out:
        for rec in manifest['parts']:
            part = parts_dir / rec['name']
            if not part.exists():
                raise FileNotFoundError(part)
            if part.stat().st_size != int(rec['size_bytes']):
                raise RuntimeError(f'Wrong part size: {part}')
            ph = hashlib.sha256()
            with part.open('rb') as f:
                while True:
                    b = f.read(8 * 1024 * 1024)
                    if not b:
                        break
                    out.write(b)
                    h.update(b)
                    ph.update(b)
                    total += len(b)
            if ph.hexdigest() != rec['sha256']:
                raise RuntimeError(f'Part hash mismatch: {part}')
    got = {'size': total, 'sha256': h.hexdigest()}
    for source, exp in [('manifest', manifest), ('embedded expected index', expected_rec)]:
        if total != int(exp['original_size_bytes']):
            raise RuntimeError(f'Whole size mismatch against {source}: {total} != {exp["original_size_bytes"]}')
        if got['sha256'] != exp['original_sha256']:
            raise RuntimeError(f'Whole SHA mismatch against {source}: {got["sha256"]} != {exp["original_sha256"]}')
    os.replace(tmp, local_zip)
    return got


def extract_archive(local_zip: Path, raw_parent: Path) -> Path:
    if raw_parent.exists():
        shutil.rmtree(raw_parent)
    raw_parent.mkdir(parents=True)
    with zipfile.ZipFile(local_zip) as zf:
        bad = zf.testzip()
        if bad:
            raise RuntimeError(f'Corrupt ZIP member: {bad}')
        for info in zf.infolist():
            name = info.filename
            if info.is_dir() or name.startswith('__MACOSX/') or '/__MACOSX/' in name:
                continue
            base = Path(name).name
            keep = (
                re.fullmatch(r'ECoG_ch\d+\.mat', base) is not None
                or base in {'Condition.mat', 'ECoGTime.mat'}
                or base.startswith('Info-')
            )
            if keep:
                zf.extract(info, raw_parent)
    roots = [
        p for p in raw_parent.rglob('*') if p.is_dir()
        and any((p / f'Session{i}').exists() for i in range(1, 6))
    ]
    # Choose the deepest unique dataset root.
    roots = sorted(set(roots), key=lambda p: len(p.parts), reverse=True)
    if not roots:
        raise RuntimeError(f'Could not identify dataset root under {raw_parent}')
    return roots[0]


def matlab_label(x) -> str:
    while isinstance(x, np.ndarray):
        if x.size == 0:
            return ''
        x = x.reshape(-1)[0]
    return str(x)


def make_conditions(dataset_root: Path, animal: str, date: str, out_path: Path) -> None:
    sessions = {}
    for sdir in sorted(dataset_root.glob('Session*')):
        cond = sdir / 'Condition.mat'
        if not cond.exists():
            continue
        mat = loadmat(cond)
        labels = [matlab_label(x) for x in np.asarray(mat['ConditionLabel']).reshape(-1)]
        times = np.asarray(mat['ConditionTime']).reshape(-1).astype(float)
        starts, ends = {}, {}
        for t, lbl in zip(times, labels):
            if lbl.endswith('-Start'):
                starts[lbl[:-6]] = float(t)
            elif lbl.endswith('-End'):
                ends[lbl[:-4]] = float(t)
        spec = {}
        for base, code in STATE_LABELS.items():
            if base in starts and base in ends:
                spec[code] = [starts[base], ends[base]]
        if spec:
            sessions[sdir.name.replace('Session', '')] = spec
    if not sessions:
        raise RuntimeError(f'No state intervals parsed from {dataset_root}')
    payload = [{'animal': animal, 'date': date, 'sessions': sessions}]
    out_path.write_text(json.dumps(payload, indent=2), encoding='utf-8')


def montage_for(assets: Path, animal: str) -> pd.DataFrame:
    allm = pd.read_csv(assets / 'corrected_local_montages.csv')
    m = allm[allm.animal.str.lower() == animal.lower()].copy()
    m['bipolar_id'] = m['pair_id'].astype(str)
    m['montage_source'] = 'official-map minimum-bottleneck/minimum-total-distance perfect matching'
    m['region'] = 'unknown'
    cols = ['ch1', 'ch2', 'bipolar_id', 'distance_px', 'mid_x', 'mid_y', 'montage_source', 'region']
    # Strict audit: every contact exactly once and 64 full-row-rank pairs.
    contacts = pd.concat([m.ch1, m.ch2]).astype(int)
    if len(m) != 64 or len(set(contacts)) != 128 or contacts.value_counts().max() != 1:
        raise RuntimeError(f'{animal} montage failed no-reuse/full-coverage audit')
    B = np.zeros((len(m), 128))
    for i, r in enumerate(m.itertuples(index=False)):
        B[i, int(r.ch1)-1] = 1
        B[i, int(r.ch2)-1] = -1
    if np.linalg.matrix_rank(B) != 64:
        raise RuntimeError(f'{animal} montage incidence matrix is not full row rank')
    return m[cols]


def copy_compact(day_local: Path, day_drive: Path) -> None:
    """Persist a restart-safe day result to Drive.

    The preprocessed state blocks are retained because the final block-trajectory,
    slow-wave-control, and spectral audits require them. The compact final ZIP
    deliberately excludes these large cache arrays.
    """
    day_drive.mkdir(parents=True, exist_ok=True)
    for name in COMPACT_FILES:
        src = day_local / name
        if src.exists():
            shutil.copy2(src, day_drive / name)
    for src in day_local.glob('A_*.npy'):
        shutil.copy2(src, day_drive / src.name)
    src_pre = day_local / 'preprocessed'
    dst_pre = day_drive / 'preprocessed'
    if dst_pre.exists():
        shutil.rmtree(dst_pre)
    if src_pre.exists():
        shutil.copytree(src_pre, dst_pre)
    (day_drive / 'DAY_COMPLETE.ok').write_text('complete\n', encoding='utf-8')


def run_day(
    work: Path, output_root: Path, split_root: Path, assets: Path,
    animal: str, date: str, expected: dict,
) -> Path:
    day_work = work / 'day_results' / f'{animal.lower()}_{date}'
    day_drive = output_root / 'day_results' / f'{animal.lower()}_{date}'
    expected_rec = expected[target_filename(animal, date)]
    if ((day_work/'summary.json').exists() and (day_work/'preprocessed/PREPROCESS_COMPLETE.ok').exists()
            and (day_work/'RAW_ARCHIVE_PROVENANCE.json').exists()):
        record=json.loads((day_work/'RAW_ARCHIVE_PROVENANCE.json').read_text(encoding='utf-8'))
        validate_raw_provenance(record, expected_rec, animal, date)
        log(f'[SKIP LOCAL DAY — RAW PROVENANCE VERIFIED] {animal} {date}')
        return day_work
    if ((day_drive/'DAY_COMPLETE.ok').exists() and (day_drive/'summary.json').exists()
            and (day_drive/'preprocessed/PREPROCESS_COMPLETE.ok').exists()
            and (day_drive/'RAW_ARCHIVE_PROVENANCE.json').exists()):
        record=json.loads((day_drive/'RAW_ARCHIVE_PROVENANCE.json').read_text(encoding='utf-8'))
        validate_raw_provenance(record, expected_rec, animal, date)
        log(f'[RESTORE DAY FROM DRIVE — RAW PROVENANCE VERIFIED] {animal} {date}')
        if day_work.exists(): shutil.rmtree(day_work)
        shutil.copytree(day_drive, day_work)
        return day_work
    if day_work.exists():
        shutil.rmtree(day_work)
    day_work.mkdir(parents=True)
    expected_name = target_filename(animal, date)
    manifest, parts_dir = find_manifest_and_parts(split_root, animal, date, expected_rec)
    local_zip = work / 'archives' / expected_name
    log(f'[REASSEMBLE] {animal} {date} from {parts_dir}')
    got = reassemble_archive(manifest, parts_dir, local_zip, expected_rec)
    log(f'[ARCHIVE VERIFIED] {got["size"]:,} bytes, {got["sha256"]}')
    dataset_root = extract_archive(local_zip, work / 'raw' / f'{animal.lower()}_{date}')
    provenance = {
        'animal':animal,'date':date,'expected_archive_name':expected_name,
        'expected_archive_sha256':expected_rec['original_sha256'],
        'actual_archive_sha256':got['sha256'],
        'expected_archive_size_bytes':int(expected_rec['original_size_bytes']),
        'actual_archive_size_bytes':int(got['size']),
        'manifest_original_name':manifest['original_name'],
        'manifest_original_sha256':manifest['original_sha256'],
        'parts_directory':str(parts_dir),'part_count':len(manifest['parts']),
        'verified_part_count':len(manifest['parts']),
        'dataset_root_name':dataset_root.name,'dataset_root_path_at_runtime':str(dataset_root),
        'pipeline_version':'v4-provenance-locked-2026-08-16',
        'verification':{'part_sizes_checked':True,'part_sha256_checked':True,
            'whole_archive_size_checked':True,'whole_archive_sha256_checked':True,
            'zip_integrity_checked':True},
    }
    validate_raw_provenance(provenance, expected_rec, animal, date)
    (day_work/'RAW_ARCHIVE_PROVENANCE.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
    conditions = work / 'conditions' / f'{animal.lower()}_{date}.json'
    conditions.parent.mkdir(parents=True, exist_ok=True)
    make_conditions(dataset_root, animal, date, conditions)
    pairs = montage_for(assets, animal)
    pair_csv = work / 'conditions' / f'{animal.lower()}_pairs.csv'
    pairs.to_csv(pair_csv, index=False)
    cmd = [
        sys.executable, '-u', str(assets / 'run_ktmd_state_v2.py'),
        '--root', str(dataset_root), '--animal', animal, '--date', date,
        '--conditions', str(conditions), '--pairs-csv', str(pair_csv),
        '--out', str(day_work), '--rebuild',
    ]
    env = os.environ.copy()
    env['PYTHONPATH'] = str(assets)
    subprocess.run(cmd, check=True, env=env)
    day_summary=json.loads((day_work/'summary.json').read_text(encoding='utf-8'))
    if str(day_summary.get('animal')) != animal or str(day_summary.get('date')) != date:
        raise RuntimeError(f'{animal} {date}: day summary identity mismatch: {day_summary}')
    copy_compact(day_work, day_drive)
    shutil.rmtree(work / 'raw' / f'{animal.lower()}_{date}', ignore_errors=True)
    local_zip.unlink(missing_ok=True)
    log(f'[DONE DAY] {animal} {date}')
    return day_work


def run_crossday(work: Path, output_root: Path, assets: Path, animal: str, days: list[Path]) -> Path:
    out_local = work / 'crossday' / animal
    out_drive = output_root / 'crossday' / animal
    if not (out_local / 'lodo_ratios.csv').exists() and (out_drive / 'lodo_ratios.csv').exists():
        log(f'[RESTORE CROSSDAY FROM DRIVE] {animal}')
        if out_local.exists():
            shutil.rmtree(out_local)
        shutil.copytree(out_drive, out_local)
    if not (out_local / 'lodo_ratios.csv').exists():
        out_local.mkdir(parents=True, exist_ok=True)
        cmd = [
            sys.executable, '-u', str(assets / 'run_cross_day.py'),
            '--animal', animal, '--days', *map(str, days), '--out', str(out_local),
        ]
        env = os.environ.copy()
        env['PYTHONPATH'] = str(assets)
        subprocess.run(cmd, check=True, env=env)
    if out_drive.exists():
        shutil.rmtree(out_drive)
    shutil.copytree(out_local, out_drive)
    return out_local


def stat_from_blocks(blocks: list[np.ndarray]) -> dict:
    xx = yx = yy = None
    n = 0
    for X in blocks:
        x = X[:, :-LAG]
        y = X[:, LAG:]
        if xx is None:
            xx, yx, yy = x @ x.T, y @ x.T, y @ y.T
        else:
            xx += x @ x.T
            yx += y @ x.T
            yy += y @ y.T
        n += x.shape[1]
    return {'xx': xx, 'yx': yx, 'yy': yy, 'n': n}


def load_state_arrays(daypath: Path, state: str) -> list[np.ndarray]:
    plan = pd.read_csv(daypath / 'block_plan.csv')
    rows = plan[plan.state.eq(state)]
    scale = np.load(daypath / 'awake_scale.npy').astype(float)
    out = []
    for r in rows.itertuples(index=False):
        x = np.load(daypath / 'preprocessed' / f'{state}_block{int(r.block):02d}.npy', mmap_mode='r').astype(float)
        out.append(x / scale[:, None])
    return out


def transform_blocks(awake: list[np.ndarray], deep: list[np.ndarray], kind: str):
    if kind == 'broadband':
        return awake, deep
    if kind == 'highpass4':
        return [signal.sosfiltfilt(SOS_HP, x, axis=1) for x in awake], [signal.sosfiltfilt(SOS_HP, x, axis=1) for x in deep]
    if kind == 'delta':
        return [signal.sosfiltfilt(SOS_DELTA, x, axis=1) for x in awake], [signal.sosfiltfilt(SOS_DELTA, x, axis=1) for x in deep]
    if kind == 'state_zscore':
        def z(blocks):
            ss = sum(np.sum(x*x, axis=1) for x in blocks)
            nn = sum(x.shape[1] for x in blocks)
            sc = np.maximum(np.sqrt(ss / nn), 1e-8)
            return [x / sc[:, None] for x in blocks]
        return z(awake), z(deep)
    if kind == 'remove_pc1':
        def rem(blocks):
            cov = sum(x @ x.T for x in blocks) / sum(x.shape[1] for x in blocks)
            v = np.linalg.eigh(cov)[1][:, -1]
            return [x - v[:, None] * (v @ x)[None, :] for x in blocks]
        return rem(awake), rem(deep)
    raise ValueError(kind)


def compute_slowwave_controls(daypaths: dict[tuple[str, str], Path], crossdirs: dict[str, Path]) -> pd.DataFrame:
    rows = []
    for animal, dates in DATES_BY_ANIMAL.items():
        cdir = crossdirs[animal]
        canddf = pd.read_csv(cdir / 'lodo_candidates.csv')
        day_objs = [load_day(daypaths[(animal, d)]) for d in dates]
        for held in day_objs:
            date = str(held['date'])
            train = [d for d in day_objs if str(d['date']) != date]
            sub = canddf[canddf.heldout_date.astype(str).eq(date)]
            lam = float(sub['lambda'].iloc[0])
            train_blocks = [d['stats'][k] for d in train for k in keys(d, AWAKE)]
            trainA = fit_operator(combine_stats(train_blocks), lam)[0]
            membership, _ = module_membership(trainA)
            daypath = daypaths[(animal, date)]
            awake = load_state_arrays(daypath, 'eyes_open') + load_state_arrays(daypath, 'eyes_closed')
            deep = load_state_arrays(daypath, 'deep_anesthesia')
            trans = {}
            for kind in ['broadband', 'state_zscore', 'highpass4', 'delta', 'remove_pc1']:
                aw, dp = transform_blocks(awake, deep, kind)
                trans[kind] = (
                    fit_operator(stat_from_blocks(aw), lam)[0],
                    fit_operator(stat_from_blocks(dp), lam)[0],
                )
            for k in (3, 4, 5):
                cr = sub[sub.k.eq(k)].iloc[0]
                cand = tuple(int(x) for x in str(cr.candidate).split(';'))
                for kind, (Aaw, Adp) in trans.items():
                    a = signature(Aaw, membership, cand)
                    d = signature(Adp, membership, cand)
                    rec = {'animal': animal, 'date': date, 'k': k, 'transform': kind, 'lambda': lam}
                    for m in METRICS:
                        rec[f'{m}_ratio'] = d[m] / a[m] if a[m] != 0 else np.nan
                    rows.append(rec)
            log(f'[SLOWWAVE] {animal} {date}')
    return pd.DataFrame(rows)


def compute_block_spectral(daypaths: dict[tuple[str, str], Path]) -> pd.DataFrame:
    rows = []
    for (animal, date), daypath in daypaths.items():
        plan = pd.read_csv(daypath / 'block_plan.csv')
        for pr in plan.itertuples(index=False):
            X = np.load(daypath / 'preprocessed' / f'{pr.state}_block{int(pr.block):02d}.npy', mmap_mode='r').astype(np.float64)
            X = X - X.mean(axis=1, keepdims=True)
            rms = float(np.median(np.sqrt(np.mean(X*X, axis=1))))
            win = np.hanning(X.shape[1])
            P = np.abs(np.fft.rfft(X * win, axis=1))**2
            f = np.fft.rfftfreq(X.shape[1], 1/FS)
            denom = P[:, (f >= .5) & (f <= 40)].sum(axis=1) + 1e-30
            delta = float(np.median(P[:, (f >= .5) & (f < 4)].sum(axis=1) / denom))
            theta = float(np.median(P[:, (f >= 4) & (f < 8)].sum(axis=1) / denom))
            alpha = float(np.median(P[:, (f >= 8) & (f < 13)].sum(axis=1) / denom))
            ac = {}
            for lag in (5, 10, 20):
                a, b = X[:, :-lag], X[:, lag:]
                num = np.sum(a*b, axis=1)
                den = np.sqrt(np.sum(a*a, axis=1) * np.sum(b*b, axis=1)) + 1e-30
                ac[lag] = float(np.median(num / den))
            cov = X @ X.T / X.shape[1]
            eig = np.maximum(np.linalg.eigvalsh(cov), 0)
            pc1 = float(eig[-1] / eig.sum()) if eig.sum() > 0 else np.nan
            p = eig / eig.sum() if eig.sum() > 0 else np.ones(len(eig)) / len(eig)
            erank = float(np.exp(-np.sum(p[p > 0] * np.log(p[p > 0]))))
            sd = np.sqrt(np.diag(cov))
            corr = cov / (sd[:, None] * sd[None, :] + 1e-30)
            mean_abs_corr = float(np.mean(np.abs(corr[np.triu_indices_from(corr, 1)])))
            rows.append({
                'animal': animal, 'date': date, 'state': pr.state, 'block': int(pr.block),
                'session': int(pr.session), 'start_s': float(pr.start_s),
                'rms_median': rms, 'delta_fraction': delta, 'theta_fraction': theta,
                'alpha_fraction': alpha, 'autocorr_25ms': ac[5],
                'autocorr_50ms': ac[10], 'autocorr_100ms': ac[20],
                'pc1_variance_fraction': pc1, 'covariance_effective_rank': erank,
                'mean_abs_correlation': mean_abs_corr,
            })
        log(f'[SPECTRAL] {animal} {date}')
    return pd.DataFrame(rows)


def compute_block_trajectories(daypaths: dict[tuple[str, str], Path], crossdirs: dict[str, Path]) -> pd.DataFrame:
    rows = []
    for animal, dates in DATES_BY_ANIMAL.items():
        days = [load_day(daypaths[(animal, d)]) for d in dates]
        canddf = pd.read_csv(crossdirs[animal] / 'lodo_candidates.csv')
        for held in days:
            date = str(held['date'])
            train = [d for d in days if d is not held]
            train_blocks = [d['stats'][k] for d in train for k in keys(d, AWAKE)]
            sub = canddf[canddf.heldout_date.astype(str).eq(date)]
            lam = float(sub['lambda'].iloc[0])
            train_A = fit_operator(combine_stats(train_blocks), lam)[0]
            membership, _ = module_membership(train_A)
            awake_A = fit_operator(combine_stats(held['stats'][k] for k in keys(held, AWAKE)), lam)[0]
            plan = pd.read_csv(held['path'] / 'block_plan.csv')
            for k in (3, 4, 5):
                cr = sub[sub.k.eq(k)].iloc[0]
                cand = tuple(int(x) for x in str(cr.candidate).split(';'))
                base = signature(awake_A, membership, cand)
                for pr in plan.itertuples(index=False):
                    st = held['stats'][(str(pr.state), int(pr.block))]
                    A, rho, r2 = fit_operator(st, lam)
                    sig = signature(A, membership, cand)
                    rec = {
                        'animal': animal, 'date': date, 'k': k, 'state': str(pr.state),
                        'block': int(pr.block), 'session': int(pr.session),
                        'start_s': float(pr.start_s), 'end_s': float(pr.end_s),
                        'lambda': lam, 'fit_r2': r2, 'rho_raw': rho,
                        'candidate': cr.candidate, 'nodes': cr.nodes,
                    }
                    for m in METRICS:
                        rec[m] = sig[m]
                        rec[f'{m}_over_awake'] = sig[m] / base[m] if base[m] != 0 else np.nan
                    rows.append(rec)
    return pd.DataFrame(rows)


def make_same_day_fixed(daypaths: dict[tuple[str, str], Path]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    fixed_rows, crossfit_rows, qc_rows, montage_rows = [], [], [], []
    for (animal, date), daydir in daypaths.items():
        summ = json.loads((daydir / 'summary.json').read_text())
        day = f'{date}_{animal.lower()}'
        qc_rows.append({'day': day, **summ})
        sig = pd.read_csv(daydir / 'candidate_signatures.csv')
        full = sig[sig.fold.eq('full_awake')]
        for k in (3, 4, 5):
            g = full[full.k.eq(k)].set_index('evaluation')
            rec = {
                'day': day, 'date': date, 'animal': animal, 'k': k,
                'fit_r2_awake': summ['full_awake_r2'], 'fit_r2_deep': summ['deep_anesthesia_r2'],
            }
            for m in METRICS:
                rec[f'{m}_awake'] = float(g.loc['full_awake', m])
                rec[f'{m}_deep'] = float(g.loc['deep_anesthesia', m])
                rec[f'{m}_ratio'] = rec[f'{m}_deep'] / rec[f'{m}_awake']
                for state in ('recovery_eyes_closed', 'recovery_eyes_open'):
                    if state in g.index:
                        rec[f'{m}_{state}'] = float(g.loc[state, m])
                        rec[f'{m}_{state}_ratio'] = float(g.loc[state, m]) / rec[f'{m}_awake']
            fixed_rows.append(rec)
        cf = pd.read_csv(daydir / 'crossfit_ratios.csv')
        cf.insert(0, 'day', day)
        cf.insert(1, 'date', date)
        cf.insert(2, 'animal', animal)
        crossfit_rows.append(cf)
        pairs = pd.read_csv(daydir / 'bipolar_pairs.csv')
        contacts = pd.concat([pairs.ch1, pairs.ch2]).astype(int)
        B = np.zeros((len(pairs), 128))
        for i, r in enumerate(pairs.itertuples(index=False)):
            B[i, int(r.ch1)-1] = 1
            B[i, int(r.ch2)-1] = -1
        montage_rows.append({
            'day': day, 'date': date, 'animal': animal, 'n_pairs': len(pairs),
            'n_unique_contacts': contacts.nunique(), 'max_contact_use': int(contacts.value_counts().max()),
            'incidence_rank': int(np.linalg.matrix_rank(B)),
            'omitted_contacts': ';'.join(map(str, sorted(set(range(1,129))-set(contacts)))),
            'montage_source': pairs.get('montage_source', pd.Series(['unknown'])).iloc[0],
            'known_region_fraction': 0.0,
        })
    return (
        pd.DataFrame(fixed_rows), pd.concat(crossfit_rows, ignore_index=True),
        pd.DataFrame(qc_rows), pd.DataFrame(montage_rows),
    )


def ratio_col(metric: str, state: str = 'deep_anesthesia') -> str:
    return f'{metric}_{state}_over_awake'


def hierarchical_summary(df: pd.DataFrame, col: str, direction: str, n_boot: int = 100000, seed: int = 20260816) -> dict:
    work = df[['animal', 'heldout_date', 'k', col]].dropna().copy()
    work = work[work[col] > 0]
    work['log_ratio'] = np.log(work[col])
    animal_means = work.groupby('animal').log_ratio.mean()
    vals = animal_means.to_numpy(float)
    grand = float(vals.mean())
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(vals), size=(n_boot, len(vals)))
    boots = vals[idx].mean(axis=1)
    lo, hi = np.quantile(boots, [.025, .975])
    if len(vals) > 1:
        sem = stats.sem(vals)
        tcrit = stats.t.ppf(.975, len(vals)-1)
        tlo, thi = grand - tcrit*sem, grand + tcrit*sem
    else:
        tlo = thi = np.nan
    loo = [float(np.delete(vals, i).mean()) for i in range(len(vals))] if len(vals) > 1 else [grand]
    return {
        'n_days': len(work), 'n_animals': len(animal_means),
        'geomean_ratio': float(np.exp(grand)),
        'animal_boot_ci_low': float(np.exp(lo)), 'animal_boot_ci_high': float(np.exp(hi)),
        'animal_t_ci_low': float(np.exp(tlo)), 'animal_t_ci_high': float(np.exp(thi)),
        'day_direction_count': int((work[col] > 1).sum() if direction == 'increase' else (work[col] < 1).sum()),
        'animal_direction_count': int((animal_means > 0).sum() if direction == 'increase' else (animal_means < 0).sum()),
        'loo_min': float(np.exp(min(loo))), 'loo_max': float(np.exp(max(loo))),
        'animal_ratios_json': json.dumps({a: float(np.exp(v)) for a, v in animal_means.items()}),
    }


def parse_set(s) -> frozenset[int]:
    return frozenset(int(x) for x in str(s).split(';') if str(x) not in {'nan', ''})


def load_maps(asset_zip: Path) -> dict:
    paths = {
        'George': '20110112KTMD_Anesthesia+and+Sleep_George_Toru+Yanagawa_mat_2Dimg/GeorgeMap.mat',
        'Kin2': '20110513KTMD_Anesthesia+and+Sleep_Kin2_Toru+Yanagawa_mat_2Dimg/Kin2Map.mat',
        'Su': '20110523KTMD_Anesthesia+and+Sleep_Su_Toru+Yanagawa_mat_2Dimg/SuMap.mat',
        'Chibi': '20110621KTMD_Anesthesia+and+Sleep_Chibi_Toru+Yanagawa_mat_2Dimg/ChibiMap.mat',
    }
    out = {}
    with zipfile.ZipFile(asset_zip) as zf:
        for a, p in paths.items():
            d = loadmat(io.BytesIO(zf.read(p)))
            out[a] = {
                'I': np.asarray(d['I']),
                'X': np.asarray(d['X']).reshape(-1).astype(float),
                'Y': np.asarray(d['Y']).reshape(-1).astype(float),
            }
    return out


def component_boxes(img: np.ndarray) -> dict:
    gray = img.mean(axis=2)
    mask = gray < 248
    lab, _ = label(mask)
    comps = []
    for i, sl in enumerate(find_objects(lab), start=1):
        if sl is None:
            continue
        area = int((lab[sl] == i).sum())
        if area > 5000:
            y0, y1 = sl[0].start, sl[0].stop
            x0, x1 = sl[1].start, sl[1].stop
            comps.append({'area': area, 'x0': x0, 'x1': x1, 'y0': y0, 'y1': y1, 'yc': (y0+y1)/2})
    comps = sorted(sorted(comps, key=lambda c: c['area'], reverse=True)[:4], key=lambda c: c['yc'])
    return {'medial': comps[0], 'lateral': comps[-1]}


def make_candidate_frequency(candidates: pd.DataFrame, corrected_montage: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    pair_lookup = {}
    for _, r in corrected_montage.iterrows():
        pair_lookup[(str(r.animal), str(r.pair_id))] = (int(r.ch1), int(r.ch2))
    for animal, adf in candidates.groupby('animal'):
        nfolds = adf.heldout_date.astype(str).nunique()
        pair_ids = sorted({p for nodes in adf.nodes.dropna().astype(str) for p in nodes.split(';') if p})
        for pair in pair_ids:
            rec = {'animal': animal, 'pair_id': pair, 'n_lodo_folds': nfolds}
            vals = []
            for k in (3, 4, 5):
                sub = adf[adf.k == k]
                count = sum(pair in str(x).split(';') for x in sub.nodes)
                freq = count / max(1, nfolds)
                rec[f'frequency_k{k}'] = freq
                vals.append(freq)
            rec['balanced_frequency'] = float(np.mean(vals))
            rec['raw_selection_count'] = int(sum(sum(pair in str(x).split(';') for x in adf[adf.k == k].nodes) for k in (3,4,5)))
            if (animal, pair) in pair_lookup:
                rec['ch1'], rec['ch2'] = pair_lookup[(animal, pair)]
            else:
                m = re.fullmatch(r'BP(\d+)-(\d+)', pair)
                rec['ch1'], rec['ch2'] = (int(m.group(1)), int(m.group(2))) if m else (np.nan, np.nan)
            rows.append(rec)
    freq = pd.DataFrame(rows)
    contacts = []
    for _, r in freq.iterrows():
        for endpoint in ('ch1', 'ch2'):
            if pd.notna(r[endpoint]):
                contacts.append({
                    'animal': r.animal, 'electrode': int(r[endpoint]),
                    'pair_id': r.pair_id, 'pair_balanced_frequency': r.balanced_frequency,
                })
    c = pd.DataFrame(contacts)
    csum = c.groupby(['animal', 'electrode'], as_index=False).pair_balanced_frequency.sum().rename(columns={'pair_balanced_frequency': 'contact_score'})
    return freq, csum


def plot_main_figures(
    output_root: Path, hier: pd.DataFrame, crossfit: pd.DataFrame,
    blocktraj: pd.DataFrame, recovery: pd.DataFrame, slowwave: pd.DataFrame,
    old_new: pd.DataFrame, candidates: pd.DataFrame, freq: pd.DataFrame,
    contacts: pd.DataFrame, assets: Path,
) -> None:
    F = output_root / 'figures'
    F.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False})

    # Updated cross-day effect forest.
    labels = {'Q':'Mediation strength Q','Cspec':'Capacity envelope','Aspec':'Alignment','Deff_frac':'Effective-rank fraction','Gpair':'Routed breadth','Oorg':'Organization','top_share':'Top-mode share','WMI':'Raw WMI'}
    order = list(labels)
    fig, ax = plt.subplots(figsize=(9, 6.5), dpi=220)
    ybase = np.arange(len(order))[::-1]
    offsets = {3:-.20, 4:0, 5:.20}
    for k in (3,4,5):
        g = hier[hier.k.eq(k)].set_index('metric').loc[order]
        x = g.geomean_ratio.to_numpy()*100
        lo = g.animal_boot_ci_low.to_numpy()*100
        hi = g.animal_boot_ci_high.to_numpy()*100
        ax.errorbar(x, ybase+offsets[k], xerr=[x-lo, hi-x], fmt='o', capsize=3, label=f'k={k}')
    ax.axvline(100, color='black', lw=1)
    ax.set_yticks(ybase, [labels[m] for m in order])
    ax.set_xlabel('Deep / awake ratio (animal-balanced geometric mean, %)')
    ax.set_xscale('log')
    ax.legend()
    ax.set_title('Corrected official-map montage: same-animal cross-day transfer')
    fig.tight_layout()
    fig.savefig(F/'figure_updated_crossday_transfer.png', bbox_inches='tight')
    plt.close(fig)

    # Cross-fit directional consistency.
    drows = []
    for m, direction in EXPECTED_DIRECTION.items():
        col = f'{m}_deep_anesthesia_over_heldout'
        ok = crossfit[col] > 1 if direction == 'increase' else crossfit[col] < 1
        drows.append({'metric': m, 'count': int(ok.sum()), 'total': int(ok.notna().sum()), 'fraction': float(ok.mean())})
    d = pd.DataFrame(drows)
    fig, ax = plt.subplots(figsize=(9, 5), dpi=220)
    x = np.arange(len(d))
    bars = ax.bar(x, d.fraction)
    ax.axhline(.5, color='black', ls='--', lw=1)
    ax.set_ylim(0, 1.08)
    ax.set_xticks(x, d.metric, rotation=25, ha='right')
    ax.set_ylabel('Fraction of 132 held-out comparisons')
    ax.set_title('Corrected montage: within-day selection-bias-safe consistency')
    for b, r in zip(bars, d.itertuples()):
        ax.text(b.get_x()+b.get_width()/2, b.get_height()+.02, f'{r.count}/{r.total}', ha='center', fontsize=8)
    fig.tight_layout()
    fig.savefig(F/'figure_updated_crossfit_directional_consistency.png', bbox_inches='tight')
    plt.close(fig)

    # Montage effect sensitivity for Kin2/Su.
    show = ['Q','Aspec','Deff_frac','Gpair','Oorg','WMI']
    fig, axs = plt.subplots(2, 3, figsize=(13, 8), dpi=190)
    for ax, m in zip(axs.ravel(), show):
        for (animal, source), g in old_new.groupby(['animal','source']):
            g = g.sort_values('k')
            style = '-' if source == 'corrected_official_map' else '--'
            ax.plot(g.k, g[m], marker='o', ls=style, label=f'{animal} {source}')
        ax.axhline(1, color='black', lw=.8)
        ax.set_title(m)
        ax.set_xticks([3,4,5])
        ax.grid(alpha=.2)
    axs[0,0].legend(fontsize=6)
    fig.suptitle('Working versus corrected montage: animal-level LODO effects')
    fig.tight_layout(rect=[0,0,1,.95])
    fig.savefig(F/'figure_working_vs_corrected_montage_effects.png', bbox_inches='tight')
    plt.close(fig)

    # Animal-balanced blockwise trajectories.
    states = ['eyes_open','eyes_closed','deep_anesthesia','recovery_eyes_closed','recovery_eyes_open']
    state_labels = ['Awake\nEO','Awake\nEC','Deep','Recovery\nEC','Recovery\nEO']
    metrics = ['Aspec','Deff_frac','Gpair','Oorg','top_share']
    titles = ['Alignment','Effective-rank fraction','Routed breadth','Gain-free organization','Leading-mode share']
    fig, axs = plt.subplots(2, 3, figsize=(14, 8), dpi=180)
    axs = axs.ravel()
    for ax, m, title in zip(axs[:5], metrics, titles):
        xpos = 0
        xticks, xlabels = [], []
        animal_curves = {a: [] for a in sorted(blocktraj.animal.unique())}
        animal_x = {a: [] for a in animal_curves}
        mean_x, mean_y, mean_se = [], [], []
        for state, slabel in zip(states, state_labels):
            sg = blocktraj[blocktraj.state.eq(state)]
            if sg.empty:
                xpos += 1
                continue
            for block in sorted(sg.block.unique()):
                bg = sg[sg.block.eq(block)]
                vals = []
                for animal, ag in bg.groupby('animal'):
                    # days and k values receive equal geometric weight within animal.
                    v = gmean(ag[f'{m}_over_awake'])
                    animal_curves[animal].append(v)
                    animal_x[animal].append(xpos)
                    if np.isfinite(v) and v > 0:
                        vals.append(np.log(v))
                if vals:
                    mean_x.append(xpos)
                    mean_y.append(float(np.exp(np.mean(vals))))
                    mean_se.append(float(np.exp(np.std(vals, ddof=1)/np.sqrt(len(vals)))) if len(vals)>1 else 1.0)
                xpos += 1
            xticks.append(xpos - 3.5)
            xlabels.append(slabel)
            xpos += 1
        for animal in animal_curves:
            ax.plot(animal_x[animal], animal_curves[animal], alpha=.45, lw=1)
        ax.plot(mean_x, mean_y, color='black', lw=2.4)
        # log-scale SE converted to multiplicative band.
        se = np.asarray(mean_se)
        y = np.asarray(mean_y)
        ax.fill_between(mean_x, y/np.maximum(se,1e-9), y*np.maximum(se,1e-9), color='black', alpha=.15)
        ax.axhline(1, color='gray', ls='--', lw=.8)
        ax.set_xticks(xticks, xlabels)
        ax.set_title(title)
        ax.set_ylabel('Ratio to same-day awake')
        ax.grid(alpha=.15)
    axs[5].axis('off')
    fig.suptitle('Corrected montage: animal-balanced blockwise trajectories')
    fig.tight_layout(rect=[0,0,1,.95])
    fig.savefig(F/'figure_updated_blockwise_trajectories.png', bbox_inches='tight')
    plt.close(fig)

    # Recovery summary.
    fig, axs = plt.subplots(1, 5, figsize=(16, 4), dpi=200)
    for ax, m in zip(axs, ['Q','Aspec','Deff_frac','Gpair','Oorg']):
        for j, state in enumerate(['deep_anesthesia','recovery_eyes_closed','recovery_eyes_open']):
            r = recovery[(recovery.metric.eq(m)) & (recovery.state.eq(state))].sort_values('k')
            ax.plot(r.k + (j-1)*.04, r.geomean_ratio, marker='o', label=state.replace('_',' '))
            ax.fill_between(r.k + (j-1)*.04, r.ci_low, r.ci_high, alpha=.12)
        ax.axhline(1, color='black', ls='--', lw=.8)
        ax.set_title(m)
        ax.set_xticks([3,4,5])
    axs[0].set_ylabel('Ratio to awake')
    axs[-1].legend(fontsize=6)
    fig.suptitle('Corrected montage: component-specific recovery')
    fig.tight_layout(rect=[0,0,1,.94])
    fig.savefig(F/'figure_updated_recovery.png', bbox_inches='tight')
    plt.close(fig)

    # Slow-wave controls Q and Oorg.
    for metric in ['Q','Oorg']:
        transforms = ['broadband','state_zscore','highpass4','delta','remove_pc1']
        fig, ax = plt.subplots(figsize=(9, 5), dpi=200)
        x = np.arange(len(transforms))
        width = .22
        for i, k in enumerate((3,4,5)):
            vals = []
            for tr in transforms:
                g = slowwave[(slowwave.k.eq(k)) & (slowwave['transform'].eq(tr))]
                # animal-balanced geometric mean
                animal = g.groupby('animal')[f'{metric}_ratio'].apply(gmean)
                vals.append(gmean(animal))
            bars = ax.bar(x+(i-1)*width, vals, width, label=f'k={k}')
            for b, v in zip(bars, vals):
                ax.text(b.get_x()+b.get_width()/2, v+.025, f'{v:.2f}', ha='center', fontsize=7)
        ax.axhline(1, color='black', ls='--', lw=.8)
        ax.set_xticks(x, ['Broadband','State z-score','>4 Hz','0.5–4 Hz','Remove state PC1'], rotation=20, ha='right')
        ax.set_ylabel(f'Deep / awake {metric} ratio')
        ax.set_title(f'Corrected montage: {metric} under slow-wave controls')
        ax.legend()
        fig.tight_layout()
        fig.savefig(F/f'figure_updated_slowwave_{metric}.png', bbox_inches='tight')
        plt.close(fig)

    # Official maps and common-template summary.
    maps = load_maps(assets/'2DMap.zip')
    corrected = pd.read_csv(assets/'corrected_local_montages.csv')
    boxes = {a: component_boxes(d['I']) for a,d in maps.items()}
    ref = 'Chibi'
    ref_boxes = boxes[ref]
    coord_rows = []
    for animal, d in maps.items():
        scores = contacts[contacts.animal.eq(animal)].set_index('electrode').contact_score.to_dict()
        total = sum(scores.values()) or 1.0
        for electrode, score in scores.items():
            x0, y0 = d['X'][electrode-1], d['Y'][electrode-1]
            # Official maps show separate medial panels only for George and Chibi.
            panel = 'medial' if animal in {'George','Chibi'} and (52 <= electrode <= 64 or 121 <= electrode <= 128) else 'lateral'
            src, dst = boxes[animal][panel], ref_boxes[panel]
            tx = dst['x0'] + (x0-src['x0']) * (dst['x1']-dst['x0']) / max(1, src['x1']-src['x0'])
            ty = dst['y0'] + (y0-src['y0']) * (dst['y1']-dst['y0']) / max(1, src['y1']-src['y0'])
            coord_rows.append({'animal':animal,'electrode':electrode,'panel':panel,'template_x':tx,'template_y':ty,'score':score,'normalized_score':score/total})
    aligned = pd.DataFrame(coord_rows)
    aligned.to_csv(output_root/'tables/updated_panel_registered_contact_frequency.csv', index=False)
    img = maps[ref]['I']
    H, W = img.shape[:2]
    gray = img.mean(axis=2, keepdims=True)
    bg = np.repeat(.82*255 + .18*gray, 3, axis=2).astype(np.uint8)
    grid = np.zeros((H,W), float)
    for r in aligned.itertuples(index=False):
        x0, y0 = int(round(r.template_x)), int(round(r.template_y))
        if 0 <= x0 < W and 0 <= y0 < H:
            grid[y0,x0] += r.normalized_score / 4
    heat = gaussian_filter(grid, sigma=18)
    heat /= heat.max() if heat.max() > 0 else 1
    fig, ax = plt.subplots(figsize=(8.4,10), dpi=220)
    ax.imshow(bg)
    rgba = plt.cm.autumn(heat)
    rgba[...,3] = np.clip(heat*.98,0,.98)
    ax.imshow(rgba)
    mx = aligned.normalized_score.max() or 1
    sc = ax.scatter(aligned.template_x, aligned.template_y, c=aligned.normalized_score,
                    s=18+220*aligned.normalized_score/mx, cmap='autumn', vmin=0, vmax=mx,
                    edgecolors='black', linewidths=.35)
    ax.set_title('Corrected official-map montage\nAll-animal recurrent candidate contacts')
    ax.axis('off')
    cb = fig.colorbar(sc, ax=ax, fraction=.035, pad=.02)
    cb.set_label('Within-animal normalized recurrence')
    fig.tight_layout()
    fig.savefig(F/'figure_updated_allanimal_official_template_heatmap.png', bbox_inches='tight')
    plt.close(fig)

    fig, axes = plt.subplots(2,2,figsize=(12,14),dpi=180)
    for ax, animal in zip(axes.ravel(), ['George','Chibi','Kin2','Su']):
        d = maps[animal]
        gray = d['I'].mean(axis=2,keepdims=True)
        bgi = np.repeat(.88*255+.12*gray,3,axis=2).astype(np.uint8)
        ax.imshow(bgi)
        dd = contacts[contacts.animal.eq(animal)].merge(pd.DataFrame({'electrode':np.arange(1,129),'x':d['X'],'y':d['Y']}), on='electrode')
        mx = dd.contact_score.max() or 1
        ax.scatter(dd.x, dd.y, c=dd.contact_score, s=30+260*dd.contact_score/mx, cmap='autumn', edgecolors='black', linewidths=.4)
        for r in dd.sort_values('contact_score',ascending=False).head(10).itertuples(index=False):
            ax.text(r.x+5,r.y-5,str(int(r.electrode)),fontsize=6.5,weight='bold',bbox=dict(facecolor='white',alpha=.55,edgecolor='none',pad=.5))
        ax.set_title(animal)
        ax.axis('off')
    fig.suptitle('Corrected recurrent candidates on subject-specific official maps')
    fig.tight_layout(rect=[0,0,1,.97])
    fig.savefig(F/'figure_updated_subject_specific_official_maps.png', bbox_inches='tight')
    plt.close(fig)


def make_manuscript_materials(
    output_root: Path, hier: pd.DataFrame, crossfit: pd.DataFrame,
    recovery: pd.DataFrame, old_new: pd.DataFrame, freq: pd.DataFrame,
    qc: pd.DataFrame, montage_qc: pd.DataFrame,
) -> None:
    R = output_root/'manuscript_materials'
    R.mkdir(parents=True, exist_ok=True)
    # Main numeric table in both CSV and LaTeX-ready text.
    wide = hier.pivot(index='metric', columns='k', values='geomean_ratio').loc[METRICS]
    wide.to_csv(R/'updated_table_lodo_point_estimates.csv')
    lines = ['# Manuscript-ready result patch', '', '## Corrected official-map montage analysis', '']
    lines.append('All three Kin2 days and all three Su days were rerun using a deterministic, no-contact-reuse, 64-pair geometry-aware montage derived independently from each animal’s official NeuroTycho X/Y electrode map. George and Chibi retain their prior map-grounded independent montages.')
    lines.append('')
    lines.append('### Updated animal-balanced LODO ratios')
    for k in (3,4,5):
        g = hier[hier.k.eq(k)].set_index('metric')
        vals = ', '.join(f'{m}={g.loc[m,"geomean_ratio"]:.3f} [{g.loc[m,"animal_boot_ci_low"]:.3f}, {g.loc[m,"animal_boot_ci_high"]:.3f}]' for m in METRICS)
        lines.append(f'- k={k}: {vals}')
    lines.append('')
    lines.append('### Updated within-day held-out directional consistency')
    for m,direction in EXPECTED_DIRECTION.items():
        col=f'{m}_deep_anesthesia_over_heldout'
        ok = crossfit[col]>1 if direction=='increase' else crossfit[col]<1
        lines.append(f'- {m}: {int(ok.sum())}/{int(ok.notna().sum())} comparisons in the prespecified {direction} direction.')
    lines.append('')
    lines.append('### Montage statement for Methods')
    lines.append('The corrected Kin2 and Su montages each contain 64 independent bipolar variables and use every one of the 128 contacts exactly once. The earlier statement that Kin2 necessarily has only 63 local variables should be removed: that restriction arose from transferring the separate-medial-panel layout of another map entry to Kin2. In the official Kin2 map used here, all 128 contacts are displayed on the lateral layout, and a 64-pair local perfect matching exists.')
    lines.append('')
    lines.append('### Figure replacement')
    lines.append('- Replace the provisional Kin2/Su localization panel with `figure_updated_subject_specific_official_maps.png`.')
    lines.append('- Replace the pooled display with `figure_updated_allanimal_official_template_heatmap.png`.')
    lines.append('- Replace the main cross-day state-effect figure with `figure_updated_crossday_transfer.png`.')
    lines.append('- Replace the cross-fit, recovery, trajectory, and slow-wave figures with their `figure_updated_*` counterparts.')
    lines.append('')
    lines.append('### Claim wording')
    lines.append('The corrected multiday rerun removes the “provisional pending complete reruns” qualification. Effect magnitudes remain montage dependent and should be reported explicitly through the working-versus-corrected comparison rather than described as invariant. The defensible claim is that the multicomponent gain–geometry dissociation is reproduced after geometry-aware rematching, while exact effect sizes and selected channels depend on the observation montage.')
    (R/'MANUSCRIPT_RESULTS_PATCH.md').write_text('\n'.join(lines), encoding='utf-8')

    captions = '''# Updated figure captions

## Corrected same-animal cross-day transfer
Deep/awake ratios are shown for candidates selected from the other days of the same animal after replacing Kin2 and Su with deterministic official-map local montages. Point estimates are equal-animal geometric means; intervals are descriptive animal-cluster bootstrap intervals.

## Corrected subject-specific localization
Bubble size and color encode balanced same-animal LODO candidate recurrence averaged across k=3–5. All four panels now use completed montage-specific reruns; no panel is provisional.

## Corrected common-template display
Contact recurrence from the four animals is normalized within animal and projected panel-wise onto the Chibi official NeuroTycho map for visualization. This is a display normalization, not stereotactic registration.

## Montage sensitivity
Working and corrected LODO estimates are compared for Kin2 and Su. Directional concordance of the principal geometry components is reported together with the observed changes in effect magnitude.
'''
    (R/'UPDATED_FIGURE_CAPTIONS.md').write_text(captions, encoding='utf-8')

    matrix = pd.DataFrame([
        ['Abstract','Update empirical sentence using corrected all-day ratios and remove provisional wording.'],
        ['Section 9.1','State the final montage counts: George/Chibi as before; Kin2=64 and Su=64 in the official-map corrected rerun.'],
        ['Section 9.2','Replace Q, Cspec, Aspec, Deff/k, Gpair, Oorg, top-share and WMI values with the new hierarchical table.'],
        ['Section 9.3','Replace candidate localization frequencies and official-map figure.'],
        ['Section 9.4','Replace blockwise trajectory values and figure.'],
        ['Appendix I.1','Remove the K2/Kin2 medial-panel conflation and document the deterministic matching algorithm.'],
        ['Appendix I.3–I.5','Replace within-day, LODO, candidate-stability, QC and spectral tables.'],
        ['Appendix J.1','Replace slow-wave Q/Oorg summaries because selected candidates and state coordinates changed.'],
        ['Appendix J.2','Replace the one-day validation narrative with the completed six-day rerun and montage-sensitivity analysis.'],
        ['Appendix J.3','Replace recovery ratios and intervals.'],
        ['Figure 23 / localization','Remove all provisional daggers and captions.'],
        ['Table 5/6','Replace all LODO point estimates and intervals.'],
    ], columns=['manuscript_location','required_change'])
    matrix.to_csv(R/'MANUSCRIPT_UPDATE_MATRIX.csv', index=False)

    # Machine-readable bundle for the writing thread.
    payload = {
        'analysis_complete': True,
        'corrected_animals': ['Kin2','Su'],
        'corrected_days': [d for _,d in TARGETS],
        'montage_pairs': {'Kin2':64,'Su':64},
        'hierarchical_results': hier.to_dict(orient='records'),
        'montage_qc': montage_qc.to_dict(orient='records'),
        'model_qc': qc.to_dict(orient='records'),
        'top_pairs': freq.sort_values(['animal','balanced_frequency'],ascending=[True,False]).groupby('animal').head(10).to_dict(orient='records'),
    }
    (R/'RESULTS_FOR_WRITING_THREAD.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')


def assemble_summary(output_root: Path, assets: Path, daypaths: dict, crossdirs: dict) -> None:
    T = output_root/'tables'
    T.mkdir(parents=True, exist_ok=True)
    expected_index=load_expected(assets)
    provenance_rows=[]
    for animal,date in TARGETS:
        day=daypaths[(animal,date)]
        prov_path=day/'RAW_ARCHIVE_PROVENANCE.json'
        if not prov_path.exists(): raise RuntimeError(f'Missing raw provenance: {prov_path}')
        record=json.loads(prov_path.read_text(encoding='utf-8'))
        expected_rec=expected_index[target_filename(animal,date)]
        validate_raw_provenance(record,expected_rec,animal,date)
        day_summary=json.loads((day/'summary.json').read_text(encoding='utf-8'))
        if str(day_summary.get('animal'))!=animal or str(day_summary.get('date'))!=date:
            raise RuntimeError(f'{animal} {date}: summary/provenance identity mismatch')
        provenance_rows.append({'animal':animal,'date':date,
            'archive_name':record['expected_archive_name'],
            'archive_size_bytes':int(record['actual_archive_size_bytes']),
            'archive_sha256':record['actual_archive_sha256'],
            'manifest_sha256':record['manifest_original_sha256'],
            'part_count':int(record['part_count']),
            'verified_part_count':int(record['verified_part_count']),
            'dataset_root_name':record['dataset_root_name'],
            'pipeline_version':record['pipeline_version']})
    provenance_table=pd.DataFrame(provenance_rows)
    provenance_table.to_csv(T/'RAW_ARCHIVE_PROVENANCE_ALL_SIX_DAYS.csv',index=False)
    # New Kin2/Su tables.
    new_fixed, new_crossfit, new_qc, new_montage_qc = make_same_day_fixed(daypaths)
    new_lodo, new_cands, new_sigs = [], [], []
    for animal in ('Kin2','Su'):
        r = pd.read_csv(crossdirs[animal]/'lodo_ratios.csv'); r.insert(0,'animal',animal); new_lodo.append(r)
        c = pd.read_csv(crossdirs[animal]/'lodo_candidates.csv'); c.insert(0,'animal',animal); new_cands.append(c)
        s = pd.read_csv(crossdirs[animal]/'lodo_signatures.csv'); s.insert(0,'animal',animal); new_sigs.append(s)
    new_lodo = pd.concat(new_lodo, ignore_index=True)
    new_cands = pd.concat(new_cands, ignore_index=True)
    new_sigs = pd.concat(new_sigs, ignore_index=True)

    # Merge unchanged George/Chibi rows from the established analysis.
    old_lodo = pd.read_csv(assets/'old_lodo_ratios.csv')
    old_cands = pd.read_csv(assets/'old_lodo_candidates.csv')
    old_sigs = pd.read_csv(assets/'old_lodo_signatures.csv')
    old_cross = pd.read_csv(assets/'old_within_day_crossfit.csv')
    old_fixed = pd.read_csv(assets/'old_same_day_fixed.csv')
    old_qc = pd.read_csv(assets/'old_day_model_qc.csv')
    old_mqc = pd.read_csv(assets/'old_montage_qc.csv')
    keep = ['George','Chibi']
    lodo = pd.concat([old_lodo[old_lodo.animal.isin(keep)], new_lodo], ignore_index=True, sort=False)
    cands = pd.concat([old_cands[old_cands.animal.isin(keep)], new_cands], ignore_index=True, sort=False)
    sigs = pd.concat([old_sigs[old_sigs.animal.isin(keep)], new_sigs], ignore_index=True, sort=False)
    crossfit = pd.concat([old_cross[old_cross.animal.isin(keep)], new_crossfit], ignore_index=True, sort=False)
    fixed = pd.concat([old_fixed[old_fixed.animal.isin(keep)], new_fixed], ignore_index=True, sort=False)
    qc = pd.concat([old_qc[old_qc.animal.isin(keep)], new_qc], ignore_index=True, sort=False)
    montage_qc = pd.concat([old_mqc[old_mqc.animal.isin(keep)], new_montage_qc], ignore_index=True, sort=False)
    lodo.to_csv(T/'updated_same_animal_leave_one_day_out_ratios.csv', index=False)
    cands.to_csv(T/'updated_same_animal_leave_one_day_out_candidates.csv', index=False)
    sigs.to_csv(T/'updated_same_animal_leave_one_day_out_signatures.csv', index=False)
    crossfit.to_csv(T/'updated_within_day_awake_crossfit_ratios_11days.csv', index=False)
    fixed.to_csv(T/'updated_same_day_full_awake_fixed_ratios_11days.csv', index=False)
    qc.to_csv(T/'updated_day_model_qc_11days.csv', index=False)
    montage_qc.to_csv(T/'updated_montage_qc_11days.csv', index=False)

    # Trajectories, slow-wave controls, and spectral diagnostics.
    new_traj = compute_block_trajectories(daypaths, crossdirs)
    old_traj = pd.read_csv(assets/'old_lodo_blockwise_trajectories.csv')
    blocktraj = pd.concat([old_traj[old_traj.animal.isin(keep)], new_traj], ignore_index=True, sort=False)
    blocktraj.to_csv(T/'updated_lodo_blockwise_trajectories.csv', index=False)
    new_slow = compute_slowwave_controls(daypaths, crossdirs)
    old_slow = pd.read_csv(assets/'old_slowwave_controls.csv')
    slowwave = pd.concat([old_slow[old_slow.animal.isin(keep)], new_slow], ignore_index=True, sort=False)
    slowwave.to_csv(T/'updated_slowwave_transform_controls_lodo_candidates.csv', index=False)
    new_spec = compute_block_spectral(daypaths)
    old_spec = pd.read_csv(assets/'old_block_spectral_metrics.csv')
    spectral = pd.concat([old_spec[old_spec.animal.isin(keep)], new_spec], ignore_index=True, sort=False)
    spectral.to_csv(T/'updated_block_spectral_dynamical_metrics.csv', index=False)

    # Hierarchical state effects.
    hrows = []
    for k in (3,4,5):
        sub = lodo[lodo.k.eq(k)]
        for i, m in enumerate(METRICS):
            direction = EXPECTED_DIRECTION[m]
            r = hierarchical_summary(sub, ratio_col(m), direction, seed=20260816+k*100+i)
            hrows.append({'k':k,'metric':m,'state':'deep_anesthesia','expected_direction':direction,**r})
    hier = pd.DataFrame(hrows)
    hier.to_csv(T/'updated_hierarchical_lodo_deep_effects.csv', index=False)

    # Animal-level effects.
    animal_rows = []
    for (animal,k), g in lodo.groupby(['animal','k']):
        rec = {'animal':animal,'k':int(k),'n_days':len(g)}
        for m in METRICS:
            rec[f'{m}_geomean'] = gmean(g[ratio_col(m)])
        animal_rows.append(rec)
    animal_eff = pd.DataFrame(animal_rows)
    animal_eff.to_csv(T/'updated_animal_level_lodo_effects.csv', index=False)

    # Candidate stability.
    stab = []
    for (animal,k), g in cands.groupby(['animal','k']):
        sets = [parse_set(x) for x in g.candidate]
        js = [len(a&b)/len(a|b) for a,b in itertools.combinations(sets,2)]
        union = set().union(*sets)
        inter = set(sets[0])
        for s in sets[1:]: inter &= set(s)
        freqnode = {i:sum(i in s for s in sets)/len(sets) for i in union}
        stab.append({'animal':animal,'k':k,'n_lodo_folds':len(sets),'mean_pairwise_jaccard':float(np.mean(js)) if js else 1.0,
                     'min_pairwise_jaccard':float(np.min(js)) if js else 1.0,'union_size':len(union),'intersection_size':len(inter),
                     'max_node_frequency':max(freqnode.values()) if freqnode else np.nan,'n_nodes_frequency_ge_half':sum(v>=.5 for v in freqnode.values()),
                     'node_frequencies_json':json.dumps(freqnode,sort_keys=True)})
    pd.DataFrame(stab).to_csv(T/'updated_cross_day_candidate_stability.csv', index=False)

    # Recovery estimates using animal-cluster bootstrap.
    recovery_rows = []
    for k in (3,4,5):
        sub = lodo[lodo.k.eq(k)]
        for m in METRICS:
            for state in ('deep_anesthesia','recovery_eyes_closed','recovery_eyes_open'):
                col = ratio_col(m,state)
                if col not in sub.columns:
                    continue
                work = sub[['animal','heldout_date','k',col]].dropna()
                if work.empty:
                    continue
                direction = EXPECTED_DIRECTION[m]
                hs = hierarchical_summary(work, col, direction, n_boot=20000, seed=20260816+k+METRICS.index(m)*17+len(state))
                recovery_rows.append({'k':k,'metric':m,'state':state,'geomean_ratio':hs['geomean_ratio'],'ci_low':hs['animal_boot_ci_low'],'ci_high':hs['animal_boot_ci_high'],'n_days':hs['n_days'],'n_animals':hs['n_animals']})
    recovery = pd.DataFrame(recovery_rows)
    recovery.to_csv(T/'updated_recovery_summary.csv', index=False)

    # Working versus corrected Kin2/Su animal-level LODO effects.
    old_ks = old_lodo[old_lodo.animal.isin(['Kin2','Su'])]
    comp = []
    for source, df in [('working_montage',old_ks),('corrected_official_map',new_lodo)]:
        for (animal,k), g in df.groupby(['animal','k']):
            rec={'source':source,'animal':animal,'k':int(k)}
            for m in METRICS: rec[m]=gmean(g[ratio_col(m)])
            comp.append(rec)
    old_new = pd.DataFrame(comp)
    old_new.to_csv(T/'working_vs_corrected_kin2_su_lodo_effects.csv', index=False)

    # Candidate recurrence and localization.
    corrected = pd.read_csv(assets/'corrected_local_montages.csv')
    freq, contacts = make_candidate_frequency(cands, corrected)
    freq.to_csv(T/'updated_pair_frequency.csv', index=False)
    contacts.to_csv(T/'updated_contact_frequency.csv', index=False)
    freq.sort_values(['animal','balanced_frequency'],ascending=[True,False]).groupby('animal').head(12).to_csv(T/'updated_top_pairs_by_animal.csv', index=False)

    # Directional summary table.
    drows=[]
    for m,direction in EXPECTED_DIRECTION.items():
        col=f'{m}_deep_anesthesia_over_heldout'
        ok=crossfit[col]>1 if direction=='increase' else crossfit[col]<1
        drows.append({'metric':m,'expected_direction':direction,'count':int(ok.sum()),'total':int(ok.notna().sum()),'fraction':float(ok.mean())})
    pd.DataFrame(drows).to_csv(T/'updated_crossfit_directional_summary.csv', index=False)

    plot_main_figures(output_root,hier,crossfit,blocktraj,recovery,slowwave,old_new,cands,freq,contacts,assets)
    make_manuscript_materials(output_root,hier,crossfit,recovery,old_new,freq,qc,montage_qc)

    # Strict completion audit.
    audit = {
        'target_days_complete': int(new_qc[['animal','date']].drop_duplicates().shape[0]) == 6,
        'updated_total_days': int(qc[['animal','date']].drop_duplicates().shape[0]),
        'updated_crossfit_rows': int(len(crossfit)),
        'updated_lodo_rows': int(len(lodo)),
        'new_corrected_lodo_rows': int(len(new_lodo)),
        'new_corrected_crossfit_rows': int(len(new_crossfit)),
        'montage_all_64_pairs': bool((new_montage_qc.n_pairs==64).all()),
        'montage_all_128_contacts': bool((new_montage_qc.n_unique_contacts==128).all()),
        'montage_full_row_rank': bool((new_montage_qc.incidence_rank==64).all()),
        'montage_no_contact_reuse': bool((new_montage_qc.max_contact_use==1).all()),
        'hierarchical_rows': int(len(hier)),
        'block_trajectory_rows': int(len(blocktraj)),
        'slowwave_rows': int(len(slowwave)),
        'spectral_rows': int(len(spectral)),
        'raw_provenance_rows':int(len(provenance_table)),
        'raw_unique_archive_sha256':int(provenance_table.archive_sha256.nunique()),
        'raw_unique_animal_date':int(provenance_table[['animal','date']].drop_duplicates().shape[0]),
        'raw_target_identities_exact':set(map(tuple,provenance_table[['animal','date']].astype(str).to_records(index=False)))==set(TARGETS),
        'raw_all_archive_manifest_sha_match':bool((provenance_table.archive_sha256==provenance_table.manifest_sha256).all()),
        'raw_all_part_counts_verified':bool((provenance_table.part_count==provenance_table.verified_part_count).all()),
    }
    audit['all_required_complete'] = all([
        audit['target_days_complete'], audit['updated_total_days']==11,
        audit['updated_crossfit_rows']==132, audit['updated_lodo_rows']==33,
        audit['new_corrected_lodo_rows']==18, audit['new_corrected_crossfit_rows']==72,
        audit['montage_all_64_pairs'], audit['montage_all_128_contacts'],
        audit['montage_full_row_rank'], audit['montage_no_contact_reuse'],
        audit['hierarchical_rows']==24,
        audit['raw_provenance_rows']==6,audit['raw_unique_archive_sha256']==6,
        audit['raw_unique_animal_date']==6,audit['raw_target_identities_exact'],
        audit['raw_all_archive_manifest_sha_match'],audit['raw_all_part_counts_verified'],
    ])
    (output_root/'COMPLETION_AUDIT.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    if not audit['all_required_complete']:
        raise RuntimeError(f'Completion audit failed: {audit}')
    summary = {
        'completed': True,
        'analysis': 'Kin2 3 days + Su 3 days corrected official-map montage rerun',
        'corrected_montage_pairs': {'Kin2':64,'Su':64},
        'updated_total_days':11,
        'updated_crossfit_comparisons':132,
        'updated_lodo_day_k_rows':33,
        'output_tables':len(list(T.glob('*.csv'))),
        'output_figures':len(list((output_root/'figures').glob('*'))),
        'raw_data_provenance_locked':True,'verified_distinct_raw_archives':6,
        'provenance_table':'tables/RAW_ARCHIVE_PROVENANCE_ALL_SIX_DAYS.csv',
    }
    (output_root/'FINAL_SUMMARY.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    (output_root/'REAL_RAW_DATA_PROVENANCE_VERIFIED.ok').write_text('six distinct expected raw archives verified by SHA-256\n',encoding='utf-8')
    (output_root/'ALL_ANALYSES_COMPLETE.ok').write_text('complete\n',encoding='utf-8')

    # Compact final ZIP excludes temporary/preprocessed data and raw data.
    zip_path = output_root.parent / (output_root.name + '_DERIVED_RESULTS.zip')
    zip_path.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED) as zf:
        for p in output_root.rglob('*'):
            if not p.is_file(): continue
            rel=p.relative_to(output_root)
            if 'day_results' in rel.parts and p.name not in {'summary.json','model_fit.csv','candidate_sets.csv','candidate_signatures.csv','crossfit_ratios.csv','bipolar_pairs.csv','block_plan.csv','awake_scale_qc.csv','DAY_COMPLETE.ok','RAW_ARCHIVE_PROVENANCE.json'}:
                continue
            zf.write(p,arcname=str(Path(output_root.name)/rel))
    log(f'[DERIVED ZIP] {zip_path}')


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument('--split-root',type=Path,required=True)
    ap.add_argument('--output-root',type=Path,required=True)
    ap.add_argument('--assets',type=Path,required=True)
    ap.add_argument('--work-root',type=Path,default=Path('/content/ktmd_corrected_fullrerun_work'))
    args=ap.parse_args()
    started=time.time()
    expected=load_expected(args.assets)
    split=locate_split_root(args.split_root)
    args.output_root.mkdir(parents=True,exist_ok=True)
    args.work_root.mkdir(parents=True,exist_ok=True)
    daypaths={}
    for animal,date in TARGETS:
        daypaths[(animal,date)] = run_day(args.work_root,args.output_root,split,args.assets,animal,date,expected)
    crossdirs={}
    for animal,dates in DATES_BY_ANIMAL.items():
        crossdirs[animal]=run_crossday(args.work_root,args.output_root,args.assets,animal,[daypaths[(animal,d)] for d in dates])
    assemble_summary(args.output_root,args.assets,daypaths,crossdirs)
    elapsed=(time.time()-started)/60
    log(f'ALL ANALYSES COMPLETE in {elapsed:.1f} min')
    # Clean large transient arrays only after completion and output ZIP creation.
    shutil.rmtree(args.work_root/'raw',ignore_errors=True)
    shutil.rmtree(args.work_root/'archives',ignore_errors=True)


if __name__=='__main__':
    main()
