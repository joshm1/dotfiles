#!/bin/bash
#
# Dotfiles bootstrap for a fresh macOS machine.
#
#   bash <(curl -fsSL https://raw.githubusercontent.com/joshm1/dotfiles/main/bootstrap.sh)
#
# This script handles the chicken-and-egg problem: you need a browser to sign
# into Dropbox/1Password, but those are installed by the setup script.
#
# Flow:
#   1. Install Xcode CLI tools (for git)
#   2. Install Homebrew
#   3. Clone the dotfiles repo
#   4. Install essential apps (browser, 1Password, Dropbox, Claude Code)
#   5. Prompt user to sign in
#   6. Wait for Dropbox to sync
#   7. Hand off to Claude Code to finish setup
#

set -e

FORCE=false
[[ "${1:-}" == "--force" ]] && FORCE=true

REPO_DIR="$HOME/projects/joshm1/dotfiles"
REPO_URL="https://github.com/joshm1/dotfiles.git"
DROPBOX_DOTFILES="$HOME/Dropbox/dotfiles"

# --- Helpers ---

info()    { printf '\033[1;34m==> %s\033[0m\n' "$1"; }
success() { printf '\033[1;32m==> %s\033[0m\n' "$1"; }
warn()    { printf '\033[1;33m==> %s\033[0m\n' "$1"; }
error()   { printf '\033[1;31m==> %s\033[0m\n' "$1"; }

prompt_continue() {
    if [[ "$FORCE" == true ]]; then
        info "(skipping prompt: $1)"
        return
    fi
    printf '\n\033[1;33m==> %s\033[0m\n' "$1"
    printf '    Press Enter to continue... '
    read -r </dev/tty
}

# --- Phase 0: Xcode CLI tools ---

if ! xcode-select -p &>/dev/null; then
    info "Installing Xcode Command Line Tools..."
    xcode-select --install
    echo "Waiting for Xcode CLI tools to finish installing..."
    until xcode-select -p &>/dev/null; do
        sleep 5
    done
    success "Xcode CLI tools installed"
else
    success "Xcode CLI tools already installed"
fi

# --- Phase 1: Homebrew ---

# Fix permissions before anything else (common on migrated/restored machines or re-runs)
if [[ -d /opt/homebrew && ! -w /opt/homebrew ]]; then
    warn "Fixing Homebrew permissions on /opt/homebrew (requires sudo)..."
    # Ensure sudo can prompt even when script is piped via curl | bash
    sudo -v </dev/tty
    sudo chown -R "$(whoami)" /opt/homebrew
    success "Homebrew permissions fixed"
fi

if ! command -v brew &>/dev/null; then
    # brew not on PATH — check if it exists but just needs shellenv
    if [[ -f /opt/homebrew/bin/brew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
        success "Homebrew already installed (added to PATH)"
    elif [[ -f /usr/local/bin/brew ]]; then
        eval "$(/usr/local/bin/brew shellenv)"
        success "Homebrew already installed (added to PATH)"
    else
        info "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        if [[ -f /opt/homebrew/bin/brew ]]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        elif [[ -f /usr/local/bin/brew ]]; then
            eval "$(/usr/local/bin/brew shellenv)"
        fi
        success "Homebrew installed"
    fi
else
    success "Homebrew already installed"
fi

# --- Phase 2: Clone repo ---

if [[ -d "$REPO_DIR/.git" ]]; then
    success "Dotfiles repo already cloned at $REPO_DIR"
else
    info "Cloning dotfiles repo..."
    mkdir -p "$(dirname "$REPO_DIR")"
    git clone "$REPO_URL" "$REPO_DIR"
    success "Cloned to $REPO_DIR"
fi

# --- Phase 3: Essential apps ---

info "Installing essential apps..."

ESSENTIAL_CASKS=(google-chrome 1password dropbox)
for cask in "${ESSENTIAL_CASKS[@]}"; do
    if brew list --cask "$cask" &>/dev/null; then
        success "$cask already installed"
    else
        info "Installing $cask..."
        brew install --cask "$cask"
    fi
done

# Set Chrome as default browser (may fail over SSH, that's ok)
if ! command -v duti &>/dev/null; then
    brew install duti
fi
info "Setting Chrome as default browser..."
duti -s com.google.Chrome http 2>/dev/null || true
duti -s com.google.Chrome https 2>/dev/null || true
duti -s com.google.Chrome public.html 2>/dev/null || true
duti -s com.google.Chrome public.url 2>/dev/null || true
prompt_continue "If macOS prompted you to change default browser, accept it now."

# Claude Code needs Node.js
if ! command -v node &>/dev/null; then
    info "Installing Node.js..."
    brew install node
fi

if ! command -v claude &>/dev/null; then
    info "Installing Claude Code..."
    npm install -g @anthropic-ai/claude-code
    success "Claude Code installed"
else
    success "Claude Code already installed"
fi

# --- Phase 4: Sign in ---

info "Opening essential apps..."
open -a "Google Chrome"
open -a "1Password"
open -a "Dropbox"

prompt_continue "Sign into Google Chrome, 1Password, and Dropbox, then come back here."

# Authenticate Claude Code
if claude auth status 2>&1 | grep -q 'subscriptionType.*max'; then
    success "Claude Code already authenticated"
else
    info "Authenticating Claude Code..."
    claude auth login --claudeai
fi

# --- Phase 5: Wait for Dropbox sync ---

if [[ -d "$DROPBOX_DOTFILES" ]]; then
    success "Dropbox dotfiles already synced"
else
    info "Waiting for Dropbox to sync ~/Dropbox/dotfiles..."
    echo "    (Tip: in Dropbox preferences, prioritize syncing the 'dotfiles' folder)"
    while [[ ! -d "$DROPBOX_DOTFILES" ]]; do
        printf '.'
        sleep 5
    done
    echo
    success "Dropbox dotfiles synced"
fi

# --- Phase 6: Hand off to Claude Code ---

info "Handing off to Claude Code to finish setup..."
cd "$REPO_DIR"
exec claude "$(cat <<'PROMPT'
Set up this machine using the dotfiles in this repo.

1. Ask me two questions before starting:
   a. What device ID to use for this machine (e.g. mac.personal, mac.work). Device IDs use dot-separated namespaces for hierarchical config.
   b. Should I copy the existing ~/.zsh_history to Dropbox? (Only if ~/.zsh_history exists and has content worth preserving)

2. Create the device ID file:
   echo "{device_id}" > ~/.device_id

3. If I said yes to copying zsh_history:
   mkdir -p ~/Dropbox/dotfiles/zsh_history
   cp ~/.zsh_history ~/Dropbox/dotfiles/zsh_history/.zsh_history.{device_id}

4. Run the setup script:
   ./setup

5. After setup completes, remind me to open a new terminal tab and run: p10k configure
PROMPT
)"
