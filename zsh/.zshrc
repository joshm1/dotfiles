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

source $HOME/.antigen.zsh

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

alias be="bundle exec"
alias rc="bundle exec rails console"

export NODE_REPL_HISTORY_FILE=~/.node_history

# do not beep on error
setopt no_beep

alias vim="nvim"
alias vi="nvim"

# kubernetes aliases
alias pods="kubectl get pods --show-labels -o wide"
alias nodes="kubectl get nodes -a"

path=("$HOME/.linkerd2/bin" "$HOME/bin" $path)

# add psql to path
[ -d /Applications/Postgres.app ] && path=("/Applications/Postgres.app/Contents/Versions/latest/bin" $path)

if [ $commands[stern] ]; then
  source <(stern --completion zsh)
fi

# load more configuration I don't care to add to a public repository
test -f "${HOME}/Dropbox/dotfiles/.zshrc.after" && source "${HOME}/Dropbox/dotfiles/.zshrc.after"

test -e "${HOME}/.iterm2_shell_integration.zsh" && source "${HOME}/.iterm2_shell_integration.zsh"

export PATH="$HOME/.yarn/bin:$HOME/.config/yarn/global/node_modules/.bin:$PATH"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion
