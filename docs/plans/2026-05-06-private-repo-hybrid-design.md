# Private dotfiles → GitHub + GDrive runtime hybrid

## Context

`~/.dotfiles-private/` previously resolved through a Google Drive shortcut
path. On machines where that resolves to `Library/CloudStorage/.../​
.shortcut-targets-by-id/​<id>/...`, DriveFS restarts intermittently —
observed on `mac.openclaw` six times in 90 minutes. Each restart wedges
any `stat()` against the path, causing `zsh: write error` and shell
startup hangs because the zshrc reads `~/.dotfiles-private/...` paths
during initialization.

A pure local-mirror (rsync) approach was prototyped earlier the same day
and discarded: it gave us speed but not version history. This design
replaces it with a split-by-churn-rate model.

## Decision

Split storage by edit cadence:

- **Slow-moving config files** → private GitHub repo at
  `~/projects/joshm1/dotfiles-private`. `~/.dotfiles-private` becomes a
  symlink to that local clone. Edits travel through `git commit/push`.
  History recoverable; diffs reviewable across machines.
- **High-churn / per-device / large** files → never in git, synced
  through Google Drive into a per-machine subdir
  `<gdrive>/dotfiles-runtime/${device_id}/`. Each machine writes only to
  its own subdir, so there are no cross-machine merge conflicts.

The cron jobs are passive monitors, not auto-syncers:

- `check-private-repo` runs hourly: `git fetch` + count behind/ahead/dirty,
  fire one macOS notification when state diverges. Never auto-pulls/pushes.
- `sync-private-runtime` runs every 5 minutes: rsync the runtime subset
  to/from GDrive (pull-then-push, mtime-based `--update`).

## Architecture

```
github.com/joshm1/dotfiles-private (private)
       │
       │  user-driven git pull/push (notification-prompted)
       ▼
~/projects/joshm1/dotfiles-private/  ◄── ~/.dotfiles-private (symlink)
   home/.zshrc.before/.after.*       [git-tracked]
   home/.gitconfig*                  [git-tracked]
   home/.config/.../config.toml      [git-tracked]
   home/.claude/{skills,agents,...}/ [git-tracked]
   home/.ssh/config                  [git-tracked]
   home/bin/jabba                    [git-tracked, stable across machines]
   home/bin/codex-...-proxy          [git-tracked]
   ──────────────────────────────────────────────────
   zsh_history/                      [.gitignored]    ─┐
   home/.pry_history                 [.gitignored]     │
   home/.node_repl_history           [.gitignored]     │
   home/.psql_history                [.gitignored]     │
   home/.clipboard                   [.gitignored]     │ rsync ↔ GDrive
   home/.ssh/known_hosts             [.gitignored]     │ every 5 min
   home/.ssh/authorized_keys         [.gitignored]     │
                                                       │
   $HOME (NOT in repo)                                 │
   ~/.claude/projects/   ← 248 MB    ──────────────────┤
   ~/.claude/history.jsonl           ──────────────────┘

GDrive: <root>/dotfiles-runtime/${device_id}/
   repo/<rel-path-of-each-runtime-file>
   home/.claude/projects/
   home/.claude/history.jsonl
```

Existing `$HOME/.zshrc.before*` and `$HOME/.zshrc.after*` symlinks
continue to point at `~/.dotfiles-private/home/...` — no change to them
or to zshrc. The only mutation in $HOME is the one symlink retarget on
`~/.dotfiles-private` itself.

## File classification

### Git-tracked

- `home/.zshrc.before*`, `home/.zshrc.after*` (all device suffixes)
- `home/.config/dotfiles/.dotfiles-config*`
- `home/.config/atuin/config.toml`, `home/.config/gh/`,
  `home/.config/snapback/manifest.toml`, `home/.config/gcloud/configurations/config_*`
- `home/.gitconfig*`, `home/.npmrc`, `home/.dotfiles.yaml`,
  `.gpg-keys.yaml`, root `.gitconfig*`
