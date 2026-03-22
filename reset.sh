#!/bin/bash
#
# Reset machine state so bootstrap.sh can be re-tested from scratch.
# Does NOT uninstall Homebrew, Xcode CLI tools, or GUI apps.
#
# Usage:
#   ./reset.sh          # interactive confirmation (requires TTY)
#   ./reset.sh --force  # skip confirmation (for scripting/SSH)
#

set -e

info()    { printf '\033[1;34m==> %s\033[0m\n' "$1"; }
success() { printf '\033[1;32m==> %s\033[0m\n' "$1"; }
warn()    { printf '\033[1;33m==> %s\033[0m\n' "$1"; }
error()   { printf '\033[1;31m==> %s\033[0m\n' "$1"; }

FORCE=false
[[ "${1:-}" == "--force" ]] && FORCE=true

if [[ "$FORCE" != true ]]; then
    if [[ ! -t 0 ]]; then
        error "Not running in a TTY. Use --force to skip confirmation."
        exit 1
    fi

    warn "This will reset your dotfiles setup:"
    echo "    - Remove ~/projects/joshm1/dotfiles"
    echo "    - Remove ~/.dotfiles symlink"
    echo "    - Remove ~/.device_id"
    echo "    - Remove ~/.claude"
    echo "    - Uninstall Claude Code (npm)"
    echo
    printf '    Type "reset" to confirm: '
    read -r confirm
    if [[ "$confirm" != "reset" ]]; then
        echo "Aborted."
        exit 0
    fi
fi

REPO_DIR="$HOME/projects/joshm1/dotfiles"

# Remove cloned dotfiles repo
if [[ -d "$REPO_DIR" ]]; then
    info "Removing $REPO_DIR..."
    rm -rf "$REPO_DIR"
    success "Removed"
fi

# Remove dotfiles symlink
if [[ -L "$HOME/.dotfiles" ]]; then
    info "Removing ~/.dotfiles symlink..."
    rm "$HOME/.dotfiles"
    success "Removed"
fi

# Remove device ID
if [[ -f "$HOME/.device_id" ]]; then
    info "Removing ~/.device_id..."
    rm "$HOME/.device_id"
    success "Removed"
fi

# Remove Claude Code auth
if [[ -d "$HOME/.claude" ]]; then
    info "Removing ~/.claude..."
    rm -rf "$HOME/.claude"
    success "Removed"
fi

# Remove npm global claude-code
if command -v claude &>/dev/null; then
    info "Uninstalling Claude Code..."
    npm uninstall -g @anthropic-ai/claude-code 2>/dev/null || true
    success "Uninstalled"
fi

success "Reset complete. Ready to re-run bootstrap.sh"
