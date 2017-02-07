#!/bin/bash

# macOS config
defaults write com.apple.finder AppleShowAllFiles YES.

# link dotfiles
DOTFILES="$HOME/.dotfiles"
ln -s $HOME/projects/joshm1/dotfiles $HOME/.dotfiles

ln -s $DOTFILES/git/gitconfig $HOME/.gitconfig
ln -s $DOTFILES/git/gitignore $HOME/.gitignore

ln -s $DOTFILES/ruby/gemrc $HOME/.gemrc

mkdir -p $HOME/.config
ln -s $DOTFILES/nvim $HOME/.config/nvim
ln -s $DOTFILES/nvim $HOME/.nvim
ln -s $DOTFILES/nvim/init.vim $HOME/.nvimrc
ln -s $DOTFILES/vimrc $HOME/.vimrc
ln -s $DOTFILES/vim $HOME/.vim

ln -s $DOTFILES/warprc $HOME/.warprc

ln -s $DOTFILES/zsh/.zshrc $HOME/.zshrc
ln -s $DOTFILES/zsh/oh-my-zsh $HOME/.oh-my-zsh
ln -s $DOTFILES/zsh/zshrc $HOME/.zshrc

ln -s $DOTFILES/iterm2/.iterm2_shell_integration.zsh $HOME/

# homebrew
ln -s $DOTFILES/homebrew/Brewfile ~/Brewfile
if [[ ! -f $DOTFILES/homebrew/.installed ]]; then
  brew tap homebrew/bundle
  brew bundle
  echo $(date) >> $DOTFILES/homebrew/.installed
fi

# fzf: install useful keybindings and fuzzy completion
/usr/local/opt/fzf/install

# private config files should be in Dropbox
if [[ -d $HOME/Dropbox ]]; then
  ln -s $HOME/Dropbox/dotfiles/.npmrc $HOME/.npmrc
  ln -s $HOME/Dropbox/dotfiles/.warprc $HOME/.warprc
else
  echo "!!! Install Dropbox to link more dotfiles !!!"
fi
