DOTFILES="$HOME/.dotfiles"
DROPBOX_DIR=$HOME/Dropbox
BCKDIR="$HOME/.dotfiles.$(date +%Y%m%d-%H%M%S).bck"

DEFAULT_NODE_VERSION=17.8.0
DEFAULT_RUBY_VERSION=2.7.4
DEFAULT_JAVA_VERSION=adoptopenjdk-17.0.5+8
DEFAULT_PYTHON_VERSION=3.11.1

# set to "true" to install Python 2
INSTALL_PYTHON2=false
LOCAL_DEVICE_ID_FILE=$HOME/.device_id
[ -f $LOCAL_DEVICE_ID_FILE ] && LOCAL_DEVICE_ID=$(cat $LOCAL_DEVICE_ID_FILE)

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

# echo "Loaded utils.sh"
