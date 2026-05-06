#!/usr/bin/env python3
"""Bootstrap the GitHub-backed private dotfiles repo on this machine.

Performs the one-time migration from the cloud-only model
(``~/.dotfiles-private`` → Google Drive shortcut) to the GitHub +
GDrive-runtime hybrid:

1. Make sure ``gh`` is installed and authenticated.
2. Create ``joshm1/dotfiles-private`` on GitHub if it doesn't exist
   (no-op on the second machine onward).
3. Clone or pull the repo to ``~/projects/joshm1/dotfiles-private``.
4. **First machine only**: walk the existing GDrive copy of
   ``~/.dotfiles-private/`` and copy the git-tracked subset into the
   fresh clone, write ``.gitignore``, commit, push.
5. Snapshot the current ``~/.dotfiles-private`` symlink target (for
   ``--rollback``) and retarget the symlink at the local clone.
6. Set up ``<gdrive>/dotfiles-runtime/${device_id}/`` (machine-specific
   runtime bucket) and run an initial ``sync_private_runtime --pull``.
7. Install + load the two LaunchAgents.

Subsequent machines: same script does steps 2–7 but step 4 is replaced
by ``git pull`` (the repo already has content).

Use ``--rollback`` to reverse step 5 only (re-point ``~/.dotfiles-private``
back at the snapshotted target). The clone, runtime dir, and LaunchAgents
are left in place so a re-bootstrap is fast.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import click

from dotfiles_scripts.setup_utils import (
    DOTFILES,
    PRIVATE_DOTFILES,
    PRIVATE_DOTFILES_REPO,
    gdrive_candidates,
    print_error,
    print_header,
    print_step,
    print_success,
    print_warning,
)
from dotfiles_scripts.sync_private_runtime import (
    GDRIVE_RUNTIME_DIR_NAME,
    HOME_RUNTIME_PATHS,
    REPO_RUNTIME_PATHS,
)

CACHE_DIR = Path.home() / ".cache" / "dotfiles-private"
SYMLINK_SNAPSHOT = CACHE_DIR / "old-symlink-target.txt"

# Resolution order for the private GitHub repo identifier (e.g. "alice/secrets"):
#
#   1. ``--repo owner/name`` CLI flag — explicit override.
#   2. ``DOTFILES_PRIVATE_REPO`` env var — same shape, useful for
#      non-interactive setups (e.g. baking into a machine's shell config).
#   3. Inferred owner from the public dotfiles repo's origin remote +
#      ``dotfiles-private`` as the name. So someone cloning their own fork
#      at ``user/dotfiles`` automatically targets ``user/dotfiles-private``.
#   4. Interactive prompt — ask the user.
#   5. (Non-interactive only) error out with a clear message.
#
# Resolution happens at cli() entry, NOT at import; the module-level
# variables below start empty and are filled in once we know the answer.
_DEFAULT_GH_REPO_NAME = "dotfiles-private"

GH_FULL: str = ""
GH_OWNER: str = ""
GH_REPO: str = ""


def _infer_gh_owner() -> str | None:
    """Return the owner of the public dotfiles repo's origin remote, or None
    if it can't be determined."""
    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            check=False,
            capture_output=True,
            text=True,
            cwd=DOTFILES,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    # Matches git@github.com:owner/repo(.git) and https://github.com/owner/repo(.git)
    match = re.search(r"github\.com[:/]([^/]+)/[^/.]+", result.stdout.strip())
    return match.group(1) if match else None


def _resolve_gh_full(cli_override: str | None) -> str:
    """Pick the private repo identifier via CLI > env > infer > prompt.

    Raises click.UsageError when nothing works and stdin isn't a TTY.
    """
    candidates: list[tuple[str, str]] = []
    if cli_override:
        candidates.append(("--repo", cli_override))
    env = os.environ.get("DOTFILES_PRIVATE_REPO", "").strip()
    if env:
        candidates.append(("DOTFILES_PRIVATE_REPO", env))
    for source, value in candidates:
        if "/" not in value:
            raise click.UsageError(
                f"{source}={value!r} is missing a '/' (expected owner/name)"
            )
        return value

    owner = _infer_gh_owner()
    if owner:
        return f"{owner}/{_DEFAULT_GH_REPO_NAME}"

    # Couldn't infer; ask the user.
    if not sys.stdin.isatty():
        raise click.UsageError(
            "Could not determine the private dotfiles repo identifier. Set "
            "the DOTFILES_PRIVATE_REPO env var or pass --repo owner/name."
        )
    print_step(
        "Could not infer the GitHub owner from the public dotfiles repo's origin remote."
    )
    answer = click.prompt(
        "Enter the private repo identifier (owner/name)", type=str
    ).strip()
    if "/" not in answer:
        raise click.UsageError(f"{answer!r} is missing a '/' (expected owner/name)")
    return answer


