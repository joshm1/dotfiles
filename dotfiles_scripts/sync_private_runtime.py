#!/usr/bin/env python3
"""Sync runtime state to a per-machine subdir on Google Drive.

Bridge between two storage layers in the dotfiles design:

- ``~/.dotfiles-private`` — git-tracked private config, symlinked to
  the local clone (handled by ``check_private_repo.py``).
- ``<gdrive>/dotfiles-runtime/${device_id}/`` — runtime state that
  doesn't belong in git: zsh history, REPL histories, Claude Code
  per-session state, etc.

Each machine writes only to its own ``${device_id}/`` subdir, so there
are no cross-machine conflicts to resolve. The same machine's
runtime state is kept consistent between local and Drive via mtime-
based ``rsync --update`` runs every 5 minutes.

Sync sources are split into two lists:

- ``REPO_RUNTIME_PATHS`` — paths relative to the repo root (resolved
  through ``~/.dotfiles-private``). These are gitignored files that
  live inside the repo checkout. Mirrored under
  ``${device_id}/repo/<same-relative-path>``.
- ``HOME_RUNTIME_PATHS`` — absolute ``$HOME``-rooted paths that are
  not part of the repo. Mirrored under
  ``${device_id}/home/<path-relative-to-$HOME>``.

Exit codes are always 0 (launchd-friendly). Persistent failures
(crossing the 1h threshold) emit a single macOS notification with
its own cooldown.
"""

from __future__ import annotations

import fcntl
import json
import platform
import shlex
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import cast

import click

from dotfiles_scripts.detach_cloud_cache import DEFAULT_PATTERNS as CACHE_DIR_PATTERNS
from dotfiles_scripts.setup_utils import (
    DROPBOX_DIR,
    PRIVATE_DOTFILES,
    gdrive_candidates,
    print_header,
    print_step,
    print_success,
    read_dotfiles_config,
)

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

CACHE_DIR = Path.home() / ".cache" / "dotfiles-private"
LOCK_FILE = CACHE_DIR / "sync-runtime.lock"
STATE_FILE = CACHE_DIR / "sync-runtime-state.json"
LOG_FILE = CACHE_DIR / "sync-runtime.log"
LOG_MAX_BYTES = 1_000_000

RUNTIME_DIR_NAME = "dotfiles-runtime"
# Backwards-compat alias — older callers (e.g. setup_private_repo) imported the
# previous name. Keep both pointing at the same string.
GDRIVE_RUNTIME_DIR_NAME = RUNTIME_DIR_NAME

# Sibling of dotfiles-runtime/ — same cloud provider, but a single shared
# directory (no device_id segment) used for identity that's the same across
# all of the user's machines. Currently: SSH private keys on opt-out devices.
SHARED_DIR_NAME = "dotfiles-shared"

# Glob patterns under the dotfiles-private repo root that participate in the
# shared bucket when SSH_IDENTITY_BACKEND=disk-keys. ``id_*`` covers both
# private keys and their .pub fallbacks; .pem covers AWS-style keypairs.
SSH_DISK_KEY_PATTERNS: tuple[str, ...] = (
    "home/.ssh/id_*",
    "home/.ssh/*.pem",
)

# Each direction has its own timeout. Pulls can be slow on big trees
# (Claude projects 248 MB on first run); push is normally tiny deltas.
PULL_TIMEOUT_SECONDS = 1800  # 30 min — accommodates the initial 248 MB ~/.claude/projects pull
PUSH_TIMEOUT_SECONDS = 600  # 10 min

INTERVAL_SECONDS = 300  # matches the launchd schedule
FAILURE_THRESHOLD_SECONDS = 3600  # 1 h
NOTIFY_COOLDOWN_SECONDS = 3600

# macOS ships Apple's openrsync at /usr/bin/rsync, which reads source files
# via mmap(). Google Drive FileProvider stub files intermittently return
# EDEADLK on those mmaps ("Resource deadlock avoided"), corrupting pulls.
# Homebrew's GNU rsync 3.x reads with sliding-window read() and works
# reliably against FileProvider. Prefer it when present.
_BREW_RSYNC = Path("/opt/homebrew/bin/rsync")
RSYNC_BIN = str(_BREW_RSYNC) if _BREW_RSYNC.is_file() else "rsync"

# Prefer terminal-notifier over osascript for failure notifications. osascript
# notifications are stuck under the "Script Editor" sender with no click action;
# terminal-notifier surfaces its own sender and supports -group (collapse repeats)
# and -execute (open the log on click).
_BREW_TERMINAL_NOTIFIER = Path("/opt/homebrew/bin/terminal-notifier")
TERMINAL_NOTIFIER_BIN: str | None = (
    str(_BREW_TERMINAL_NOTIFIER) if _BREW_TERMINAL_NOTIFIER.is_file() else None
)

