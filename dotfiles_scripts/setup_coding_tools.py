#!/usr/bin/env python3
"""Install Claude Code companion tools: git-ai, dcg, and enabled plugins."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from dotfiles_scripts.setup_utils import (
    print_header,
    print_step,
    print_success,
    print_warning,
)

_GIT_AI_INSTALL = "https://usegitai.com/install.sh"
_DCG_BIN = Path.home() / ".local" / "bin" / "dcg"
_DCG_INSTALLER = "https://raw.githubusercontent.com/Dicklesworthstone/destructive_command_guard/main/install.sh"

# settings.json (device-specific symlink) declares which plugins are enabled;
# its `enabledPlugins` keys are `plugin@marketplace` ids. The enable toggle
# syncs via dotfiles, but the actual install is per-machine runtime state — this
# is what closes that gap on a fresh box.
_CLAUDE_SETTINGS = Path.home() / ".claude" / "settings.json"

# marketplace name -> source accepted by `claude plugin marketplace add`
# (a GitHub `owner/repo` or an absolute local path). Only consulted when the
# marketplace isn't already configured on this machine. settings.json names the
# marketplace but not its origin, so keep this in sync when adding a new one.
_MARKETPLACE_SOURCES = {
    "claude-plugins-official": "anthropics/claude-plugins-official",
    "openai-codex": "openai/codex-plugin-cc",
    "superpowers-dev": "obra/superpowers",
    "chrome-devtools-plugins": "ChromeDevTools/chrome-devtools-mcp",
    "dev-browser-marketplace": "sawyerhood/dev-browser",
    "claude-code-workflows": "wshobson/agents",
    "joshm1-claude-plugins": str(Path.home() / "projects" / "joshm1" / "joshm1-claude-plugins"),
    "skills-private": str(Path.home() / "projects" / "joshm1" / "skills-private"),
}


def _security_audit(script_path: Path) -> None:
    """Run a Codex security audit on the installer script. Non-blocking."""
    if not shutil.which("codex"):
        print_warning("codex not in PATH — skipping security audit")
        return

    print_step("Running Codex security audit on installer...")
    result = subprocess.run(
        [
            "codex", "exec",
            f"Security audit of {script_path} — read the file, then report any risks: "
            "arbitrary code execution, suspicious network calls beyond downloading the binary, "
            "privilege escalation, path manipulation, eval of untrusted data, hardcoded credentials, "
            "supply chain risks. Cite line numbers. End with: SAFE TO RUN, REVIEW RECOMMENDED, or DO NOT RUN.",
        ],
        capture_output=True,
        text=True,
    )
    output = (result.stdout + result.stderr).strip()
    if output:
        print(output)
    else:
        print_warning("Codex audit returned no output")


def setup_git_ai() -> bool:
    git_ai = Path.home() / ".git-ai" / "bin" / "git-ai"
    if git_ai.exists():
        print_success("git-ai already installed")
        return True

    print_step("Installing git-ai...")
    try:
        req = urllib.request.Request(_GIT_AI_INSTALL, headers={"User-Agent": "curl/8.0"})
        script = urllib.request.urlopen(req).read()
        subprocess.run(["bash"], input=script, check=True)
        print_success("git-ai installed")
        return True
    except Exception as e:
        print_warning(f"git-ai install failed: {e}")
        print(f"  Manual install: curl -fsSL {_GIT_AI_INSTALL} | bash")
        return False


def setup_dcg() -> bool:
    if _DCG_BIN.exists():
        print_step("Updating dcg (also reconfigures hooks for all AI agents)...")
        try:
            subprocess.run([str(_DCG_BIN), "update"], check=True)
            print_success("dcg updated")
        except Exception as e:
            print_warning(f"dcg update failed: {e}")
        return True

    print_step("Installing dcg...")
    try:
        import time
        url = f"{_DCG_INSTALLER}?{int(time.time())}"
        with tempfile.NamedTemporaryFile(suffix=".sh", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            tmp_path.write_bytes(urllib.request.urlopen(url).read())

        _security_audit(tmp_path)

        subprocess.run(["bash", str(tmp_path), "--easy-mode"], check=True)
        tmp_path.unlink(missing_ok=True)
        print_success("dcg installed and hooks configured for all AI agents")
        return True
    except Exception as e:
        print_warning(f"dcg install failed: {e}")
        print(f"  Manual install: curl -fsSL '{_DCG_INSTALLER}?$(date +%s)' | bash -s -- --easy-mode")
        return False


def _enabled_plugin_ids() -> list[str]:
    """Read `plugin@marketplace` ids that settings.json marks enabled."""
    try:
        data = json.loads(_CLAUDE_SETTINGS.read_text())
    except FileNotFoundError:
        print_warning(f"{_CLAUDE_SETTINGS} not found — skipping plugin install")
        return []
    except (OSError, json.JSONDecodeError) as e:
        print_warning(f"could not read {_CLAUDE_SETTINGS}: {e}")
        return []
    return sorted(pid for pid, on in data.get("enabledPlugins", {}).items() if on)


def _claude_json(*args: str) -> list | None:
    """Run a `claude ... --json` command and parse its array output, or None."""
    try:
        out = subprocess.run(
            ["claude", *args, "--json"], capture_output=True, text=True, check=True
        ).stdout
        return json.loads(out)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None


def setup_claude_plugins() -> bool:
    """Install the plugins settings.json declares enabled (idempotent).

    The enable toggle travels with dotfiles, but each machine must install the
    plugins itself. Derives the needed marketplaces from the enabled ids, adds
    any that are missing, then installs whatever isn't already present.
    """
    if not shutil.which("claude"):
        print_warning("claude not in PATH — skipping plugin install")
        return False

    enabled = _enabled_plugin_ids()
    if not enabled:
        return True

    print_step(f"Ensuring {len(enabled)} enabled Claude Code plugins are installed...")

    # Configure every marketplace the enabled plugins reference.
    configured = {m["name"] for m in (_claude_json("plugin", "marketplace", "list") or [])}
    needed = {pid.split("@", 1)[1] for pid in enabled if "@" in pid}
    for mp in sorted(needed - configured):
        source = _MARKETPLACE_SOURCES.get(mp)
        if not source:
            print_warning(f"unknown marketplace '{mp}' — add it manually; its plugins will be skipped")
            continue
        if Path(source).is_absolute() and not Path(source).exists():
            print_warning(f"marketplace '{mp}' source path missing: {source} — skipping")
            continue
        print_step(f"Adding marketplace {mp} ({source})...")
        try:
            subprocess.run(["claude", "plugin", "marketplace", "add", source], check=True)
            configured.add(mp)
        except subprocess.CalledProcessError as e:
            print_warning(f"failed to add marketplace {mp}: {e}")

    # Install each enabled plugin that isn't already installed.
    installed = {p["id"] for p in (_claude_json("plugin", "list") or [])}
    ok = True
    for pid in enabled:
        if pid in installed:
            continue
        mp = pid.split("@", 1)[1] if "@" in pid else ""
        if mp and mp not in configured:
            print_warning(f"skipping {pid}: marketplace '{mp}' not configured")
            ok = False
            continue
        print_step(f"Installing {pid}...")
        try:
            subprocess.run(["claude", "plugin", "install", pid], check=True)
        except subprocess.CalledProcessError as e:
            print_warning(f"failed to install {pid}: {e}")
            ok = False

    print_success("Claude Code plugins ready (restart Claude Code to load them)")
    return ok


def main() -> int:
    print_header("Setting up Claude Code companion tools")
    ok = True
    ok = setup_git_ai() and ok
    ok = setup_dcg() and ok
    ok = setup_claude_plugins() and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
