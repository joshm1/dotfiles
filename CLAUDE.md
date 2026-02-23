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

## Key Architecture

### Configuration Variables
Common paths are defined in `dotfiles_scripts/setup_utils.py`:
- `DOTFILES = $HOME/.dotfiles`
- `DOTFILES_REPO = ~/projects/joshm1/dotfiles`
- `DROPBOX_DIR = $HOME/Dropbox`

Language versions are managed by mise (see `.mise.toml` files).

### Machine-Specific Configuration
Device-specific config files use hierarchical namespaces (e.g., `mac.personal`).
Files are in `~/Dropbox/dotfiles/home/.config/dotfiles/` and symlinked to `~/.config/dotfiles/`:

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
Private/sensitive configs are stored in Dropbox (not in this repo). Files are sourced hierarchically based on device_id (e.g., `mac.personal`):

```
.zshrc.before              # shared
.zshrc.before.mac          # all mac devices
.zshrc.before.mac.personal # this specific device
...main zshrc...
.zshrc.after               # shared
.zshrc.after.mac           # all mac devices
.zshrc.after.mac.personal  # this specific device
```

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
2. Source private pre-config from Dropbox (`.zshrc.before.*`)
3. Configure direnv (silent export before instant prompt)
4. Enable Powerlevel10k instant prompt
5. Load antidote (zsh plugin manager) from static plugin list (`~/.zsh_plugins.txt`):
   - oh-my-zsh lib, brew, command-not-found
   - zsh-syntax-highlighting, zsh-autosuggestions (deferred)
   - fzf, git, wd, zap-zsh/supercharge, zap-zsh/exa
   - Powerlevel10k theme
   - Node.js bundles (conditional on `ANTIGEN_BUNDLE_NODE=y`)
7. Autoload custom functions from `~/.zsh/functions/`
8. Configure Dropbox-synced zsh history (device-specific files)
9. Initialize zoxide (better cd)
10. Set up eza aliases, fzf config, tool completions (Docker, AWS, bun, just, uv)
11. Configure PATH for go, pnpm, bun, cargo, Claude CLI, neovim nightly
12. Source private post-config from Dropbox (`.zshrc.after.*`)
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