# Paths to sync, split by source root. Each entry is a *relative* path
# from the source root; the destination preserves the same shape under
# ``<gdrive>/dotfiles-runtime/${device_id}/<repo|home>/``.
#
# REPO_RUNTIME_PATHS resolve through PRIVATE_DOTFILES (i.e.
# ``~/.dotfiles-private``); after the bootstrap retargets the symlink,
# they're real local files in the git checkout.
REPO_RUNTIME_PATHS: tuple[str, ...] = (
    # zsh history is per-device by filename suffix; we sync the entire
    # zsh_history/ dir but only this device's file is ever the writer.
    "zsh_history/",
    "home/.pry_history",
    "home/.node_repl_history",
    "home/.psql_history",
    "home/.clipboard",
    "home/.ssh/known_hosts",
    "home/.ssh/authorized_keys",
)

# HOME_RUNTIME_PATHS live in $HOME directly and are not symlinked into the repo.
HOME_RUNTIME_PATHS: tuple[str, ...] = (
    ".claude/projects",  # 248 MB conversation state
    ".claude/history.jsonl",
)

# ---------------------------------------------------------------------------
# State / log
# ---------------------------------------------------------------------------

_DEFAULT_STATE: dict[str, object] = {
    "last_pull_ok": None,
    "last_push_ok": None,
    "consecutive_pull_failures": 0,
    "consecutive_push_failures": 0,
    "last_notify_ts": None,
}


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _now_epoch() -> float:
    return time.time()


def _ensure_cache_dir() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _load_state() -> dict[str, object]:
    if not STATE_FILE.is_file():
        return dict(_DEFAULT_STATE)
    try:
        with STATE_FILE.open("r", encoding="utf-8") as f:
            data: object = json.load(f)
        if not isinstance(data, dict):
            return dict(_DEFAULT_STATE)
        merged: dict[str, object] = dict(_DEFAULT_STATE)
        merged.update(cast("dict[str, object]", data))
        return merged
    except (OSError, json.JSONDecodeError):
        return dict(_DEFAULT_STATE)


def _save_state(state: dict[str, object]) -> None:
    _ensure_cache_dir()
    tmp = STATE_FILE.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
    tmp.replace(STATE_FILE)


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


# ---------------------------------------------------------------------------
# Locking
# ---------------------------------------------------------------------------


@contextmanager
def _flock_or_skip() -> Iterator[bool]:
    """Yield True if we hold the sync lock, False if another run is in progress."""
    _ensure_cache_dir()
    f = LOCK_FILE.open("w")
    try:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        yield True
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    finally:
        f.close()


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------


def _is_mac() -> bool:
    return platform.system() == "Darwin"


