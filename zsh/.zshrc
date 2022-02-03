(( ${+commands[direnv]} )) && emulate zsh -c "$(direnv export zsh)"

# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

(( ${+commands[direnv]} )) && emulate zsh -c "$(direnv hook zsh)"

# zmodload zsh/zprof
test -f "$HOME/Dropbox/dotfiles/.zshrc.before" && source "$HOME/Dropbox/dotfiles/.zshrc.before"

export LANG=en_US.UTF-8
export NVM_LAZY_LOAD=true

# Preferred editor for local and remote sessions
if [[ -n $SSH_CONNECTION ]]; then
  export VISUAL='nvim'
else
  export VISUAL='nvim'
fi

export EDITOR="$VISUAL"
export GIT_EDITOR="$EDITOR"
export FZF_DEFAULT_COMMAND='ag -g ""'

if [ -f $HOME/.antigen.zsh ]; then
  source $HOME/.antigen.zsh
else
  echo "$HOME/.antigen.zsh does not exist..."
fi


antigen use oh-my-zsh


antigen bundle brew
antigen bundle command-not-found
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
  rvm)
    # antigen bundle unixorn/rvm-plugin
    antigen bundle FrederickGeek8/zsh-rvm-lazy
    ;;
  *)
    antigen bundle rbenv
    ;;
esac

# nodejs

# antigen bundle lukechilds/zsh-better-npm-completion
# antigen bundle lukechilds/zsh-nvm
# antigen bundle g-plane/zsh-yarn-autocompletions

# kubernetes
[[ "$ENABLE_K8S" == true ]] && antigen bundle mattbangert/kubectl-zsh-plugin

# antigen theme robbyrussell
antigen theme romkatv/powerlevel10k

antigen apply

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

if [ $commands[stern] ]; then
  source <(stern --completion zsh)
fi

test -e "${HOME}/.iterm2_shell_integration.zsh" && source "${HOME}/.iterm2_shell_integration.zsh"

# test -d "/Library/TeX/texbin" && path=("/Library/TeX/texbin" $path)
# test -d $HOME/.yarn && path=("$HOME/.yarn/bin" "$HOME/.config/yarn/global/node_modules/.bin" $path)

# function git_prompt_info() {
#   ref=$(git symbolic-ref HEAD 2> /dev/null) || return
#   echo "$ZSH_THEME_GIT_PROMPT_PREFIX${ref#refs/heads/}$ZSH_THEME_GIT_PROMPT_SUFFIX"
# }

# load more configuration I don't care to add to a public repository
test -f "${HOME}/Dropbox/dotfiles/.zshrc.after" && source "${HOME}/Dropbox/dotfiles/.zshrc.after"

# zprof

# asdf
asdf_sh=/usr/local/opt/asdf/libexec/asdf.sh
test -f $asdf_sh && source $asdf_sh

# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh
