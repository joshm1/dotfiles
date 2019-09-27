DOTFILES="$HOME/.dotfiles"
BCKDIR="$HOME/.dotfiles.$(date +%Y%m%d-%H%M%S).bck"

symlink() {
  local bck=${BCKDIR}/$(basename $2)
  if [[ -e $2 ]]; then
    mkdir -p $BCKDIR
    if [[ -L $2 && $(readlink $2) == $1 ]]; then
      echo "$1 is already linked to $2, skipping"
      return
    else
      echo "$2 exists, moving to $bck"
      mv $2 $bck
    fi
  fi

  ln -s ${@}
}
