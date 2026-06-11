#!/usr/bin/env python3
"""Point ``~/.ssh/config.identity`` at the right backend variant.

Reads ``SSH_IDENTITY_BACKEND`` from the hierarchical
``~/.config/dotfiles/.dotfiles-config*`` files. Two valid values:

- ``disk-keys`` (default) — links to ``config.identity.disk-keys``, which
  uses ``IdentityFile`` referencing ``~/.ssh/id_*``. Keys are synced from the
  private-dotfiles shared bucket via ``sync-private-runtime``.
- ``1password`` — links to ``config.identity.1password``, which sets
  ``IdentityAgent`` for each host (1Password SSH agent serves the keys).

On first switch to ``disk-keys``, kicks ``sync-private-runtime --pull`` so
keys are in place before SSH is first used. On switch back to ``1password``,
moves any lingering ``id_*`` private keys to a timestamped backup directory
rather than deleting (never destructive on a non-recoverable secret).
"""

from __future__ import annotations

import datetime
import shutil
import subprocess
import sys
from pathlib import Path

from dotfiles_scripts.setup_utils import (
    DEFAULT_SSH_IDENTITY_BACKEND,
    PRIVATE_DOTFILES,
    SSH_IDENTITY_BACKENDS,
    print_header,
    print_step,
    print_success,
    print_warning,
    read_dotfiles_config,
)

VALID_BACKENDS = SSH_IDENTITY_BACKENDS
DEFAULT_BACKEND = DEFAULT_SSH_IDENTITY_BACKEND


def _ssh_dir() -> Path:
    """SSH dir on disk — resolves through the ``~/.ssh`` wholesale symlink."""
    return PRIVATE_DOTFILES / "home" / ".ssh"


def _resolve_backend() -> str:
    backend = read_dotfiles_config("SSH_IDENTITY_BACKEND") or DEFAULT_BACKEND
    if backend not in VALID_BACKENDS:
        print_warning(
            f"SSH_IDENTITY_BACKEND={backend!r} is not one of {VALID_BACKENDS!r}; "
            f"falling back to {DEFAULT_BACKEND!r}"
        )
        return DEFAULT_BACKEND
    return backend


def _swap_identity_symlink(backend: str, ssh_dir: Path) -> bool:
    """Point ``ssh_dir/config.identity`` at the requested variant. Idempotent."""
    variant_name = f"config.identity.{backend}"
    variant = ssh_dir / variant_name
    if not variant.is_file():
        print_warning(f"Variant file missing: {variant}")
        return False

    link = ssh_dir / "config.identity"
    current = link.readlink() if link.is_symlink() else None
    if current is not None and str(current) == variant_name:
        print_success(f"config.identity already → {variant_name}")
        return True

    # Atomic replace: write to .tmp symlink then rename onto the target.
    tmp = ssh_dir / "config.identity.tmp"
    if tmp.exists() or tmp.is_symlink():
        tmp.unlink()
    tmp.symlink_to(variant_name)
    tmp.replace(link)
    print_success(f"config.identity → {variant_name}")
    return True


