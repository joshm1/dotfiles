# Install

```
xcode-select --install
mkdir -p ~/projects/joshm1
git clone https://github.com/joshm1/dotfiles.git ~/projects/joshm1/dotfiles
cd ~/projects/joshm1/dotfiles
./setup

# new tab
p10k configure 
```

# Manual

- [ ] Install [Alfred](https://www.alfredapp.com) & add license
- [ ] Install BetterTouchTool license (optional - Raycast provides many similar features)
- [ ] Install CleanShot X license: https://licenses.cleanshot.com/
- [ ] Install SublimeText license: `pbcopy < ~/Dropbox/Apps/SublimeText3/license.txt`
- [ ] Download and activate Wispr Flow: https://wisprflow.ai (use your work email)
- [ ] [Install Powerlevel10k fonts](https://github.com/romkatv/powerlevel10k#automatic-font-installation)

# Mac-specific configuration

If you want different machines to behave differently and still use the same dotfiles repository, you can
configure environment variables in the `~/.dotfiles-config` file.

* `ENABLE_K8S` - set to "true" to enable kubernetes plugins
