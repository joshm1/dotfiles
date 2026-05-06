#!/usr/bin/env python3
"""Notify when ``~/projects/joshm1/dotfiles-private`` is out of sync with origin.

Runs hourly via launchd. Performs a ``git fetch`` and counts how many
commits the local branch is behind/ahead of its upstream, plus whether
the working tree is dirty. Fires a single macOS notification when any
of those conditions is non-zero, then suppresses repeats with the same
message for one hour.

Never auto-pulls or auto-pushes — merge resolution is a human task.
Exit code is always 0 (launchd should not see "failures"; transient
network issues are recorded silently and retried on the next tick).
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import cast

import click

from dotfiles_scripts.setup_utils import (
    PRIVATE_DOTFILES_REPO,
    print_step,
    print_success,
    print_warning,
)

CACHE_DIR = Path.home() / ".cache" / "dotfiles-private"
STATE_FILE = CACHE_DIR / "check-repo-state.json"
LOG_FILE = CACHE_DIR / "check-repo.log"
LOG_MAX_BYTES = 1_000_000

NOTIFY_COOLDOWN_SECONDS = 3600  # don't repeat the same notification within 1h
FETCH_TIMEOUT_SECONDS = 30


def _is_mac() -> bool:
    return platform.system() == "Darwin"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _ensure_cache_dir() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _log(line: str) -> None:
    _ensure_cache_dir()
    try:
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > LOG_MAX_BYTES:
            data = LOG_FILE.read_bytes()[-LOG_MAX_BYTES // 2 :]
            LOG_FILE.write_bytes(data)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(f"{_now()} {line}\n")
    except OSError:
        pass


def _load_state() -> dict[str, object]:
    if not STATE_FILE.is_file():
        return {}
    try:
        with STATE_FILE.open("r", encoding="utf-8") as f:
            data: object = json.load(f)
        if isinstance(data, dict):
            return cast("dict[str, object]", data)
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _save_state(state: dict[str, object]) -> None:
    _ensure_cache_dir()
    tmp = STATE_FILE.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
    tmp.replace(STATE_FILE)


def _git(args: list[str], timeout: int | None = None) -> tuple[int, str]:
    """Run a git command in the private repo. Returns (returncode, stdout-stripped)."""
    try:
        result = subprocess.run(
            ["git", *args],
            check=False,
            capture_output=True,
            text=True,
            cwd=PRIVATE_DOTFILES_REPO,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s"
    except (OSError, subprocess.SubprocessError) as e:
        return 1, f"exec failed: {e}"
    return result.returncode, (result.stdout or "").strip()


def _has_upstream() -> bool:
    """True if the current branch tracks an upstream (origin/main or similar)."""
    code, _ = _git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    return code == 0


def _gather() -> dict[str, object] | None:
    """Run git probes and return a state dict, or None if the repo isn't usable."""
    if not (PRIVATE_DOTFILES_REPO / ".git").is_dir():
        return None

    # Fetch — soft-fail (network may be down). Don't notify on fetch failure;
    # a stale "behind" reading is fine until next tick.
    fetch_code, fetch_out = _git(["fetch", "--quiet"], timeout=FETCH_TIMEOUT_SECONDS)
    if fetch_code != 0:
        _log(f"fetch failed: {fetch_out}")

    if not _has_upstream():
        # Branch has no upstream yet (fresh clone before push). Treat as no-op.
        return {"behind": 0, "ahead": 0, "dirty": False, "no_upstream": True}

    behind_code, behind_out = _git(["rev-list", "--count", "HEAD..@{u}"])
    ahead_code, ahead_out = _git(["rev-list", "--count", "@{u}..HEAD"])
    dirty_code, dirty_out = _git(["status", "--porcelain"])

    behind = int(behind_out) if behind_code == 0 and behind_out.isdigit() else 0
    ahead = int(ahead_out) if ahead_code == 0 and ahead_out.isdigit() else 0
    dirty = dirty_code == 0 and bool(dirty_out)

    return {"behind": behind, "ahead": ahead, "dirty": dirty, "no_upstream": False}


