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
export NVM_LAZY_LOAD=true

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
antigen bundle davidparsson/zsh-pyenv-lazy
# antigen bundle pip

# ruby version manager
# antigen bundle bundler
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

# [ -f ~/.fzf.zsh ] && source ~/.fzf.zsh

alias gitpurge="git checkout master && git remote update --prune | git branch -r --merged | grep -v master | grep origin/ | sed -e 's/origin\//:/' | xargs git push origin"

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
  local asdf_sh=/usr/local/opt/asdf/libexec/asdf.sh
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

# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh

test -d $HOME/.yarn && path=("$HOME/.yarn/bin" "$HOME/.config/yarn/global/node_modules/.bin" $path)
