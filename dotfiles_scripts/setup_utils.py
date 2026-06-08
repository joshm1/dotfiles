"""Shared utilities for setup scripts."""

from __future__ import annotations

import re
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
#
# Once ``setup-private-repo`` has run, this symlink points at the local
# GitHub clone (resolved via PRIVATE_DOTFILES_REPO_PATH config). Until then
# it points at the cloud-synced copy. Code paths that just need a working
# directory (git ops with cwd=..., file reads, rsync sources) should route
# through this symlink — the resolved clone path is only required during the
# bootstrap itself (see get_private_repo_path).
PRIVATE_DOTFILES = Path.home() / ".dotfiles-private"

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

# Per-directory config consumed by the symlink walker. Currently supports a
# ``symlinks:`` block that overrides the default same-name mapping; see
# ``_resolve_symlinks_directives``. Also consumed by ``setup_dropbox`` for
# ``chmod:`` rules.
DOTFILES_YAML = ".dotfiles.yaml"

# Files to skip when traversing
SKIP_FILES = {
    ".DS_Store", ".git", SYMLINK_DIR_TAG, DOTFILES_YAML,
    # build / dependency / cache artifacts that must never be symlinked into $HOME
    # (e.g. a Python project living inside the dotfiles tree produces these).
    ".venv", "__pycache__", "node_modules", "build", "dist",
    ".pytest_cache", ".ruff_cache", ".mypy_cache", ".turbo", ".coverage",
}

# Name suffixes that are likewise never symlinked (globs SKIP_FILES can't express).
SKIP_SUFFIXES = (".pyc", ".pyo", ".egg-info")


def _read_dotfiles_yaml(directory: Path) -> dict[str, Any]:
    """Read ``.dotfiles.yaml`` from ``directory``; return an empty dict on miss."""
    config_file = directory / DOTFILES_YAML
    if not config_file.is_file():
        return {}
    try:
        import yaml

        loaded = yaml.safe_load(config_file.read_text())
    except (yaml.YAMLError, ImportError, OSError) as exc:
        print_warning(f"Could not read {config_file}: {exc}")
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _resolve_symlinks_directives(
    directory: Path, device_id: str
) -> tuple[dict[str, str], set[str]]:
    """Parse the ``symlinks:`` block of ``directory/.dotfiles.yaml``.

    Returns a tuple ``(active, variants)``:

    * ``active`` maps the home-side filename to the repo-side filename for
      the current device. Each entry overrides the default same-name
      symlinking for that one file.
    * ``variants`` is the set of filenames in ``directory`` that match any
      ``use:`` template (treating ``${device_id}`` as a wildcard). The
      walker should skip these during normal iteration so other devices'
      copies do not get auto-symlinked into ``$HOME``.

    Schema::

        symlinks:
          manifest.toml:
            use: manifest.toml.${device_id}
    """
    config = _read_dotfiles_yaml(directory)
    raw = config.get("symlinks")
    if not isinstance(raw, dict):
        return {}, set()

    active: dict[str, str] = {}
    variants: set[str] = set()

    for home_name, spec in raw.items():
        if not isinstance(home_name, str) or not isinstance(spec, dict):
            continue
        use_template = spec.get("use")
        if not isinstance(use_template, str):
            continue

        active[home_name] = use_template.replace("${device_id}", device_id)

        if "${device_id}" in use_template:
            prefix, _, suffix = use_template.partition("${device_id}")
            for f in directory.iterdir():
                if (
                    f.name.startswith(prefix)
                    and f.name.endswith(suffix)
                    and len(f.name) > len(prefix) + len(suffix)
                ):
                    variants.add(f.name)
        else:
            variants.add(use_template)

    return active, variants


def _read_device_id() -> str:
    """Return the contents of ``~/.device_id``, or empty string if absent."""
    device_file = Path.home() / ".device_id"
    if device_file.is_file():
        return device_file.read_text().strip()
    return ""


# ``KEY=value`` / ``export KEY=value`` lines in the .dotfiles-config files,
# with optional surrounding quotes. Matches what shell sourcing produces
# without actually executing the file (so we don't need a subprocess).
_CONFIG_LINE_RE = re.compile(
    r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$"
)


def read_dotfiles_config(key: str) -> str | None:
    """Resolve a setting from the hierarchical ``~/.config/dotfiles/.dotfiles-config*`` files.

    Mirrors the shell ``_source_hierarchy`` in ``home/.zshrc`` (lines 6-14):
    starts from the base file and walks dotted ``device_id`` segments
    (e.g. ``mac`` then ``mac.primary``), with later files overriding
    earlier ones. Returns the last value seen for ``key`` across the chain,
    or ``None`` if absent.
    """
    base = Path.home() / ".config" / "dotfiles" / ".dotfiles-config"
    device_id = _read_device_id()

    candidates: list[Path] = [base]
    if device_id:
        prefix = ""
        for segment in device_id.split("."):
            prefix = f"{prefix}.{segment}" if prefix else segment
            candidates.append(base.with_name(f"{base.name}.{prefix}"))

    value: str | None = None
    for path in candidates:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            stripped = line.lstrip()
            if not stripped or stripped.startswith("#"):
                continue
            match = _CONFIG_LINE_RE.match(line)
            if match is None or match.group(1) != key:
                continue
            raw = match.group(2)
            # Strip a matching pair of surrounding quotes; leave mismatched
            # quotes alone (shell would error on those anyway).
            if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
                raw = raw[1:-1]
            value = raw
    return value


