#!/usr/bin/env python3
"""Migrate the user's cloud-synced private dotfiles to Google Drive.

Workflow:

* The canonical local pointer is ``~/.dotfiles-private``.
* The migration target is ``<google-drive>/dotfiles-private``.
* Sources we know how to migrate from: an existing ``~/.dotfiles-private``
  symlink, or the legacy ``~/Dropbox/dotfiles`` directory.
* Source data is never deleted — Dropbox stays populated for other laptops
  that have not migrated yet (per the project decision recorded in the plan).

The script always runs a divergence check first so a *second* laptop
migrating later can see, per file, exactly what differs between its local
Dropbox copy and what was previously published to Google Drive. The user
chooses how to resolve via ``--prefer-gdrive``, ``--prefer-dropbox``, or
``--ignore-divergence``.

Usage::

    uv run migrate-to-gdrive                    # plan + divergence report
    uv run migrate-to-gdrive --apply            # execute (errors on divergence)
    uv run migrate-to-gdrive --apply --prefer-gdrive
    uv run migrate-to-gdrive --apply --prefer-dropbox
    uv run migrate-to-gdrive --apply --ignore-divergence
    uv run migrate-to-gdrive --rollback /tmp/migrate-to-gdrive-<timestamp>.log
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import click

from dotfiles_scripts.setup_utils import (
    DROPBOX_DIR,
    PRIVATE_DOTFILES,
    gdrive_candidates,
    print_error,
    print_header,
    print_step,
    print_success,
    print_warning,
)

# Where the migrated data lives on Google Drive.
TARGET_DIR_NAME = "dotfiles-private"

CHUNK = 1024 * 1024


@dataclass
class CopyPair:
    """A directory tree to migrate."""

    source: Path
    dest: Path

    @property
    def label(self) -> str:
        return f"{self.source} → {self.dest}"


@dataclass
class FileDiff:
    """A divergence between a source file and its Google Drive counterpart."""

    rel_path: Path
    # "modified"            — present in both, content differs
    # "missing-from-gdrive" — present in source, absent (or whole tree absent) in gdrive
    # "missing-from-source" — present in gdrive, absent in source
    state: str


@dataclass
class MigrationPlan:
    """Everything the script intends to do, materialized for inspection."""

    source_root: Path
    gdrive_root: Path
    pairs: list[CopyPair] = field(default_factory=list)
    diffs: dict[str, list[FileDiff]] = field(default_factory=dict)


def _resolve_source_dotfiles() -> Path | None:
    """Find the directory that should be copied to Google Drive.

    Order of preference:
        1. Whatever ``~/.dotfiles-private`` currently resolves to (if it's a
           real directory and not already inside Google Drive).
        2. ``~/Dropbox/dotfiles`` (legacy Dropbox layout).
    """
    if PRIVATE_DOTFILES.is_dir():
        target = PRIVATE_DOTFILES.resolve()
        if "CloudStorage/GoogleDrive-" not in str(target):
            return target
    legacy = DROPBOX_DIR / "dotfiles"
    if legacy.is_dir():
        return legacy
    return None


def _pick_gdrive_root() -> Path | None:
    """Return the first mounted Google Drive ``My Drive`` root, or None."""
    candidates = gdrive_candidates()
    return candidates[0] if candidates else None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def _walk_relative(root: Path) -> list[Path]:
    """All regular files under ``root`` as paths relative to ``root``."""
    files: list[Path] = []
    for p in root.rglob("*"):
        if p.is_file() and not p.is_symlink():
            files.append(p.relative_to(root))
    return files


def _diff_trees(source: Path, dest: Path) -> list[FileDiff]:
    """Compute per-file divergence between ``source`` and ``dest`` trees.

    A missing destination directory is treated as "every source file is
    missing from gdrive" rather than as a no-op. Callers want to see that
    Google Drive is empty, not be told there's no divergence.
    """
    diffs: list[FileDiff] = []
    src_files = {p: source / p for p in _walk_relative(source)}
    dst_files: dict[Path, Path] = (
        {p: dest / p for p in _walk_relative(dest)} if dest.is_dir() else {}
    )
    for rel, src_path in src_files.items():
        dst_path = dst_files.get(rel)
        if dst_path is None:
            diffs.append(FileDiff(rel, "missing-from-gdrive"))
            continue
        try:
            if (
                src_path.stat().st_size != dst_path.stat().st_size
                or _sha256(src_path) != _sha256(dst_path)
            ):
                diffs.append(FileDiff(rel, "modified"))
        except OSError:
            diffs.append(FileDiff(rel, "modified"))
    for rel in dst_files.keys() - src_files.keys():
        diffs.append(FileDiff(rel, "missing-from-source"))
    return sorted(diffs, key=lambda d: (d.state, str(d.rel_path)))


def _build_pairs(source_root: Path, gdrive_root: Path) -> list[CopyPair]:
    """Concrete (src, dst) directory pairs that this run will copy.

    Only the private dotfiles tree itself is migrated. Source name varies
    (legacy ``dotfiles``, current ``dotfiles-private``, etc.); the destination
    on Google Drive is always ``dotfiles-private``.
    """
    return [CopyPair(source=source_root, dest=gdrive_root / TARGET_DIR_NAME)]


def _run_diffs(pairs: list[CopyPair]) -> dict[str, list[FileDiff]]:
    diffs: dict[str, list[FileDiff]] = {}
    for pair in pairs:
        diffs[pair.label] = _diff_trees(pair.source, pair.dest)
    return diffs


def _print_diffs(diffs: dict[str, list[FileDiff]]) -> int:
    """Print the per-tree diff report. Returns total number of differences."""
    total = 0
    for label, items in diffs.items():
        if not items:
            print(f"  no divergence: {label}")
            continue
        print(f"  DIVERGENCE: {label}")
        for item in items:
            print(f"    {item.state}: {item.rel_path}")
        total += len(items)
    return total


def _rsync(src: Path, dst: Path, *, delete_extras_in_dest: bool = False) -> None:
    """Copy ``src`` to ``dst``. Source is never deleted.

    When ``delete_extras_in_dest`` is true (used by ``--prefer-dropbox`` to
    fully mirror source state), files that exist in ``dst`` but not ``src``
    are removed.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    # `--stats` is the cross-platform progress flag; BSD rsync on macOS
    # rejects GNU's `--info=stats1`, so we stick to `--stats`.
    cmd = ["rsync", "-a", "--stats"]
    if delete_extras_in_dest:
        cmd.append("--delete")
    cmd += [f"{src}/", f"{dst}/"]
    subprocess.run(cmd, check=True)