- `home/.ssh/config`
- `home/.claude/skills/`, `home/.claude/agents/`, `home/.claude/commands/`
- `home/bin/jabba`, `home/bin/codex-responses-api-proxy`
- `zshrc/zshrc.*`

### GDrive runtime, machine-specific subdir

Source = repo paths (resolved via `~/.dotfiles-private`):

- `zsh_history/.zsh_history.${device_id}` (whole `zsh_history/` dir is
  rsync'd; only this device's file is ever the writer)
- `home/.pry_history`, `home/.node_repl_history`, `home/.psql_history`
- `home/.clipboard`
- `home/.ssh/known_hosts`, `home/.ssh/authorized_keys`

Source = `$HOME` directly:

- `~/.claude/projects/` (248 MB)
- `~/.claude/history.jsonl`

### Excluded entirely

`node_modules`, `.venv`, `venv`, `virtenv`, `__pycache__`,
`.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.turbo`, `.next`,
`.nuxt`, `.tox`, `bower_components`, `**/test/fixtures/`,
`**/skills/*/logs/`, `home/.agents/` (intentionally not synced).

## Components

**Files in `joshm1/dotfiles` (this repo):**

| Path | Purpose |
|---|---|
| `dotfiles_scripts/check_private_repo.py` | Hourly git-state check + macOS notification |
| `dotfiles_scripts/sync_private_runtime.py` | 5-min rsync to/from GDrive runtime root |
| `dotfiles_scripts/setup_private_repo.py` | One-shot bootstrap |
| `home/Library/LaunchAgents/com.dotfiles-private.check-repo.plist` | StartInterval = 3600s |
| `home/Library/LaunchAgents/com.dotfiles-private.sync-runtime.plist` | StartInterval = 300s |
| `dotfiles_scripts/setup_utils.py` | Adds `PRIVATE_DOTFILES_REPO` constant |
| `pyproject.toml` | Registers three new console scripts |
| `CLAUDE.md` | Updated "Private Configuration" section |

**Reused infrastructure:**

- `setup_utils.run_cmd` / `print_*` / `gdrive_candidates` / `PRIVATE_DOTFILES`
- `detach_cloud_cache.DEFAULT_PATTERNS` for cache excludes
- LaunchAgent shape from `com.dotfiles-private.detach-cloud-cache.plist`
- Plists with `com.dotfiles-private.*` prefix get auto-loaded by
  existing `setup_launchd.py`

## CLI surface

```
setup-private-repo [--force] [--rollback] [--skip-confirm]
check-private-repo [--force] [--status]
sync-private-runtime [--pull | --push | --status]
```

Default invocation (no flag):

- `check-private-repo` does the check.
- `sync-private-runtime` does pull-then-push.

These are what launchd runs.

## Failure handling

- All three scripts always exit 0 — launchd doesn't see "failures."
- `check-private-repo`: any single notification has a 1h cooldown keyed
  on the message text. Going clean clears the cooldown so the next
  problem fires immediately.
- `sync-private-runtime`: `flock(LOCK_NB)` makes overlapping runs no-op.
  State counters track consecutive failures; when failures × 5 min ≥ 1 h,
  one macOS notification fires (then suppressed for 1 h).
- `setup-private-repo` fails fast on preflight (gh, git, rsync, repo not
  pre-existing without `--force`) and on critical operations (clone,
  commit, push).

## Bootstrap (`setup-private-repo`) outline

1. Preflight: `gh`, `git`, `rsync`, GDrive's `~/.dotfiles-private`
   directory exists, target clone path doesn't exist (or `--force`).
2. Confirm with user.
3. `gh repo view` to detect existing repo; create with `gh repo create`
   if missing.
4. `gh repo clone` into `~/projects/joshm1/dotfiles-private`. Falls back
   to `git init && git remote add origin` if upstream is empty.