def get_private_repo_path() -> Path:
    """Return the resolved local clone path for the private dotfiles repo.

    Reads ``PRIVATE_DOTFILES_REPO_PATH`` from the hierarchical
    ``~/.config/dotfiles/.dotfiles-config*`` files. Exits the process with a
    clear error if unset — this value is required by the ``setup-private-repo``
    bootstrap and there is intentionally no default. Other code paths should
    use ``PRIVATE_DOTFILES`` (the symlink) instead.
    """
    value = read_dotfiles_config("PRIVATE_DOTFILES_REPO_PATH")
    if not value:
        print_error(
            "PRIVATE_DOTFILES_REPO_PATH is not set in ~/.config/dotfiles/.dotfiles-config*"
        )
        print(
            "  Set it in the most-specific .dotfiles-config file for this machine.\n"
            "  Example: PRIVATE_DOTFILES_REPO_PATH=$HOME/projects/<you>/<repo>"
        )
        sys.exit(1)
    import os

    return Path(os.path.expandvars(value)).expanduser()


def get_private_repo_gh() -> str:
    """Return the ``owner/name`` identifier of the private dotfiles GitHub repo.

    Reads ``PRIVATE_DOTFILES_REPO_GH`` from ``.dotfiles-config*``. Exits with a
    clear error if unset or malformed. Required by ``setup-private-repo`` to
    create / clone / push the remote.
    """
    value = read_dotfiles_config("PRIVATE_DOTFILES_REPO_GH")
    if not value:
        print_error(
            "PRIVATE_DOTFILES_REPO_GH is not set in ~/.config/dotfiles/.dotfiles-config*"
        )
        print(
            "  Set it in the most-specific .dotfiles-config file for this machine.\n"
            "  Example: PRIVATE_DOTFILES_REPO_GH=<github-user>/<repo>"
        )
        sys.exit(1)
    if "/" not in value:
        print_error(
            f"PRIVATE_DOTFILES_REPO_GH={value!r} is missing a '/' (expected owner/name)"
        )
        sys.exit(1)
    return value


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

    # Already routed via a wholesale-symlinked ancestor: target itself isn't
    # a symlink, but its resolved path is the same file as source. Treat as
    # a no-op so we don't rename the source out from under ourselves and
    # then create a self-referential symlink in its place.
    if target.exists() and target.resolve() == source.resolve():
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


def symlink_home_dir(home_dir: Path) -> bool:
    """
    Traverse home_dir and symlink everything to $HOME.

    If a directory contains .symlink-dir, symlink the directory itself.
    Otherwise, recurse into it and symlink children.

    A directory may also contain a ``.dotfiles.yaml`` with a ``symlinks:``
    block to remap individual files (e.g., pick a per-device variant); see
    ``_resolve_symlinks_directives``.

    Returns True if every symlink succeeded, False otherwise.
    """
    success = True
    device_id = _read_device_id()

    def process_dir(src_dir: Path, target_dir: Path) -> None:
        nonlocal success

        active, variants = _resolve_symlinks_directives(src_dir, device_id)

        for src in sorted(src_dir.iterdir()):
            if src.name in SKIP_FILES or src.name.endswith(SKIP_SUFFIXES):
                continue
            # Skip files that are device-keyed variants (other devices' copies,
            # or the current device's copy which is handled via `active` below).
            if src.name in variants:
                continue

            target = target_dir / src.name

            if src.is_dir():
                if (src / SYMLINK_DIR_TAG).exists():
                    if not create_symlink(src, target):
                        success = False
                elif target.is_symlink() and target.resolve() == src.resolve():
                    # Some ancestor in $HOME is already wholesale-symlinked to
                    # this source dir — recursing would loop back through the
                    # symlink and corrupt the repo. Treat as already linked.
                    continue
                else:
                    target.mkdir(parents=True, exist_ok=True)
                    process_dir(src, target)
            else:
                if not create_symlink(src, target):
                    success = False

        # Apply explicit per-file overrides (e.g., manifest.toml -> manifest.toml.mac.primary).
        for home_name, repo_filename in active.items():
            repo_path = src_dir / repo_filename
            if not repo_path.is_file():
                if not device_id:
                    print_warning(
                        f"~/.device_id missing; cannot resolve symlinks "
                        f"directive for {src_dir / home_name}"
                    )
                else:
                    print_warning(
                        f"symlinks override: {repo_path} not found "
                        f"(device_id={device_id!r}); skipping {home_name}"
                    )
                success = False
                continue
            if not create_symlink(repo_path, target_dir / home_name):
                success = False

    process_dir(home_dir, Path.home())
    return success
