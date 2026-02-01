# Install

## Manual Install

```
xcode-select --install
mkdir -p ~/projects/joshm1
git clone https://github.com/joshm1/dotfiles.git ~/projects/joshm1/dotfiles
cd ~/projects/joshm1/dotfiles
./setup

# new tab
p10k configure
```

## Claude Code Install

**Prerequisites:** Dropbox must be installed and synced with `~/Dropbox/dotfiles` accessible (contains private dotfiles).

Copy/paste this prompt into Claude Code on a new machine:

```
Clone my dotfiles repo and set up this machine.

1. First, ask me two questions:
   a. What device ID to use for this machine (e.g. macbook-pro, mac.personal, mac.work). Device IDs use dot-separated namespaces for hierarchical config.
   b. Should I copy the existing ~/.zsh_history to ~/Dropbox/dotfiles/zsh_history/.zsh_history.{device_id}? (Only if ~/.zsh_history exists and has content worth preserving)

2. Verify Dropbox is set up:
   - Check that ~/Dropbox/dotfiles exists
   - If not, stop and tell me to set up Dropbox first

3. Install Xcode command line tools if needed:
   xcode-select --install

4. Clone the repo:
   mkdir -p ~/projects/joshm1
   git clone https://github.com/joshm1/dotfiles.git ~/projects/joshm1/dotfiles

5. Create the device ID file with the ID I provided:
   echo "{device_id}" > ~/.device_id

6. If I said yes to copying zsh_history:
   mkdir -p ~/Dropbox/dotfiles/zsh_history
   cp ~/.zsh_history ~/Dropbox/dotfiles/zsh_history/.zsh_history.{device_id}

7. Run the setup script:
   cd ~/projects/joshm1/dotfiles && ./setup

After setup completes, remind me to run `p10k configure` in a new terminal tab.
```

# Manual

- [ ] Install [Alfred](https://www.alfredapp.com) & add license
- [ ] Install BetterTouchTool license (optional - Raycast provides many similar features)
- [ ] Install CleanShot X license: https://licenses.cleanshot.com/
- [ ] Install SublimeText license: `pbcopy < ~/Dropbox/Apps/SublimeText3/license.txt`

# Machine-specific configuration

Each machine has a device-specific config file in Dropbox, symlinked to `~/.dotfiles-config`:

```
~/Dropbox/dotfiles/machine-config/{device_id}.zsh  # actual file
~/.dotfiles-config                                  # symlink
```

Available settings:

* `ENABLE_ZPROF=yes` - enable zsh startup profiling
* `ANTIGEN_BUNDLE_NODE=y` - enable Node.js completion bundles (npm/yarn tab completion)

# GPG Keys (Optional)

To auto-generate GPG keys during setup, create `~/Dropbox/dotfiles/.gpg-keys.yaml`:

```yaml
keys:
  - name: Your Name
    email: personal@example.com
  - name: Your Name
    email: work@example.com
```

The `setup-gpg` script will:
- Skip keys that already exist (matched by email)
- Generate 4096-bit RSA keys with no passphrase
- Keys never expire

Run manually with: `uv run setup-gpg`
