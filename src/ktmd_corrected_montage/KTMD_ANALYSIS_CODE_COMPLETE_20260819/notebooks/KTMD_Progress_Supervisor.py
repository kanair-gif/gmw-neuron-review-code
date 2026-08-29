#!/usr/bin/env python3
"""Background supervisor and persistent Drive dashboard for the KTMD rerun."""
from __future__ import annotations

import argparse
import csv
import html
import json
import os
import selectors
import signal
import subprocess
import sys
import time
import traceback
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

TARGETS = (
    ("Kin2", "20110513"), ("Kin2", "20110524"), ("Kin2", "20110525"),
    ("Su", "20110523"), ("Su", "20110526"), ("Su", "20110527"),
)
DAY_CHECKS = (
    ("raw archive verified", ("RAW_ARCHIVE_PROVENANCE.json",), .12),
    ("preprocessing complete", ("PREPROCESS_COMPLETE.ok",), .28),
    ("state model fitted", ("model_fit.csv",), .48),
    ("candidate search complete", ("candidate_sets.csv", "candidate_signatures.csv"), .68),
    ("within-day cross-fit complete", ("crossfit_ratios.csv",), .88),
    ("day complete", ("DAY_COMPLETE.ok", "summary.json"), 1.0),
)
GLOBAL_CHECKS = (
    ("corrected LODO", ("*leave_one_day_out*", "*lodo*ratio*"), .20),
    ("11-day within-day table", ("updated_within_day_awake_crossfit_ratios_11days.csv",), .35),
    ("11-day LODO table", ("updated_same_animal_leave_one_day_out_ratios.csv",), .50),
    ("animal-balanced hierarchy", ("updated_hierarchical_lodo_deep_effects.csv",), .65),
    ("recovery and slow-wave controls", ("*recovery*.csv", "*slow*wave*.csv"), .76),
    ("manuscript figures", ("figure_updated_crossday_transfer.png", "figure_updated_subject_specific_official_maps.png"), .86),
    ("writing-thread materials", ("RESULTS_FOR_WRITING_THREAD.json", "MANUSCRIPT_RESULTS_PATCH.md"), .94),
    ("strict final audit", ("ALL_ANALYSES_COMPLETE.ok", "REAL_RAW_DATA_PROVENANCE_VERIFIED.ok"), 1.0),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def atomic_json(path: Path, obj: Any) -> None:
    atomic_write(path, json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def pid_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def read_json(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def read_tail(path: Path, n: int = 50) -> list[str]:
    lines: deque[str] = deque(maxlen=n)
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                lines.append(line.rstrip("\n"))
    except Exception as exc:
        return [f"Could not read log: {exc}"]
    return list(lines)


def all_files(roots: Iterable[Path]) -> list[Path]:
    result: list[Path] = []
    for root in roots:
        if root.exists():
            try:
                result.extend(p for p in root.rglob("*") if p.is_file())
            except Exception:
                pass
    return result


def summary_identity(path: Path) -> tuple[str | None, str | None]:
    if path.name != "summary.json":
        return None, None
    data = read_json(path)
    a, d = data.get("animal"), data.get("date")
    return (str(a) if a is not None else None, str(d) if d is not None else None)


def files_for_day(files: list[Path], animal: str, date: str) -> list[Path]:
    selected = [p for p in files if animal.lower() in str(p).lower() and date in str(p)]
    for summary in (p for p in files if p.name == "summary.json"):
        a, d = summary_identity(summary)
        if a == animal and d == date:
            parent = summary.parent
            selected.extend(p for p in files if p == parent or parent in p.parents)
    return list(dict.fromkeys(selected))


def stage_check(day_files: list[Path], names: tuple[str, ...]) -> bool:
    available = {p.name for p in day_files}
    if names == ("DAY_COMPLETE.ok", "summary.json"):
        return "DAY_COMPLETE.ok" in available or (
            "summary.json" in available and "candidate_sets.csv" in available and "crossfit_ratios.csv" in available
        )
    return all(name in available for name in names)


def day_status(files: list[Path], animal: str, date: str) -> dict[str, Any]:
    subset = files_for_day(files, animal, date)
    fraction, stage = 0.0, "not started"
    checks: dict[str, bool] = {}
    for label, names, value in DAY_CHECKS:
        ok = stage_check(subset, names)
        checks[label] = ok
        if ok and value >= fraction:
            fraction, stage = value, label
    newest = max((p.stat().st_mtime for p in subset), default=0.0)
    return {
        "animal": animal, "date": date, "fraction": fraction,
        "percent": round(100 * fraction, 1), "stage": stage, "checks": checks,
        "file_count": len(subset),
        "last_update_utc": datetime.fromtimestamp(newest, timezone.utc).isoformat(timespec="seconds") if newest else None,
    }


def glob_any(root: Path, pattern: str) -> bool:
    try:
        return root.exists() and any(root.rglob(pattern))
    except Exception:
        return False


def downstream_status(output_root: Path) -> dict[str, Any]:
    fraction, stage = 0.0, "waiting for six day-level analyses"
    checks: dict[str, bool] = {}
    for label, patterns, value in GLOBAL_CHECKS:
        ok = all(glob_any(output_root, pattern) for pattern in patterns)
        checks[label] = ok
        if ok and value >= fraction:
            fraction, stage = value, label
    return {"fraction": fraction, "percent": round(100 * fraction, 1), "stage": stage, "checks": checks}


def progress_snapshot(*, output_root: Path, work_root: Path, progress_dir: Path, log_path: Path,
                      supervisor_pid: int, child_pid: int | None, started_at: float,
                      return_code: int | None, attempt: int, stall_minutes: float) -> dict[str, Any]:
    files = all_files([output_root, work_root])
    days = [day_status(files, a, d) for a, d in TARGETS]
    day_fraction = sum(d["fraction"] for d in days) / len(days)
    downstream = downstream_status(output_root)
    overall = min(1.0, .78 * day_fraction + .22 * downstream["fraction"])
    mtimes = [p.stat().st_mtime for p in files]
    if log_path.exists():
        mtimes.append(log_path.stat().st_mtime)
    last_activity = max(mtimes, default=time.time())
    idle_seconds = max(0.0, time.time() - last_activity)
    running = pid_alive(child_pid) if return_code is None else False
    marker = (output_root / "ALL_ANALYSES_COMPLETE.ok").exists()
    if return_code is None and running:
        state = "running"
    elif return_code == 0 and marker:
        state = "complete"
    elif return_code == 0:
        state = "finished_incomplete"
    elif return_code is None:
        state = "stopped_or_stale"
    else:
        state = "failed"
    tail = read_tail(log_path)
    current = next((line for line in reversed(tail) if line.strip() and "[HEARTBEAT]" not in line), "No pipeline console output yet")
    return {
        "updated_utc": utc_now(), "state": state, "attempt": attempt,
        "supervisor_pid": supervisor_pid, "pipeline_pid": child_pid,
        "pipeline_pid_alive": running, "return_code": return_code,
        "started_utc": datetime.fromtimestamp(started_at, timezone.utc).isoformat(timespec="seconds"),
        "elapsed_minutes": round((time.time() - started_at) / 60, 1),
        "overall_percent": round(100 * overall, 1),
        "completed_days": sum(d["fraction"] >= 1.0 for d in days), "target_days": len(days),
        "current_message": current[-800:],
        "last_activity_utc": datetime.fromtimestamp(last_activity, timezone.utc).isoformat(timespec="seconds"),
        "idle_minutes": round(idle_seconds / 60, 1),
        "stall_warning": bool(running and idle_seconds > stall_minutes * 60),
        "days": days, "downstream": downstream,
        "paths": {"output_root": str(output_root), "work_root": str(work_root),
                  "progress_dir": str(progress_dir), "console_log": str(log_path)},
        "log_tail": tail,
    }


def publish(progress_dir: Path, data: dict[str, Any], refresh_seconds: int) -> None:
    progress_dir.mkdir(parents=True, exist_ok=True)
    atomic_json(progress_dir / "progress.json", data)
    csv_tmp = progress_dir / "progress.csv.tmp"
    with csv_tmp.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["animal", "date", "percent", "stage", "file_count", "last_update_utc"])
        writer.writeheader()
        for row in data["days"]:
            writer.writerow({key: row.get(key) for key in writer.fieldnames})
    os.replace(csv_tmp, progress_dir / "progress.csv")

    md = [
        "# KTMD corrected-montage rerun progress", "",
        f"- Updated: **{data['updated_utc']}**", f"- State: **{data['state']}**",
        f"- Overall: **{data['overall_percent']:.1f}%**",
        f"- Completed days: **{data['completed_days']}/{data['target_days']}**",
        f"- Elapsed: **{data['elapsed_minutes']:.1f} min**",
        f"- Last activity: **{data['last_activity_utc']}** ({data['idle_minutes']:.1f} min ago)",
        f"- Current message: `{data['current_message']}`", "",
        "| Animal | Date | Progress | Stage | Last update |", "|---|---:|---:|---|---|",
    ]
    for day in data["days"]:
        md.append(f"| {day['animal']} | {day['date']} | {day['percent']:.1f}% | {day['stage']} | {day['last_update_utc'] or '—'} |")
    md += ["", "## Downstream aggregation", ""]
    md += [f"- {'✅' if ok else '⬜'} {label}" for label, ok in data["downstream"]["checks"].items()]
    if data["stall_warning"]:
        md += ["", "> **Warning:** no log or output-file update beyond the stall threshold."]
    atomic_write(progress_dir / "LATEST_STATUS.md", "\n".join(md) + "\n")

    rows = "".join(
        f"<tr><td>{html.escape(d['animal'])}</td><td>{d['date']}</td><td>{d['percent']:.1f}%</td>"
        f"<td>{html.escape(d['stage'])}</td><td>{html.escape(d['last_update_utc'] or '—')}</td></tr>"
        for d in data["days"]
    )
    checklist = "".join(f"<li>{'✅' if ok else '⬜'} {html.escape(label)}</li>" for label, ok in data["downstream"]["checks"].items())
    warning = "<div class='warning'>No log or output-file change beyond the stall threshold.</div>" if data["stall_warning"] else ""
    log_tail = html.escape("\n".join(data["log_tail"]))
    pct = data["overall_percent"]
    page = f"""<!doctype html><html><head><meta charset='utf-8'><meta http-equiv='refresh' content='{refresh_seconds}'>
<title>KTMD progress</title><style>
body{{font-family:Arial,sans-serif;max-width:1100px;margin:24px auto;padding:0 18px;line-height:1.45}}
.bar{{height:26px;background:#e5e7eb;border-radius:13px;overflow:hidden;border:1px solid #aaa}}
.fill{{height:100%;width:{pct:.1f}%;background:linear-gradient(90deg,#fbbf24,#dc2626)}}
table{{border-collapse:collapse;width:100%;margin:16px 0}}th,td{{border:1px solid #bbb;padding:7px}}th{{background:#f3f4f6}}
pre{{background:#111827;color:#e5e7eb;padding:12px;overflow:auto;max-height:430px;white-space:pre-wrap}}
.warning{{background:#fee2e2;border-left:5px solid #b91c1c;padding:10px;margin:12px 0}}
.small{{color:#555;font-size:.92em}}</style></head><body>
<h1>KTMD corrected-montage full rerun</h1><div class='bar'><div class='fill'></div></div>
<h2>{pct:.1f}% — {html.escape(data['state'])}</h2>
<p>Completed days: <b>{data['completed_days']}/{data['target_days']}</b> · Elapsed: <b>{data['elapsed_minutes']:.1f} min</b> · Attempt: <b>{data['attempt']}</b></p>
<p>Current message: <code>{html.escape(data['current_message'])}</code></p>
<p class='small'>Updated {data['updated_utc']}; last activity {data['last_activity_utc']} ({data['idle_minutes']:.1f} min ago). Refreshes every {refresh_seconds}s.</p>{warning}
<h2>Six corrected days</h2><table><tr><th>Animal</th><th>Date</th><th>Progress</th><th>Stage</th><th>Last update</th></tr>{rows}</table>
<h2>Downstream analyses</h2><ul>{checklist}</ul><h2>Recent console output</h2><pre>{log_tail}</pre></body></html>"""
    atomic_write(progress_dir / "status.html", page)
    atomic_write(progress_dir / "heartbeat.txt", f"{data['updated_utc']}\t{data['state']}\t{pct:.1f}%\t{data['completed_days']}/{data['target_days']} days\t{data['current_message']}\n")


def run(args: argparse.Namespace) -> int:
    progress_dir = args.progress_dir
    progress_dir.mkdir(parents=True, exist_ok=True)
    old = read_json(progress_dir / "run_state.json")
    if (pid_alive(int(old.get("supervisor_pid") or 0)) or pid_alive(int(old.get("pipeline_pid") or 0))) and not args.force:
        print("A rerun process is already alive; use status or stop.", file=sys.stderr)
        return 2
    attempt = int(old.get("attempt") or 0) + 1
    started, supervisor_pid = time.time(), os.getpid()
    state = {"attempt": attempt, "supervisor_pid": supervisor_pid, "pipeline_pid": None,
             "started_utc": utc_now(), "command": args.pipeline_cmd, "state": "starting"}
    atomic_json(progress_dir / "run_state.json", state)
    env = os.environ.copy()
    env.update({"PYTHONUNBUFFERED": "1", "MPLBACKEND": "Agg", "OMP_NUM_THREADS": str(args.threads),
                "MKL_NUM_THREADS": str(args.threads), "OPENBLAS_NUM_THREADS": str(args.threads),
                "NUMEXPR_NUM_THREADS": str(args.threads)})
    return_code: int | None = None
    child: subprocess.Popen[str] | None = None
    try:
        args.log_path.parent.mkdir(parents=True, exist_ok=True)
        with args.log_path.open("a", encoding="utf-8", buffering=1) as log:
            log.write(f"\n\n=== SUPERVISED RUN ATTEMPT {attempt} @ {utc_now()} ===\nCOMMAND: {' '.join(args.pipeline_cmd)}\n")
            child = subprocess.Popen(args.pipeline_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, bufsize=1, env=env, start_new_session=True)
            state.update({"pipeline_pid": child.pid, "state": "running"})
            atomic_json(progress_dir / "run_state.json", state)
            assert child.stdout is not None
            selector = selectors.DefaultSelector()
            selector.register(child.stdout, selectors.EVENT_READ)
            next_heartbeat = 0.0
            while True:
                events = selector.select(timeout=1.0)
                line = child.stdout.readline() if events else ""
                if line:
                    log.write(f"[{utc_now()}] {line.rstrip()}\n")
                polled, now = child.poll(), time.time()
                if now >= next_heartbeat or polled is not None:
                    data = progress_snapshot(output_root=args.output_root, work_root=args.work_root,
                                             progress_dir=progress_dir, log_path=args.log_path,
                                             supervisor_pid=supervisor_pid, child_pid=child.pid,
                                             started_at=started, return_code=polled, attempt=attempt,
                                             stall_minutes=args.stall_minutes)
                    publish(progress_dir, data, args.refresh_seconds)
                    log.write(f"[{utc_now()}] [HEARTBEAT] {data['overall_percent']:.1f}% · {data['completed_days']}/{data['target_days']} days · idle {data['idle_minutes']:.1f} min\n")
                    next_heartbeat = now + args.heartbeat_seconds
                if polled is not None:
                    return_code = int(polled)
                    break
    except BaseException:
        return_code = 130 if isinstance(sys.exc_info()[1], KeyboardInterrupt) else 1
        with args.log_path.open("a", encoding="utf-8") as log:
            log.write(f"[{utc_now()}] SUPERVISOR EXCEPTION\n{traceback.format_exc()}\n")
        if child and child.poll() is None:
            try: os.killpg(child.pid, signal.SIGTERM)
            except Exception: pass
    finally:
        pid = child.pid if child else None
        data = progress_snapshot(output_root=args.output_root, work_root=args.work_root,
                                 progress_dir=progress_dir, log_path=args.log_path,
                                 supervisor_pid=supervisor_pid, child_pid=pid,
                                 started_at=started, return_code=return_code, attempt=attempt,
                                 stall_minutes=args.stall_minutes)
        publish(progress_dir, data, args.refresh_seconds)
        state.update({"state": data["state"], "return_code": return_code, "finished_utc": utc_now(), "pipeline_pid": pid})
        atomic_json(progress_dir / "run_state.json", state)
        atomic_write(progress_dir / "EXIT_CODE.txt", f"{return_code}\n")
    return int(return_code or 0)


def status(args: argparse.Namespace) -> int:
    data = read_json(args.progress_dir / "progress.json")
    if not data:
        print("No progress snapshot exists yet.")
        return 1
    print(f"{data.get('state')} · {data.get('overall_percent',0):.1f}% · {data.get('completed_days',0)}/{data.get('target_days',6)} days · elapsed {data.get('elapsed_minutes',0):.1f} min")
    for d in data.get("days", []):
        print(f"  {d['animal']} {d['date']}: {d['percent']:5.1f}%  {d['stage']}")
    print("Current:", data.get("current_message"))
    if data.get("stall_warning"): print("WARNING: stall threshold exceeded.")
    print("Status HTML:", args.progress_dir / "status.html")
    print("Markdown:", args.progress_dir / "LATEST_STATUS.md")
    print("Log:", data.get("paths", {}).get("console_log"))
    return 0


def stop(args: argparse.Namespace) -> int:
    state = read_json(args.progress_dir / "run_state.json")
    stopped = False
    for key in ("pipeline_pid", "supervisor_pid"):
        pid = int(state.get(key) or 0)
        if pid_alive(pid):
            try: os.killpg(pid, signal.SIGTERM)
            except ProcessLookupError: continue
            except PermissionError: os.kill(pid, signal.SIGTERM)
            print("Sent SIGTERM to", pid)
            stopped = True
    return 0 if stopped else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("run")
    p.add_argument("--output-root", type=Path, required=True)
    p.add_argument("--work-root", type=Path, required=True)
    p.add_argument("--progress-dir", type=Path, required=True)
    p.add_argument("--log-path", type=Path, required=True)
    p.add_argument("--heartbeat-seconds", type=int, default=30)
    p.add_argument("--refresh-seconds", type=int, default=30)
    p.add_argument("--stall-minutes", type=float, default=45)
    p.add_argument("--threads", type=int, default=2)
    p.add_argument("--force", action="store_true")
    p.add_argument("pipeline_cmd", nargs=argparse.REMAINDER)
    p = sub.add_parser("status"); p.add_argument("--progress-dir", type=Path, required=True)
    p = sub.add_parser("stop"); p.add_argument("--progress-dir", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "run":
        if args.pipeline_cmd and args.pipeline_cmd[0] == "--": args.pipeline_cmd = args.pipeline_cmd[1:]
        if not args.pipeline_cmd: raise SystemExit("Pass pipeline command after --")
        return run(args)
    if args.command == "status": return status(args)
    if args.command == "stop": return stop(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
