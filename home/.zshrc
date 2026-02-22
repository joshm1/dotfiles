# Load device ID for device-specific config (e.g., mac.personal, macbook-pro.work)
[[ -f "$HOME/.device_id" ]] && _device_id=$(<"$HOME/.device_id")

# Source hierarchical config files
# For device_id=mac.personal: sources base, base.mac, base.mac.personal (if they exist)
_source_hierarchy() {
  local base="$1" id="$2" prefix=""
  test -f "$base" && source "$base"
  [[ -z "$id" ]] && return
  for segment in ${(s:.:)id}; do
    prefix="${prefix:+$prefix.}$segment"
    test -f "$base.$prefix" && source "$base.$prefix"
  done
}

# Machine-specific env vars (symlinked from ~/Dropbox/dotfiles/home/.config/dotfiles/)
_source_hierarchy "$HOME/.config/dotfiles/.dotfiles-config" "$_device_id"

# Private config sourced before everything else
_source_hierarchy "$HOME/.zshrc.before" "$_device_id"

# var $1 is truthy if it starts with "y", equals "true", or equals "1"
bool() {
  [[ $1 = y* || $1 = true || $1 = 1 ]]
}

# Platform detection
is_macos() { [[ "$OSTYPE" == darwin* ]] }
is_linux() { [[ "$OSTYPE" == linux* ]] }

# set ENABLE_ZPROF=yes in ~/.dotfiles-config to enable
enable_zprof() { bool $ENABLE_ZPROF }
enable_zprof && zmodload zsh/zprof

# direnv export: Silently set up environment vars BEFORE instant prompt (no console output)
# This is needed to prevent "direnv: unloading" messages during instant prompt
(( ${+commands[direnv]} )) && emulate zsh -c "$(direnv export zsh)"

# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

export LANG=en_US.UTF-8

# Preferred editor for local and remote sessions
export VISUAL='nvim'
export EDITOR="$VISUAL"
export GIT_EDITOR="$EDITOR"
export FZF_DEFAULT_COMMAND='ag -g ""'

if [ -f $HOME/.antigen.zsh ]; then
  source $HOME/.antigen.zsh
else
  (){
    declare -i i=0
    antigen() {
      [[ $i -eq 0 ]] && echo "ERROR: ~/.antigen.zsh does not exist"
      echo "  * cannot run antigen $@"
      ((i++))
    }
  }
fi

antigen use oh-my-zsh

antigen bundle brew
antigen bundle command-not-found
antigen bundle fzf
antigen bundle git
antigen bundle wd
antigen bundle zsh-users/zsh-syntax-highlighting
antigen bundle zsh-users/zsh-autosuggestions
antigen bundle zap-zsh/supercharge
antigen bundle zap-zsh/exa

# REMOVED: zsh-autoswitch-virtualenv conflicts with custom load-local-venv function (line ~258)
# Causes "_default_venv:8: command not found: deactivate" error

# set ANTIGEN_BUNDLE_NODE=y in ~/.dotfiles-config to enable
if [[ "$ANTIGEN_BUNDLE_NODE" = y* ]]; then
  antigen bundle lukechilds/zsh-better-npm-completion
  antigen bundle g-plane/zsh-yarn-autocompletions
fi

antigen theme romkatv/powerlevel10k

antigen apply

