# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a personal dotfiles repository for macOS that manages shell configuration (zsh), development tools (via Homebrew and asdf), tmux setup, neovim configuration, and git settings. The repository uses symlinks to install dotfiles from `~/projects/joshm1/dotfiles` (stored as `$DOTFILES` = `~/.dotfiles`) to their standard locations.

## Git Workflow

**IMPORTANT:** Do NOT proactively run `git add` or `git commit` commands unless the user explicitly asks you to create a commit. The user prefers to handle git operations themselves.

- ✅ Make code changes, create files, edit files as requested
- ✅ Show git status when asked or when changes are complete
- ❌ Do NOT run `git add` without being asked
- ❌ Do NOT run `git commit` without being asked
- ❌ Do NOT run `git push` without being asked

When the user explicitly says "commit this" or "create a commit", then and only then should you stage changes and create commits.

## Installation & Setup

### Initial Setup
```bash
xcode-select --install
mkdir -p ~/projects/joshm1
git clone https://github.com/joshm1/dotfiles.git ~/projects/joshm1/dotfiles
cd ~/projects/joshm1/dotfiles
./setup
# In new tab: p10k configure
```

### Main Setup Script
`./setup` is the main entry point that:
1. Updates git submodules
2. Creates symlinks for all dotfiles
3. Runs component-specific setup scripts in order

### Setup Scripts
All setup scripts source `./utils.sh` for common functions and variables. Run these individually only when needed:
- `setup-zsh` - Configures zsh with antigen
- `setup-vim` - Sets up neovim
- `setup-asdf` - Installs asdf plugins (java, nodejs, python, ruby) with default versions
- `setup-python`, `setup-nodejs`, `setup-ruby` - Language-specific setups (run after asdf)
- `setup-dropbox` - Links private config files
- `setup-zsh-history` - Configures shared zsh history (requires Dropbox)

## Key Architecture

### Configuration Variables (utils.sh)
Default versions for tools are defined in `utils.sh`:
- `DEFAULT_NODE_VERSION=24.4.0`
- `DEFAULT_RUBY_VERSION=2.7.4`
- `DEFAULT_JAVA_VERSION=adoptopenjdk-17.0.5+8`
- `DEFAULT_PYTHON_VERSION=3.12.7`
- `DOTFILES=$HOME/.dotfiles`
- `DROPBOX_DIR=$HOME/Dropbox`

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
      nvim/ → $HOME/.config/nvim/
      tmux/ → $HOME/.config/tmux/
    ...
```

**How it works:**
1. Python script `symlink-home-files` (from `dotfiles_scripts/symlink_home.py`) auto-discovers files in `home/`
2. For each file/directory, it creates a symlink to the corresponding location in `$HOME`
3. Existing files are backed up to timestamped directory (`~/.dotfiles.YYYYMMDD-HHMMSS.bck/`)
4. Already-correct symlinks are skipped

**Adding new dotfiles:**
Simply add the file to `home/` in the structure you want (e.g., `home/.myconfig` → `~/.myconfig`), and it will be automatically symlinked on next setup run.

### Shell Configuration Flow (home/.zshrc)
1. Load private pre-config from Dropbox
2. Enable Powerlevel10k instant prompt
3. Configure direnv
4. Load antigen (zsh plugin manager) and bundles:
   - oh-my-zsh base
   - zsh-syntax-highlighting, zsh-autosuggestions
   - fzf, git, wd (warp directory)
   - Language version managers (conditional on env vars)
5. Apply antigen theme (Powerlevel10k)
6. Initialize zoxide (better cd)
7. Set up custom aliases and functions
8. Load private post-config from Dropbox
9. Initialize asdf (lazy loaded via `source_asdf` function)

### Version Management Strategy
This dotfiles repo uses asdf for all language version management (Java, Node.js, Python, Ruby, Go).

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
- `source_asdf()` - Lazy loads asdf or prompts to install via Homebrew
- `set_java_home()` - Sets JAVA_HOME for asdf-managed Java
- `gch()` - Interactive git branch checkout with fzf and log preview
- `sesh-sessions()` - Fuzzy find tmux/zellij sessions (bound to Alt+s)
- `load-local-venv()` - Auto-activates `.venv` when entering project directories

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
```bash
# Check current versions in utils.sh
vim utils.sh

# Install new version with asdf
source_asdf  # Initialize asdf if not loaded
asdf install python 3.13.0
asdf global python 3.13.0

# Or re-run setup script
source ./setup-python
```

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
2. **Changing default versions**: Edit version constants in `utils.sh`
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
    utils.py              # Shared utilities
    symlink_home.py       # Auto-symlink home/ files
    check_homebrew.py     # Check Homebrew apps
```

### Writing New Scripts

**Guidelines:**
1. Add new scripts to `dotfiles_scripts/` as Python modules
2. Use shared utilities from `dotfiles_scripts.utils` (e.g., `get_dotfiles_dir()`, `get_backup_dir()`)
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

### Example: Creating a New Script

```python
# dotfiles_scripts/my_new_script.py
"""Description of what this script does."""

import click
from rich.console import Console
from dotfiles_scripts.utils import get_dotfiles_dir

console = Console()

@click.command()
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def main(verbose):
    """My new utility script."""
    dotfiles = get_dotfiles_dir()
    console.print(f"[green]Dotfiles directory: {dotfiles}[/green]")
    # Your logic here

if __name__ == "__main__":
    main()
```

Then add to `pyproject.toml`:
```toml
[project.scripts]
my-new-script = "dotfiles_scripts.my_new_script:main"
```

## Notes

- The repo expects to be cloned at `~/projects/joshm1/dotfiles`
- Symlink target is always `~/.dotfiles`
- Setup is idempotent - scripts check for existing installations
- Homebrew bundle only runs once (tracked by `homebrew/.installed`)
- asdf setup is commented out in main setup and loaded lazily via zsh function
