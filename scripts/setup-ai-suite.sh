#!/usr/bin/env bash
#
# Install the AI coding CLIs and link agent skills on a headless Linux box
# (or any Linux/macOS machine). Idempotent and additive: it never touches shell
# config, system settings, or secrets, and it never signs in to anything.
#
#   Claude Code  (@anthropic-ai/claude-code)  -> `claude`
#   OpenAI Codex (@openai/codex)              -> `codex`
#   Antigravity  (official install.sh)        -> `agy`
#   T3 Code      (t3, optional: T3=1)         -> `t3`
#
# Expected clone locations (created as symlinks when missing; never moves an
# existing checkout, so macOS and Ubuntu/WSL paths are left alone):
#   ~/.dotfiles              -> this public repo
#   ~/.dotfiles-private      -> the private repo (if found)
#   ~/projects/joshm1/dotfiles[ -private ]
#     (what setup.py's DOTFILES_REPO / PRIVATE_DOTFILES_REPO_PATH expect)
#
# Skills: ~/.agents/skills is the canonical location (Codex reads it directly).
# ~/.claude/skills and ~/.gemini/config/skills (Antigravity) symlink to it.
# When both private (home/.agents/skills) and public (.agents/skills) trees
# exist, a union directory is built so both are visible.
#
# Env overrides:
#   SKILLS_SRC   if set, link ~/.agents/skills here and skip the union.
#   PRIVATE_DOTFILES_REPO  path to a clone of the private dotfiles repo.
#   T3=1         also install the T3 Code CLI.
#   SKIP_INSTALL=1  only link paths and skills.
#   FORCE_LINK=1 repoint existing working skills/path symlinks (default: leave them).

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="$HOME/.local/bin:$PATH"

log() { printf '==> %s\n' "$*" >&2; }
warn() { printf 'warn: %s\n' "$*" >&2; }

# Link $2 -> $1. Never replaces a real file/dir, and never repoints a working
# symlink (e.g. on a Mac that already manages these) unless FORCE_LINK=1.
link() {
    local target="$1" path="$2"
    mkdir -p "$(dirname "$path")"
    if [[ -e "$path" && ! -L "$path" ]]; then
        warn "$path exists and is not a symlink; leaving it alone"
        return 0
    fi
    if [[ -L "$path" && -e "$path" && "${FORCE_LINK:-0}" != 1 ]]; then
        log "$path already links to $(readlink "$path"); leaving it (FORCE_LINK=1 to repoint)"
        return 0
    fi
    ln -sfn "$target" "$path"
    log "linked $path -> $target"
}

install_npm_cli() {
    local bin="$1" pkg="$2"
    if command -v "$bin" >/dev/null 2>&1; then
        log "$bin already installed ($(command -v "$bin"))"
        return 0
    fi
    if ! command -v npm >/dev/null 2>&1; then
        warn "npm not found; cannot install $pkg"
        return 1
    fi
    log "installing $pkg"
    # Install into ~/.local so no sudo is needed (npm prefix is overridden for this call only).
    # Claude Code needs its postinstall script to fetch its native binary.
    npm install -g --prefix "$HOME/.local" --allow-scripts="$pkg" "$pkg"
}

install_agy() {
    if command -v agy >/dev/null 2>&1; then
        log "agy already installed ($(command -v agy))"
        return 0
    fi
    log "installing Antigravity CLI (official installer)"
    local tmp
    tmp="$(mktemp)"
    curl -fsSL https://antigravity.google/cli/install.sh -o "$tmp"
    bash "$tmp"
    rm -f "$tmp"
}

# Resolve the private clone without assuming a single layout.
find_private_repo() {
    local cand
    for cand in \
        "${PRIVATE_DOTFILES_REPO:-}" \
        "$HOME/.dotfiles-private" \
        "$HOME/projects/joshm1/dotfiles-private" \
        "$(dirname "$REPO_DIR")/dotfiles-private"; do
        if [[ -n "$cand" && -d "$cand/home" ]]; then
            # Prefer the real path so nested symlinks don't loop.
            (cd "$cand" && pwd -P)
            return
        fi
    done
}

