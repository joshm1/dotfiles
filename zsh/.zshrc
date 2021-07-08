export LANG=en_US.UTF-8
# export NVM_LAZY_LOAD=true

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
antigen bundle bundler
antigen bundle command-not-found
antigen bundle davidparsson/zsh-pyenv-lazy
antigen bundle direnv
antigen bundle fzf
antigen bundle git
antigen bundle rbenv
antigen bundle pip
antigen bundle wd
antigen bundle zsh-users/zsh-syntax-highlighting

# nodejs

antigen bundle lukechilds/zsh-better-npm-completion
antigen bundle lukechilds/zsh-nvm
antigen bundle g-plane/zsh-yarn-autocompletions

# kubernetes
antigen bundle mattbangert/kubectl-zsh-plugin

antigen theme robbyrussell

antigen apply

# direnv
eval "$(direnv hook $0)"

alias be="bundle exec"
alias rc="bundle exec rails console"

export NODE_REPL_HISTORY_FILE=~/.node_history

# do not beep on error
setopt no_beep

alias vim="nvim"
alias vi="nvim"

path=("$HOME/bin" $path)

[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh

alias gitpurge="git checkout master && git remote update --prune | git branch -r --merged | grep -v master | grep origin/ | sed -e 's/origin\//:/' | xargs git push origin"

# pyenv: https://github.com/yyuu/pyenv
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"

# add psql to path
[ -d /Applications/Postgres.app ] && path=("/Applications/Postgres.app/Contents/Versions/latest/bin" $path)

if [ $commands[stern] ]; then
  source <(stern --completion zsh)
fi

# load more configuration I don't care to add to a public repository
test -f "${HOME}/Dropbox/dotfiles/.zshrc.after" && source "${HOME}/Dropbox/dotfiles/.zshrc.after"

test -e "${HOME}/.iterm2_shell_integration.zsh" && source "${HOME}/.iterm2_shell_integration.zsh"

# The next line updates PATH for the Google Cloud SDK.
test -f "$HOME/Downloads/google-cloud-sdk/path.zsh.inc"  && source '/Users/josh/Downloads/google-cloud-sdk/path.zsh.inc'

# The next line enables shell command completion for gcloud.
test -f "$HOME/Downloads/google-cloud-sdk/completion.zsh.inc" && source '/Users/josh/Downloads/google-cloud-sdk/completion.zsh.inc'

test -d "$HOME/flyway" && path=("$HOME/flyway" $path)

test -d "/Library/TeX/texbin" && path=("/Library/TeX/texbin" $path)

test -d $HOME/.yarn && path=("$HOME/.yarn/bin" "$HOME/.config/yarn/global/node_modules/.bin" $path")
