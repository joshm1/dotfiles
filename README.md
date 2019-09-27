# Install

```
xcode-select --install
mkdir -p ~/projects/joshm1
git clone https://github.com/joshm1/dotfiles.git ~/projects/joshm1
cd ~/projects/joshm1/dotfiles
./setup
```

# Manual

- [ ] Install [Alfred](https://www.alfredapp.com) & add license
- [ ] Install BetterTouchTool license
- [ ] Install SublimeText license: `pbcopy < ~/Dropbox/Apps/SublimeText3/license.txt`
- [ ] Increase Docker image file (see below)
- [ ] [Install pgAdmin](https://www.pgadmin.org/download/macos4.php)

### Increase Docker VM Image

WARNING this deletes all docker images/containers/volumes; see
https://community.hortonworks.com/articles/65901/how-to-increase-the-size-of-the-base-docker-for-ma.html
for how to do a backup/restore.

```
qemu-img create -f qcow2 ~/data.qcow2 120G
mv ~/data.qcow2 ~/Library/Containers/com.docker.docker/Data/com.docker.driver.amd64-linux/Docker.qcow2
```
