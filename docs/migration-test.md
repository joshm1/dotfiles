# Dotfiles-Private Migration: Verification Playbook

How to verify a machine that's been migrated to the GitHub + GDrive hybrid
architecture (`setup-private-repo`) hasn't lost any files relative to the
old Dropbox / GDrive-only setup.

Run this **after** `git pull` on both repos, **after** `setup-private-repo`
on a fresh machine, or anytime you suspect drift.

---

## Quick health check (60s)

Run this one-liner block. Every line should pass cleanly.

```bash
echo "=== ~/.dotfiles-private symlink ==="
readlink ~/.dotfiles-private
# Expect: /Users/<you>/.dotfiles-private  (the local clone, NOT a Cloud path)

echo
echo "=== Critical \$HOME symlinks resolve through the repo ==="
DEV=$(cat ~/.device_id)
for f in .zshrc.before.$DEV .zshrc.after.$DEV .gitconfig .gitconfig_local \
         .ssh/config .ssh/id_ed25519.pub .config/dotfiles/.dotfiles-config; do
  rp=$(realpath -q "$HOME/$f" 2>/dev/null || echo "MISSING")
  printf "  %-45s -> %s\n" "$f" "$rp"
done
# Expect: every line resolves to a real path under either ~/.dotfiles or
# ~/.dotfiles-private. No "MISSING". No paths containing "Dropbox" or
# "CloudStorage" (that means a stale Cloud-pointing symlink slipped through).

echo
echo "=== ~/bin wholesale-symlinked & populated ==="
readlink ~/bin
# Expect: ~/.dotfiles-private/home/bin (or the absolute clone path)
ls ~/bin | wc -l
# Expect: >= 24 scripts

echo
echo "=== ~/.ssh wholesale-symlinked & populated ==="
readlink ~/.ssh
ls ~/.ssh
# Expect: config, id_ed25519.pub, known_hosts, authorized_keys at minimum

echo
echo "=== sync status (private repo + runtime bucket) ==="
cd ~/.dotfiles && uv run check-private-repo --status
# Expect: behind=0, ahead=0, dirty=False (or only files you intend to commit)
cd ~/.dotfiles && uv run sync-private-runtime --status
# Expect: pull failures=0, push failures=0, recent last_pull_ok / last_push_ok

echo
echo "=== zsh startup time ==="
for i in 1 2 3; do /usr/bin/time -p zsh -ic exit 2>&1 | grep real; done
# Expect: <1s. If >2s, GDrive FileProvider is probably stalling — check that
# no remaining symlinks point through ~/Library/CloudStorage.
```

If everything above looks right, the machine is healthy. The deep audit
below is for when you suspect files actually went missing.

---

## Deep audit: did anything in legacy storage NOT land in the new repo?

The audit script at `/tmp/audit_repo.py` walks `~/Dropbox/dotfiles`, expands
the include globs from `setup_private_repo.py` against it, and compares the
matched set to `~/.dotfiles-private/`. Use this on a machine that **still
has the original Dropbox copy intact** (typically the second machine being
migrated, or any machine before its first `setup-private-repo` run).

```bash
cd ~ && python3 /tmp/audit_repo.py
```

Output sections:
- `MISSING from repo` — files Dropbox has that match include globs but
  aren't in the local clone. **These are real misses.** Copy them over,
  commit, push.
- `DIFFERENT content` — same path, different bytes. Inspect each:

  ```bash
  diff ~/Dropbox/dotfiles/<rel> ~/.dotfiles-private/<rel>
  # If the diff is just CRLF vs LF:
  diff <(tr -d '\r' < ~/Dropbox/dotfiles/<rel>) <(tr -d '\r' < ~/.dotfiles-private/<rel>)
  # If empty after that, the repo's LF version is canonical — no action.
  ```
- `match exactly` — already correct, no action.

### If `/tmp/audit_repo.py` is missing

The audit script lives at `/tmp/audit_repo.py` only because that's where it
was written during the mac.primary migration. To recreate it on another
machine, see the source in this repo's git history (commit b2c831b era,
mac.primary work) or copy it over. It's a ~140-line standalone Python
script with no third-party deps; see this file's appendix.

### Known-benign discrepancies

- `home/.config/gh/hosts.yml` — gh CLI rewrites this per-machine on each
  auth refresh; the `git_protocol`, `users.<account>.oauth_token`, etc.
  fields drift constantly. As long as the *active* user listed matches
  the account you actually use on this machine, the repo's snapshot is
  fine. **Don't commit hosts.yml diffs unless you've intentionally
  changed which gh account is primary.**
- CRLF line endings — Windows-line-ending files in Dropbox legacy
  appear as content diffs. The repo's LF is canonical.

---

## Migration-specific spot-checks

These caught real bugs during the mac.primary migration. Re-run them
after any `setup-private-repo` invocation.

### 1. Did `~/bin` get wholesale-symlinked?