def _set_gh_identifier(full: str) -> None:
    """Populate the module-level GH_* globals from a resolved owner/name."""
    global GH_FULL, GH_OWNER, GH_REPO
    GH_FULL = full
    GH_OWNER, GH_REPO = full.split("/", 1)

LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
PLIST_NAMES = (
    "com.dotfiles-private.check-repo.plist",
    "com.dotfiles-private.sync-runtime.plist",
)

# Files to seed the first-machine commit with. Globs are evaluated relative to
# the source root (the resolved ``~/.dotfiles-private/``). Anything under the
# matched path is copied unless it matches a SKIP pattern below.
GIT_INCLUDE_GLOBS: tuple[str, ...] = (
    # Hierarchical zshrc fragments
    "home/.zshrc.before",
    "home/.zshrc.before.*",
    "home/.zshrc.after",
    "home/.zshrc.after.*",
    # Device-specific / app config
    "home/.config/dotfiles/.dotfiles-config",
    "home/.config/dotfiles/.dotfiles-config.*",
    "home/.config/atuin/config.toml",
    "home/.config/gh/config.yml",
    "home/.config/gh/hosts.yml",
    "home/.config/gcloud/configurations/config_*",
    "home/.config/snapback/manifest.toml",
    # Git config
    "home/.gitconfig",
    "home/.gitconfig*",
    "home/.gitignore",
    # Other small dotfiles
    "home/.npmrc",
    "home/.dotfiles.yaml",
    "home/.ssh/config",
    # SSH public keys — safe to track (they're public by definition).
    "home/.ssh/*.pub",
    # Preserve wholesale-symlink behavior for ~/.ssh on new bootstraps.
    # symlink_home_dir checks for this marker and symlinks the parent dir
    # as a unit instead of recursing into it. Without it, gitignored
    # sensitive files (known_hosts, authorized_keys) wouldn't be visible
    # from $HOME because they live only in dotfiles-private.
    "home/.ssh/.symlink-dir",
    # Hand-curated Claude / agent assets (skill source, command source, agent definitions)
    "home/.claude/skills/**",
    "home/.claude/agents/**",
    "home/.claude/commands/**",
    # NOTE: ~/.agents/ is intentionally not synced; revisit if/when needed.
    # Stable binaries (stay in git rather than being duplicated per-machine in GDrive)
    "home/bin/jabba",
    "home/bin/codex-responses-api-proxy",
    # Repo-root files
    ".gitconfig",
    ".gitconfig.*",
    ".gitignore",
    ".gpg-keys.yaml",
    "zshrc/zshrc.*",
)

# Patterns that, even if matched by an include glob above, should NOT be
# copied into the repo on first migration. (Test fixtures and skill log
# directories under .claude/skills/ and .agents/skills/ live alongside the
# hand-curated content; we want to seed only the source.)
GIT_EXCLUDE_GLOBS: tuple[str, ...] = (
    "**/test/fixtures/**",
    "**/logs/**",
    "**/__pycache__/**",
    "**/.venv/**",
    "**/venv/**",
    "**/node_modules/**",
    "**/.next/**",
    "**/.nuxt/**",
    "**/.turbo/**",
    "**/.pytest_cache/**",
    "**/.mypy_cache/**",
    "**/.ruff_cache/**",
    "**/.tox/**",
    "**/bower_components/**",
    "**/.DS_Store",
)

