# Install

## Fresh Machine (recommended)

On a brand new Mac, open Terminal and run:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/joshm1/dotfiles/main/bootstrap.sh)
```

This handles the full bootstrap:
1. Installs Xcode CLI tools and Homebrew
2. Clones the repo to `~/projects/joshm1/dotfiles`
3. Installs Chrome, 1Password, Dropbox, and Claude Code
4. Prompts you to sign into all apps and authenticate Claude Code
5. Waits for Dropbox to sync `~/Dropbox/dotfiles`
6. Hands off to Claude Code to finish setup (device ID, `./setup`, etc.)

## Existing Machine

If Homebrew and Dropbox are already set up:

```bash
cd ~/projects/joshm1/dotfiles
./setup
```

# Post-Install

- [ ] Install CleanShot X license: https://licenses.cleanshot.com/
- [ ] Setup Default Obsidian vault at `~/Obsidian`

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
