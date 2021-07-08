DOTFILES="$HOME/.dotfiles"
DROPBOX_DIR=$HOME/Dropbox
BCKDIR="$HOME/.dotfiles.$(date +%Y%m%d-%H%M%S).bck"
DEFAULT_RUBY_VERSION=2.5.7
DEFAULT_PYTHON_VERSION=3.7.4
# set to "true" to install Python 2
INSTALL_PYTHON2=false
NVM_VERSION=v0.35.0
DEFAULT_NODE_VERSION=lts/dubnium

trap ctrl_c INT

function ctrl_c() {
  echo "Goodbye."
  exit 0
}

symlink() {
  local bck=${BCKDIR}/$(basename $2)
  if [[ -e $2 || -L $2 ]]; then
    mkdir -p $BCKDIR
    if [[ -L $2 && $(readlink $2) == $1 ]]; then
      echo "$1 is already linked to $2, skipping"
      return
    else
      echo "$2 exists, moving to $bck"
      mv "$2" "$bck"
    fi
  fi

  ln -s "$1" "$2"
}

echo "Loaded utils.sh"
