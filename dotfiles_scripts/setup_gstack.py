#!/usr/bin/env python3
"""Set up gstack on this machine and register it with the configured agent
hosts (Claude Code, Codex, ...).

Two structural problems this fixes:

1. ``~/.claude/skills`` was a wholesale symlink into the dotfiles-private
   tree. When gstack/setup runs, it creates one shadow directory per
   gstack skill (each containing only a ``SKILL.md`` symlink into
   ``~/gstack/<name>/SKILL.md``). With the wholesale symlink, those
   shadows land *inside* dotfiles-private — polluting the repo with 46
   directories of generated content.

2. The pre-existing dotfiles-private checkout still has the 1 GB gstack
   source and the 46 shadow dirs from a previous setup run. Disk waste
   in the repo working tree.

What this script does (idempotent — safe to re-run on every machine):

- **Cleanup**: remove the 46 shadow dirs and the bulk
  ``home/.claude/skills/gstack/`` tree from dotfiles-private.
- **Split**: convert ``~/.claude/skills`` from a single symlink into a
  real directory. For each user-authored skill in dotfiles-private,
  create an individual symlink in the new real directory. gstack's
  later writes go to the real directory, never the repo.
- **Clone gstack**: ``git clone --depth 1 --single-branch`` to
  ``~/gstack`` if missing.
- **Run gstack/setup**: invoke ``~/gstack/setup --host claude`` so it
  installs into the real ``~/.claude/skills/`` dir.

After running once on a machine, future re-runs are no-ops other than
``git pull`` on gstack (and re-running gstack/setup, which is itself
idempotent).
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import click

from dotfiles_scripts.setup_utils import (
    PRIVATE_DOTFILES,
    print_error,
    print_header,
    print_step,
    print_success,
    print_warning,
)

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

# The agent-style skills tree on the local machine. After splitting (below),
# this is a real directory; each subdir is either a symlink into dotfiles-private
# (user-authored) or a real dir / symlink created by gstack/setup.
LOCAL_CLAUDE_SKILLS = Path.home() / ".claude" / "skills"

# Where user-authored skills live in dotfiles-private. Symlinked individually
# from LOCAL_CLAUDE_SKILLS after the split.
DOTFILES_SKILLS_DIR = PRIVATE_DOTFILES / "home" / ".claude" / "skills"

# Default location to clone gstack into. Outside both the dotfiles repo and
# Google Drive — gstack's 1 GB of node_modules / dist / etc. lives here.
GSTACK_REPO_DIR = Path.home() / "gstack"
GSTACK_DEFAULT_URL = "https://github.com/garrytan/gstack.git"

# A "gstack shadow" directory under DOTFILES_SKILLS_DIR is a directory that
# contains exactly one entry: a ``SKILL.md`` symlink whose target lives inside
# the gstack repo. These are byproducts of gstack/setup running while the
# wholesale symlink was in place. Safe to delete during cleanup.
SHADOW_NAMES_HINT = (
    str(GSTACK_REPO_DIR),
    "/.claude/skills/gstack/",
    "/gstack/",
)


# ---------------------------------------------------------------------------
# Cleanup pollution from dotfiles-private
# ---------------------------------------------------------------------------


def _is_gstack_shadow(d: Path) -> bool:
    """A dir under DOTFILES_SKILLS_DIR that holds only a SKILL.md symlink into gstack."""
    if not d.is_dir():
        return False
    children = list(d.iterdir())
    if len(children) != 1:
        return False
    skill_md = children[0]
    if skill_md.name != "SKILL.md" or not skill_md.is_symlink():
        return False
    target = str(skill_md.readlink())
    return any(hint in target for hint in SHADOW_NAMES_HINT)


def _clean_pollution() -> None:
    """Remove gstack-generated content from inside dotfiles-private."""
    print_header("Clean dotfiles-private of gstack pollution")

    # 1. The 1 GB stale gstack source under skills/gstack/ — gstack now lives at ~/gstack.
    stale_gstack = DOTFILES_SKILLS_DIR / "gstack"
    if stale_gstack.exists() and not stale_gstack.is_symlink():
        size_mb = _dir_size_mb(stale_gstack)
        print_step(f"removing stale gstack source: {stale_gstack} (~{size_mb} MB)")
        shutil.rmtree(stale_gstack)
        print_success("removed stale gstack source")
    elif stale_gstack.is_symlink():
        print_step(f"{stale_gstack} is already a symlink; leaving alone")
    else:
        print_step("no stale gstack source in dotfiles-private")

    # 2. Shadow dirs whose only content is a SKILL.md symlink into gstack.
    if not DOTFILES_SKILLS_DIR.is_dir():
        print_warning(f"{DOTFILES_SKILLS_DIR} not present; skipping shadow cleanup")
        return
    shadows = [d for d in DOTFILES_SKILLS_DIR.iterdir() if _is_gstack_shadow(d)]
    if not shadows:
        print_step("no gstack shadow directories present")
        return
    for d in sorted(shadows):
        print_step(f"removing shadow dir: {d.relative_to(PRIVATE_DOTFILES)}")
        shutil.rmtree(d)
    print_success(f"removed {len(shadows)} shadow dir(s)")


def _dir_size_mb(p: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(p, followlinks=False):
        for name in files:
            with contextlib.suppress(OSError):
                total += (Path(root) / name).stat().st_size
    return total // (1024 * 1024)


# ---------------------------------------------------------------------------
# Split ~/.claude/skills
# ---------------------------------------------------------------------------


def _split_claude_skills() -> None:
    """Convert ~/.claude/skills from a wholesale symlink into a real dir.

    For each subdir in DOTFILES_SKILLS_DIR (user-authored skills), create
    an individual symlink at LOCAL_CLAUDE_SKILLS/<name>. gstack/setup
    will later add its own entries (gstack source dir, per-gstack-skill
    SKILL.md shadows) into LOCAL_CLAUDE_SKILLS *as a real dir* — they
    won't bleed into dotfiles-private anymore.
    """
    print_header("Split ~/.claude/skills (wholesale symlink → real dir)")

    LOCAL_CLAUDE_SKILLS.parent.mkdir(parents=True, exist_ok=True)

    if LOCAL_CLAUDE_SKILLS.is_symlink():
        target = LOCAL_CLAUDE_SKILLS.readlink()
        try:
            inside_dotfiles = target.resolve().is_relative_to(PRIVATE_DOTFILES.resolve())
        except (OSError, AttributeError):
            inside_dotfiles = False
        if inside_dotfiles:
            print_step(f"removing wholesale symlink: {LOCAL_CLAUDE_SKILLS} → {target}")
            LOCAL_CLAUDE_SKILLS.unlink()
        else:
            print_warning(
                f"{LOCAL_CLAUDE_SKILLS} is a symlink but points outside dotfiles-private "
                f"({target}); leaving it alone"
            )
            return

    LOCAL_CLAUDE_SKILLS.mkdir(parents=True, exist_ok=True)

    if not DOTFILES_SKILLS_DIR.is_dir():
        print_warning(f"{DOTFILES_SKILLS_DIR} not present; nothing to symlink")
        return

    linked = 0
    skipped = 0
    for src in sorted(DOTFILES_SKILLS_DIR.iterdir()):
        if not src.is_dir():
            continue
        if src.name.startswith("."):
            # `.symlink-dir` and similar — not user-authored skill dirs.
            continue
        dst = LOCAL_CLAUDE_SKILLS / src.name
        # Already correct symlink?
        if dst.is_symlink() and dst.readlink() == src:
            skipped += 1
            continue
        if dst.exists() or dst.is_symlink():
            # Existing entry that doesn't match — likely a gstack shadow from
            # a prior run. Preserve gstack writes; only replace if it's our
            # own (broken) symlink.
            if dst.is_symlink():
                dst.unlink()
            else:
                print_warning(f"existing non-symlink at {dst}; leaving it alone")
                skipped += 1
                continue
        dst.symlink_to(src)
        linked += 1
    print_success(f"linked {linked} user-authored skill(s); {skipped} already in place")


# ---------------------------------------------------------------------------
# Clone + run gstack
# ---------------------------------------------------------------------------


def _clone_gstack(url: str, depth: int) -> bool:
    """Shallow-clone gstack to GSTACK_REPO_DIR if missing."""
    print_header("Clone gstack")
    if (GSTACK_REPO_DIR / ".git").is_dir():
        print_step(f"gstack already present at {GSTACK_REPO_DIR}")
        return True
    if GSTACK_REPO_DIR.exists():
        print_error(
            f"{GSTACK_REPO_DIR} exists but is not a git checkout; "
            "remove it manually before re-running"
        )
        return False
    cmd = ["git", "clone"]
    if depth > 0:
        cmd.extend(["--depth", str(depth), "--single-branch"])
    cmd.extend([url, str(GSTACK_REPO_DIR)])
    print_step(" ".join(cmd))
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        print_error(f"clone failed: {result.stderr.strip() or result.stdout.strip()}")
        return False
    print_success(f"cloned to {GSTACK_REPO_DIR}")
    return True


def _bun_available() -> bool:
    return shutil.which("bun") is not None


def _run_gstack_setup(host: str) -> bool:
    """Invoke ``~/gstack/setup --host <host>``.

    gstack/setup writes per-host install paths:
    - ``claude``: ``~/.claude/skills/`` (real dir thanks to _split_claude_skills)
    - ``codex``: ``~/.codex/skills/gstack/``
    - others: see ``gstack/setup --help``

    Each host invocation is independent and idempotent — gstack tracks
    its own installed marker, so re-runs are no-ops.
    """
    setup_script = GSTACK_REPO_DIR / "setup"
    if not setup_script.is_file():
        print_error(f"{setup_script} missing; clone may have failed")
        return False
    if not _bun_available():
        print_warning(
            "bun is not installed; skipping gstack/setup. "
            "Install bun (see https://bun.sh) and re-run `setup-gstack`."
        )
        return True
    print_step(f"{setup_script} --host {host}")
    # Inherit stdout/stderr — gstack/setup prints progress that is useful.
    result = subprocess.run(
        [str(setup_script), "--host", host],
        check=False,
        cwd=GSTACK_REPO_DIR,
    )
    if result.returncode != 0:
        print_error(f"gstack/setup --host {host} exited {result.returncode}")
        return False
    print_success(f"gstack/setup --host {host} complete")
    return True


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run(
    skip_cleanup: bool = False,
    skip_split: bool = False,
    skip_gstack: bool = False,
    gstack_url: str = GSTACK_DEFAULT_URL,
    gstack_depth: int = 1,
    gstack_hosts: str = "claude,codex",
) -> int:
    """Do the setup work. Returns 0 on success, non-zero on failure.

    Called both by the click CLI (``setup-gstack``) and by the dotfiles-setup
    orchestrator. Decoupled from click so the orchestrator can invoke this
    with defaults regardless of its own argv.
    """
    if not skip_cleanup:
        _clean_pollution()
    if not skip_split:
        _split_claude_skills()
    if not skip_gstack:
        if not _clone_gstack(gstack_url, gstack_depth):
            return 1
        hosts = [h.strip() for h in gstack_hosts.split(",") if h.strip()]
        if not hosts:
            print_error("gstack-hosts produced an empty list")
            return 1
        print_header(f"Run gstack setup ({', '.join(hosts)})")
        for host in hosts:
            if not _run_gstack_setup(host):
                return 1
    print()
    print_success("setup-gstack complete")
    print_step("verify: ls ~/.claude/skills | head")
    print_step("verify: ls ~/.codex/skills/gstack 2>/dev/null | head")
    print_step(
        "verify: cd ~/.dotfiles-private && git status   "
        "# should NOT show new untracked dirs"
    )
    return 0


def main() -> int:
    """Entry point for the dotfiles-setup orchestrator (no click args)."""
    return run()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command()
@click.option(
    "--skip-cleanup",
    is_flag=True,
    help="Skip removing gstack pollution from dotfiles-private.",
)
@click.option(
    "--skip-split",
    is_flag=True,
    help="Skip restructuring ~/.claude/skills.",
)
@click.option(
    "--skip-gstack",
    is_flag=True,
    help="Skip cloning gstack and running gstack/setup.",
)
@click.option(
    "--gstack-url",
    default=GSTACK_DEFAULT_URL,
    show_default=True,
    help="Override the gstack repo URL.",
)
@click.option(
    "--gstack-depth",
    default=1,
    show_default=True,
    type=int,
    help="git clone --depth value (0 = full history).",
)
@click.option(
    "--gstack-hosts",
    default="claude,codex",
    show_default=True,
    help=(
        "Comma-separated list of hosts to register gstack with. "
        "Each runs `gstack/setup --host <name>`. "
        "Valid: claude, codex, kiro, factory, opencode."
    ),
)
def cli(
    skip_cleanup: bool,
    skip_split: bool,
    skip_gstack: bool,
    gstack_url: str,
    gstack_depth: int,
    gstack_hosts: str,
) -> None:
    """Set up gstack on this machine and register it with each agent host.

    Idempotent: re-runs are safe and will only do work that hasn't been done.
    """
    sys.exit(
        run(
            skip_cleanup=skip_cleanup,
            skip_split=skip_split,
            skip_gstack=skip_gstack,
            gstack_url=gstack_url,
            gstack_depth=gstack_depth,
            gstack_hosts=gstack_hosts,
        )
    )


if __name__ == "__main__":
    cli()