# Put clones where the walker / install.sh / setup.py look. Safe on a Mac:
# existing real checkouts or working symlinks are left alone.
link_expected_paths() {
    local private
    private="$(find_private_repo || true)"

    mkdir -p "$HOME/projects/joshm1"
    link "$REPO_DIR" "$HOME/projects/joshm1/dotfiles"
    link "$REPO_DIR" "$HOME/.dotfiles"
    if [[ -n "$private" ]]; then
        link "$private" "$HOME/projects/joshm1/dotfiles-private"
        link "$private" "$HOME/.dotfiles-private"
    fi

    local cfg_dir="$HOME/.config/dotfiles"
    local cfg="$cfg_dir/.dotfiles-config"
    mkdir -p "$cfg_dir"
    if [[ ! -e "$cfg" ]]; then
        {
            echo "export PRIVATE_DOTFILES_REPO_PATH=\$HOME/projects/joshm1/dotfiles-private"
            echo "export PRIVATE_DOTFILES_REPO_GH=joshm1/dotfiles-private"
        } >"$cfg"
        log "wrote $cfg (box/local defaults; existing machines already have this file)"
    fi
}

# Build $HOME/.agents/skills-union with one symlink per skill dir from every
# source (private wins on name collision). Returns the path to use as
# ~/.agents/skills.
build_skills_union() {
    local union="$HOME/.agents/skills-union"
    local src name
    mkdir -p "$union"
    # Drop stale union entries so removed skills disappear on re-run.
    find "$union" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
    for src in "$@"; do
        [[ -d "$src" ]] || continue
        log "skills source: $src"
        for name in "$src"/*; do
            if [[ ! -e "$name" ]]; then
                if [[ -L "$name" ]]; then
                    warn "skipping broken skill symlink $name -> $(readlink "$name")"
                fi
                continue
            fi
            # Private is listed first; skip if a higher-priority entry exists.
            if [[ -e "$union/$(basename "$name")" ]]; then
                continue
            fi
            ln -sfn "$name" "$union/$(basename "$name")"
        done
    done
    printf '%s\n' "$union"
}

link_skills() {
    local private public src
    if [[ -n "${SKILLS_SRC:-}" ]]; then
        src="$SKILLS_SRC"
    else
        private="$(find_private_repo || true)"
        public="$REPO_DIR/.agents/skills"
        local -a sources=()
        if [[ -n "$private" && -d "$private/home/.agents/skills" ]]; then
            sources+=("$private/home/.agents/skills")
        elif [[ -d "$HOME/.dotfiles-private/home/.agents/skills" ]]; then
            sources+=("$HOME/.dotfiles-private/home/.agents/skills")
        fi
        if [[ -d "$public" ]]; then
            sources+=("$public")
        fi
        if [[ ${#sources[@]} -eq 0 ]]; then
            warn "no skills source found; set SKILLS_SRC"
            return 0
        fi
        if [[ ${#sources[@]} -eq 1 ]]; then
            src="${sources[0]}"
        else
            src="$(build_skills_union "${sources[@]}")"
        fi
    fi
    log "skills target: $src"
    link "$src" "$HOME/.agents/skills"
    if [[ -L "$HOME/.agents/skills" || -d "$HOME/.agents/skills" ]]; then
        link "$HOME/.agents/skills" "$HOME/.claude/skills"
        link "$HOME/.agents/skills" "$HOME/.gemini/config/skills"
    fi
    if [[ -d "$HOME/.agents/skills" ]]; then
        local dirs skillmds
        dirs="$(find -L "$HOME/.agents/skills" -mindepth 1 -maxdepth 1 | wc -l | tr -d ' ')"
        skillmds="$(find -L "$HOME/.agents/skills" -name SKILL.md | wc -l | tr -d ' ')"
        log "skills visible: $dirs top-level entries, $skillmds SKILL.md files"
    fi
}

main() {
    link_expected_paths

    if [[ "${SKIP_INSTALL:-0}" != 1 ]]; then
        install_npm_cli claude @anthropic-ai/claude-code || warn "claude-code install failed"
        install_npm_cli codex @openai/codex || warn "codex install failed"
        install_agy || warn "agy install failed"
        if [[ "${T3:-0}" == 1 ]]; then
            install_npm_cli t3 t3 || warn "t3 install failed"
        fi
    fi

    link_skills

    log "done. Sign in yourself: 'claude auth login', 'codex login --device-auth', 'agy'."
}

main "$@"
