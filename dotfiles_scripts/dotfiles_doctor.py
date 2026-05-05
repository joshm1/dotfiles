#!/usr/bin/env python3
"""Health check + interactive cleanup for ~/.dotfiles-private/.

Detects common cruft that accumulates in cloud-synced dotfiles trees and
offers per-category fixes:

* Regenerable build artifacts (``node_modules``, ``.venv``, etc.) that should
  not be cloud-synced — fix delegates to ``detach-cloud-cache``.
* Dropbox/Drive conflicted-copy files (e.g. ``foo (Mac's conflicted copy
  2024-01-01).db``) — fix deletes them.
* Stale top-level junk files (zero-byte ``.warprc``, decade-old ``.DS_Store``,
  one-off scripts).
* Stale per-device zsh history files for retired machines.
* Security flags: SSH private keys and AWS credentials inside the cloud tree —
  reported only; never auto-removed.

Each category prints findings, then prompts before doing anything destructive.
Run with ``--check`` to skip prompts and exit non-zero if any findings exist
(useful for CI / pre-commit / wakeup-loop).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import click

from dotfiles_scripts.detach_cloud_cache import (
    CACHE_ROOT,
    DEFAULT_PATTERNS as DETACH_PATTERNS,
)
from dotfiles_scripts.setup_utils import (
    PRIVATE_DOTFILES,
    print_error,
    print_header,
    print_step,
    print_success,
    print_warning,
)

CONFLICTED_COPY_RE = re.compile(r"\bconflicted copy\b", re.IGNORECASE)


@dataclass
class Finding:
    """A single thing the doctor noticed."""

    path: Path
    note: str = ""


@dataclass
class Category:
    """A group of related findings, optionally with an auto-fix."""

    title: str
    findings: list[Finding] = field(default_factory=list)
    fix_label: str | None = None
    # Returns True if the fix was applied.
    fixer: "callable[[list[Finding]], bool] | None" = None  # type: ignore[name-defined]
    severity: str = "warn"  # "warn" | "info" | "security"

    def add(self, path: Path, note: str = "") -> None:
        self.findings.append(Finding(path=path, note=note))

    @property
    def empty(self) -> bool:
        return not self.findings


# ---------------------------------------------------------------- detectors


def detect_build_artifacts(root: Path) -> Category:
    cat = Category(
        title="Regenerable build artifacts in cloud (run detach-cloud-cache)",
        fix_label="run `detach-cloud-cache` to move them to ~/.cache/dotfiles-private/",
        fixer=_fix_detach,
    )
    pattern_set = set(DETACH_PATTERNS)
    for current_root, dirs, _ in os.walk(root, followlinks=False):
        # Don't descend through symlinks (already detached) or detached dirs.
        dirs[:] = [d for d in dirs if not Path(current_root, d).is_symlink()]
        for name in list(dirs):
            if name in pattern_set:
                p = Path(current_root, name)
                cat.add(p, note=f"size: {_du(p)}")
                dirs.remove(name)
    return cat


def detect_conflicted_copies(root: Path) -> Category:
    cat = Category(
        title="Cloud-sync conflicted-copy files",
        fix_label="delete them",
        fixer=_fix_delete,
    )
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if CONFLICTED_COPY_RE.search(path.name):
            cat.add(path, note=f"{_size(path)}")
    return cat


def detect_top_level_junk(root: Path) -> Category:
    cat = Category(
        title="Stale top-level junk in cloud root",
        fix_label="delete them",
        fixer=_fix_delete,
    )
    for relpath, reason in _TOP_LEVEL_JUNK:
        p = root / relpath
        if p.exists():
            cat.add(p, note=reason)
    # Empty placeholder files anywhere in the top level.
    for child in root.iterdir():
        if child.is_file() and child.stat().st_size == 0:
            cat.add(child, note="zero-byte file")
    # .DS_Store at any level — always junk.
    for path in root.rglob(".DS_Store"):
        if path.is_file():
            cat.add(path, note="macOS Finder metadata")
    return cat


_TOP_LEVEL_JUNK: tuple[tuple[str, str], ...] = (
    ("setup/create-pow-links", "old standalone setup script (2017)"),
    ("setup/setup-dropbox", "old standalone setup script (2021)"),
    ("make-backup.sh", "old standalone script"),
)


def detect_stale_device_history(root: Path) -> Category:
    cat = Category(
        title="Stale per-device zsh history (likely retired machines)",
        fix_label="delete them",
        fixer=_fix_delete,
    )
    history_dir = root / "zsh_history"
    if not history_dir.is_dir():
        return cat
    active = _active_device_ids(root)
    if not active:
        # Without a known set of active devices, can't decide — skip.
        return cat
    for path in history_dir.iterdir():
        if not path.is_file():
            continue
        if path.name == ".zsh_history":
            continue  # the legacy global file; user may still rely on it
        if not path.name.startswith(".zsh_history."):
            continue
        suffix = path.name.removeprefix(".zsh_history.")
        if not suffix:
            cat.add(path, note="empty suffix")
            continue
        if suffix in active:
            continue
        cat.add(path, note=f"device '{suffix}' not in active set {sorted(active)}")
    return cat


def detect_security_concerns(root: Path) -> Category:
    cat = Category(
        title="Secrets stored in cloud tree (review manually)",
        severity="security",
    )
    ssh = root / "home/.ssh"
    if ssh.is_dir():
        for path in ssh.iterdir():
            if path.is_file() and _looks_like_private_key(path):
                cat.add(path, note="private key — consider 1Password SSH agent")
    aws = root / "home/.aws/credentials"
    if aws.is_file():
        cat.add(aws, note="AWS credentials — consider aws sso login or 1Password")
    return cat


# ---------------------------------------------------------------- fixers


def _fix_detach(_findings: list[Finding]) -> bool:
    print_step("Invoking detach-cloud-cache...")
    result = subprocess.run(
        [sys.executable, "-m", "dotfiles_scripts.detach_cloud_cache"],
        check=False,
    )
    return result.returncode == 0


def _fix_delete(findings: list[Finding]) -> bool:
    for f in findings:
        try:
            if f.path.is_dir() and not f.path.is_symlink():
                shutil.rmtree(f.path)
            else:
                f.path.unlink()
            print_step(f"deleted {f.path}")
        except OSError as exc:
            print_error(f"could not delete {f.path}: {exc}")
            return False
    return True


# ---------------------------------------------------------------- helpers


def _du(path: Path) -> str:
    """Human-readable directory size; quiet on errors."""
    try:
        out = subprocess.check_output(["du", "-sh", str(path)], stderr=subprocess.DEVNULL)
        return out.decode().split()[0]
    except (OSError, subprocess.CalledProcessError):
        return "?"


def _size(path: Path) -> str:
    try:
        n = path.stat().st_size
    except OSError:
        return "?"
    for unit in ("B", "K", "M", "G"):
        if n < 1024:
            return f"{n:.0f}{unit}"
        n /= 1024
    return f"{n:.0f}T"


def _active_device_ids(root: Path) -> set[str]:
    """Read .config/dotfiles/.dotfiles-config.* file names to learn active devices."""
    cfg_dir = root / "home" / ".config" / "dotfiles"
    if not cfg_dir.is_dir():
        return set()
    devices: set[str] = set()
    for path in cfg_dir.iterdir():
        if not path.name.startswith(".dotfiles-config."):
            continue
        suffix = path.name.removeprefix(".dotfiles-config.")
        if suffix:
            devices.add(suffix)
    return devices


def _looks_like_private_key(path: Path) -> bool:
    if path.name.endswith((".pub", ".pem.pub")):
        return False
    if path.name in {".symlink-dir", ".dotfiles.yaml", "config", "known_hosts", "known_hosts.old", "authorized_keys"}:
        return False
    try:
        head = path.read_bytes()[:128]
    except OSError:
        return False
    return b"PRIVATE KEY" in head or path.suffix in {".pem", ".key"} or "rsa" in path.name.lower() or "ed25519" in path.name.lower()


# ---------------------------------------------------------------- CLI


@click.command()
@click.option(
    "--check",
    is_flag=True,
    help="Report only; do not prompt or fix. Exits non-zero if any findings.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Apply all available fixes without prompting.",
)
def cli(check: bool, yes: bool) -> None:
    """Audit and (optionally) clean up ~/.dotfiles-private/."""
    if not PRIVATE_DOTFILES.is_dir():
        print_warning(f"{PRIVATE_DOTFILES} is not a directory; nothing to check")
        sys.exit(0)

    root = PRIVATE_DOTFILES.resolve()
    print_header("dotfiles-doctor")
    print(f"Inspecting: {root}")
    print(f"Local cache: {CACHE_ROOT}")
    print()

    categories: list[Category] = [
        detect_build_artifacts(root),
        detect_conflicted_copies(root),
        detect_top_level_junk(root),
        detect_stale_device_history(root),
        detect_security_concerns(root),
    ]

    total = sum(len(c.findings) for c in categories)
    if total == 0:
        print_success("Nothing to clean up. ✓")
        sys.exit(0)

    if check:
        for cat in categories:
            if cat.empty:
                continue
            print_header(cat.title)
            for f in cat.findings:
                print(f"  {f.path}{'  (' + f.note + ')' if f.note else ''}")
        print()
        print_warning(
            f"{total} findings across {sum(1 for c in categories if not c.empty)} categories"
        )
        sys.exit(1)

    # Interactive: re-print each category's findings right before its prompt so
    # the user doesn't have to scroll to remember what's about to be acted on.
    for cat in categories:
        if cat.empty:
            continue
        print_header(f"{cat.title}  ({len(cat.findings)})")
        for f in cat.findings:
            print(f"  {f.path}{'  (' + f.note + ')' if f.note else ''}")
        print()

        if cat.fixer is None:
            if cat.severity == "security":
                print_warning(f"no auto-fix; please review the {len(cat.findings)} item(s) above manually")
            continue

        prompt = f"→ Fix the {len(cat.findings)} path(s) above ({cat.fix_label})?"
        if yes or click.confirm(prompt, default=False):
            ok = cat.fixer(cat.findings)
            if ok:
                print_success(f"Fixed: {cat.title}")
            else:
                print_error(f"Fix failed for: {cat.title}")
        else:
            print_step(f"skipped: {cat.title}")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
