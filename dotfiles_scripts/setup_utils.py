"""Shared utilities for setup scripts."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, cast

# Configuration
DOTFILES_REPO = Path.home() / "projects" / "joshm1" / "dotfiles"
DOTFILES = Path.home() / ".dotfiles"
DROPBOX_DIR = Path.home() / "Dropbox"

# Single canonical local pointer to the user's cloud-synced "private" dotfiles
# tree. Setup scripts and shell config always read through this path; cloud
# provider discovery only happens when this symlink does not yet exist (or is
# being repointed by the migration script). Named to match the public
# ``~/.dotfiles`` symlink (DOTFILES) for visual grouping.
PRIVATE_DOTFILES = Path.home() / ".dotfiles-private"

# Local clone of the private GitHub repo, when the user has migrated off the
# pure-cloud storage model. ``setup-private-repo`` retargets PRIVATE_DOTFILES
# to point here. Mirrors the DOTFILES_REPO / DOTFILES split.
PRIVATE_DOTFILES_REPO = Path.home() / "projects" / "joshm1" / "dotfiles-private"

# Names this script will look for inside each cloud root, in order. Newer
# machines use "dotfiles-private" (matches the local symlink name); older
# machines on Dropbox keep the legacy "dotfiles" directory.
_PRIVATE_DIR_NAMES: tuple[str, ...] = ("dotfiles-private", "dotfiles")

# Cloud-storage discovery: probe Google Drive (preferred) then Dropbox, returning
# the first cloud root whose requested subdir exists. Google Drive's
# account-scoped path is discovered via glob so the email address is not
# hardcoded — works for any Google account signed into "Drive for Desktop".
_GDRIVE_BASE = Path.home() / "Library" / "CloudStorage"
_GDRIVE_ACCOUNT_GLOB = "GoogleDrive-*"
_GDRIVE_ROOT_NAME = "My Drive"


def gdrive_candidates() -> list[Path]:
    """All ``GoogleDrive-*/My Drive`` roots currently mounted, sorted for stability."""
    if not _GDRIVE_BASE.is_dir():
        return []
    return sorted(
        (account / _GDRIVE_ROOT_NAME)
        for account in _GDRIVE_BASE.glob(_GDRIVE_ACCOUNT_GLOB)
        if (account / _GDRIVE_ROOT_NAME).is_dir()
    )


def _cloud_candidates() -> list[Path]:
    """Ordered cloud roots to probe (Google Drive accounts, then Dropbox)."""
    return [*gdrive_candidates(), DROPBOX_DIR]


def discover_cloud_private_dotfiles() -> Path | None:
    """Return the first ``<cloud>/<private-dir>`` directory that exists.

    Probes each cloud root in order, then each known directory name. Used only
    when the local ``~/.private-dotfiles`` symlink needs to be (re)created.
    """
    for base in _cloud_candidates():
        for name in _PRIVATE_DIR_NAMES:
            candidate = base / name
            if candidate.is_dir():
                return candidate
    return None


def get_private_dotfiles() -> Path | None:
    """Return the resolved ``~/.private-dotfiles`` directory, or None if absent.

    Returns the symlink path itself (not the target) when it resolves to an
    existing directory; callers can ``.resolve()`` if they need the real path.
    """
    if PRIVATE_DOTFILES.is_dir():
        return PRIVATE_DOTFILES
    return None


def ensure_private_dotfiles_symlink() -> Path | None:
    """Make sure ``~/.private-dotfiles`` points at a real cloud-synced directory.

    Behavior:
    - If the symlink already exists and resolves to a directory, leaves it
      alone and returns the path.
    - If it does not exist (or is broken), probes available cloud providers
      (Google Drive accounts, then Dropbox) for a ``private-dotfiles`` or
      ``dotfiles`` subdirectory and creates the symlink if found.
    - Returns ``None`` if no candidate exists (caller should warn the user).
    """
    if PRIVATE_DOTFILES.is_dir():
        return PRIVATE_DOTFILES

    target = discover_cloud_private_dotfiles()
    if target is None:
        return None

    # Replace any stale broken symlink before creating the new one.
    if PRIVATE_DOTFILES.is_symlink() or PRIVATE_DOTFILES.exists():
        PRIVATE_DOTFILES.unlink()
    PRIVATE_DOTFILES.symlink_to(target)
    return PRIVATE_DOTFILES

# Backup directory (created lazily)
_backup_dir: Path | None = None


def get_backup_dir() -> Path:
    """Get a timestamped backup directory (created once per session)."""
    global _backup_dir
    if _backup_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        _backup_dir = Path.home() / f".dotfiles.{timestamp}.bck"
    return _backup_dir


def print_header(msg: str) -> None:
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}\n")


def print_step(msg: str) -> None:
    """Print a step message."""
    print(f"→ {msg}")


def print_success(msg: str) -> None:
    """Print a success message."""
    print(f"✓ {msg}")


def print_warning(msg: str) -> None:
    """Print a warning message."""
    print(f"⚠ {msg}")


def print_error(msg: str) -> None:
    """Print an error message."""
    print(f"✗ {msg}", file=sys.stderr)


def run_cmd(
    cmd: list[str] | str,
    check: bool = True,
    shell: bool = False,
    capture: bool = False,
    cwd: Path | None = None,
    quiet: bool = False,
    **kwargs: Any,
) -> subprocess.CompletedProcess[Any]:
    """Run a command and return the result.

    Additional keyword arguments are passed directly to subprocess.run().
    Common examples include: env, timeout, stdin, stdout, stderr, encoding, etc.
    """
    # Type narrowing: kwargs is dict[str, Any] at runtime
    typed_kwargs: dict[str, Any] = kwargs

    if capture:
        typed_kwargs.setdefault("capture_output", True)
        typed_kwargs.setdefault("text", True)
    if cwd:
        typed_kwargs["cwd"] = cwd
    if not quiet:
        cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
        print_step(f"Running: {cmd_str}")

    # cast() required: subprocess.run has complex overloads that pyright cannot resolve
    # when using **kwargs. The return type depends on runtime kwargs values (text, capture_output).
    # Using Any for the generic parameter is correct since stdout/stderr can be str, bytes, or None.
    return cast(
        subprocess.CompletedProcess[Any],
        subprocess.run(cmd, check=check, shell=shell, **typed_kwargs),
    )


# Tag file that indicates a directory should be symlinked as a whole
SYMLINK_DIR_TAG = ".symlink-dir"

# Files to skip when traversing
SKIP_FILES = {".DS_Store", ".git", SYMLINK_DIR_TAG, ".dotfiles.yaml"}


def create_symlink(source: Path, target: Path, backup_dir: Path | None = None) -> bool:
    """Create a symlink, backing up existing files if needed."""
    # Don't create broken symlinks
    if not source.exists():
        print_warning(f"Skipping {target.name}: source does not exist ({source})")
        return False

    # Already correct symlink?
    if target.is_symlink() and target.resolve() == source.resolve():
        print(f"  {target.name} already linked")
        return True

    # Backup existing file/directory
    if target.exists() or target.is_symlink():
        if backup_dir is None:
            backup_dir = get_backup_dir()
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / target.name
        print_warning(f"Backing up {target} → {backup_path}")
        target.rename(backup_path)

    # Create parent directory if needed
    target.parent.mkdir(parents=True, exist_ok=True)

    # Create symlink
    target.symlink_to(source)
    print_success(f"Linked {target} → {source}")
    return True


def symlink_home_dir(home_dir: Path) -> None:
    """
    Traverse home_dir and symlink everything to $HOME.

    If a directory contains .symlink-dir, symlink the directory itself.
    Otherwise, recurse into it and symlink children.
    """

    def process_dir(src_dir: Path, target_dir: Path) -> None:
        for src in sorted(src_dir.iterdir()):
            if src.name in SKIP_FILES:
                continue

            target = target_dir / src.name

            if src.is_dir():
                if (src / SYMLINK_DIR_TAG).exists():
                    create_symlink(src, target)
                else:
                    target.mkdir(parents=True, exist_ok=True)
                    process_dir(src, target)
            else:
                create_symlink(src, target)

    process_dir(home_dir, Path.home())
