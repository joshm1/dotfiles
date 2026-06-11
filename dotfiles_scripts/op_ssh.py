#!/usr/bin/env python3
"""Shared 1Password ↔ on-disk SSH-key plumbing.

Two commands build on this module:

- ``export-ssh-to-private-dotfiles`` — 1Password → the GDrive *shared bucket*
  (legacy hop; opted-out machines later pull from there via
  ``sync-private-runtime``).
- ``pull-ssh-keys-from-op`` — 1Password → the local ``~/.ssh`` *on disk*
  directly. Preferred: private keys never touch cloud storage.

Both read the same manifest
(``~/.dotfiles-private/home/.config/dotfiles/ssh-export-items.yaml``) and use
``op read`` to fetch key material.

An item may be identified two ways in the manifest (or via CLI):

1. Human-readable ``op_item`` + ``vault`` + ``account`` fields.
2. A 1Password *item link* — the "Copy Item Link" URL, e.g.
   ``https://start.1password.com/open/i?a=…&v=…&i=…&h=…`` — supplied as a
   ``link`` field (plus ``filename``). The vault/item *ids* in the link are
   unambiguous where titles can collide or be renamed.

``op read`` cannot biometric-prompt headless, so callers must already have an
unlocked ``op`` session (``eval "$(op signin)"`` / Touch ID) before fetching.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, urlparse

import click
import yaml

from dotfiles_scripts.setup_utils import (
    PRIVATE_DOTFILES,
    print_error,
    print_step,
    print_success,
    print_warning,
)

ITEMS_CONFIG_PATH = (
    PRIVATE_DOTFILES / "home" / ".config" / "dotfiles" / "ssh-export-items.yaml"
)


@dataclass(frozen=True)
class OpSshItem:
    """A single 1Password SSH-key item to fetch.

    ``vault`` and ``op_item`` may be names OR opaque ids — ``op read`` accepts
    both. Item-link entries populate them with the ids from the URL.
    """

    op_item: str
    filename: str
    account: str
    vault: str


def parse_op_link(url: str) -> dict[str, str]:
    """Parse a 1Password "Copy Item Link" URL into its components.

    Returns a dict with ``account`` (``a``), ``vault`` (``v``), ``item``
    (``i``) and ``host`` (``h``). Raises ``click.UsageError`` when the vault
    or item id is absent (those are the parts ``op read`` cannot do without).
    """
    query = parse_qs(urlparse(url).query)

    def _first(key: str) -> str:
        values = query.get(key, [])
        return values[0] if values else ""

    parts = {
        "account": _first("a"),
        "vault": _first("v"),
        "item": _first("i"),
        "host": _first("h"),
    }
    missing = [k for k in ("vault", "item") if not parts[k]]
    if missing:
        raise click.UsageError(
            f"1Password link missing required component(s) {missing}: {url!r}"
        )
    return parts


def item_from_link(url: str, filename: str) -> OpSshItem:
    """Build an :class:`OpSshItem` from a 1Password item link + target filename."""
    parts = parse_op_link(url)
    # Prefer the account id (``a``); fall back to the host (``h``). op read
    # accepts either as ``--account``.
    account = parts["account"] or parts["host"]
    if not account:
        raise click.UsageError(
            f"1Password link missing both account id (a) and host (h): {url!r}"
        )
    return OpSshItem(
        op_item=parts["item"],
        filename=filename,
        account=account,
        vault=parts["vault"],
    )


def parse_item_spec(spec: str) -> OpSshItem:
    """Parse a CLI ``--item NAME:FILENAME:ACCOUNT:VAULT`` spec."""
    fields = spec.split(":")
    if len(fields) != 4:
        raise click.BadParameter(
            f"--item must be NAME:FILENAME:ACCOUNT:VAULT (got {spec!r})"
        )
    return OpSshItem(op_item=fields[0], filename=fields[1], account=fields[2], vault=fields[3])


def _item_from_entry(entry: dict[str, Any], where: str) -> OpSshItem:
    """Build an item from one manifest entry (link form or explicit form)."""
    if "link" in entry:
        filename = str(entry.get("filename") or "").strip()
        if not filename:
            raise click.UsageError(f"{where}: 'link' entries also require 'filename'")
        return item_from_link(str(entry["link"]), filename)
    missing = [k for k in ("op_item", "filename", "account", "vault") if k not in entry]
    if missing:
        raise click.UsageError(f"{where}: missing required keys: {missing}")
    return OpSshItem(
        op_item=str(entry["op_item"]),
        filename=str(entry["filename"]),
        account=str(entry["account"]),
        vault=str(entry["vault"]),
    )


def load_items_from_yaml(path: Path = ITEMS_CONFIG_PATH) -> list[OpSshItem] | None:
    """Read the manifest at ``path``; return parsed items or None if absent.

    Raises ``click.UsageError`` if the file exists but is malformed — we don't
    silently fall back to "no items" when the user clearly meant to configure
    some.
    """
    if not path.is_file():
        return None
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise click.UsageError(f"could not read {path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise click.UsageError(f"{path}: top level must be a mapping")
    raw_items = cast("dict[str, Any]", loaded).get("items")
    if not isinstance(raw_items, list):
        raise click.UsageError(f"{path}: 'items:' must be a list")

    parsed: list[OpSshItem] = []
    for i, entry in enumerate(cast("list[Any]", raw_items)):
        if not isinstance(entry, dict):
            raise click.UsageError(f"{path} items[{i}]: each entry must be a mapping")
        parsed.append(_item_from_entry(cast("dict[str, Any]", entry), f"{path} items[{i}]"))
    return parsed


def resolve_items(item_specs: tuple[str, ...]) -> list[OpSshItem]:
    """Resolve the item list: inline ``--item`` specs override the manifest.

    Raises ``click.UsageError`` when neither source yields any items, so the
    caller gets a clean message instead of silently doing nothing.
    """
    if item_specs:
        return [parse_item_spec(spec) for spec in item_specs]
    loaded = load_items_from_yaml()
    if loaded is None:
        raise click.UsageError(
            f"No item list configured. Create {ITEMS_CONFIG_PATH} with:\n"
            "  items:\n"
            "    - op_item: <1P item title>\n"
            "      filename: <key filename>\n"
            "      account: <1P account URL or id>\n"
            "      vault: <vault name>\n"
            "  # …or, using a 1Password 'Copy Item Link':\n"
            "    - link: https://start.1password.com/open/i?a=…&v=…&i=…&h=…\n"
            "      filename: <key filename>\n"
            "or pass one or more --item NAME:FILENAME:ACCOUNT:VAULT flags."
        )
    if not loaded:
        raise click.UsageError(f"{ITEMS_CONFIG_PATH} has an empty 'items:' list; nothing to do.")
    return loaded


def ensure_op_signed_in() -> bool:
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
            "op is not signed in. Run `eval \"$(op signin)\"` in your shell first, "
            "then re-run this command."
        )
        return False
    return True


def op_read(reference: str, account: str, verbose: bool) -> bytes | None:
    """Run ``op read --account ... <reference>``; return stdout bytes or None."""
    cmd = ["op", "read", "--account", account, reference]
    if verbose:
        print_step(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=False, capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        print_warning(f"op read failed: {exc}")
        return None
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        print_warning(f"op read {reference} → exit {result.returncode}: {stderr}")
        return None
    return result.stdout


def atomic_write(dest: Path, content: bytes, mode: int) -> bool:
    """Write ``content`` to ``dest`` atomically; return True if it changed."""
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


def _normalize_newline(data: bytes) -> bytes:
    """``op read`` usually appends a trailing newline; ensure exactly one."""
    return data if data.endswith(b"\n") else data + b"\n"


def fetch_item(
    item: OpSshItem,
    dest_dir: Path,
    *,
    include_pub: bool,
    dry_run: bool,
    verbose: bool,
) -> bool:
    """Fetch one item from 1Password and write its key file(s) to ``dest_dir``.

    Always writes the private key (mode 0600). When ``include_pub`` is set,
    also writes ``<filename>.pub`` (mode 0644) — used by the shared-bucket
    export, where no git-tracked ``.pub`` exists. The on-disk pull leaves it
    off because the repo already ships the public keys.

    Returns True on success, False if any required read/write failed.
    """
    private_ref = f"op://{item.vault}/{item.op_item}/private key?ssh-format=openssh"
    private_dest = dest_dir / item.filename

    print_step(f"Fetching 1Password item {item.op_item!r} → {item.filename}")
    if dry_run:
        print(f"  would write: {private_dest} (0600)")
        if include_pub:
            print(f"  would write: {private_dest}.pub (0644)")
        return True

    private_bytes = op_read(private_ref, item.account, verbose)
    if private_bytes is None:
        print_warning(f"Skipping {item.op_item}: failed to read private key")
        return False
    private_changed = atomic_write(private_dest, _normalize_newline(private_bytes), 0o600)
    print_success(f"wrote {private_dest}") if private_changed else print(
        f"  unchanged: {private_dest}"
    )

    if include_pub:
        public_ref = f"op://{item.vault}/{item.op_item}/public key"
        public_dest = dest_dir / f"{item.filename}.pub"
        public_bytes = op_read(public_ref, item.account, verbose)
        if public_bytes is None:
            print_warning(f"Skipping {item.filename}.pub: failed to read public key")
            return False
        public_changed = atomic_write(public_dest, _normalize_newline(public_bytes), 0o644)
        print_success(f"wrote {public_dest}") if public_changed else print(
            f"  unchanged: {public_dest}"
        )

    return True