def _notify(title: str, message: str) -> None:
    if not _is_mac():
        return
    try:
        t = title.replace('"', '\\"')
        m = message.replace('"', '\\"')
        script = f'display notification "{m}" with title "{t}"'
        subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as e:
        _log(f"notify failed: {e}")


def _build_message(probe: dict[str, object]) -> str | None:
    """Compose a single human-readable message, or None if everything is clean."""
    parts: list[str] = []
    behind = probe.get("behind", 0)
    ahead = probe.get("ahead", 0)
    if isinstance(behind, int) and behind > 0:
        parts.append(f"{behind} commit{'s' if behind != 1 else ''} behind origin")
    if isinstance(ahead, int) and ahead > 0:
        parts.append(f"{ahead} commit{'s' if ahead != 1 else ''} ahead of origin")
    if probe.get("dirty"):
        parts.append("uncommitted changes")
    return "; ".join(parts) if parts else None


def _maybe_notify(message: str, force: bool) -> bool:
    """Fire notification respecting cooldown. Returns True if fired."""
    state = _load_state()
    now = time.time()
    if not force:
        last_message = state.get("last_message")
        last_ts = state.get("last_notify_ts")
        if (
            isinstance(last_ts, (int, float))
            and isinstance(last_message, str)
            and last_message == message
            and now - last_ts < NOTIFY_COOLDOWN_SECONDS
        ):
            return False
    _notify(
        "dotfiles-private out of sync",
        f"{message}. Run `cd ~/.dotfiles-private && git status`.",
    )
    state["last_message"] = message
    state["last_notify_ts"] = now
    _save_state(state)
    _log(f"notified: {message}")
    return True


def _do_check(force: bool) -> int:
    probe = _gather()
    if probe is None:
        _log("repo not bootstrapped — skipping")
        return 0
    if probe.get("no_upstream"):
        _log("branch has no upstream yet — skipping")
        return 0
    message = _build_message(probe)
    if message is None:
        # Clean state — clear any stale notify suppression so the next problem fires immediately.
        state = _load_state()
        if "last_message" in state:
            state.pop("last_message", None)
            state.pop("last_notify_ts", None)
            _save_state(state)
        _log("clean")
        return 0
    fired = _maybe_notify(message, force=force)
    _log(f"detected '{message}' (notification {'fired' if fired else 'suppressed by cooldown'})")
    return 0


def _do_status() -> int:
    """Print a human-readable status summary; do not notify."""
    print_step(f"repo: {PRIVATE_DOTFILES_REPO}")
    if not (PRIVATE_DOTFILES_REPO / ".git").is_dir():
        print_warning("repo not bootstrapped on this machine")
        return 0
    probe = _gather()
    if probe is None:
        print_warning("could not probe repo state")
        return 0
    if probe.get("no_upstream"):
        print_warning("current branch has no upstream tracking")
        return 0
    behind = probe.get("behind", 0)
    ahead = probe.get("ahead", 0)
    dirty = probe.get("dirty", False)
    print(f"  behind origin : {behind}")
    print(f"  ahead origin  : {ahead}")
    print(f"  dirty         : {dirty}")
    state = _load_state()
    last_ts = state.get("last_notify_ts")
    last_message = state.get("last_message")
    if isinstance(last_ts, (int, float)) and last_message:
        ago = int(time.time() - last_ts)
        print(f"  last notify   : {last_message!r} ({ago}s ago)")
    if behind == 0 and ahead == 0 and not dirty:
        print_success("in sync")
    return 0


@click.command()
@click.option(
    "--force",
    is_flag=True,
    help="Ignore the 1h notification cooldown — fire even if the same message recently fired.",
)
@click.option("--status", "show_status", is_flag=True, help="Print state, no notification.")
def cli(force: bool, show_status: bool) -> None:
    """Check the local dotfiles-private repo against origin and notify on divergence."""
    if show_status:
        sys.exit(_do_status())
    sys.exit(_do_check(force=force))


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
