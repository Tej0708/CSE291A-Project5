#!/usr/bin/env python3
"""Auto-loop: resolve each authorized 429 slot, retry, and continue until all runs are terminal."""
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUN_DIR = ROOT / "results/workflow2_phase1_20261103_210112"
MANIFEST = RUN_DIR / "manifest.json"
PY = str(ROOT / ".venv/bin/python")
EXPECTED = json.loads(MANIFEST.read_text())["expected_run_count"]
BUFFER_S = 20
MAX_WAIT_S = 4000
MAX_CYCLES = 60


def completed_count():
    n = 0
    for f in RUN_DIR.glob("*/complete.json"):
        if json.loads(f.read_text()).get("execution") == "completed":
            n += 1
    return n


def errored_slot():
    for f in sorted(RUN_DIR.glob("*/complete.json")):
        d = json.loads(f.read_text())
        if d.get("execution") not in ("completed", "failed") or not d.get("sanity_passed"):
            return f.parent.name
    return None


def wait_seconds(slot):
    secs, reset_dt = 60, None
    p = RUN_DIR / slot / "provider_requests.jsonl"
    if p.exists():
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("status") == "failed" and rec.get("status_code") == 429:
                try:
                    secs = int(rec.get("retry_after") or secs)
                except ValueError:
                    pass
                m = re.search(r"Limit resets at: ([0-9-]+ [0-9:]+) UTC", rec.get("provider_error_message", ""))
                if m:
                    reset_dt = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    wait = secs
    if reset_dt:
        wait = max(wait, (reset_dt - datetime.now(timezone.utc)).total_seconds())
    return max(0.0, min(MAX_WAIT_S, wait + BUFFER_S))


def run(cmd):
    print(">>", " ".join(cmd), flush=True)
    return subprocess.run(cmd).returncode


def main():
    for cycle in range(1, MAX_CYCLES + 1):
        comp = completed_count()
        print(f"[driver] cycle={cycle} completed={comp}/{EXPECTED} remaining={EXPECTED - comp}", flush=True)
        if comp >= EXPECTED:
            print("[driver] ALL DONE", flush=True)
            return 0
        slot = errored_slot()
        if slot:
            print(f"[driver] authorizing errored slot: {slot}", flush=True)
            plan = RUN_DIR / f"continuation_plan_{slot}.json"
            if run([PY, "infrastructure_continuation.py", "--run-dir", str(RUN_DIR),
                    "--slot", slot, "--output", str(plan)]) != 0:
                print("[driver] prepare failed; stopping for manual review", flush=True)
                return 1
            w = wait_seconds(slot)
            print(f"[driver] waiting {w:.0f}s for rate-limit window to reset", flush=True)
            time.sleep(w)
            run([PY, "workflow2_phase1.py", "execute", "--manifest", str(MANIFEST),
                 "--output", str(RUN_DIR), "--resume", "--continuation-plan", str(plan)])
        else:
            run([PY, "workflow2_phase1.py", "execute", "--manifest", str(MANIFEST),
                 "--output", str(RUN_DIR), "--resume"])
    print("[driver] reached MAX_CYCLES; stopping", flush=True)
    return 2


if __name__ == "__main__":
    sys.exit(main())
