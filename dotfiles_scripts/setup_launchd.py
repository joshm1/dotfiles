#!/usr/bin/env python3
"""Load any LaunchAgents this repo ships into the user's launchd context.

Each ``home/Library/LaunchAgents/*.plist`` file in the repo is symlinked to
``~/Library/LaunchAgents/`` by the regular home-symlink walk. This module
makes sure they're also *loaded* (so the schedules actually run) and
re-loaded if their content changed since the last run.
"""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

from dotfiles_scripts.setup_utils import (
    print_header,
    print_step,
    print_success,
    print_warning,
)

LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
DOTFILES_LABEL_PREFIX = "com.dotfiles-private."


def _is_mac() -> bool:
    return platform.system() == "Darwin"


def _ensure_cache_dir() -> None:
    cache = Path.home() / ".cache" / "dotfiles-private"
    cache.mkdir(parents=True, exist_ok=True)


def _load_plist(plist: Path) -> bool:
    label = plist.stem  # e.g. com.dotfiles-private.detach-cloud-cache
    # If already loaded, unload first so an updated plist replaces the cached version.
    subprocess.run(
        ["launchctl", "unload", str(plist)],
        check=False,
        capture_output=True,
    )
    result = subprocess.run(
        ["launchctl", "load", "-w", str(plist)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print_warning(f"launchctl load failed for {label}: {result.stderr.strip() or result.stdout.strip()}")
        return False
    print_success(f"loaded LaunchAgent: {label}")
    return True


def main() -> int:
    """Main entry point."""
    print_header("Loading LaunchAgents")
    if not _is_mac():
        print_step("Not macOS — skipping launchd setup")
        return 0
    if not LAUNCH_AGENTS_DIR.is_dir():
        print_step(f"{LAUNCH_AGENTS_DIR} does not exist yet — skipping")
        return 0

    _ensure_cache_dir()

    plists = sorted(LAUNCH_AGENTS_DIR.glob(f"{DOTFILES_LABEL_PREFIX}*.plist"))
    if not plists:
        print_step("No dotfiles LaunchAgents found")
        return 0
    for plist in plists:
        _load_plist(plist)
    return 0


if __name__ == "__main__":
    sys.exit(main())
