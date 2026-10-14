#!/usr/bin/env python3
"""The daemon log stays bounded (no tablet needed, stdlib only).

Button commands used to inherit the daemon log as stdout/stderr, so an app
launched from a pad button (browser, terminal…) appended its output there
for as long as it ran, with no rotation. Commands now run under
`systemd-cat`, so their output goes to the journal (which rotates), and
daemon.log is rotated at startup once it passes LOG_MAX_BYTES.
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location(
    "wacom_daemon", os.path.join(REPO_ROOT, "scripts", "wacom-daemon.py")
)
wd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wd)

FAILURES = []


def check(name, cond, detail=""):
    if cond:
        print("ok   - %s" % name)
    else:
        print("FAIL - %s %s" % (name, detail))
        FAILURES.append(name)


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def main():
    os.environ["XDG_STATE_HOME"] = tempfile.mkdtemp(prefix="wacom-state-log-")
    log = wd.log_file()

    # 1. Rotation: an oversized log moves to daemon.log.1, a small one stays.
    with open(log, "w", encoding="utf-8") as fh:
        fh.write("small\n")
    wd.rotate_log()
    check("rotate_log keeps a small log", read(log) == "small\n")

    with open(log, "w", encoding="utf-8") as fh:
        fh.write("x" * (wd.LOG_MAX_BYTES + 1))
    wd.rotate_log()
    check("rotate_log moves an oversized log aside",
          len(read(log + ".1")) == wd.LOG_MAX_BYTES + 1)
    check("rotate_log starts a fresh log", read(log) == "")

    # 2. Commands run under systemd-cat when available, plain sh otherwise.
    check(
        "command_argv wraps in systemd-cat",
        wd.command_argv("echo hi", systemd_cat="/usr/bin/systemd-cat")
        == ["/usr/bin/systemd-cat", "-t", wd.JOURNAL_TAG, "sh", "-c", "echo hi"],
    )
    check(
        "command_argv falls back to sh",
        wd.command_argv("echo hi", systemd_cat=None) == ["sh", "-c", "echo hi"],
    )

    # 3. End to end: a command's output never lands in daemon.log.
    # The command assembles the marker at run time, so the logged command
    # text ("button 1 -> printf ...") never contains it, only the output does.
    token = uuid.uuid4().hex
    marker = "wacom-log-test-%s" % token
    wd.run_command("printf '%%s-%%s\\n' wacom-log-test %s" % token, 1)
    time.sleep(1.0)
    check("command output stays out of daemon.log", marker not in read(log))
    check("daemon.log still records the button", "button 1 -> printf" in read(log))
    if shutil.which("systemd-cat") and shutil.which("journalctl"):
        found = False
        for _ in range(20):
            out = subprocess.run(
                ["journalctl", "-t", wd.JOURNAL_TAG, "-n", "50", "-o", "cat", "--no-pager"],
                capture_output=True, text=True, timeout=10,
            ).stdout
            if marker in out:
                found = True
                break
            time.sleep(0.25)
        check("command output reaches the journal", found)
    else:
        print("skip - systemd-cat/journalctl not available")

    if FAILURES:
        print("FAIL: %d daemon log check(s) failed" % len(FAILURES))
        return 1
    print("ok - daemon log stays bounded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