5. **First-machine only** (detected via `gh repo view` defaultBranchRef
   missing OR clone has no content): walk the existing GDrive copy of
   `~/.dotfiles-private/`, copy the git-include subset into the clone,
   write `.gitignore`, `git add -A && git commit && git push -u origin main`.
6. Snapshot current `~/.dotfiles-private` symlink target to
   `~/.cache/dotfiles-private/old-symlink-target.txt`.
7. Replace `~/.dotfiles-private` with a symlink to
   `~/projects/joshm1/dotfiles-private`.
8. `mkdir -p <gdrive>/dotfiles-runtime/${device_id}/`. rsync each runtime
   file into it for first-time seed (idempotent: missing sources are
   skipped).
9. Symlink `home/Library/LaunchAgents/com.dotfiles-private.{check-repo,
   sync-runtime}.plist` into `~/Library/LaunchAgents/` and
   `launchctl load -w` each.
10. Print verification commands.

`--rollback` restores step 6's snapshotted symlink target. The clone,
runtime dir, and LaunchAgents are intentionally left in place so a
re-bootstrap is fast.

## Verification

After first-machine bootstrap:

```bash
# symlink retargeted, $HOME symlinks transparently follow through
readlink ~/.dotfiles-private
# → /Users/claw/projects/joshm1/dotfiles-private

realpath ~/.zshrc.before.mac.openclaw
# → /Users/claw/projects/joshm1/dotfiles-private/home/.zshrc.before.mac.openclaw
# (no CloudStorage anywhere in the path)

# git plumbing
cd ~/.dotfiles-private && git status     # clean, on main, with remote tracking
git log --oneline -5

# launchd plumbing
launchctl print gui/$UID/com.dotfiles-private.check-repo
launchctl print gui/$UID/com.dotfiles-private.sync-runtime

# script-side state
check-private-repo --status              # behind=0 ahead=0 dirty=false
sync-private-runtime --status            # runtime root present, last_pull_ok recent
```

End-to-end:

- Edit `~/.zshrc.before.mac.openclaw`, don't commit. Within 1h (or run
  `check-private-repo --force`), notification fires "uncommitted changes."
- Push a commit from another machine. Within 1h here, notification fires
  "1 commit behind origin."
- After a fresh shell command and 5 min wait, the appended history
  appears in
  `<gdrive>/dotfiles-runtime/mac.openclaw/repo/zsh_history/.zsh_history.mac.openclaw`.
- Resume a Claude Code session. Within 5 min,
  `<gdrive>/dotfiles-runtime/mac.openclaw/home/.claude/history.jsonl`
  reflects new entries.

## Trade-offs accepted

- **Cross-machine restore is manual.** Each machine writes only to its
  own `${device_id}/` subdir; copying another machine's runtime content
  onto this one requires a manual rsync. Acceptable for v1 — the
  alternative is shared writes with merge conflicts.
- **Cron only on macOS.** The two LaunchAgents register via `launchctl`
  and skip silently on Linux/WSL. Linux machines need to set up cron or
  systemd-user units manually to invoke `check-private-repo` and
  `sync-private-runtime` on the same cadence.
- **Provider fallback**: the runtime bucket prefers Google Drive but
  falls back to Dropbox if GD isn't mounted, using the same
  `dotfiles-runtime/${device_id}/` layout. Dropbox-only machines still
  participate in runtime sync.
- **Per-device files in git.** Each machine commits its own
  `.zshrc.before.mac.openclaw` (etc.). Other machines see those files
  but never edit them. Tiny disk waste; gain is unified history and
  cross-machine viewability.
- **`gh repo create` baked into bootstrap.** Less ceremony but assumes
  the user is authed against the right account. Override with manual
  pre-creation in the GitHub UI is fine — bootstrap detects existing
  repo and skips creation.
- **No deletion propagation.** `rsync --update` doesn't carry deletes
  between local and GDrive. To remove a file from sync, delete on both
  sides manually. Acceptable: deletions of runtime files are rare.
