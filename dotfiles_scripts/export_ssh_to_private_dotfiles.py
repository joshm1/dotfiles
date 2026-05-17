#!/usr/bin/env python3
"""Export SSH private keys from 1Password into the private-dotfiles shared bucket.

Run this on a 1Password-enabled machine to seed the shared bucket. Opted-out
machines (``SSH_IDENTITY_BACKEND=disk-keys``) then pull the keys via
``sync-private-runtime``.

Usage::

    op signin           # interactive — ``op`` cannot biometric-prompt headless
    uv run export-ssh-to-private-dotfiles --dry-run
    uv run export-ssh-to-private-dotfiles

The list of items to export lives in
``~/.dotfiles-private/home/.config/dotfiles/ssh-export-items.yaml`` (this
repo is public — item names, vaults, and account URLs are user-specific
and stay in the private repo). Schema::

    items:
      - op_item: <1P item title>
        filename: <basename written under <shared>/ssh/>
        account: <1P account URL>
        vault: <vault containing the SSH-key item>

Each ``--item`` CLI argument has the form
``NAME:FILENAME:ACCOUNT:VAULT`` and overrides the YAML list when given.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import click
import yaml

from dotfiles_scripts.setup_utils import (
    PRIVATE_DOTFILES,
    print_error,
    print_header,
    print_step,
    print_success,
    print_warning,
)
from dotfiles_scripts.sync_private_runtime import resolve_shared_root

ITEMS_CONFIG_PATH = (
    PRIVATE_DOTFILES / "home" / ".config" / "dotfiles" / "ssh-export-items.yaml"
)


@dataclass(frozen=True)
class ExportItem:
    """A single 1Password SSH-key export."""

    op_item: str
    filename: str
    account: str
    vault: str


def _load_items_from_yaml() -> list[ExportItem] | None:
    """Read ``ITEMS_CONFIG_PATH``; return parsed items or None if absent.

    Raises ``click.UsageError`` if the file exists but is malformed — we
    don't want to silently fall back to "no items" when the user clearly
    intended to configure some.
    """
    if not ITEMS_CONFIG_PATH.is_file():
        return None
    try:
        loaded = yaml.safe_load(ITEMS_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise click.UsageError(f"could not read {ITEMS_CONFIG_PATH}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise click.UsageError(f"{ITEMS_CONFIG_PATH}: top level must be a mapping")
    raw_items = cast("dict[str, Any]", loaded).get("items")
    if not isinstance(raw_items, list):
        raise click.UsageError(f"{ITEMS_CONFIG_PATH}: 'items:' must be a list")

    parsed: list[ExportItem] = []
    for i, entry in enumerate(cast("list[Any]", raw_items)):
        if not isinstance(entry, dict):
            raise click.UsageError(
                f"{ITEMS_CONFIG_PATH} items[{i}]: each entry must be a mapping"
            )
        entry_map = cast("dict[str, Any]", entry)
        missing = [k for k in ("op_item", "filename", "account", "vault") if k not in entry_map]
        if missing:
            raise click.UsageError(
                f"{ITEMS_CONFIG_PATH} items[{i}]: missing required keys: {missing}"
            )
        parsed.append(
            ExportItem(
                op_item=str(entry_map["op_item"]),
                filename=str(entry_map["filename"]),
                account=str(entry_map["account"]),
                vault=str(entry_map["vault"]),
            )
        )
    return parsed


def _parse_item(spec: str) -> ExportItem:
    """Parse a CLI ``--item`` spec. All four fields are required."""
    parts = spec.split(":")
    if len(parts) != 4:
        raise click.BadParameter(
            f"--item must be NAME:FILENAME:ACCOUNT:VAULT (got {spec!r})"
        )
    return ExportItem(op_item=parts[0], filename=parts[1], account=parts[2], vault=parts[3])


def _ensure_op_signed_in() -> bool:
    """Best-effort check that ``op account list`` works without prompting."""
    try:
        result = subprocess.run(
            ["op", "account", "list"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        print_error("op CLI not installed. brew install 1password-cli.")
        return False
    except (OSError, subprocess.SubprocessError) as exc:
        print_error(f"op invocation failed: {exc}")
        return False
    if result.returncode != 0:
        print_error(
            "op is not signed in. Run `eval $(op signin)` in your shell first, "
            "then re-run this script."
        )
        return False
    return True


def _op_read(reference: str, account: str, verbose: bool) -> bytes | None:
    """Run ``op read --account ... <reference>``; return stdout bytes or None."""
    cmd = ["op", "read", "--account", account, reference]
    if verbose:
        print_step(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=False, capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        print_warning(f"op read failed: {exc}")
        return None
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        print_warning(f"op read {reference} → exit {result.returncode}: {stderr}")
        return None
    return result.stdout


def _atomic_write(dest: Path, content: bytes, mode: int) -> bool:
    """Write content to dest atomically; return True if changed."""
    if dest.is_file() and dest.read_bytes() == content:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        with tmp.open("wb") as f:
            f.write(content)
        tmp.chmod(mode)
        tmp.replace(dest)
    except OSError as exc:
        print_warning(f"Write failed for {dest}: {exc}")
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise
    return True


def _export_item(item: ExportItem, dest_dir: Path, dry_run: bool, verbose: bool) -> bool:
    """Fetch one item from 1Password and write its key files to dest_dir."""
    private_ref = f"op://{item.vault}/{item.op_item}/private key?ssh-format=openssh"
    public_ref = f"op://{item.vault}/{item.op_item}/public key"

    private_dest = dest_dir / item.filename
    public_dest = dest_dir / f"{item.filename}.pub"

    print_step(f"Exporting 1Password item {item.op_item!r} → {item.filename}")
    if dry_run:
        print(f"  would write: {private_dest} (0600)")
        print(f"  would write: {public_dest} (0644)")
        return True

    private_bytes = _op_read(private_ref, item.account, verbose)
    if private_bytes is None:
        print_warning(f"Skipping {item.op_item}: failed to read private key")
        return False

    public_bytes = _op_read(public_ref, item.account, verbose)
    if public_bytes is None:
        print_warning(
            f"Skipping {item.op_item}.pub: failed to read public key "
            "(private key was fetched but is paired with no public key field)"
        )
        return False

    # Normalize trailing newline on both — `op read` usually appends one.
    if not private_bytes.endswith(b"\n"):
        private_bytes += b"\n"
    if not public_bytes.endswith(b"\n"):
        public_bytes += b"\n"

    private_changed = _atomic_write(private_dest, private_bytes, 0o600)
    public_changed = _atomic_write(public_dest, public_bytes, 0o644)

    if private_changed:
        print_success(f"wrote {private_dest}")
    else:
        print(f"  unchanged: {private_dest}")
    if public_changed:
        print_success(f"wrote {public_dest}")
    else:
        print(f"  unchanged: {public_dest}")
    return True


@click.command()
@click.option(
    "--dry-run",
    is_flag=True,
    help="Print what would be written without contacting 1Password or touching disk.",
)
@click.option(
    "--item",
    "items",
    multiple=True,
    metavar="NAME:FILENAME:ACCOUNT:VAULT",
    help=(
        "Inline item override. Repeatable. Bypasses ssh-export-items.yaml. "
        "Useful for one-off exports without editing the config file."
    ),
)
@click.option("--verbose", is_flag=True, help="Print every op command invoked.")
def cli(dry_run: bool, items: tuple[str, ...], verbose: bool) -> None:
    """Export SSH private keys from 1Password into the private-dotfiles shared bucket."""
    if items:
        parsed: list[ExportItem] = [_parse_item(spec) for spec in items]
    else:
        loaded = _load_items_from_yaml()
        if loaded is None:
            print_error(
                f"No item list configured. Create {ITEMS_CONFIG_PATH} with:\n"
                "  items:\n"
                "    - op_item: <1P item title>\n"
                "      filename: <name written under <shared>/ssh/>\n"
                "      account: <1P account URL>\n"
                "      vault: <vault name>\n"
                "or pass one or more --item NAME:FILENAME:ACCOUNT:VAULT flags."
            )
            sys.exit(1)
        if not loaded:
            print_error(f"{ITEMS_CONFIG_PATH} has an empty 'items:' list; nothing to do.")
            sys.exit(1)
        parsed = loaded

    print_header("Export SSH keys → private-dotfiles shared bucket")

    if not dry_run and not _ensure_op_signed_in():
        sys.exit(1)

    shared = resolve_shared_root()
    if shared is None:
        print_error(
            "No cloud storage mounted (Google Drive or Dropbox); "
            "private-dotfiles shared bucket has nowhere to live."
        )
        sys.exit(1)
    dest_dir = shared / "ssh"
    print_step(f"Destination: {dest_dir}")

    failures = 0
    for item in parsed:
        if not _export_item(item, dest_dir, dry_run=dry_run, verbose=verbose):
            failures += 1

    if failures:
        print_error(f"{failures} of {len(parsed)} item(s) failed; see warnings above.")
        sys.exit(1)
    print_success(
        f"Exported {len(parsed)} item(s) to {dest_dir}. Opted-out machines will "
        "pick these up on their next `sync-private-runtime` tick."
    )


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
