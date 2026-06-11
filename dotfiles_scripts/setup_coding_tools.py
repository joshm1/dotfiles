#!/usr/bin/env python3
"""Install Claude Code companion tools: git-ai and dcg."""

from __future__ import annotations

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


def main() -> int:
    print_header("Setting up Claude Code companion tools")
    ok = True
    ok = setup_git_ai() and ok
    ok = setup_dcg() and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
