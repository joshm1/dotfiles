# CLAUDE.md

## Repository Overview

This is a personal dotfiles repository for macOS that manages shell configuration (zsh), development tools (via Homebrew and mise), tmux setup, neovim configuration, and git settings. The repository uses symlinks to install dotfiles from `~/projects/joshm1/dotfiles` (stored as `$DOTFILES` = `~/.dotfiles`) to their standard locations.

## Git Workflow

**IMPORTANT:** Do NOT proactively run `git add` or `git commit` commands unless the user explicitly asks you to create a commit. The user prefers to handle git operations themselves.

- ✅ Make code changes, create files, edit files as requested
- ✅ Show git status when asked or when changes are complete
- ❌ Do NOT run `git add` without being asked
- ❌ Do NOT run `git commit` without being asked
- ❌ Do NOT run `git push` without being asked

When the user explicitly says "commit this" or "create a commit", then and only then should you stage changes and create commits.

## Installation & Setup

### Main Setup Script
`./setup` is a bootstrap wrapper that installs Homebrew and uv if missing, then runs `uv run dotfiles-setup`. The actual orchestration logic is in `dotfiles_scripts/setup.py`. For subsequent runs: `uv run dotfiles-setup`.

The setup:
1. Updates git submodules
2. Configures device identity and macOS defaults
3. Installs Homebrew packages
4. Installs neovim nightly and mise
5. Configures zsh and neovim
6. Symlinks all dotfiles from `home/` to `$HOME`
7. Sets up fzf, Dropbox config, zsh history, and GPG keys

