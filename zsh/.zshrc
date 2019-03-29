# Path to your oh-my-zsh installation.
export ZSH=/Users/josh/.oh-my-zsh

# Set name of the theme to load.
# Look in ~/.oh-my-zsh/themes/
# Optionally, if you set this to "random", it'll load a random theme each
# time that oh-my-zsh is loaded.
ZSH_THEME="robbyrussell"

# Uncomment the following line to use case-sensitive completion.
# CASE_SENSITIVE="true"

# Uncomment the following line to disable bi-weekly auto-update checks.
# DISABLE_AUTO_UPDATE="true"

# Uncomment the following line to change how often to auto-update (in days).
# export UPDATE_ZSH_DAYS=13

# Uncomment the following line to disable colors in ls.
# DISABLE_LS_COLORS="true"

# Uncomment the following line to disable auto-setting terminal title.
# DISABLE_AUTO_TITLE="true"

# Uncomment the following line to enable command auto-correction.
# ENABLE_CORRECTION="true"

# Uncomment the following line to display red dots whilst waiting for completion.
# COMPLETION_WAITING_DOTS="true"

# Uncomment the following line if you want to disable marking untracked files
# under VCS as dirty. This makes repository status check for large repositories
# much, much faster.
# DISABLE_UNTRACKED_FILES_DIRTY="true"

# Uncomment the following line if you want to change the command execution time
# stamp shown in the history command output.
# The optional three formats: "mm/dd/yyyy"|"dd.mm.yyyy"|"yyyy-mm-dd"
# HIST_STAMPS="mm/dd/yyyy"

# Would you like to use another custom folder than $ZSH/custom?
# ZSH_CUSTOM=/path/to/new-custom-folder

# Which plugins would you like to load? (plugins can be found in ~/.oh-my-zsh/plugins/*)
# Custom plugins may be added to ~/.oh-my-zsh/custom/plugins/
# Example format: plugins=(rails git textmate ruby lighthouse)
# Add wisely, as too many plugins slow down shell startup.
plugins=(brew bundler capistrano git git-extras gitignore history-substring-search history knife knife_ssh mosh node npm osx postgres pow redis-cli rsync sbt scala sublime sudo supervisor tmux vundle wd rbenv)

# User configuration

export PATH="~/bin:/usr/local/bin:/usr/local/sbin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/X11/bin"
# export MANPATH="/usr/local/man:$MANPATH"

source $ZSH/oh-my-zsh.sh

export LANG=en_US.UTF-8

# Preferred editor for local and remote sessions
if [[ -n $SSH_CONNECTION ]]; then
  export VISUAL='nvim'
else
  export VISUAL='nvim'
fi
export EDITOR="$VISUAL"
export GIT_EDITOR="$EDITOR"

# Compilation flags
# export ARCHFLAGS="-arch x86_64"

# ssh
# export SSH_KEY_PATH="~/.ssh/dsa_id"

# Set personal aliases, overriding those provided by oh-my-zsh libs,
# plugins, and themes. Aliases can be placed here, though oh-my-zsh
# users are encouraged to define aliases within the ZSH_CUSTOM folder.
# For a full list of active aliases, run `alias`.
#
# Example aliases
# alias zshconfig="mate ~/.zshrc"
# alias ohmyzsh="mate ~/.oh-my-zsh"

alias be="bundle exec"
alias rc="bundle exec rails console"

# nvm - node version manager
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" # This loads nvm
export NODE_REPL_HISTORY_FILE=~/.node_history

# auto-run nvm use when entering a directory with nvmrc
# source: https://github.com/creationix/nvm#deeper-shell-integration
autoload -U add-zsh-hook
load-nvmrc() {
  local node_version="$(nvm version)"
  local nvmrc_path="$(nvm_find_nvmrc)"

  if [ -n "$nvmrc_path" ]; then
    local nvmrc_node_version=$(nvm version "$(cat "${nvmrc_path}")")

    if [ "$nvmrc_node_version" = "N/A" ]; then
      nvm install
    elif [ "$nvmrc_node_version" != "$node_version" ]; then
      nvm use
    fi
  elif [ "$node_version" != "$(nvm version default)" ]; then
    echo "Reverting to nvm default version"
    nvm use default
  fi
}
add-zsh-hook chpwd load-nvmrc
load-nvmrc

# do not beep on error
setopt no_beep

alias vim="nvim"
alias vi="nvim"

# direnv - http://direnv.net
eval "$(direnv hook zsh)"

# delete all stopped containers
alias dockercleanc='printf "\n>>> Deleting stopped containers\n\n" && docker rm $(docker ps -a -q)'

# delete all untagged images
alias dockercleani='printf "\n>>> Deleting untagged images\n\n" && docker rmi $(docker images -q -f dangling=true)'

# Delete all stopped containers and untagged images.
alias dockerclean='dockercleanc || true && dockercleani'

export FZF_DEFAULT_COMMAND='ag -g ""'

# kubernetes aliases
alias pods="kubectl get pods --show-labels -o wide"
alias nodes="kubectl get nodes -a"
alias k="kubectl"

# gpr: git pull request / pushes current branch to origin, creates pull request, and opens github
gpr() {
  local current_branch=$(git branch | grep -E '^\*' | tr -d '* ')
  echo "git-push -u origin $current_branch"
  git push -u origin $current_branch
  local commit_message="$(git log -1 --pretty=%B | sed -e 's/comment: //')"
  echo "Message: $commit_message"
  local github_url=$(echo $commit_message | hub pull-request -F -)
  open $github_url
}

path=("$HOME/bin" $path)

[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh

alias gitpurge="git checkout master && git remote update --prune | git branch -r --merged | grep -v master | grep origin/ | sed -e 's/origin\//:/' | xargs git push origin"

# pyenv: https://github.com/yyuu/pyenv
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"

# kubectl auto complete
if [ $commands[kubectl] ]; then
  source <(kubectl completion zsh)
fi

if [ $commands[stern] ]; then
  source <(stern --completion zsh)
fi

# load more configuration I don't care to add to a public repository
test -f "${HOME}/Dropbox/dotfiles/.zshrc.after" && source "${HOME}/Dropbox/dotfiles/.zshrc.after"

test -e "${HOME}/.iterm2_shell_integration.zsh" && source "${HOME}/.iterm2_shell_integration.zsh"

export PATH="$HOME/.yarn/bin:$HOME/.config/yarn/global/node_modules/.bin:$PATH"
