# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a personal dotfiles repository for macOS that manages shell configuration (zsh), development tools (via Homebrew and asdf), tmux setup, neovim configuration, and git settings. The repository uses symlinks to install dotfiles from `~/projects/joshm1/dotfiles` (stored as `$DOTFILES` = `~/.dotfiles`) to their standard locations.

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
- `setup-homebrew` - Installs Homebrew and bundles from `homebrew/Brewfile*`
- `setup-zsh` - Configures zsh with antigen
- `setup-vim` - Sets up neovim
- `setup-asdf` - Installs asdf plugins (java, nodejs, python, ruby) with default versions
- `setup-python`, `setup-nodejs`, `setup-ruby` - Language-specific setups (run after asdf)
- `setup-dropbox` - Links private config files
- `setup-zsh-history` - Configures shared zsh history (requires Dropbox)
- `setup-postgres` - Sets up PostgreSQL

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
Environment variables can be set in `~/.dotfiles-config` (not tracked in repo):
- `ENABLE_K8S` - "true" to enable kubernetes plugins
- `ENABLE_ZPROF` - "yes" to enable zsh profiling
- `ANTIGEN_BUNDLE_NODE` - "y" to enable Node.js completion bundles

### Private Configuration
Private/sensitive configs are stored in Dropbox (not in this repo):
- `~/Dropbox/dotfiles/.zshrc.before` - Sourced at start of .zshrc
- `~/Dropbox/dotfiles/.zshrc.after` - Sourced at end of .zshrc

### Symlink Management
The `symlink()` function in `utils.sh` safely creates symlinks by:
1. Checking if target already exists and points to source
2. Backing up existing files to timestamped directory (`$BCKDIR`)
3. Creating the symlink

Key symlinks created by setup:
- `.gitconfig` → `$DOTFILES/git/gitconfig`
- `.tmux.conf` → `$DOTFILES/.tmux.conf`
- `~/.config/nvim` → `$DOTFILES/.config/nvim`
- `~/.tool-versions` → `$DOTFILES/.tool-versions.home`

### Shell Configuration Flow (zsh/.zshrc)
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
- Extensive git aliases (see `git/gitconfig`)
- Delta as pager for better diffs
- Pull with rebase by default
- Custom functions in .zshrc:
  - `git-stats [refs]` - Show commit statistics
  - `git-diff-stats` - Show diff statistics
  - `gch` - Interactive branch checkout with fzf preview

### Neovim
Configuration is in `.config/nvim/init.lua`.

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
vim homebrew/Brewfile-mas    # Mac App Store apps

# Re-run bundle installation
rm homebrew/.installed
source ./setup-homebrew
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

1. **Adding new tools**: Edit `homebrew/Brewfile*` and re-run setup-homebrew
2. **Changing default versions**: Edit version constants in `utils.sh`
3. **Shell customization**: Edit `zsh/.zshrc` (or private configs in Dropbox)
4. **Git aliases/config**: Edit `git/gitconfig`
5. **Tmux bindings**: Edit `.tmux.conf`
6. **Neovim**: Edit `.config/nvim/init.lua`

## Notes

- The repo expects to be cloned at `~/projects/joshm1/dotfiles`
- Symlink target is always `~/.dotfiles`
- Setup is idempotent - scripts check for existing installations
- Homebrew bundle only runs once (tracked by `homebrew/.installed`)
- asdf setup is commented out in main setup and loaded lazily via zsh function
