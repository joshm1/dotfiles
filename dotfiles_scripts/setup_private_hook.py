#!/usr/bin/env python3
"""Run per-machine setup hooks supplied by the private dotfiles repo.

This is a generic extension point: the public setup orchestrator knows
nothing about what the hooks do. If ``~/.dotfiles-private/setup-hooks/``
exists, every executable file inside it is run once, in sorted order,
with the working tree's identity exported into the environment:

- ``DOTFILES_DEVICE_ID``   — contents of ``~/.device_id`` (e.g. ``mac.primary``)
- ``DOTFILES_PRIVATE_DIR`` — resolved ``~/.dotfiles-private``
- ``DOTFILES_PUBLIC_DIR``  — the public dotfiles repo

Hooks are best-effort: a non-zero exit is reported as a warning but never
fails the overall setup. Each hook is responsible for its own idempotency
and for gating itself to the machines it applies to (e.g. reading a flag
out of ``~/.config/dotfiles/.dotfiles-config*``).

Drop-in convention (``run-parts`` style): name hooks ``NN-name`` so the
order is explicit, e.g. ``10-cubic.sh``. Non-executable files and dotfiles
are ignored, so a hook can be disabled with ``chmod -x`` without deleting it.
"""

from __future__ import annotations

import os
import subprocess
import sys

from dotfiles_scripts.setup_device_id import get_device_id
from dotfiles_scripts.setup_utils import (
    DOTFILES_REPO,
    get_private_dotfiles,
    print_header,
    print_step,
    print_success,
    print_warning,
)

HOOKS_DIRNAME = "setup-hooks"


def main() -> int:
    """Run all executable hooks in ``~/.dotfiles-private/setup-hooks/``."""
    print_header("Private setup hooks")

    private = get_private_dotfiles()
    if private is None:
        print_step("~/.dotfiles-private not available; skipping private hooks")
        return 0

    hooks_dir = private / HOOKS_DIRNAME
    if not hooks_dir.is_dir():
        print_step(f"no private hooks ({hooks_dir} not present)")
        return 0

    hooks = [
        p
        for p in sorted(hooks_dir.iterdir())
        if p.is_file() and not p.name.startswith(".") and os.access(p, os.X_OK)
    ]
    if not hooks:
        print_step(f"no executable hooks in {hooks_dir}")
        return 0

    env = {
        **os.environ,
        "DOTFILES_DEVICE_ID": get_device_id() or "",
        "DOTFILES_PRIVATE_DIR": str(private),
        "DOTFILES_PUBLIC_DIR": str(DOTFILES_REPO),
    }

    for hook in hooks:
        print_step(f"running {hook.name}")
        result = subprocess.run([str(hook)], check=False, env=env)
        if result.returncode != 0:
            print_warning(f"{hook.name} exited {result.returncode} (continuing)")

    print_success("Private setup hooks complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
