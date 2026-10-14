#!/usr/bin/env python3
"""A manual Stop pauses the widget's auto-start (no tablet needed, stdlib only).

The bar widget polls every 4 s and starts the daemon when a tablet is
present, so without a shared pause a Stop from the panel was undone a few
seconds later (and with one widget per monitor, a widget-local flag would
not be enough). `wacom-ctl stop` leaves a pause marker in the runtime dir,
`start`/`restart`/`resume` clear it, and `wacom-status --json` reports it.
"""
import json
import os
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILURES = []


def check(name, cond, detail=""):
    if cond:
        print("ok   - %s" % name)
    else:
        print("FAIL - %s %s" % (name, detail))
        FAILURES.append(name)


def run(script, *args, runtime, state):
    env = dict(os.environ, XDG_RUNTIME_DIR=runtime, XDG_STATE_HOME=state)
    return subprocess.run(
        ["bash", os.path.join(REPO_ROOT, "scripts", script)] + list(args),
        capture_output=True, text=True, timeout=15, env=env,
    )


def paused(runtime, state):
    out = run("wacom-status", "--json", runtime=runtime, state=state).stdout
    try:
        return json.loads(out).get("paused")
    except ValueError:
        return "invalid json: %r" % out


def main():
    runtime = tempfile.mkdtemp(prefix="wacom-runtime-pause-")
    state = tempfile.mkdtemp(prefix="wacom-state-pause-")
    marker = os.path.join(runtime, "omarchy-wacom-support.paused")
    try:
        check("status reports not paused by default", paused(runtime, state) is False)

        run("wacom-ctl", "stop", runtime=runtime, state=state)
        check("stop leaves a pause marker", os.path.exists(marker))
        check("status reports paused after stop", paused(runtime, state) is True)

        run("wacom-ctl", "resume", runtime=runtime, state=state)
        check("resume clears the pause", not os.path.exists(marker))

        run("wacom-ctl", "stop", runtime=runtime, state=state)
        res = run("wacom-ctl", "start", runtime=runtime, state=state)
        check("start clears the pause", not os.path.exists(marker),
              "out=%r err=%r" % (res.stdout, res.stderr))

        run("wacom-ctl", "stop", runtime=runtime, state=state)
        res = run("wacom-ctl", "restart", runtime=runtime, state=state)
        check("restart clears the pause", not os.path.exists(marker),
              "out=%r err=%r" % (res.stdout, res.stderr))
    finally:
        run("wacom-ctl", "stop", runtime=runtime, state=state)

    if FAILURES:
        print("FAIL: %d auto-start pause check(s) failed" % len(FAILURES))
        return 1
    print("ok - manual stop pauses auto-start")
    return 0


if __name__ == "__main__":
    sys.exit(main())