### Setup Scripts
Setup scripts are Python modules in `dotfiles_scripts/`. Run individually with `uv run <script-name>`:
- `setup-device-id` - Sets machine identity for device-specific config
- `setup-macos` - Configures macOS defaults
- `setup-homebrew` - Installs Homebrew and runs Brewfiles
- `setup-neovim` - Installs neovim nightly
- `setup-mise` - Installs mise for language version management
- `setup-zsh` - Configures zsh with antidote
- `setup-vim` - Sets up neovim
- `setup-fzf` - Sets up fzf
- `setup-dropbox` - Links private config files from Dropbox
- `setup-zsh-history` - Configures shared zsh history (requires Dropbox)
- `setup-gpg` - Generates GPG keys and device-specific gitconfig
- `setup-private-repo` - Migrate `~/.dotfiles-private` from cloud-only storage to a private GitHub clone + per-machine GDrive runtime sync (see [Private Configuration](#private-configuration))

## Key Architecture

### Configuration Variables
Common paths are defined in `dotfiles_scripts/setup_utils.py`:
- `DOTFILES = $HOME/.dotfiles` — symlink to this repo (public)
- `DOTFILES_REPO = ~/projects/joshm1/dotfiles` — clone location
- `PRIVATE_DOTFILES = $HOME/.dotfiles-private` — local symlink. By
  default points at the user's cloud-synced private dotfiles (Google
  Drive preferred, Dropbox fallback). After `setup-private-repo` runs,
  it instead points at `PRIVATE_DOTFILES_REPO` (a local git clone)
- `PRIVATE_DOTFILES_REPO = ~/projects/joshm1/dotfiles-private` — clone of
  the private GitHub repo created by `setup-private-repo`
- `DROPBOX_DIR = $HOME/Dropbox` — kept for the Dropbox fallback path

Cloud-storage discovery is glob-based and never hardcodes the user's email:
`get_cloud_dotfiles_dir()`-style helpers were replaced with the single
indirection above. Setup scripts and `home/.zshrc` always read through
`~/.dotfiles-private/...`; only the migration script and bootstrap touch
the cloud roots directly.

Migrating between clouds: see `migrate-to-gdrive` (Python module
`dotfiles_scripts/migrate_to_gdrive.py`). The script copies data into
`<google-drive>/dotfiles-private/`, retargets the local symlink atomically,
rewrites any home-directory symlinks that still pointed at the old source,
and journals everything for `--rollback`. It includes a per-file
sha256-based divergence report so a *second* laptop can see what differs
between its local Dropbox copy and what was previously published to
Google Drive (resolve via `--prefer-gdrive`, `--prefer-dropbox`, or
`--ignore-divergence`).

Language versions are managed by mise (see `.mise.toml` files).

### Machine-Specific Configuration
Device-specific config files use hierarchical namespaces (e.g., `mac.personal`).
Files live in `~/.dotfiles-private/home/.config/dotfiles/` (the cloud-synced
tree) and are symlinked to `~/.config/dotfiles/`:

```
.dotfiles-config              # shared across all devices
.dotfiles-config.mac          # all mac devices
.dotfiles-config.mac.personal # this specific device
```

Available settings:
- `ENABLE_ZPROF=yes` - enable zsh profiling
- `ANTIGEN_BUNDLE_NODE=y` - enable Node.js completion bundles

Use `edit-dotfiles-config` to edit the most specific config for this device.

### Private Configuration
Private/sensitive configs aren't tracked in this public repo. The local
entry point is always `~/.dotfiles-private/`, which is a symlink. There
are two backends, picked per machine:

1. **Cloud-only (legacy default)** — `~/.dotfiles-private` symlinks into
   Google Drive (preferred) or Dropbox (fallback). All edits sync via
   the cloud provider. Vulnerable to FileProvider stalls on machines
   where the GDrive folder resolves through a `.shortcut-targets-by-id/`
   path; observed multi-second `stat()` hangs that wedge shell startup.
2. **GitHub + GDrive runtime hybrid** (run `setup-private-repo` to
   migrate to this) — `~/.dotfiles-private` symlinks to a local clone
   at `~/projects/joshm1/dotfiles-private`. Slow-moving config files
   (`.zshrc.before/after.*`, `.gitconfig*`, `.config/...`, hand-curated
   skill source, etc.) are git-tracked. High-churn / per-device runtime
   state (zsh history, REPL histories, `~/.claude/projects/`,
   `~/.claude/history.jsonl`, etc.) sync via Google Drive into a
   per-machine subdir at `<gdrive>/dotfiles-runtime/${device_id}/` —
   each machine writes only to its own subdir, so there's nothing to
   merge.

Files are sourced hierarchically based on `device_id` (e.g.,
`mac.personal`):

```
.zshrc.before              # shared
.zshrc.before.mac          # all mac devices
.zshrc.before.mac.personal # this specific device
...main zshrc...
.zshrc.after               # shared
.zshrc.after.mac           # all mac devices
.zshrc.after.mac.personal  # this specific device
```

#### Switching to the GitHub + GDrive hybrid

```bash
uv run setup-private-repo               # one-time, per machine
```

Bootstrap creates the GitHub repo on first run, clones it locally,
copies the git-tracked subset of files from the existing GDrive copy
into the clone, retargets the `~/.dotfiles-private` symlink, sets up
the per-machine GDrive runtime bucket, and registers two LaunchAgents:

- `com.dotfiles-private.check-repo` (hourly) — `git fetch` + check
  for behind/ahead/uncommitted state, fire one macOS notification when
  out of sync. Never auto-pulls or auto-pushes.
- `com.dotfiles-private.sync-runtime` (every 5 min) — rsync the
  runtime subset between local and `<gdrive>/dotfiles-runtime/${device_id}/`.

Manual on-demand commands:

- `check-private-repo --status` — show local vs origin state.
- `check-private-repo --force` — fire notification regardless of cooldown.
- `sync-private-runtime` — pull-then-push immediately.
- `sync-private-runtime --pull` / `--push` / `--status`.

Rollback: `setup-private-repo --rollback` re-points
`~/.dotfiles-private` back at the old GDrive target (snapshot saved at
`~/.cache/dotfiles-private/old-symlink-target.txt`). The local clone,
runtime bucket, and LaunchAgents are left in place. The original GDrive
copy of `~/.dotfiles-private/` is never modified by the bootstrap.

**Storage providers**: the runtime bucket prefers Google Drive but falls
back to Dropbox if GD isn't mounted. So a Dropbox-only machine still
gets cross-machine sync of zsh history / `~/.claude/projects/` etc., it
just lives at `<dropbox>/dotfiles-runtime/${device_id}/` instead.

**Non-macOS limitation**: the two LaunchAgents only register on macOS.
Linux/WSL machines should set up cron or systemd-user units that invoke
`uv run check-private-repo` hourly and `uv run sync-private-runtime`
every 5 minutes.

### Symlink Management
Dotfiles are organized in the `home/` directory, which mirrors the `$HOME` directory structure. The setup script automatically discovers and symlinks all files from `home/` to `$HOME`.

**Structure:**
```
dotfiles/
  home/
    .gitconfig → $HOME/.gitconfig
    .zshrc → $HOME/.zshrc
    .tmux.conf → $HOME/.tmux.conf
    .config/
      mise/.symlink-dir → $HOME/.config/mise/
      nvim/.symlink-dir → $HOME/.config/nvim/
      tmux/.symlink-dir → $HOME/.config/tmux/
      tmux-powerline/.symlink-dir → $HOME/.config/tmux-powerline/
```

**How it works:**
1. Python script `symlink-home-files` (from `dotfiles_scripts/symlink_home.py`) auto-discovers files in `home/`
2. For each file/directory, it creates a symlink to the corresponding location in `$HOME`
3. Directories containing a `.symlink-dir` tag file are symlinked as a whole (not recursed into). This is defined in `setup_utils.py:SYMLINK_DIR_TAG`.
4. Existing files are backed up to timestamped directory (`~/.dotfiles.YYYYMMDD-HHMMSS.bck/`)
5. Already-correct symlinks are skipped

**Adding new dotfiles:**
Simply add the file to `home/` in the structure you want (e.g., `home/.myconfig` → `~/.myconfig`), and it will be automatically symlinked on next setup run. For config directories that should be symlinked as a whole, add a `.symlink-dir` tag file inside.

### Shell Configuration Flow (home/.zshrc)
1. Load device ID and hierarchical config (`_source_hierarchy`)
2. Source private pre-config from `~/.dotfiles-private/...` via the symlinked `~/.zshrc.before.*`
3. Configure direnv (silent export before instant prompt)
4. Enable Powerlevel10k instant prompt
5. Load antidote (zsh plugin manager) from static plugin list (`~/.zsh_plugins.txt`):
   - oh-my-zsh lib, brew, command-not-found
   - zsh-syntax-highlighting, zsh-autosuggestions (deferred)
   - fzf, git, wd, zap-zsh/supercharge, zap-zsh/exa
   - Powerlevel10k theme
   - Node.js bundles (conditional on `ANTIGEN_BUNDLE_NODE=y`)
7. Autoload custom functions from `~/.zsh/functions/`
8. Configure cloud-synced zsh history at `~/.dotfiles-private/zsh_history/.zsh_history.${device_id}`
9. Initialize zoxide (better cd)
10. Set up eza aliases, fzf config, tool completions (Docker, AWS, bun, just, uv)
11. Configure PATH for go, pnpm, bun, cargo, Claude CLI, neovim nightly
12. Source private post-config from `~/.dotfiles-private/...` via the symlinked `~/.zshrc.after.*`
13. Initialize atuin (shell history search)
14. Activate mise (`eval "$(mise activate zsh)"`)

### Version Management Strategy
This dotfiles repo uses mise for language version management. Legacy asdf support exists as a lazy-loaded fallback.

### Tmux Configuration
Uses TPM (Tmux Plugin Manager) with plugins:
- tmux-resurrect, tmux-continuum (session persistence)
- vim-tmux-navigator (seamless vim/tmux navigation)
- tmux-powerline, catppuccin theme
- Custom sesh integration (Ctrl+T) for session management

### Git Configuration
The gitconfig includes:
- Extensive git aliases (see `home/.gitconfig`)
- Delta as pager for better diffs
- Pull with rebase by default
- Custom functions in .zshrc:
  - `git-stats [refs]` - Show commit statistics
  - `git-diff-stats` - Show diff statistics
  - `gch` - Interactive branch checkout with fzf preview

### Neovim
Configuration is in `home/.config/nvim/init.lua`.

## Custom Shell Functions

### Notable zsh functions
Custom functions are autoloaded from `~/.zsh/functions/` via `fpath` (add new functions there):
- `load-local-venv` - Auto-activates `.venv` when entering project directories (triggered via `chpwd` hook)
- `sesh-sessions` - Fuzzy find tmux/zellij sessions (bound to Alt+s)
- `gch` - Interactive git branch checkout with fzf and log preview

## Common Development Tasks

### Managing Homebrew packages
```bash
# Edit package lists
vim homebrew/Brewfile        # Core CLI tools
vim homebrew/Brewfile-casks  # GUI applications

# Re-run bundle installation
rm homebrew/.installed
./setup
```

### Installing/upgrading language versions
Language versions are managed via `.tool-versions` or `.mise.toml` config files.
Edit the config file and run `mise install` to apply changes.

### Testing changes to .zshrc
```bash
# Reload shell config
source ~/.zshrc

# Profile zsh startup time
ENABLE_ZPROF=yes zsh -ic exit
```

## Important Files to Modify

When making changes to this dotfiles repo:

1. **Adding new tools**: Edit `homebrew/Brewfile*` and re-run `./setup` (or delete `homebrew/.installed` first)
2. **Changing default versions**: Edit `.mise.toml` or use `mise use <tool>@<version>`
3. **Shell customization**: Edit `home/.zshrc` (or private configs in Dropbox)
4. **Git aliases/config**: Edit `home/.gitconfig`
5. **Tmux bindings**: Edit `home/.tmux.conf`
6. **Neovim**: Edit `home/.config/nvim/init.lua`
7. **Adding new dotfiles**: Add to `home/` directory in desired structure

## Utility Scripts

This repository uses a Python package structure for all utility scripts. Scripts are organized as a proper Python package with dependency management via uv.

### Project Structure
```
dotfiles/
  pyproject.toml          # Python project configuration
  dotfiles_scripts/       # Python package
    __init__.py
    setup.py              # Main orchestrator (dotfiles-setup CLI)
    setup_utils.py        # Shared setup utilities (DOTFILES, DOTFILES_REPO, run_cmd, create_symlink)
    setup_*.py            # Per-component setup modules (device_id, homebrew, mise, zsh, etc.)
    utils.py              # Lightweight utilities for standalone scripts
    symlink_home.py       # Auto-symlink home/ files
    check_homebrew.py     # Check Homebrew apps
```

### Writing New Scripts

**Guidelines:**
1. Add new scripts to `dotfiles_scripts/` as Python modules
2. Use `dotfiles_scripts.setup_utils` for setup scripts (constants, `run_cmd`, `create_symlink`) or `dotfiles_scripts.utils` for standalone utility scripts (`get_dotfiles_dir`)
3. Use `click` for CLI argument parsing
4. Use `rich` for beautiful terminal output (tables, progress bars, colors)
5. Add console script entry points to `pyproject.toml`:
   ```toml
   [project.scripts]
   my-script-name = "dotfiles_scripts.my_module:main"
   ```
6. Dependencies are managed in `pyproject.toml`, NOT inline PEP 723 headers

**Running scripts:**
```bash
# Using console script (after adding to pyproject.toml)
uv run script-name

# Or run module directly
uv run -m dotfiles_scripts.module_name
```

**Available Scripts:**
- `symlink-home-files` - Auto-discover and symlink all files from `home/` to `$HOME`
  ```bash
  # Run symlink operation
  uv run symlink-home-files

  # Dry run - show what would be done without making changes
  uv run symlink-home-files --dry-run
  ```

- `check-homebrew-apps` - Find apps in /Applications available in Homebrew but not installed via Homebrew
  ```bash
  # Basic usage
  uv run check-homebrew-apps

  # Show verbose progress
  uv run check-homebrew-apps --verbose

  # Different output formats
  uv run check-homebrew-apps -f table    # Default: nice table
  uv run check-homebrew-apps -f list     # Simple list
  uv run check-homebrew-apps -f brewfile # Output as Brewfile entries
  ```

### Adding a New Script
Add module to `dotfiles_scripts/`, then register in `pyproject.toml`:
```toml
[project.scripts]
my-new-script = "dotfiles_scripts.my_new_script:main"
```

## Notes

- The repo expects to be cloned at `~/projects/joshm1/dotfiles`
- Symlink target is always `~/.dotfiles`
- Setup is idempotent - scripts check for existing installations
- Homebrew bundle only runs once (tracked by `homebrew/.installed`)
- Language runtimes are managed by mise (see `.mise.toml`)
