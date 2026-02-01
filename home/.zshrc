test -f "$HOME/Dropbox/dotfiles/.zshrc.before" && source "$HOME/Dropbox/dotfiles/.zshrc.before"

# var $1 is truthy if it starts with "y", equals "true", or equals "1"
bool() {
  [[ $1 = y* || $1 = true || $1 = 1 ]]
}

# Platform detection
is_macos() { [[ "$OSTYPE" == darwin* ]] }
is_linux() { [[ "$OSTYPE" == linux* ]] }

# add ENABLE_ZPROF=yes to ~/.dotfiles-config to run
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

# if you want these, add ANTIGEN_BUNDLE_NODE=y to ~/.dotfiles-config
if [[ "$ANTIGEN_BUNDLE_NODE" = y* ]]; then
  antigen bundle lukechilds/zsh-better-npm-completion
  antigen bundle g-plane/zsh-yarn-autocompletions
fi

antigen theme romkatv/powerlevel10k

antigen apply

# History file in Dropbox for sync across machines (must be after antigen/oh-my-zsh)
# Uses device-specific file if ~/.device_id exists (created by setup-zsh-history)
if [[ -f "$HOME/.device_id" ]]; then
  _device_id=$(<"$HOME/.device_id")
  _histfile="$HOME/Dropbox/dotfiles/zsh_history/.zsh_history.${_device_id}"
  if [[ -f "$_histfile" ]]; then
    export HISTFILE="$_histfile"
  else
    echo "Warning: Device history file not found: $_histfile"
  fi
  unset _device_id _histfile
elif [[ -f "$HOME/Dropbox/dotfiles/zsh_history/.zsh_history" ]]; then
  export HISTFILE="$HOME/Dropbox/dotfiles/zsh_history/.zsh_history"
else
  echo "Warning: Dropbox zsh_history not found, using default ~/.zsh_history"
fi

# we want to use buf from https://docs.buf.build
alias buf >/dev/null && unalias buf

# Initialize zoxide and ensure z command is not overridden by fz plugin
eval "$(zoxide init zsh)"
alias z >/dev/null 2>&1 && unalias z

alias be="bundle exec"
alias rc="bundle exec rails console"

export NODE_REPL_HISTORY_FILE=~/.node_history

# do not beep on error
setopt no_beep

alias vim="nvim"
alias vi="nvim"
# Note: nvim is in PATH via ~/nvim-macos-x86_64/bin (set below)

path=("$HOME/bin" $path)

alias gitpurge="git checkout master && git remote update --prune | git branch -r --merged | grep -v master | grep origin/ | sed -e 's/origin\//:/' | xargs git push origin"

export FZF_DEFAULT_OPTS='--preview "([[ -f {} ]] && bat --style=numbers --color=always --line-range :500 {}) || ([[ -d {} ]] && eza -T --git-ignore --icons --group-directories-first -la {})"'
export FZF_DEFAULT_COMMAND='fd --type f --strip-cwd-prefix --hidden --follow'
export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"
export FZF_CTRL_R_OPTS="--preview ''"

[ -d $HOME/bin ] && path=("$HOME/bin" $path)

# load more configuration I don't care to add to a public repository
test -f "${HOME}/Dropbox/dotfiles/.zshrc.after" && source "${HOME}/Dropbox/dotfiles/.zshrc.after"

enable_zprof && zprof
unset -f enable_zprof


# https://buildpacks.io/docs/tools/pack/
if type pack >/dev/null 2>&1; then
. $(pack completion --shell zsh)
fi

# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh

test -d $HOME/.yarn && path=("$HOME/.yarn/bin" "$HOME/.config/yarn/global/node_modules/.bin" $path)

git-stats() {
  local refs=${1:-HEAD^..HEAD}
  git log $refs --shortstat | grep -E "fil(e|es) changed" | awk '{files+=$1; inserted+=$4; deleted+=$6; delta+=$4-$6; ratio=deleted/inserted} END {printf "Commit stats:\n- Files changed (total)..  %s\n- Lines added (total)....  %s\n- Lines deleted (total)..  %s\n- Total lines (delta)....  %s\n- Add./Del. ratio (1:n)..  1 : %s\n", files, inserted, deleted, delta, ratio }' -
}

git-diff-stats() {
  git diff --stat | grep -E "fil(e|es) changed" | awk '{files+=$1; inserted+=$4; deleted+=$6; delta+=$4-$6; ratio=deleted/inserted} END {printf "Commit stats:\n- Files changed (total)..  %s\n- Lines added (total)....  %s\n- Lines deleted (total)..  %s\n- Total lines (delta)....  %s\n- Add./Del. ratio (1:n)..  1 : %s\n", files, inserted, deleted, delta, ratio }' -
}

gch() {
  local preview_cmd="git log --pretty=tformat:'%C(bold blue)%h %C(bold red)%ad %C(bold blue)%aN%C(auto) %<|(100,trunc)%s%C(reset)' --date=short --graph {}"
  local branch=$(git branch --format='%(refname:short)' --sort=-committerdate | fzf --preview "$preview_cmd" | tr -d '[:space:]')
  git checkout $branch
}