# Autoload custom functions from ~/.zsh/functions
fpath=(~/.zsh/functions $fpath)
autoload -Uz ~/.zsh/functions/*(.:t) 2>/dev/null

# History file in Dropbox for sync across machines (must be after antigen/oh-my-zsh)
# Uses device-specific file if ~/.device_id exists (created by setup-zsh-history)
if [[ -n "$_device_id" ]]; then
  _histfile="$HOME/Dropbox/dotfiles/zsh_history/.zsh_history.${_device_id}"
  if [[ -f "$_histfile" ]]; then
    export HISTFILE="$_histfile"
  else
    echo "Warning: Device history file not found: $_histfile"
  fi
  unset _histfile
elif [[ -f "$HOME/Dropbox/dotfiles/zsh_history/.zsh_history" ]]; then
  export HISTFILE="$HOME/Dropbox/dotfiles/zsh_history/.zsh_history"
else
  echo "Warning: Dropbox zsh_history not found, using default ~/.zsh_history"
fi

# we want to use buf from https://docs.buf.build
alias buf >/dev/null && unalias buf

# Initialize zoxide and ensure z command is not overridden by fz plugin
if command -v zoxide &>/dev/null; then
  eval "$(zoxide init zsh)"
  alias z >/dev/null 2>&1 && unalias z
fi

export NODE_REPL_HISTORY_FILE=~/.node_history

# do not beep on error
setopt no_beep

alias vim="nvim"
alias vi="nvim"
[ -d "$HOME/.local/bin" ] && path=("$HOME/.local/bin" $path)
[ -d "$HOME/bin" ] && path=("$HOME/bin" $path)

alias gitpurge="git checkout master && git remote update --prune | git branch -r --merged | grep -v master | grep origin/ | sed -e 's/origin\//:/' | xargs git push origin"

export FZF_DEFAULT_OPTS='--preview "([[ -f {} ]] && bat --style=numbers --color=always --line-range :500 {}) || ([[ -d {} ]] && eza -T --git-ignore --icons --group-directories-first -la {})"'
export FZF_DEFAULT_COMMAND='fd --type f --strip-cwd-prefix --hidden --follow'
export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"
export FZF_CTRL_R_OPTS="--preview ''"

# Private config sourced after everything else
_source_hierarchy "$HOME/.zshrc.after" "$_device_id"

# Cleanup
unset _device_id
unset -f _source_hierarchy

enable_zprof && zprof
unset -f enable_zprof


# https://buildpacks.io/docs/tools/pack/
if type pack >/dev/null 2>&1; then
. $(pack completion --shell zsh)
fi

# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
# Use a lean config for SSH sessions (e.g., Terminus/mosh)
if [[ -n "$SSH_CONNECTION" ]] && [[ -f ~/.p10k-ssh.zsh ]]; then
  source ~/.p10k-ssh.zsh
else
  [[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh
fi

[ -d "$HOME/.yarn/bin" ] && path=("$HOME/.yarn/bin" $path)
[ -d "$HOME/.config/yarn/global/node_modules/.bin" ] && path=("$HOME/.config/yarn/global/node_modules/.bin" $path)

[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh

if [[ -f ~/.docker/init-zsh.sh ]]; then
  source ~/.docker/init-zsh.sh || true # Added by Docker Desktop
fi

# aws completion: lazy-loaded on first aws<tab> to avoid startup cost
_lazy_aws_completer() {
  unfunction _lazy_aws_completer
  autoload -Uz bashcompinit && bashcompinit
  complete -C "${HOMEBREW_PREFIX:-/opt/homebrew}/bin/aws_completer" aws
  # Re-trigger completion for the current command line
  _bash_complete
}
type aws_completer &>/dev/null && compdef _lazy_aws_completer aws

[ -f $HOME/.cargo/env ] && . "$HOME/.cargo/env"

# Cache brew prefix to avoid repeated subprocess calls
_brew_prefix="${HOMEBREW_PREFIX:-/opt/homebrew}"

# https://github.com/eza-community/eza/blob/main/INSTALL.md#for-zsh-with-homebrew
if type brew &>/dev/null; then
  fpath=("$_brew_prefix/share/zsh/site-functions" $fpath)
fi


# alias for eza
alias ls='eza --color=always --group-directories-first --icons=always'
alias ll='eza -la --icons --octal-permissions --group-directories-first'
alias l='eza -bGF --header --git --color=always --group-directories-first --icons'
# alias llm='eza -lbGd --header --git --sort=modified --color=always --group-directories-first --icons'
alias la='eza --long --all --group --group-directories-first'
alias lx='eza -lbhHigUmuSa@ --time-style=long-iso --git --color-scale --color=always --group-directories-first --icons'
alias tree='ll --tree --level=2'

alias lS='eza -1 --color=always --group-directories-first --icons=always'
alias lt='eza --tree --level=2 --color=always --group-directories-first --icons=always'
alias l.="eza -a | grep -E '^\.'"

# source: https://github.com/astral-sh/uv/issues/8432
# Fix completions for uv run to autocomplete .py files
_uv_run_mod() {
    if [[ "$words[2]" == "run" && "$words[CURRENT]" != -* ]]; then
        _arguments '*:filename:_files -g "*.py"'
    else
        _uv "$@"
    fi
}
compdef _uv_run_mod uv

# Auto-activate venv when entering project directories
autoload -U add-zsh-hook
add-zsh-hook chpwd load-local-venv
load-local-venv  # Load for current session

# bun completions
[ -s "$HOME/.bun/_bun" ] && source "$HOME/.bun/_bun"

# bun
export BUN_INSTALL="$HOME/.bun"
[ -d "$BUN_INSTALL/bin" ] && path=("$BUN_INSTALL/bin" $path)
command -v just &>/dev/null && eval "$(just --completions zsh)"

# Docker CLI completions
[ -d "$HOME/.docker/completions" ] && fpath=("$HOME/.docker/completions" $fpath)

# Consolidated compinit — called once after all fpath modifications
autoload -Uz compinit
compinit -C

[ -f $HOME/.claude/local/claude ] && path=("$HOME/.claude/local" $path)

# go - add GOPATH/bin to PATH if go is installed
if command -v go &>/dev/null; then
  _gobin="${GOPATH:-$HOME/go}/bin"
  [ -d "$_gobin" ] && path=("$_gobin" $path)
  unset _gobin
fi

# pnpm
if is_macos; then
  export PNPM_HOME="$HOME/Library/pnpm"
else
  export PNPM_HOME="$HOME/.local/share/pnpm"
fi
if [ -d "$PNPM_HOME" ]; then
  case ":$PATH:" in
    *":$PNPM_HOME:"*) ;;
    *) path=("$PNPM_HOME" $path) ;;
  esac
fi
# pnpm end

# Added by LM Studio CLI (lms)
[ -d "$HOME/.lmstudio/bin" ] && path=($path "$HOME/.lmstudio/bin")
# End of LM Studio CLI section

# Neovim nightly
[ -d "$HOME/nvim-macos-x86_64/bin" ] && path=("$HOME/nvim-macos-x86_64/bin" $path)

# Function to get tmux session names
function _tmux_sessions_complete() {
  local -a sessions
  echo wtf
  # Get session names from tmux and clean up the output
  sessions=( "${(@f)$(tmux list-sessions -F '#{session_name}' 2>/dev/null)}" )
  _describe 'sessions' sessions
}

# Assign the completion function to 'tmux attach -t'
compdef _tmux_sessions_complete 'tmux attach -t'

zle     -N             sesh-sessions
bindkey -M emacs '\es' sesh-sessions
bindkey -M vicmd '\es' sesh-sessions
bindkey -M viins '\es' sesh-sessions

command -v atuin &>/dev/null && eval "$(atuin init zsh)"

# seshc alias - connect to sesh session with fzf
if type sesh &>/dev/null; then
  alias seshc='sesh connect $(sesh list | fzf)'
fi

# updates PATH for the Google Cloud SDK (Homebrew installation)
[ -f "$_brew_prefix/share/google-cloud-sdk/path.zsh.inc" ] && . "$_brew_prefix/share/google-cloud-sdk/path.zsh.inc"

# enables shell command completion for gcloud (Homebrew installation).
[ -f "$_brew_prefix/share/google-cloud-sdk/completion.zsh.inc" ] && . "$_brew_prefix/share/google-cloud-sdk/completion.zsh.inc"

# mise (version manager)
command -v mise &>/dev/null && eval "$(mise activate zsh)"

# omnara
export OMNARA_INSTALL="$HOME/.omnara"
[ -d "$OMNARA_INSTALL/bin" ] && path=("$OMNARA_INSTALL/bin" $path)

unset _brew_prefix

# GNU coreutils aliases (macOS compatibility)
if ! command -v timeout &> /dev/null && command -v gtimeout &> /dev/null; then
  alias timeout='gtimeout'
fi
