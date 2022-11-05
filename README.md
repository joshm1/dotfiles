# Install

```
xcode-select --install
mkdir -p ~/projects/joshm1
git clone https://github.com/joshm1/dotfiles.git ~/projects/joshm1/dotfiles
cd ~/projects/joshm1/dotfiles
./setup
```

# Manual

- [ ] Install [Alfred](https://www.alfredapp.com) & add license
- [ ] Install BetterTouchTool license
- [ ] Install SublimeText license: `pbcopy < ~/Dropbox/Apps/SublimeText3/license.txt`

# Mac-specific configuration

If you want different machines to behave differently and still use the same dotfiles repository, you can
configure environment variables in the `~/.dotfiles-config` file.

* `RUBY_VERSION_MANAGER` can be "rbenv" or "rvm" - this is to prevent both rvm or rbenv from being setup
  (default is rbenv if this value is blank)
* `ENABLE_K8S` - set to "true" to enable kubernetes plugins

# References

* [AstroNvim](https://astronvim.github.io)