[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh

if [[ -f ~/.docker/init-zsh.sh ]]; then
  source ~/.docker/init-zsh.sh || true # Added by Docker Desktop
fi

if type aws_completer >/dev/null; then
  autoload bashcompinit && bashcompinit
  autoload -Uz compinit && compinit
  complete -C "$(brew --prefix)/bin/aws_completer" aws
fi

[ -f $HOME/.cargo/env ] && . "$HOME/.cargo/env"

# https://github.com/eza-community/eza/blob/main/INSTALL.md#for-zsh-with-homebrew
if type brew &>/dev/null; then
  FPATH="$(brew --prefix)/share/zsh/site-functions:${FPATH}"
  autoload -Uz compinit
  compinit
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
load-local-venv() {
  if [[ -f .venv/bin/activate && "$VIRTUAL_ENV" != "$(pwd)/.venv" ]]; then
    source .venv/bin/activate
  fi
}
add-zsh-hook chpwd load-local-venv
load-local-venv  # Load for current session

# bun completions
[ -s "$HOME/.bun/_bun" ] && source "$HOME/.bun/_bun"

# bun
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"
eval "$(just --completions zsh)"
# The following lines have been added by Docker Desktop to enable Docker CLI completions.
fpath=($HOME/.docker/completions $fpath)
autoload -Uz compinit
compinit
# End of Docker CLI completions

[ -f $HOME/.claude/local/claude ] && path=("$HOME/.claude/local" $path)

# go - add GOPATH/bin to PATH if go is installed
if command -v go &>/dev/null; then
  path=("$(go env GOPATH)/bin" $path)
fi

# pnpm
if is_macos; then
  export PNPM_HOME="$HOME/Library/pnpm"
else
  export PNPM_HOME="$HOME/.local/share/pnpm"
fi
case ":$PATH:" in
  *":$PNPM_HOME:"*) ;;
  *) export PATH="$PNPM_HOME:$PATH" ;;
esac
# pnpm end

# Added by LM Studio CLI (lms)
export PATH="$PATH:$HOME/.lmstudio/bin"
# End of LM Studio CLI section

# Neovim nightly
[ -d "$HOME/nvim-macos-x86_64/bin" ] && export PATH="$HOME/nvim-macos-x86_64/bin:$PATH"

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

function sesh-sessions() {
  local session
  session=$(sesh list --icons | fzf \
    --no-sort --ansi --border-label ' sesh ' --prompt '⚡  ' \
    --header '  ^a all ^t tmux ^g configs ^x zoxide ^d tmux kill ^f find' \
    --bind 'tab:down,btab:up' \
    --bind 'ctrl-a:change-prompt(⚡  )+reload(sesh list --icons)' \
    --bind 'ctrl-t:change-prompt(🪟  )+reload(sesh list -t --icons)' \
    --bind 'ctrl-g:change-prompt(⚙️  )+reload(sesh list -c --icons)' \
    --bind 'ctrl-x:change-prompt(📁  )+reload(sesh list -z --icons)' \
    --bind 'ctrl-f:change-prompt(🔎  )+reload(fd -H -d 2 -t d -E .Trash . ~)' \
    --bind 'ctrl-d:execute(tmux kill-session -t {2..})+change-prompt(⚡  )+reload(sesh list --icons)' \
    --preview-window 'right:55%' \
    --preview 'sesh preview {}')
  
  [[ -z "$session" ]] && return
  sesh connect "$session"
}

zle     -N             sesh-sessions
bindkey -M emacs '\es' sesh-sessions
bindkey -M vicmd '\es' sesh-sessions
bindkey -M viins '\es' sesh-sessions

eval "$(atuin init zsh)"

# seshc alias - connect to sesh session with fzf
if type sesh &>/dev/null; then
  alias seshc='sesh connect $(sesh list | fzf)'
fi

# updates PATH for the Google Cloud SDK (Homebrew installation)
[ -f "$(brew --prefix)/share/google-cloud-sdk/path.zsh.inc" ] && . "$(brew --prefix)/share/google-cloud-sdk/path.zsh.inc"

# enables shell command completion for gcloud (Homebrew installation).
[ -f "$(brew --prefix)/share/google-cloud-sdk/completion.zsh.inc" ] && . "$(brew --prefix)/share/google-cloud-sdk/completion.zsh.inc"

# Added by Antigravity
[ -d "$HOME/.antigravity/antigravity/bin" ] && export PATH="$HOME/.antigravity/antigravity/bin:$PATH"

# mise (version manager)
eval "$(mise activate zsh)"

# omnara
export OMNARA_INSTALL="$HOME/.omnara"
export PATH="$OMNARA_INSTALL/bin:$PATH"

# GNU coreutils aliases (macOS compatibility)
if ! command -v timeout &> /dev/null && command -v gtimeout &> /dev/null; then
  alias timeout='gtimeout'
fi