def _wait_for_sync(dest: Path, expected_files: int, timeout_s: int = 120) -> bool:
    """Poll until ``dest`` contains at least ``expected_files`` entries."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        actual = sum(1 for _ in dest.rglob("*") if _.is_file())
        if actual >= expected_files:
            return True
        time.sleep(2)
    return False


def _atomic_relink(symlink: Path, target: Path) -> None:
    """Replace ``symlink`` with one pointing at ``target``.

    Strictly speaking this is a "remove + create" rather than atomic, because
    ``os.rename`` / ``os.replace`` of a regular-file-symlink onto a
    symlink-to-directory would *move into* the target directory rather than
    replace the link itself. Removing the source symlink first avoids that
    foot-gun; the (very brief) window where the symlink is missing is fine
    for our offline migration use case.
    """
    if symlink.is_symlink() or symlink.exists():
        symlink.unlink()
    os.symlink(target, symlink)


def _journal_path() -> Path:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path(f"/tmp/migrate-to-gdrive-{ts}.log")


def _write_journal(path: Path, entries: list[dict[str, str]]) -> None:
    path.write_text(json.dumps(entries, indent=2))


def _read_journal(path: Path) -> list[dict[str, str]]:
    return json.loads(path.read_text())


def _rewrite_home_symlinks(
    old_root: Path, new_via: Path, journal: list[dict[str, str]]
) -> int:
    """Rewrite symlinks under $HOME that point inside ``old_root`` to ``new_via``.

    For example: ``~/.zshrc.before -> ~/Dropbox/dotfiles/home/.zshrc.before``
    becomes ``~/.zshrc.before -> ~/.dotfiles-private/home/.zshrc.before`` (the
    suffix after the old root is preserved). Records each retarget to the
    journal so ``--rollback`` can reverse it.
    """
    home = Path.home()
    old_resolved = old_root.resolve()
    count = 0

    # Find every symlink under $HOME that resolves into the old cloud source.
    # Earlier we restricted to top-level + ~/.config, which missed
    # ~/.claude/{agents,commands,skills}, ~/projects/*/mise.toml, etc. Now we
    # actually search — but skip dirs that can't possibly contain
    # cloud-pointing symlinks (Library/, node_modules, .venv, .git, prior
    # backup dirs from setup runs).
    skip_names = {
        "Library",
        "node_modules",
        ".venv",
        "venv",
        ".git",
        "__pycache__",
        ".cache",
    }

    def walk(d: Path) -> "list[Path]":
        out: list[Path] = []
        try:
            entries = list(d.iterdir())
        except (OSError, PermissionError):
            return out
        for entry in entries:
            name = entry.name
            if name in skip_names or name.endswith(".bck") or ".bck." in name:
                continue
            if entry.is_symlink():
                out.append(entry)
            elif entry.is_dir():
                out.extend(walk(entry))
        return out

    candidates = walk(home)
    for path in candidates:
        if not path.is_symlink():
            continue
        try:
            link_target = Path(os.readlink(path))
        except OSError:
            continue
        try:
            link_resolved = path.resolve(strict=False)
        except OSError:
            continue
        if not _is_subpath(link_resolved, old_resolved):
            continue
        suffix = link_resolved.relative_to(old_resolved)
        new_target = new_via / suffix
        journal.append(
            {
                "symlink": str(path),
                "old_target": str(link_target),
                "new_target": str(new_target),
            }
        )
        _atomic_relink(path, new_target)
        count += 1
    return count


def _is_subpath(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


@click.command()
@click.option("--apply", "do_apply", is_flag=True, help="Execute the migration (default: plan only).")
@click.option(
    "--prefer-gdrive",
    is_flag=True,
    help="On divergence, trust Google Drive (skip copy, just retarget the symlink).",
)
@click.option(
    "--prefer-dropbox",
    is_flag=True,
    help="On divergence, overwrite Google Drive with the local Dropbox source.",
)
@click.option(
    "--ignore-divergence",
    is_flag=True,
    help="Proceed past divergence using the default copy direction (source → Google Drive).",
)
@click.option(
    "--rollback",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Replay a journal file to undo a previous migration's symlink retargets.",
)
def cli(
    do_apply: bool,
    prefer_gdrive: bool,
    prefer_dropbox: bool,
    ignore_divergence: bool,
    rollback: Path | None,
) -> None:
    """Migrate cloud-synced private dotfiles to Google Drive."""
    if rollback is not None:
        sys.exit(_run_rollback(rollback))

    n_resolution_flags = sum(int(b) for b in (prefer_gdrive, prefer_dropbox, ignore_divergence))
    if n_resolution_flags > 1:
        print_error("Pick at most one of --prefer-gdrive / --prefer-dropbox / --ignore-divergence")
        sys.exit(1)

    plan = _build_plan()
    if plan is None:
        sys.exit(1)

    print_header("Migration plan")
    print(f"Source:       {plan.source_root}")
    print(f"Google Drive: {plan.gdrive_root}")
    print()
    print("Subtrees to copy:")
    for pair in plan.pairs:
        print(f"  {pair.label}")

    print()
    print_header("Divergence report")
    diff_total = _print_diffs(plan.diffs)
    # "missing-from-gdrive" entries on a first migration are not real divergence
    # — they're the copy plan. Only count file states that imply actual drift
    # (mismatched content or files only present on the gdrive side).
    drift_total = sum(
        1
        for diffs in plan.diffs.values()
        for d in diffs
        if d.state in ("modified", "missing-from-source")
    )
    print()
    print(f"Total differences: {diff_total}  (drift: {drift_total})")

    if not do_apply:
        print()
        print_step("Plan-only mode. Re-run with --apply to execute.")
        return

    if drift_total > 0 and not (prefer_gdrive or prefer_dropbox or ignore_divergence):
        print_error(
            "Drift detected (modified files or gdrive-only files). Resolve by "
            "re-running with one of: --prefer-gdrive, --prefer-dropbox, --ignore-divergence"
        )
        sys.exit(2)

    sys.exit(_run_apply(plan, prefer_gdrive=prefer_gdrive, prefer_dropbox=prefer_dropbox))


def _build_plan() -> MigrationPlan | None:
    if shutil.which("rsync") is None:
        print_error("rsync is required but not found on PATH")
        return None
    source = _resolve_source_dotfiles()
    if source is None:
        print_error(
            "Could not find a source private-dotfiles directory. Expected "
            f"either {PRIVATE_DOTFILES} or {DROPBOX_DIR}/dotfiles to exist."
        )
        return None
    gdrive = _pick_gdrive_root()
    if gdrive is None:
        print_error(
            "No Google Drive root mounted at "
            f"{Path.home()}/Library/CloudStorage/GoogleDrive-*/My Drive"
        )
        return None
    pairs = _build_pairs(source, gdrive)
    diffs = _run_diffs(pairs)
    return MigrationPlan(source_root=source, gdrive_root=gdrive, pairs=pairs, diffs=diffs)


def _run_apply(plan: MigrationPlan, *, prefer_gdrive: bool, prefer_dropbox: bool) -> int:
    journal_entries: list[dict[str, str]] = []
    journal = _journal_path()

    print_header("Applying migration")

    # Copy phase. Skipped for --prefer-gdrive (trust what's already there);
    # adds rsync --delete when --prefer-dropbox so gdrive becomes a strict
    # mirror of the source instead of a superset.
    if prefer_gdrive:
        print_step("Skipping copy (--prefer-gdrive set)")
    else:
        for pair in plan.pairs:
            print_step(f"rsync {pair.label}")
            try:
                _rsync(pair.source, pair.dest, delete_extras_in_dest=prefer_dropbox)
            except subprocess.CalledProcessError as exc:
                print_error(f"rsync failed for {pair.label}: {exc}")
                return 1

        # Sync wait: ensure Google Drive has registered the new files.
        for pair in plan.pairs:
            expected = sum(1 for _ in pair.source.rglob("*") if _.is_file())
            if not _wait_for_sync(pair.dest, expected):
                print_warning(
                    f"Google Drive still settling for {pair.dest}; continuing anyway"
                )

    # Retarget the local symlink atomically.
    new_target = plan.gdrive_root / TARGET_DIR_NAME
    if not new_target.is_dir():
        print_error(f"Expected {new_target} to exist after copy; aborting before retarget")
        return 1
    old_pointer = (
        PRIVATE_DOTFILES.resolve() if PRIVATE_DOTFILES.is_dir() else plan.source_root
    )
    print_step(f"Retargeting {PRIVATE_DOTFILES} → {new_target}")
    journal_entries.append(
        {
            "symlink": str(PRIVATE_DOTFILES),
            "old_target": str(old_pointer),
            "new_target": str(new_target),
        }
    )
    _atomic_relink(PRIVATE_DOTFILES, new_target)

    # Rewrite any home symlinks that still point at the old source.
    rewritten = _rewrite_home_symlinks(old_pointer, PRIVATE_DOTFILES, journal_entries)
    print_step(f"Rewrote {rewritten} home-directory symlinks via {PRIVATE_DOTFILES}")

    _write_journal(journal, journal_entries)
    print_success(f"Journal written to {journal}")
    print_success("Migration complete. To undo: migrate-to-gdrive --rollback " + str(journal))
    return 0


def _run_rollback(journal: Path) -> int:
    print_header(f"Rolling back from {journal}")
    entries = _read_journal(journal)
    for entry in reversed(entries):
        symlink = Path(entry["symlink"])
        old_target = entry.get("old_target") or ""
        if not old_target:
            print_step(f"Removing {symlink} (created during migration)")
            if symlink.is_symlink() or symlink.exists():
                symlink.unlink()
            continue
        print_step(f"Reverting {symlink} → {old_target}")
        _atomic_relink(symlink, Path(old_target))
    print_success("Rollback complete")
    return 0


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