```bash
[ -L ~/bin ] && echo "OK: wholesale symlink to $(readlink ~/bin)" \
             || echo "BUG: ~/bin is a real dir — re-run 'uv run symlink-home-files'"
```

If `~/bin` is a real directory with per-file symlinks, the `.symlink-dir`
tag was missing when `setup_private_repo` first ran. Verify
`~/.dotfiles-private/home/bin/.symlink-dir` exists, then re-run
`uv run symlink-home-files`.

### 2. Is `~/.ssh/config` reachable?

```bash
ssh -G github.com >/dev/null && echo "OK: ssh sees config" || echo "BUG: ssh can't read config"
test -s ~/.ssh/config && echo "OK: config non-empty" || echo "BUG: empty"
```

If missing: the `home/.ssh/config` file should exist in
`~/.dotfiles-private/`. If it doesn't, copy it from
`~/Dropbox/dotfiles/home/.ssh/config` (or `~/Dropbox/dotfiles/.ssh/config`)
into the clone, commit, push. **Watch out for global `~/.gitignore`
patterns shadowing the file** — see issue 4 below.

### 3. Are runtime-only files syncing?

`known_hosts`, `authorized_keys`, `~/.psql_history`, mise project tomls,
`~/.warprc`, etc. are NOT git-tracked but ARE rsync'd via the runtime
bucket. After `sync-private-runtime --pull`:

```bash
test -s ~/.ssh/known_hosts && echo "OK: known_hosts populated" || echo "MISS"
test -s ~/.psql_history && echo "OK: psql_history populated" || echo "(maybe never used)"
ls ~/.config/dotfiles/  # should have .dotfiles-config.<your-device-id>
```

### 4. Has the global `~/.gitignore` swallowed `.ssh/`?

The legacy global gitignore had `[._]s[a-w][a-z]` (vim anonymous swap
pattern) which matched `.ssh` as a 4-char path component. Removed in
commit b2c831b. Confirm:

```bash
grep -n '\[._\]s\[a-w\]\[a-z\]' ~/.gitignore
# Expect: no matches (the bare pattern). The named pattern
# `[._]*.s[a-w][a-z]` IS expected and harmless.
```

If the bad pattern is still there, `git pull` in `~/.dotfiles` and verify
the symlink resolves to the new content:

```bash
realpath ~/.gitignore  # should be ~/.dotfiles/home/.gitignore
```

### 5. Did `migrate-to-gdrive` leave broken symlinks under `$HOME`?

The walker had a bug that descended into `~/Dropbox` and rewrote internal
symlinks (fixed in commit 9db6b3a). To confirm none survived:

```bash
# Find broken symlinks in $HOME (top 2 levels) — should be empty
find ~ -maxdepth 2 -type l ! -exec test -e {} \; -print 2>/dev/null
```

If any show up, check the migration journal at
`~/.cache/dotfiles-private/migrate-to-gdrive-*.json` and restore from the
recorded `old_target`.

---

## What "nothing got lost" means

A migration is complete when **all** of these hold:

| Check | Pass condition |
|---|---|
| `readlink ~/.dotfiles-private` | points at the local clone, not a Cloud path |
| `realpath ~/.zshrc.before.$DEVICE_ID` | resolves into the local clone |
| `~/bin/op-cached --help` | runs (proves the bin glob worked) |
| `ssh -T git@github.com` | authenticates (proves `.ssh/config` is wired) |
| `check-private-repo --status` | dirty=False, behind=0 |
| `sync-private-runtime --status` | pull/push failures=0, recent timestamps |
| `python3 /tmp/audit_repo.py` (on Dropbox-still-present machines) | 0 missing, 0 differs (modulo hosts.yml + CRLF) |
| `zsh -ic exit` | <1s |

If any one of these fails, the migration isn't done. Don't archive the
legacy Dropbox copy until they all pass.

---

## Appendix: `/tmp/audit_repo.py` source

Lives at `/tmp/audit_repo.py` after the mac.primary migration. It's
standalone (only stdlib) and ~140 lines. To recreate:

1. Copy from `/tmp/audit_repo.py` if still present.
2. Otherwise the canonical version is in conversation history at
   `/Users/josh/.claude/projects/-Users-josh-projects-joshm1-dotfiles/`
   (search for `parse_globs("GIT_INCLUDE_GLOBS")`).

Key behaviors:
- Parses `GIT_INCLUDE_GLOBS` and `GIT_EXCLUDE_GLOBS` constants from
  `~/.dotfiles/dotfiles_scripts/setup_private_repo.py` via `ast.parse`
  (NOT regex — earlier regex parser only captured 17 of ~30 globs).
- Uses `pathlib.glob` to expand patterns (matches `_expand_includes`
  semantics — `*` doesn't cross `/`).
- Compares by sha256, reports size mismatch separately.
- Skips `.git`, `__pycache__`, `.cache`, `.venv`, `node_modules`,
  `.DS_Store`.