def _notify_via_terminal_notifier(title: str, message: str) -> bool:
    """Try terminal-notifier. Return True only if it actually ran cleanly.

    A file-exists check isn't enough: a broken code signature can get the
    binary SIGKILL'd by the kernel (returncode -9), so we check the exit
    status and let the caller fall back to osascript on any failure.
    """
    if TERMINAL_NOTIFIER_BIN is None:
        return False
    try:
        result = subprocess.run(
            [
                TERMINAL_NOTIFIER_BIN,
                "-title", title,
                "-message", message,
                "-group", "dotfiles-runtime",
                "-execute", f"open {shlex.quote(str(LOG_FILE))}",
            ],
            check=False,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as e:
        _log(f"terminal-notifier failed ({e}) — falling back to osascript")
        return False
    if result.returncode != 0:
        _log(
            f"terminal-notifier exited {result.returncode} — "
            "falling back to osascript"
        )
        return False
    return True


def _notify(title: str, message: str) -> None:
    if not _is_mac():
        return
    if _notify_via_terminal_notifier(title, message):
        return
    try:
        t = title.replace('"', '\\"')
        m = message.replace('"', '\\"')
        subprocess.run(
            ["osascript", "-e", f'display notification "{m}" with title "{t}"'],
            check=False,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as e:
        _log(f"notify failed: {e}")


def _maybe_notify(state: dict[str, object], kind: str) -> None:
    counter = state.get(f"consecutive_{kind}_failures", 0)
    failures = counter if isinstance(counter, int) else 0
    elapsed = failures * INTERVAL_SECONDS
    if elapsed < FAILURE_THRESHOLD_SECONDS:
        return
    last_notify = state.get("last_notify_ts")
    if isinstance(last_notify, (int, float)) and (
        _now_epoch() - last_notify < NOTIFY_COOLDOWN_SECONDS
    ):
        return
    minutes = elapsed // 60
    _notify(
        title=f"dotfiles-runtime sync-{kind} failing",
        message=(
            f"{failures} consecutive failures (~{minutes} min). "
            f"Run `sync-private-runtime --status`."
        ),
    )
    state["last_notify_ts"] = _now_epoch()
    _log(f"notified user: sync-{kind} failing for ~{minutes} min")


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def _device_id() -> str | None:
    p = Path.home() / ".device_id"
    if not p.is_file():
        return None
    try:
        return p.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _runtime_storage_candidates() -> list[Path]:
    """Cloud storage roots eligible for the runtime bucket, ordered by preference.

    Google Drive accounts come first (preferred), then Dropbox if mounted.
    Same ordering pattern used elsewhere for cloud-sync provider discovery.
    """
    roots: list[Path] = list(gdrive_candidates())
    if DROPBOX_DIR.is_dir():
        roots.append(DROPBOX_DIR)
    return roots


def _resolve_runtime_root() -> Path | None:
    """Return ``<storage>/dotfiles-runtime/${device_id}/`` or None if not bootstrappable.

    Storage is whichever cloud provider is mounted on this machine. If a
    runtime bucket already exists on one provider, prefer it; otherwise
    create on the first available provider (GDrive > Dropbox).
    """
    dev = _device_id()
    if not dev:
        _log("device id missing (~/.device_id)")
        return None
    storages = _runtime_storage_candidates()
    if not storages:
        _log("no cloud storage mounted (Google Drive or Dropbox)")
        return None
    # Prefer the storage that already has this device's runtime bucket — keeps
    # us pinned to the same provider across runs even if a new one gets mounted.
    for storage in storages:
        bucket = storage / RUNTIME_DIR_NAME / dev
        if bucket.is_dir():
            return bucket
    # No bucket exists yet — pick the highest-preference provider for first run.
    return storages[0] / RUNTIME_DIR_NAME / dev


def resolve_shared_root() -> Path | None:
    """Return ``<storage>/dotfiles-shared/`` or None if no cloud storage is mounted.

    Public counterpart to ``_resolve_runtime_root`` — same cloud-provider
    selection logic, but no device segment: every machine writes to/reads
    from the same place. The exporter on a 1Password-enabled machine
    pushes here; opted-out machines pull from here.
    """
    storages = _runtime_storage_candidates()
    if not storages:
        return None
    for storage in storages:
        bucket = storage / SHARED_DIR_NAME
        if bucket.is_dir():
            return bucket
    return storages[0] / SHARED_DIR_NAME


def _ssh_backend() -> str:
    """Return the SSH identity backend for this machine.

    Reads ``SSH_IDENTITY_BACKEND`` from the hierarchical
    ``~/.config/dotfiles/.dotfiles-config*`` files. Defaults to ``1password``.
    """
    return read_dotfiles_config("SSH_IDENTITY_BACKEND") or "1password"


def _repo_root() -> Path | None:
    """Return the dotfiles-private repo root (resolves the symlink)."""
    if not PRIVATE_DOTFILES.is_dir():
        return None
    return PRIVATE_DOTFILES


def _trail(p: Path) -> str:
    s = str(p)
    return s if s.endswith("/") else s + "/"


# ---------------------------------------------------------------------------
# rsync
# ---------------------------------------------------------------------------


def _rsync_excludes() -> list[str]:
    args = [f"--exclude={p}" for p in CACHE_DIR_PATTERNS]
    args.extend(
        [
            "--exclude=.git",
            "--exclude=.git/",
            "--exclude=*.lock",
            "--exclude=.DS_Store",
        ]
    )
    return args


def _run_rsync(args: list[str], timeout: int) -> tuple[int, str]:
    try:
        result = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s"
    except (OSError, subprocess.SubprocessError) as e:
        return 1, f"exec failed: {e}"
    out = (result.stdout or "") + (result.stderr or "")
    return result.returncode, out.strip()


def sync_path(
    source: Path,
    dest: Path,
    timeout: int,
) -> tuple[bool, str]:
    """Sync a single source path to dest. Skips silently if source is missing."""
    if not source.exists():
        return True, f"skip (source absent): {source}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        args = [
            RSYNC_BIN,
            "-a",
            "--update",
            *_rsync_excludes(),
            _trail(source),
            _trail(dest),
        ]
    else:
        args = [
            RSYNC_BIN,
            "-a",
            "--update",
            *_rsync_excludes(),
            str(source),
            str(dest),
        ]
    code, out = _run_rsync(args, timeout=timeout)
    if code == 0:
        return True, f"ok: {source} → {dest}"
    return False, f"FAIL ({code}): {source} → {dest}: {out[-300:]}"


def _ssh_filename_matches_patterns(name: str) -> bool:
    """True if ``name`` matches any of ``SSH_DISK_KEY_PATTERNS`` (bare-filename match)."""
    from fnmatch import fnmatch

    bare_patterns = [Path(p).name for p in SSH_DISK_KEY_PATTERNS]
    return any(fnmatch(name, pat) for pat in bare_patterns)


def _sync_ssh_keys_pull(repo: Path) -> tuple[int, list[str]]:
    """Pull SSH disk-keys from the shared bucket into the private repo's ~/.ssh/.

    Returns ``(successes, failures)``. Skips silently if the shared bucket
    or its ``ssh/`` subdir is missing.
    """
    shared = resolve_shared_root()
    if shared is None or not (shared / "ssh").is_dir():
        return 0, []
    failures: list[str] = []
    successes = 0
    ssh_local = repo / "home" / ".ssh"
    ssh_local.mkdir(parents=True, exist_ok=True)
    for entry in (shared / "ssh").iterdir():
        if not entry.is_file() or not _ssh_filename_matches_patterns(entry.name):
            continue
        dst = ssh_local / entry.name
        ok, msg = sync_path(entry, dst, timeout=PULL_TIMEOUT_SECONDS)
        _log(msg)
        if not ok:
            failures.append(msg)
            continue
        successes += 1
        # Defense-in-depth: cloud storage may flatten perms. Re-tighten private
        # keys after pull; .pub stays world-readable.
        if not entry.name.endswith(".pub"):
            try:
                dst.chmod(0o600)
            except OSError as exc:
                _log(f"chmod 0600 failed for {dst}: {exc}")
    return successes, failures


def _sync_ssh_keys_push(repo: Path) -> tuple[int, list[str]]:
    """Push SSH disk-keys from the private repo's ~/.ssh/ to the shared bucket.

    Returns ``(successes, failures)``. Skips silently if no matching files
    exist locally.
    """
    shared = resolve_shared_root()
    if shared is None:
        return 0, []
    ssh_local = repo / "home" / ".ssh"
    if not ssh_local.is_dir():
        return 0, []

    matches: list[Path] = []
    for pattern in SSH_DISK_KEY_PATTERNS:
        matches.extend(ssh_local.glob(Path(pattern).name))
    if not matches:
        return 0, []

    failures: list[str] = []
    successes = 0
    (shared / "ssh").mkdir(parents=True, exist_ok=True)
    for src in matches:
        if not src.is_file():
            continue
        dst = shared / "ssh" / src.name
        ok, msg = sync_path(src, dst, timeout=PUSH_TIMEOUT_SECONDS)
        _log(msg)
        if ok:
            successes += 1
        else:
            failures.append(msg)
    return successes, failures


def _do_pull() -> tuple[bool, str]:
    """GDrive runtime → local. Returns (ok, summary_line)."""
    runtime = _resolve_runtime_root()
    if runtime is None:
        return False, "runtime root unavailable (missing ~/.device_id or no cloud storage mounted)"
    if not runtime.is_dir():
        # First-ever run on this machine before any push happened. Not an error.
        return True, f"runtime root does not yet exist: {runtime}"
    repo = _repo_root()
    if repo is None:
        return False, f"repo root unavailable: {PRIVATE_DOTFILES} not a directory"

    failures: list[str] = []
    successes = 0
    for rel in REPO_RUNTIME_PATHS:
        src = runtime / "repo" / rel
        dst = repo / rel
        ok, msg = sync_path(src, dst, timeout=PULL_TIMEOUT_SECONDS)
        _log(msg)
        if ok:
            successes += 1
        else:
            failures.append(msg)
    for rel in HOME_RUNTIME_PATHS:
        src = runtime / "home" / rel
        dst = Path.home() / rel
        ok, msg = sync_path(src, dst, timeout=PULL_TIMEOUT_SECONDS)
        _log(msg)
        if ok:
            successes += 1
        else:
            failures.append(msg)

    if _ssh_backend() == "disk-keys":
        ssh_ok, ssh_failures = _sync_ssh_keys_pull(repo)
        successes += ssh_ok
        failures.extend(ssh_failures)

    if failures:
        return False, (
            f"pull: {len(failures)} failure(s); {successes} ok; "
            f"first error: {failures[0]}"
        )
    return True, f"pull: {successes} path(s) synced"


def _do_push() -> tuple[bool, str]:
    """Local → GDrive runtime. Returns (ok, summary_line)."""
    runtime = _resolve_runtime_root()
    if runtime is None:
        return False, "runtime root unavailable (missing ~/.device_id or no cloud storage mounted)"
    repo = _repo_root()
    if repo is None:
        return False, f"repo root unavailable: {PRIVATE_DOTFILES} not a directory"
    runtime.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    successes = 0
    for rel in REPO_RUNTIME_PATHS:
        src = repo / rel
        dst = runtime / "repo" / rel
        ok, msg = sync_path(src, dst, timeout=PUSH_TIMEOUT_SECONDS)
        _log(msg)
        if ok:
            successes += 1
        else:
            failures.append(msg)
    for rel in HOME_RUNTIME_PATHS:
        src = Path.home() / rel
        dst = runtime / "home" / rel
        ok, msg = sync_path(src, dst, timeout=PUSH_TIMEOUT_SECONDS)
        _log(msg)
        if ok:
            successes += 1
        else:
            failures.append(msg)

    if _ssh_backend() == "disk-keys":
        ssh_ok, ssh_failures = _sync_ssh_keys_push(repo)
        successes += ssh_ok
        failures.extend(ssh_failures)

    if failures:
        return False, (
            f"push: {len(failures)} failure(s); {successes} ok; "
            f"first error: {failures[0]}"
        )
    return True, f"push: {successes} path(s) synced"


def _record_result(kind: str, ok: bool, message: str) -> None:
    state = _load_state()
    counter_key = f"consecutive_{kind}_failures"
    last_ok_key = f"last_{kind}_ok"
    if ok:
        state[counter_key] = 0
        state[last_ok_key] = _now()
        _log(f"{kind} ok: {message[:200]}")
    else:
        prev = state.get(counter_key, 0)
        state[counter_key] = (prev if isinstance(prev, int) else 0) + 1
        _log(f"{kind} FAIL: {message[:500]}")
        _maybe_notify(state, kind)
    _save_state(state)


def _run_with_lock(kind: str, op: Callable[[], tuple[bool, str]]) -> int:
    with _flock_or_skip() as held:
        if not held:
            _log(f"{kind} skipped: lock held")
            return 0
        ok, msg = op()
        _record_result(kind, ok, msg)
    return 0


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


def _do_status() -> int:
    print_header("dotfiles-runtime sync status")
    repo = _repo_root()
    runtime = _resolve_runtime_root()
    print_step(f"repo root        : {repo if repo else 'NOT MOUNTED'}")
    print_step(f"runtime root     : {runtime if runtime else 'NOT AVAILABLE'}")
    print_step(f"device id        : {_device_id() or 'MISSING'}")
    state = _load_state()
    print()
    print(f"  last pull ok    : {state.get('last_pull_ok') or 'never'}")
    print(f"  last push ok    : {state.get('last_push_ok') or 'never'}")
    print(f"  pull failures   : {state.get('consecutive_pull_failures', 0)}")
    print(f"  push failures   : {state.get('consecutive_push_failures', 0)}")
    last_notify = state.get("last_notify_ts")
    if isinstance(last_notify, (int, float)):
        ago = int(_now_epoch() - last_notify)
        print(f"  last notify     : {ago}s ago")
    if runtime and runtime.is_dir():
        print()
        print_success(f"runtime root present at {runtime}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command()
@click.option("--pull", "action_pull", is_flag=True, help="Sync GDrive runtime → local only.")
@click.option("--push", "action_push", is_flag=True, help="Sync local → GDrive runtime only.")
@click.option(
    "--status",
    "action_status",
    is_flag=True,
    help="Print state and recent sync results.",
)
def cli(action_pull: bool, action_push: bool, action_status: bool) -> None:
    """Sync runtime state to a per-machine subdir on Google Drive.

    With no flags: pull then push (the launchd-driven default). Order
    keeps a freshly-edited local file from being clobbered by a stale
    Drive copy: pull is mtime-based ``--update``, so newer-local files
    are not overwritten.
    """
    if sum([action_pull, action_push, action_status]) > 1:
        raise click.UsageError("--pull, --push, and --status are mutually exclusive")

    if action_status:
        sys.exit(_do_status())
    if action_pull:
        sys.exit(_run_with_lock("pull", _do_pull))
    if action_push:
        sys.exit(_run_with_lock("push", _do_push))

    # Default: pull then push.
    with _flock_or_skip() as held:
        if not held:
            _log("default sync skipped: lock held")
            sys.exit(0)
        pull_ok, pull_msg = _do_pull()
        _record_result("pull", pull_ok, pull_msg)
        push_ok, push_msg = _do_push()
        _record_result("push", push_ok, push_msg)
    sys.exit(0)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
