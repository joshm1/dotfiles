#!/usr/bin/env python3
"""Verify and repair dotfile symlinks across both home/ trees.

Walks ``~/.dotfiles/home/`` and ``~/.dotfiles-private/home/``, running the
shared idempotent walker (``symlink_home_dir``) against each to make sure
every file there is correctly symlinked into ``$HOME``.

Additionally scans ``$HOME`` (up to a shallow depth) for *stale* symlinks
pointing at older layouts that have no replacement in the current trees
(e.g. ``~/Dropbox/dotfiles/home/...``). Stale symlinks are reported by
default; pass ``--clean`` to remove broken ones.

This is the maintenance counterpart to ``symlink-home-files``: re-runs the
same walker against both trees and surfaces cruft left over from older
layouts.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from dotfiles_scripts.setup_utils import (
    DOTFILES,
    DROPBOX_DIR,
    PRIVATE_DOTFILES,
    print_error,
    print_header,
    print_step,
    print_success,
    print_warning,
    symlink_home_dir,
)

# Symlink targets starting with any of these prefixes are treated as stale.
# Keep these as literal string prefixes (matched against the symlink's raw
# target text), so we catch broken links even when the target path no longer
# resolves to anything on disk.
_STALE_TARGET_PREFIXES: tuple[str, ...] = (
    f"{DROPBOX_DIR}/dotfiles/",
)

# Top-level directories under $HOME that we never descend into when scanning
# for stale symlinks — either too large, too noisy, or known not to contain
# managed dotfiles.
_SCAN_SKIP_TOPLEVEL: tuple[str, ...] = (
    "Library",
    "Dropbox",
    ".Trash",
    ".cache",
    ".npm",
    ".pnpm-store",
    ".cargo",
    ".rustup",
    "node_modules",
    ".venv",
)

# Maximum depth (relative to $HOME) to walk when looking for stale symlinks.
# 4 is enough to catch e.g. ``~/projects/<org>/<repo>/mise.toml``.
_SCAN_MAX_DEPTH = 4


def _walk_tree(label: str, home_dir: Path) -> bool:
    print_header(f"Verifying symlinks from {label}")
    if not home_dir.is_dir():
        print_warning(f"{home_dir} is not a directory; skipping")
        return True
    return symlink_home_dir(home_dir)


def _is_stale_target(target_text: str) -> bool:
    return any(target_text.startswith(prefix) for prefix in _STALE_TARGET_PREFIXES)


def _scan_stale_symlinks(home: Path) -> list[Path]:
    """Return symlinks under $HOME (depth <= _SCAN_MAX_DEPTH) with a stale target."""
    stale: list[Path] = []

    def is_backup_dir(name: str) -> bool:
        return name.startswith(".dotfiles.") and name.endswith(".bck")

    def walk(directory: Path, depth: int) -> None:
        if depth > _SCAN_MAX_DEPTH:
            return
        try:
            entries = list(directory.iterdir())
        except (PermissionError, OSError):
            return
        for entry in entries:
            if entry.is_symlink():
                try:
                    target_text = str(entry.readlink())
                except OSError:
                    continue
                if _is_stale_target(target_text):
                    stale.append(entry)
                continue
            # Don't descend into symlinked directories (avoids loops via
            # ``home/.symlink-dir`` wholesale symlinks).
            if not entry.is_dir():
                continue
            if depth == 0:
                if entry.name in _SCAN_SKIP_TOPLEVEL or is_backup_dir(entry.name):
                    continue
            walk(entry, depth + 1)

    walk(home, 0)
    return stale


def _print_link(p: Path) -> None:
    try:
        target = p.readlink()
    except OSError:
        target = Path("?")
    print(f"  {p} -> {target}")


@click.command()
@click.option(
    "--clean",
    is_flag=True,
    help="Remove broken stale symlinks (default: report only).",
)
@click.option(
    "--scan-only",
    is_flag=True,
    help="Skip the symlink walk; just scan for stale links.",
)
def main(clean: bool, scan_only: bool) -> None:
    """Verify dotfile symlinks across public + private trees, then report stale ones."""
    home = Path.home()
    ok = True

    if not scan_only:
        if not _walk_tree("~/.dotfiles/home", DOTFILES / "home"):
            ok = False
        if not _walk_tree("~/.dotfiles-private/home", PRIVATE_DOTFILES / "home"):
            ok = False

    print_header("Scanning $HOME for stale symlinks")
    stale = _scan_stale_symlinks(home)

    if not stale:
        print_success("No stale symlinks found")
        sys.exit(0 if ok else 1)

    broken = [p for p in stale if not p.exists()]
    live = [p for p in stale if p.exists()]

    if broken:
        print_warning(f"{len(broken)} broken symlink(s) pointing at old layouts:")
        for p in broken:
            _print_link(p)

    if live:
        print_warning(
            f"{len(live)} live-but-stale symlink(s) (target still exists at old path):"
        )
        for p in live:
            _print_link(p)

    if broken:
        if clean:
            print_step(f"Removing {len(broken)} broken symlink(s)...")
            for p in broken:
                try:
                    p.unlink()
                    print_success(f"removed {p}")
                except OSError as exc:
                    print_error(f"failed to remove {p}: {exc}")
                    ok = False
        else:
            print_step("Re-run with --clean to remove broken symlinks")

    if live:
        print_step(
            "Live-but-stale symlinks left alone — repoint or remove them manually"
        )

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
