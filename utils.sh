DOTFILES="$HOME/.dotfiles"
DROPBOX_DIR=$HOME/Dropbox
BCKDIR="$HOME/.dotfiles.$(date +%Y%m%d-%H%M%S).bck"

DEFAULT_NODE_VERSION=24.4.0
DEFAULT_RUBY_VERSION=2.7.4
DEFAULT_JAVA_VERSION=adoptopenjdk-17.0.5+8
DEFAULT_PYTHON_VERSION=3.12.7

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

# Auto-discover and symlink all files from home/ directory to $HOME
symlink_home_files() {
  local home_dir="${DOTFILES}/home"

  if [[ ! -d "$home_dir" ]]; then
    echo "Warning: home/ directory not found at $home_dir"
    return 1
  fi

  echo "Auto-discovering and symlinking files from home/..."

  # Symlink all top-level files in home/
  find "$home_dir" -mindepth 1 -maxdepth 1 -type f | while read -r source_path; do
    local filename=$(basename "$source_path")
    local target_path="${HOME}/${filename}"
    symlink "$source_path" "$target_path"
  done

  # Symlink entire .config subdirectories (nvim, tmux, etc.)
  if [[ -d "$home_dir/.config" ]]; then
    find "$home_dir/.config" -mindepth 1 -maxdepth 1 | while read -r source_path; do
      local dirname=$(basename "$source_path")
      local target_path="${HOME}/.config/${dirname}"
      symlink "$source_path" "$target_path"
    done
  fi

  echo "Home files symlinked!"
}

# echo "Loaded utils.sh"