GITIGNORE_TEXT = """\
# Per-device shell history (synced via GDrive runtime, machine-specific)
zsh_history/

# REPL / interpreter history (synced via GDrive runtime)
home/.pry_history
home/.node_repl_history
home/.psql_history

# Ephemeral
home/.clipboard

# Skill / agent log directories
home/.claude/skills/*/logs/

# Test fixtures and downloaded blobs
home/.claude/skills/*/test/fixtures/

# gstack source — installed by setup-gstack to ~/gstack and symlinked into
# ~/.claude/skills/ at runtime. Should never be a real subdir of the repo.
home/.claude/skills/gstack/
home/.claude/skills/gstack

# Agent skills tree intentionally not tracked here
home/.agents/

# SSH directory: whitelist what's allowed in git, ignore everything else.
# Keeps private keys / credentials out by default — even files with names
# that wouldn't match the conventional id_* / *.pem / *.key patterns.
# Sensitive files (known_hosts, authorized_keys, *.pem, id_*, etc.) sync
# via the GDrive runtime bucket instead.
home/.ssh/*
home/.ssh/.*
!home/.ssh/config
!home/.ssh/*.pub
!home/.ssh/.symlink-dir
!home/.ssh/.gitkeep

# Cache directories
**/node_modules/
**/.venv/
**/venv/
**/__pycache__/
**/.pytest_cache/
**/.mypy_cache/
**/.ruff_cache/
**/.next/
**/.nuxt/
**/.tox/
**/.turbo/
**/bower_components/

# OS
.DS_Store
"""


# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _gh_authed() -> bool:
    if not _have("gh"):
        return False
    result = subprocess.run(
        ["gh", "auth", "status"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _existing_clone_is_ours() -> bool:
    """True if PRIVATE_DOTFILES_REPO is a git checkout of the expected GitHub repo."""
    if not (PRIVATE_DOTFILES_REPO / ".git").exists():
        return False
    result = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"],
        check=False,
        capture_output=True,
        text=True,
        cwd=PRIVATE_DOTFILES_REPO,
    )
    if result.returncode != 0:
        return False
    url = result.stdout.strip()
    return GH_FULL in url


def _preflight(force: bool) -> bool:
    if not _have("git"):
        print_error("git not installed.")
        return False
    if not _have("rsync"):
        print_error("rsync not installed.")
        return False
    if not PRIVATE_DOTFILES.is_dir():
        print_error(f"{PRIVATE_DOTFILES} is not a directory; cloud private dotfiles not set up.")
        return False
    # gh is only required when we'd need to create/probe the GitHub repo via API.
    # If the user has already cloned the expected remote into PRIVATE_DOTFILES_REPO
    # locally (over SSH, for example), we can do the whole bootstrap without gh.
    if not _existing_clone_is_ours() and not _gh_authed():
        print_error(
            "gh CLI not installed or not authenticated, and no existing local clone of "
            f"{GH_FULL} was found. Either run `gh auth login` or pre-clone the repo to "
            f"{PRIVATE_DOTFILES_REPO}."
        )
        return False
    if PRIVATE_DOTFILES_REPO.exists() and not _existing_clone_is_ours() and not force:
        print_error(
            f"{PRIVATE_DOTFILES_REPO} already exists and isn't a clone of {GH_FULL}. "
            "Re-run with --force to overwrite, or use --rollback to reverse a previous bootstrap."
        )
        return False
    return True


# ---------------------------------------------------------------------------
# GitHub repo + clone
# ---------------------------------------------------------------------------


def _gh_repo_exists() -> bool:
    result = subprocess.run(
        ["gh", "repo", "view", GH_FULL, "--json", "name"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _gh_repo_has_commits() -> bool:
    """True if the GitHub repo has at least one commit on its default branch."""
    result = subprocess.run(
        ["gh", "repo", "view", GH_FULL, "--json", "defaultBranchRef", "-q",
         ".defaultBranchRef.name"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() != ""


def _gh_repo_create() -> bool:
    print_step(f"creating GitHub repo {GH_FULL} (private)")
    result = subprocess.run(
        ["gh", "repo", "create", GH_FULL, "--private",
         "--description", "Personal private dotfiles (managed by joshm1/dotfiles)"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print_error(f"gh repo create failed: {result.stderr.strip() or result.stdout.strip()}")
        return False
    print_success(f"created {GH_FULL}")
    return True


def _try_clone(transport: str, url: str) -> tuple[bool, bool, str]:
    """Run ``git clone`` (or ``gh repo clone``) once. Returns (ok, empty_upstream, message).

    ``empty_upstream`` is True when the clone succeeded against an empty
    GitHub repo (different code paths that we want to treat uniformly via
    _git_init_with_remote). Otherwise False.
    """
    if transport == "ssh" or transport == "https":
        cmd = ["git", "clone", url, str(PRIVATE_DOTFILES_REPO)]
    elif transport == "gh":
        cmd = ["gh", "repo", "clone", GH_FULL, str(PRIVATE_DOTFILES_REPO)]
    else:
        raise ValueError(f"unknown transport: {transport}")
    print_step(" ".join(cmd))
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    msg = (result.stderr.strip() or result.stdout.strip()).strip()
    if result.returncode != 0:
        return False, False, msg
    # An empty upstream repo sometimes leaves the destination missing entirely.
    empty = "empty" in msg.lower() and not PRIVATE_DOTFILES_REPO.exists()
    return True, empty, msg


def _git_clone() -> bool:
    """Clone PRIVATE_DOTFILES_REPO with SSH preferred, gh-CLI as fallback.

    Order of attempts:
      1. ``git clone git@github.com:<owner>/<repo>.git`` — fast, no gh
         dependency, works on any machine with an SSH key registered.
      2. ``gh repo clone <owner>/<repo>`` — uses gh's stored auth, works
         when SSH keys aren't set up on the new machine.

    Empty-upstream case (no commits yet) is treated identically to a
    success but routed through _git_init_with_remote so we end up with a
    well-formed local clone either way.
    """
    print_step(f"cloning {GH_FULL} into {PRIVATE_DOTFILES_REPO}")
    PRIVATE_DOTFILES_REPO.parent.mkdir(parents=True, exist_ok=True)

    # SSH first.
    ssh_url = f"git@github.com:{GH_FULL}.git"
    ok, empty, msg = _try_clone("ssh", ssh_url)
    if ok:
        if empty:
            print_step("upstream is empty; initializing local repo and wiring remote")
            return _git_init_with_remote()
        print_success("cloned (ssh)")
        return True
    print_warning(f"ssh clone failed; falling back to gh: {msg.splitlines()[-1] if msg else ''}")

    # Fallback to gh.
    ok, empty, msg = _try_clone("gh", "")
    if ok:
        if empty:
            print_step("upstream is empty; initializing local repo and wiring remote")
            return _git_init_with_remote()
        print_success("cloned (gh)")
        return True

    # Neither worked.
    if "empty" in msg.lower() and not PRIVATE_DOTFILES_REPO.exists():
        # gh can fail on empty repos in older versions; fall through to init.
        print_step("upstream is empty; initializing local repo and wiring remote")
        return _git_init_with_remote()
    print_error(f"clone failed: {msg}")
    return False


def _git_init_with_remote() -> bool:
    PRIVATE_DOTFILES_REPO.mkdir(parents=True, exist_ok=True)
    cmds = [
        ["git", "init", "-b", "main"],
        ["git", "remote", "add", "origin", f"git@github.com:{GH_FULL}.git"],
    ]
    for c in cmds:
        result = subprocess.run(c, check=False, cwd=PRIVATE_DOTFILES_REPO,
                                capture_output=True, text=True)
        if result.returncode != 0:
            print_error(f"{' '.join(c)}: {result.stderr.strip() or result.stdout.strip()}")
            return False
    return True


# ---------------------------------------------------------------------------
# First-machine migration: copy git-worthy files into the clone
# ---------------------------------------------------------------------------


def _path_is_excluded(path: Path, source_root: Path) -> bool:
    rel = path.relative_to(source_root)
    return any(rel.match(p) for p in GIT_EXCLUDE_GLOBS)


def _safe_is_file(p: Path) -> bool:
    try:
        return p.is_file()
    except OSError:
        return False


def _safe_is_dir(p: Path) -> bool:
    try:
        return p.is_dir()
    except OSError:
        return False


def _safe_walk_files(root: Path, skipped: list[Path]) -> list[Path]:
    """Walk ``root`` yielding regular files. Records OSError-prone paths in ``skipped``."""
    out: list[Path] = []

    def _on_error(e: OSError) -> None:
        if e.filename:
            skipped.append(Path(e.filename))

    for current_dir, _dirs, files in os.walk(root, followlinks=True, onerror=_on_error):
        cur = Path(current_dir)
        for name in files:
            p = cur / name
            if _safe_is_file(p):
                out.append(p)
            else:
                skipped.append(p)
    return out


def _expand_includes(source_root: Path) -> tuple[list[Path], list[Path]]:
    """Resolve include globs against ``source_root``. Returns (paths, skipped).

    Skipped paths are files/dirs that raised OSError (typically PermissionError
    from GDrive's FileProvider) — surfaced to the user so they know what
    didn't make it into the migration.
    """
    seen: set[Path] = set()
    out: list[Path] = []
    skipped: list[Path] = []

    for pattern in GIT_INCLUDE_GLOBS:
        try:
            matches = list(source_root.glob(pattern))
        except OSError as e:
            if e.filename:
                skipped.append(Path(e.filename))
            continue
        for match in matches:
            if _safe_is_dir(match):
                for child in _safe_walk_files(match, skipped):
                    if not _path_is_excluded(child, source_root) and child not in seen:
                        seen.add(child)
                        out.append(child)
            elif (
                _safe_is_file(match)
                and not _path_is_excluded(match, source_root)
                and match not in seen
            ):
                seen.add(match)
                out.append(match)
    out.sort()
    return out, skipped


def _copy_into_repo(source_root: Path) -> int:
    """Copy git-worthy files from the GDrive copy into the fresh clone.

    Preserves directory layout. Returns the count of files copied.
    Skips (with warning) any source file we can't read.
    """
    files, skipped = _expand_includes(source_root)
    print_step(f"migrating {len(files)} file(s) from {source_root}")
    copied = 0
    copy_errors: list[tuple[Path, str]] = []
    for src in files:
        rel = src.relative_to(source_root)
        dst = PRIVATE_DOTFILES_REPO / rel
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst, follow_symlinks=True)
            copied += 1
        except OSError as e:
            copy_errors.append((src, str(e)))

    if skipped or copy_errors:
        # Write the full list out so the user can grep/diff it; terminal output
        # is capped to keep the bootstrap scannable.
        log_path = CACHE_DIR / "migration-skipped.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", encoding="utf-8") as f:
            f.write(f"# {len(skipped)} walk-skipped path(s)\n")
            for p in skipped:
                f.write(f"walk-skip\t{p}\n")
            f.write(f"\n# {len(copy_errors)} copy-fail entry(ies)\n")
            for p, err in copy_errors:
                f.write(f"copy-fail\t{p}\t{err}\n")

        print_warning(
            f"{len(skipped)} path(s) inaccessible during walk; "
            f"{len(copy_errors)} file(s) failed to copy"
        )
        cap = 15
        for p in skipped[:cap]:
            print_warning(f"  walk-skip: {p}")
        if len(skipped) > cap:
            print_warning(f"  …{len(skipped) - cap} more walk-skip entries (see log)")
        for p, err in copy_errors[:cap]:
            print_warning(f"  copy-fail: {p}: {err}")
        if len(copy_errors) > cap:
            print_warning(f"  …{len(copy_errors) - cap} more copy-fail entries (see log)")
        print_warning(f"full list: {log_path}")
        print_warning(
            "If those files matter, fix the source (often a stale GDrive cache) and "
            "re-run with --force, or copy them in by hand and amend the migration commit."
        )
    return copied


def _write_gitignore() -> None:
    (PRIVATE_DOTFILES_REPO / ".gitignore").write_text(GITIGNORE_TEXT, encoding="utf-8")
    print_success("wrote .gitignore")


def _initial_commit_and_push() -> bool:
    cmds: list[list[str]] = [
        ["git", "add", "-A"],
        ["git", "commit", "-m", "Initial migration from GDrive cloud-only storage"],
        ["git", "push", "-u", "origin", "main"],
    ]
    for c in cmds:
        result = subprocess.run(c, check=False, cwd=PRIVATE_DOTFILES_REPO,
                                capture_output=True, text=True)
        if result.returncode != 0:
            print_error(f"{' '.join(c)}: {result.stderr.strip() or result.stdout.strip()}")
            return False
    print_success("committed and pushed initial migration")
    return True


# ---------------------------------------------------------------------------
# Symlink retargeting + rollback snapshot
# ---------------------------------------------------------------------------


def _save_symlink_snapshot() -> None:
    """Snapshot the pre-migration ~/.dotfiles-private target for --rollback.

    Only writes when the symlink still points at its ORIGINAL target (i.e.
    a previous bootstrap hasn't already retargeted it at the local clone).
    Re-bootstraps preserve the existing snapshot so rollback still works.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if not PRIVATE_DOTFILES.is_symlink():
        return
    current = PRIVATE_DOTFILES.readlink()
    try:
        already_retargeted = current.resolve() == PRIVATE_DOTFILES_REPO.resolve()
    except OSError:
        already_retargeted = False
    if already_retargeted:
        if SYMLINK_SNAPSHOT.is_file():
            print_step(f"symlink already retargeted; preserving snapshot at {SYMLINK_SNAPSHOT}")
        else:
            print_warning(
                "symlink already points at the local clone but no rollback snapshot exists; "
                "rollback will not work without one (write the original GDrive path manually "
                f"to {SYMLINK_SNAPSHOT} if you need it)"
            )
        return
    SYMLINK_SNAPSHOT.write_text(str(current), encoding="utf-8")
    print_success(f"snapshotted old symlink target → {SYMLINK_SNAPSHOT}")


def _retarget_symlink() -> None:
    if PRIVATE_DOTFILES.is_symlink() or PRIVATE_DOTFILES.exists():
        PRIVATE_DOTFILES.unlink()
    PRIVATE_DOTFILES.symlink_to(PRIVATE_DOTFILES_REPO)
    print_success(f"{PRIVATE_DOTFILES} → {PRIVATE_DOTFILES_REPO}")


def _rollback_symlink() -> int:
    if not SYMLINK_SNAPSHOT.is_file():
        print_error(f"no snapshot at {SYMLINK_SNAPSHOT}; cannot rollback")
        return 1
    target = Path(SYMLINK_SNAPSHOT.read_text(encoding="utf-8").strip())
    if PRIVATE_DOTFILES.is_symlink() or PRIVATE_DOTFILES.exists():
        PRIVATE_DOTFILES.unlink()
    PRIVATE_DOTFILES.symlink_to(target)
    print_success(f"reverted {PRIVATE_DOTFILES} → {target}")
    return 0


# ---------------------------------------------------------------------------
# GDrive runtime root
# ---------------------------------------------------------------------------


def _device_id() -> str | None:
    p = Path.home() / ".device_id"
    if not p.is_file():
        return None
    try:
        return p.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _seed_runtime_root() -> bool:
    """Create ``<gdrive>/dotfiles-runtime/${device_id}/`` and seed runtime files into it."""
    dev = _device_id()
    if not dev:
        print_warning("device id missing (~/.device_id); skipping runtime seed")
        return False
    candidates = gdrive_candidates()
    if not candidates:
        print_warning("no Google Drive account mounted; skipping runtime seed")
        return False
    runtime_root = candidates[0] / GDRIVE_RUNTIME_DIR_NAME / dev
    runtime_root.mkdir(parents=True, exist_ok=True)
    print_success(f"runtime root ready: {runtime_root}")

    # Seed: rsync each runtime path that exists locally up to GDrive so other
    # machines (and this machine on next bootstrap) see it. Empty / missing
    # sources are skipped silently inside sync_path.
    from dotfiles_scripts.sync_private_runtime import sync_path  # local import to avoid cycle

    repo = PRIVATE_DOTFILES_REPO
    for rel in REPO_RUNTIME_PATHS:
        ok, msg = sync_path(repo / rel, runtime_root / "repo" / rel, timeout=600)
        if ok:
            print_step(f"seeded repo runtime: {rel}")
        else:
            print_warning(msg)
    for rel in HOME_RUNTIME_PATHS:
        ok, msg = sync_path(Path.home() / rel, runtime_root / "home" / rel, timeout=1800)
        if ok:
            print_step(f"seeded home runtime: {rel}")
        else:
            print_warning(msg)
    return True


# ---------------------------------------------------------------------------
# LaunchAgents
# ---------------------------------------------------------------------------


def _install_launch_agents() -> bool:
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    repo_plist_dir = Path.home() / ".dotfiles" / "home" / "Library" / "LaunchAgents"
    for name in PLIST_NAMES:
        src = repo_plist_dir / name
        dst = LAUNCH_AGENTS_DIR / name
        if not src.is_file():
            print_error(f"missing plist in repo: {src}")
            return False
        if dst.is_symlink() and dst.resolve() == src.resolve():
            pass  # already linked
        else:
            if dst.exists() or dst.is_symlink():
                dst.unlink()
            dst.symlink_to(src)
            print_success(f"linked {dst.name}")
        # (re)load
        subprocess.run(["launchctl", "unload", str(dst)], check=False, capture_output=True)
        result = subprocess.run(
            ["launchctl", "load", "-w", str(dst)],
            check=False, capture_output=True, text=True,
        )
        if result.returncode != 0:
            print_warning(f"launchctl load failed for {name}: "
                          f"{result.stderr.strip() or result.stdout.strip()}")
        else:
            print_success(f"loaded {name}")
    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command()
@click.option(
    "--force",
    is_flag=True,
    help="Bootstrap even if PRIVATE_DOTFILES_REPO already exists (destructive).",
)
@click.option(
    "--rollback",
    is_flag=True,
    help="Reverse a previous bootstrap: re-point ~/.dotfiles-private back at its old target.",
)
@click.option(
    "--skip-confirm",
    is_flag=True,
    help="Skip the interactive confirmation. For unattended re-bootstraps.",
)
@click.option(
    "--repo",
    "repo_override",
    metavar="OWNER/NAME",
    default=None,
    help=(
        "Private dotfiles GitHub repo identifier (e.g. 'alice/my-secrets'). "
        "Overrides the inferred owner and the default name 'dotfiles-private'. "
        "Same effect via env var DOTFILES_PRIVATE_REPO."
    ),
)
def cli(
    force: bool,
    rollback: bool,
    skip_confirm: bool,
    repo_override: str | None,
) -> None:
    """Migrate ~/.dotfiles-private from cloud-only storage to GitHub + cloud runtime."""
    _set_gh_identifier(_resolve_gh_full(repo_override))
    print_step(f"private repo: {GH_FULL}")

    if rollback:
        sys.exit(_rollback_symlink())

    print_header("Bootstrap private dotfiles repo")

    if not _preflight(force):
        sys.exit(1)

    if not skip_confirm:
        click.confirm(
            f"Migrate {PRIVATE_DOTFILES} from GDrive-only to a GitHub clone "
            f"at {PRIVATE_DOTFILES_REPO}? Old GDrive copy stays intact as backup.",
            abort=True,
            default=True,
        )

    # Step 1–2: ensure the repo exists on GitHub. Skip if we already have a
    # valid local clone of it (the user pre-cloned and gh may not be authed).
    if _existing_clone_is_ours():
        print_step(f"existing local clone of {GH_FULL} found; skipping gh repo probe")
    elif _gh_repo_exists():
        print_step(f"{GH_FULL} already exists on GitHub")
    elif not _gh_repo_create():
        sys.exit(1)

    # Step 3: clone (or accept existing clone if it points at the right remote).
    if PRIVATE_DOTFILES_REPO.exists():
        if _existing_clone_is_ours():
            print_step(f"using existing clone at {PRIVATE_DOTFILES_REPO}")
        elif force:
            print_warning(f"--force given; clearing {PRIVATE_DOTFILES_REPO}")
            shutil.rmtree(PRIVATE_DOTFILES_REPO)
            if not _git_clone():
                sys.exit(1)
        else:
            print_error(f"{PRIVATE_DOTFILES_REPO} unexpectedly present; use --force.")
            sys.exit(1)
    elif not _git_clone():
        sys.exit(1)

    # Step 4: first-machine migration vs subsequent pull. The clone tells us
    # everything: an empty local checkout means this machine is the first one
    # to populate the repo (subsequent clones would arrive with content).
    home_dir_in_repo = PRIVATE_DOTFILES_REPO / "home"
    is_first_machine = not home_dir_in_repo.is_dir() or not any(home_dir_in_repo.iterdir())
    if is_first_machine:
        # Source = the existing GDrive symlink target.
        source_root = PRIVATE_DOTFILES.resolve()
        copied = _copy_into_repo(source_root)
        _write_gitignore()
        if copied == 0:
            print_warning("no files matched include globs; nothing to migrate")
        if not _initial_commit_and_push():
            sys.exit(1)
    else:
        print_step("repo already has content on origin; nothing to migrate from GDrive")

    # Step 5: snapshot + retarget the symlink
    _save_symlink_snapshot()
    _retarget_symlink()

    # Step 6: GDrive runtime root + initial seed
    _seed_runtime_root()

    # Step 7: install + load LaunchAgents
    if sys.platform == "darwin":
        _install_launch_agents()
    else:
        print_warning("non-macOS; skipping launchd setup")

    print()
    print_success("bootstrap complete")
    print_step("verify: readlink ~/.dotfiles-private")
    print_step("verify: cd ~/.dotfiles-private && git status")
    print_step("verify: check-private-repo --status")
    print_step("verify: sync-private-runtime --status")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
