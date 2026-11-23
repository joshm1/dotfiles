# scripts

- `setup-ai-suite.sh` — installs Claude Code, OpenAI Codex CLI and the Antigravity CLI (`agy`),
  places `~/.dotfiles` and `~/.dotfiles-private` (and `~/projects/joshm1/...`) so the rest of
  this repo's setup scripts can find both clones, and links `~/.agents/skills` (plus
  `~/.claude/skills` and `~/.gemini/config/skills`) to a union of private
  (`home/.agents/skills`) and public (`.agents/skills`) skill trees. Linux/macOS, idempotent,
  never signs in, never changes the login shell, and never replaces an existing real checkout
  or working symlink unless `FORCE_LINK=1`. Env overrides: `SKILLS_SRC`, `PRIVATE_DOTFILES_REPO`,
  `T3=1`, `SKIP_INSTALL=1`.
