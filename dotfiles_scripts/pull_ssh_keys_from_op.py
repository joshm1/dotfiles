#!/usr/bin/env python3
"""Pull SSH private keys from 1Password straight onto disk under ``~/.ssh``.

The preferred provisioning path for the ``disk-keys`` SSH backend: fetch the
private keys from 1Password (the source of truth) directly into
``~/.dotfiles-private/home/.ssh`` (which ``~/.ssh`` symlinks to), so the key
material never lands in cloud storage. Compare ``export-ssh-to-private-dotfiles``,
which writes to the GDrive shared bucket instead.

Public keys are NOT written by default — the repo already ships git-tracked
``*.pub`` files. Pass ``--with-pub`` to fetch them too.

Usage::

    eval "$(op signin)"        # interactive unlock; op can't biometric-prompt headless
    uv run pull-ssh-keys-from-op --dry-run
    uv run pull-ssh-keys-from-op

    # ad-hoc, straight from a 1Password "Copy Item Link":
    uv run pull-ssh-keys-from-op \\
        --link 'https://start.1password.com/open/i?a=…&v=…&i=…&h=…' --filename id_foo

The default item list is ``ssh-export-items.yaml``; see ``dotfiles_scripts.op_ssh``
for the schema (explicit fields or item links).
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from dotfiles_scripts.op_ssh import (
    ensure_op_signed_in,
    fetch_item,
    item_from_link,
    resolve_items,
)
from dotfiles_scripts.setup_utils import (
    PRIVATE_DOTFILES,
    print_error,
    print_header,
    print_step,
    print_success,
)


def _ssh_dir() -> Path:
    """On-disk ``~/.ssh``, resolved through the private-dotfiles symlink."""
    return PRIVATE_DOTFILES / "home" / ".ssh"


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
    help="Inline item override. Repeatable. Bypasses ssh-export-items.yaml.",
)
@click.option(
    "--link",
    default=None,
    metavar="URL",
    help="Pull a single key from a 1Password 'Copy Item Link'. Requires --filename.",
)
@click.option(
    "--filename",
    default=None,
    metavar="NAME",
    help="Target key filename under ~/.ssh (only with --link).",
)
@click.option(
    "--with-pub",
    is_flag=True,
    help="Also fetch the .pub (normally unnecessary — the repo tracks public keys).",
)
@click.option("--verbose", is_flag=True, help="Print every op command invoked.")
def cli(
    dry_run: bool,
    items: tuple[str, ...],
    link: str | None,
    filename: str | None,
    with_pub: bool,
    verbose: bool,
) -> None:
    """Pull SSH private keys from 1Password directly onto disk under ~/.ssh."""
    if link:
        if not filename:
            raise click.UsageError("--link requires --filename")
        if items:
            raise click.UsageError("--link cannot be combined with --item")
        parsed = [item_from_link(link, filename)]
    else:
        if filename:
            raise click.UsageError("--filename only applies together with --link")
        parsed = resolve_items(items)

    ssh_dir = _ssh_dir()
    print_header("Pull SSH keys from 1Password → ~/.ssh")
    if not ssh_dir.is_dir():
        print_error(
            f"{ssh_dir} not found; the private-dotfiles symlink may not be set up yet."
        )
        sys.exit(1)
    print_step(f"Destination: {ssh_dir}")

    if not dry_run and not ensure_op_signed_in():
        sys.exit(1)

    failures = sum(
        0
        if fetch_item(item, ssh_dir, include_pub=with_pub, dry_run=dry_run, verbose=verbose)
        else 1
        for item in parsed
    )

    if failures:
        print_error(f"{failures} of {len(parsed)} item(s) failed; see warnings above.")
        sys.exit(1)
    print_success(f"Pulled {len(parsed)} key(s) into {ssh_dir} (mode 0600).")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
