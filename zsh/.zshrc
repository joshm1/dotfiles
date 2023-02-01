test -f "$HOME/Dropbox/dotfiles/.zshrc.before" && source "$HOME/Dropbox/dotfiles/.zshrc.before"

# var $1 is truthy if it starts with "y", equals "true", or equals "1"
bool() {
  [[ $1 = y* || $1 = true || $1 = 1 ]]
}

# add ENABLE_ZPROF=yes to ~/.dotfiles-config to run
enable_zprof() { bool $ENABLE_ZPROF ]] }
enable_zprof && zmodload zsh/zprof

(( ${+commands[direnv]} )) && emulate zsh -c "$(direnv export zsh)"

# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

(( ${+commands[direnv]} )) && emulate zsh -c "$(direnv hook zsh)"

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

# b/c of powerlevel10k and instant-prompt, we load direnv differently
# antigen bundle direnv

antigen bundle fzf
antigen bundle git
antigen bundle wd
antigen bundle zsh-users/zsh-syntax-highlighting

# java version manager
# antigen bundle shihyuho/zsh-jenv-lazy

# python version manager
case $PYTHON_VERSION_MANAGER in
  pyenv)
    antigen bundle davidparsson/zsh-pyenv-lazy
    antigen bundle pip
    ;;
  *)
    # do nothing, assume asdf
    ;;
esac

# ruby version manager
case $RUBY_VERSION_MANAGER in
  asdf)
    # do nothing - the asdf plugin didn't work last time I checked
    ;;
  rvm)
    # antigen bundle unixorn/rvm-plugin
    antigen bundle FrederickGeek8/zsh-rvm-lazy
    ;;
  *)
    antigen bundle rbenv
    ;;
esac

# nodejs
case $NODE_VERSION_MANAGER in
  nvm)
    export NVM_LAZY_LOAD=true
    antigen bundle lukechilds/zsh-nvm
    ;;
  *)
    # do nothing, assume asdf
    ;;
esac

# if you want these, add ANTIGEN_BUNDLE_NODE=y to ~/.dotfiles-config
if [[ "$ANTIGEN_BUNDLE_NODE" = y* ]]; then
  antigen bundle lukechilds/zsh-better-npm-completion
  antigen bundle g-plane/zsh-yarn-autocompletions
fi

# kubernetes
enable_k8s() { bool "$ENABLE_K8S" }
enable_k8s && antigen bundle mattbangert/kubectl-zsh-plugin

antigen theme romkatv/powerlevel10k

antigen apply

# we want to use buf from https://docs.buf.build
alias buf >/dev/null && unalias buf

# direnv
# eval "$(direnv hook $0)"

alias be="bundle exec"
alias rc="bundle exec rails console"

export NODE_REPL_HISTORY_FILE=~/.node_history

# do not beep on error
setopt no_beep

alias vim="nvim"
alias vi="nvim"

path=("$HOME/bin" $path)

alias gitpurge="git checkout master && git remote update --prune | git branch -r --merged | grep -v master | grep origin/ | sed -e 's/origin\//:/' | xargs git push origin"

# export FZF_DEFAULT_OPTS='--height=70% --preview="cat {}" --preview-window=right:60%:wrap'
export FZF_DEFAULT_OPTS='--preview "bat --style=numbers --color=always --line-range :500 {}"'
# export FZF_DEFAULT_COMMAND='rg --files'
export FZF_DEFAULT_COMMAND='fd --type f --strip-cwd-prefix --hidden --follow'
export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"
export FZF_CTRL_R_OPTS="--preview ''"

[ -d $HOME/bin ] && path=("$HOME/bin" $path)

# add psql to path
[ -d /Applications/Postgres.app ] && path=("/Applications/Postgres.app/Contents/Versions/latest/bin" $path)

# sterm is used for k8s logging, not necessary if we aren't using k8s
if enable_k8s && [ $commands[stern] ]; then
  source <(stern --completion zsh)
fi

test -e "${HOME}/.iterm2_shell_integration.zsh" && source "${HOME}/.iterm2_shell_integration.zsh"

# test -d $HOME/.yarn && path=("$HOME/.yarn/bin" "$HOME/.config/yarn/global/node_modules/.bin" $path)

# function git_prompt_info() {
#   ref=$(git symbolic-ref HEAD 2> /dev/null) || return
#   echo "$ZSH_THEME_GIT_PROMPT_PREFIX${ref#refs/heads/}$ZSH_THEME_GIT_PROMPT_SUFFIX"
# }

# load more configuration I don't care to add to a public repository
test -f "${HOME}/Dropbox/dotfiles/.zshrc.after" && source "${HOME}/Dropbox/dotfiles/.zshrc.after"

enable_zprof && zprof
unset -f enable_zprof

# asdf
(){
  local asdf_sh=$(brew --prefix asdf)/libexec/asdf.sh
  if [ -f $asdf_sh ]; then
    source $asdf_sh
  else
    asdf() {
      echo -n "asdf is not installed. Install via homebrew? (y/n) > "
      read answer
      if [[ "$answer" = y* ]]; then
        brew install asdf
      fi
    }
  fi
}

set_java_home() {
  local set_java_home_sh=$HOME/.asdf/plugins/java/set-java-home.zsh
  if [ -f $set_java_home_sh ]; then
    . $set_java_home_sh
  else
    echo "asdf java plugin is not installed"
  fi
}

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
  git checkout "$(git branch --sort=-committerdate | fzf | tr -d '[:space:]')"
}

# https://github.com/wting/autojump
(){
  if [ -f /usr/local/etc/profile.d/autojump.sh ]; then
    . /usr/local/etc/profile.d/autojump.sh
  else
    local aj_file=$(brew --prefix autojump)/etc/autojump.sh
    [ -f $aj_file ] && . $aj_file
  fi
}

[ -f "$HOME/.cargo/bin" ] && path=("$HOME/.cargo/bin" $path)

# The next line updates PATH for the Google Cloud SDK.
if [ -f "$HOME/google-cloud-sdk/path.zsh.inc" ]; then . "$HOME/google-cloud-sdk/path.zsh.inc"; fi

# The next line enables shell command completion for gcloud.
if [ -f "$HOME/google-cloud-sdk/completion.zsh.inc" ]; then . "$HOME/google-cloud-sdk/completion.zsh.inc"; fi
