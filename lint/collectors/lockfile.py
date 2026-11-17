#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One writer per output file.

Concurrent appends are not atomic on Windows: two processes can both seek to the
current end of the file and one record is silently lost. A lock file turns that
silent data loss into an explicit refusal.

The lock is advisory and lives next to the output: `<out>.lock`, containing the
holder's pid. It is removed on normal exit; `force` takes over a stale lock.
"""
import os


def _read_holder(lock):
    try:
        with open(lock, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def acquire(out_path, force=False):
    """Try to take the lock for out_path.

    Returns a dict: ok, lock, holder, forced, error.
    """
    lock = out_path + ".lock"
    forced = False
    if force and os.path.exists(lock):
        try:
            os.remove(lock)
            forced = True
        except OSError:
            pass
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return {"ok": False, "lock": lock, "holder": _read_holder(lock), "forced": forced, "error": ""}
    except OSError as e:
        return {"ok": False, "lock": lock, "holder": "", "forced": forced, "error": str(e)}
    try:
        os.write(fd, str(os.getpid()).encode("utf-8"))
    finally:
        os.close(fd)
    return {"ok": True, "lock": lock, "holder": str(os.getpid()), "forced": forced, "error": ""}


def release(lock):
    if not lock:
        return
    try:
        os.remove(lock)
    except OSError:
        pass