def _pull_keys_now() -> bool:
    """Best-effort ``sync-private-runtime --pull`` so keys land before SSH use."""
    print_step("Pulling SSH keys from private-dotfiles shared bucket")
    try:
        result = subprocess.run(
            ["uv", "run", "sync-private-runtime", "--pull"],
            check=False,
            timeout=300,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print_warning(f"sync-private-runtime invocation failed: {exc}")
        return False
    if result.returncode != 0:
        print_warning(
            f"sync-private-runtime --pull exited {result.returncode}; "
            "keys may not be in place yet"
        )
        return False
    return True


def _pull_keys_from_op() -> bool:
    """Best-effort ``pull-ssh-keys-from-op`` — fetch disk keys from 1Password.

    Preferred over the shared bucket: private keys come straight from the
    source of truth and never touch cloud storage. Requires the 1Password CLI
    to be installed *and* signed in — both checked up front so an unconfigured
    machine degrades quietly to the shared-bucket fallback (``_pull_keys_now``)
    instead of erroring. ``op`` needs an interactive unlock, so on a fresh
    bootstrap (before the user has signed into 1Password) this returns False;
    re-run ``setup-ssh-identity`` once signed in to pull from op.
    """
    if shutil.which("op") is None:
        print_step("1Password CLI (op) not installed yet; skipping op key pull")
        return False
    # ``op read`` triggers an interactive Touch ID unlock — ``op account list``
    # succeeds even when the vault is *locked*, so it can't tell us whether a
    # read would hang. Gate on a TTY instead: unattended runs skip op (falling
    # back to the shared bucket) rather than blocking on a prompt nobody answers.
    if not sys.stdin.isatty():
        print_step(
            "non-interactive shell; skipping the 1Password pull (needs Touch ID). "
            "Run `uv run setup-ssh-identity` in a terminal to pull from op."
        )
        return False
    # Lazy import: only needed on the disk-keys path.
    from dotfiles_scripts.op_ssh import ensure_op_signed_in

    if not ensure_op_signed_in():
        print_step(
            "After `op signin`, run `uv run setup-ssh-identity` to pull keys from 1Password."
        )
        return False
    print_step("Pulling SSH keys from 1Password (op)")
    try:
        result = subprocess.run(
            ["uv", "run", "pull-ssh-keys-from-op"],
            check=False,
            timeout=180,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print_warning(f"pull-ssh-keys-from-op invocation failed: {exc}")
        return False
    if result.returncode != 0:
        print_warning(
            f"pull-ssh-keys-from-op exited {result.returncode}; "
            "falling back to the shared bucket"
        )
        return False
    return True


def _tighten_private_key_perms(ssh_dir: Path) -> None:
    """Force 0600 on any non-``.pub`` ``id_*`` / ``*.pem`` after pull."""
    for entry in ssh_dir.iterdir():
        if not entry.is_file():
            continue
        if entry.name.endswith(".pub"):
            continue
        if not (entry.name.startswith("id_") or entry.name.endswith(".pem")):
            continue
        try:
            entry.chmod(0o600)
        except OSError as exc:
            print_warning(f"chmod 0600 failed for {entry}: {exc}")


def _backup_stale_private_keys(ssh_dir: Path) -> int:
    """Move ``id_*`` (non-pub) files into a timestamped backup dir.

    Used when reverting from ``disk-keys`` back to ``1password`` — we don't
    want stale on-disk keys taking precedence over the 1Password agent, but
    deleting them is too dangerous if the user didn't actually mean to revert.
    """
    stale: list[Path] = []
    for entry in ssh_dir.iterdir():
        if not entry.is_file():
            continue
        if entry.name.endswith(".pub"):
            continue
        if entry.name.startswith("id_") or entry.name.endswith(".pem"):
            stale.append(entry)
    if not stale:
        return 0
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = ssh_dir / f".opt-out-backup-{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for src in stale:
        dst = backup_dir / src.name
        shutil.move(str(src), str(dst))
    print_warning(
        f"Moved {len(stale)} stale private key(s) to {backup_dir}. "
        "Remove manually once you're sure 1Password is providing the keys."
    )
    return len(stale)


def main() -> int:
    print_header("SSH identity backend")

    ssh_dir = _ssh_dir()
    if not ssh_dir.is_dir():
        print_warning(
            f"{ssh_dir} not found; private-dotfiles symlink may not be in place yet"
        )
        return 0

    backend = _resolve_backend()
    print_step(f"Backend: {backend} (SSH_IDENTITY_BACKEND from .dotfiles-config*)")

    if not _swap_identity_symlink(backend, ssh_dir):
        return 1

    if backend == "disk-keys":
        has_local_private_key = any(
            (ssh_dir / f.name).is_file()
            for f in ssh_dir.iterdir()
            if f.name.startswith("id_") and not f.name.endswith(".pub")
        )
        # No on-disk key yet → fetch one. 1Password first (source of truth),
        # shared bucket as fallback.
        if not has_local_private_key and not _pull_keys_from_op():
            _pull_keys_now()
        _tighten_private_key_perms(ssh_dir)
    else:  # 1password
        _backup_stale_private_keys(ssh_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
