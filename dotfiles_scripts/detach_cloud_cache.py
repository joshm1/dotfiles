#!/usr/bin/env python3
"""Detach regenerable build artifacts from the cloud-synced private dotfiles.

Walks ``~/.dotfiles-private/`` for known cache/build directories
(``node_modules``, ``.venv``, ``venv``, ``__pycache__``, etc.) and moves them
out to ``~/.cache/dotfiles-private/<mirror-path>/``. The cloud copy is
replaced with an absolute-target symlink, so the cloud carries only the
(small) symlink and not the gigabytes of regenerable artifacts.

On other machines: when the cloud syncs the symlink, the local cache target
won't exist initially. This script also ensures empty cache target dirs
exist for any incoming symlinks pointing into ``~/.cache/dotfiles-private/``,
so the symlink resolves (to an empty dir) instead of dangling. Re-running
whatever populated the original directory (``npm install`` / ``uv sync`` /
etc.) will fill it back in.

Designed to run on a launchd schedule (hourly). Idempotent.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import click

from dotfiles_scripts.setup_utils import (
    PRIVATE_DOTFILES,
    print_header,
    print_step,
    print_success,
    print_warning,
)

CACHE_ROOT = Path.home() / ".cache" / "dotfiles-private"

# Default patterns: directory *names* that mean "regenerable build/cache state".
# Conservative on purpose — does not include `dist`, `build`, or `target`,
# which are common project directory names that may be intentional.
DEFAULT_PATTERNS: tuple[str, ...] = (
    "node_modules",
    ".venv",
    "venv",
    "virtenv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".turbo",
    ".next",
    ".nuxt",
    ".tox",
    "bower_components",
)


def _resolve_private_root() -> Path | None:
    """Return the resolved cloud-synced private dotfiles root, or None."""
    if not PRIVATE_DOTFILES.is_dir():
        return None
    # Resolve so we walk the actual cloud filesystem, not via the symlink. This
    # matters because os.walk on the symlink path would still work, but we want
    # rel-paths anchored at the resolved root for clarity in cache placement.
    return PRIVATE_DOTFILES.resolve()


def _detach_one(source: Path, root: Path, dry_run: bool) -> bool:
    """Detach ``source`` (a real directory) to the local cache.

    Returns True if action was taken (or would be in dry-run).
    """
    if source.is_symlink() or not source.is_dir():
        return False

    rel = source.relative_to(root)
    target = CACHE_ROOT / rel

    if dry_run:
        print_step(f"[dry-run] {source} → {target}")
        return True

    print_step(f"detach {rel}")
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        # Previous detach ran here. Trust the cache copy; drop the cloud copy.
        # (If the user had newer content in the cloud copy, they'd see it after
        # populating the cache via their normal install flow.)
        shutil.rmtree(source)
    else:
        shutil.move(str(source), str(target))

    # Use an absolute symlink target so other machines (and this machine across
    # symlink-resolution boundaries) all interpret the link the same way.
    os.symlink(target, source)
    return True


def _ensure_symlink_targets(root: Path, dry_run: bool) -> int:
    """Create empty cache directories for any symlinks pointing into the cache.

    Used on the receiving end after a peer machine detaches and syncs the
    symlink: that symlink's local target won't exist until something populates
    it. Creating it as an empty directory makes the symlink resolve cleanly.
    """
    count = 0
    for path in root.rglob("*"):
        if not path.is_symlink():
            continue
        try:
            link = Path(os.readlink(path))
        except OSError:
            continue
        target = link if link.is_absolute() else (path.parent / link).resolve()
        try:
            target.relative_to(CACHE_ROOT)
        except ValueError:
            continue
        if target.exists():
            continue
        if dry_run:
            print_step(f"[dry-run] mkdir empty {target}")
        else:
            target.mkdir(parents=True, exist_ok=True)
            print_step(f"created empty cache target {target}")
        count += 1
    return count


@click.command()
@click.option("--dry-run", is_flag=True, help="Show what would happen, don't change anything.")
@click.option(
    "--patterns",
    default=",".join(DEFAULT_PATTERNS),
    show_default=True,
    help="Comma-separated directory names to detach.",
)
def cli(dry_run: bool, patterns: str) -> None:
    """Detach build artifacts from ~/.dotfiles-private/ to ~/.cache/dotfiles-private/."""
    root = _resolve_private_root()
    if root is None:
        print_warning(
            f"{PRIVATE_DOTFILES} is not a directory; cloud private dotfiles not set up"
        )
        sys.exit(0)

    pattern_set = {p.strip() for p in patterns.split(",") if p.strip()}

    print_header("Detach regenerable artifacts from cloud")
    print(f"Cloud tree: {root}")
    print(f"Cache root: {CACHE_ROOT}")
    print(f"Patterns:   {sorted(pattern_set)}")
    print()

    detached = 0
    # Walk without following symlinks, and skip descending into directories
    # we just detached (to avoid os.walk choking on the freshly-created link).
    for current_root, dirs, _files in os.walk(root, followlinks=False):
        # Don't descend into anything that's already a symlink.
        dirs[:] = [d for d in dirs if not Path(current_root, d).is_symlink()]
        # Detach any matched dirs at this level, then prune them so we don't recurse.
        for name in list(dirs):
            if name in pattern_set:
                if _detach_one(Path(current_root, name), root, dry_run):
                    detached += 1
                dirs.remove(name)

    ensured = _ensure_symlink_targets(root, dry_run)

    print()
    print_success(f"Detached {detached} dir(s); ensured {ensured} incoming symlink target(s)")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
