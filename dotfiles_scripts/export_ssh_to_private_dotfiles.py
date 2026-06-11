#!/usr/bin/env python3
"""Export SSH private keys from 1Password into the private-dotfiles shared bucket.

Legacy hop: 1Password → ``<shared>/ssh/`` (GDrive). Opted-out (``disk-keys``)
machines then pull from there via ``sync-private-runtime``.

Prefer ``pull-ssh-keys-from-op``, which writes straight to ``~/.ssh`` and keeps
private keys off cloud storage entirely. This command remains for seeding the
shared bucket on a 1Password-enabled machine.

Usage::

    eval "$(op signin)"   # interactive — op cannot biometric-prompt headless
    uv run export-ssh-to-private-dotfiles --dry-run
    uv run export-ssh-to-private-dotfiles

The item list lives in ``ssh-export-items.yaml`` under the private repo; see
``dotfiles_scripts.op_ssh`` for the schema (explicit fields or item links).
"""

from __future__ import annotations

import sys

import click

from dotfiles_scripts.op_ssh import (
    ensure_op_signed_in,
    fetch_item,
    resolve_items,
)
from dotfiles_scripts.setup_utils import (
    print_error,
    print_header,
    print_step,
    print_success,
)
from dotfiles_scripts.sync_private_runtime import resolve_shared_root


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
    parsed = resolve_items(items)

    print_header("Export SSH keys → private-dotfiles shared bucket")

    if not dry_run and not ensure_op_signed_in():
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

    failures = sum(
        0 if fetch_item(item, dest_dir, include_pub=True, dry_run=dry_run, verbose=verbose) else 1
        for item in parsed
    )

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
