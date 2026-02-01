#!/usr/bin/env python3
"""Setup GPG keys from manifest file."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

from dotfiles_scripts.setup_utils import (
    DROPBOX_DIR,
    print_header,
    print_step,
    print_success,
    print_warning,
)

GPG_KEYS_MANIFEST = DROPBOX_DIR / "dotfiles" / ".gpg-keys.yaml"


def get_key_id_for_email(email: str) -> str | None:
    """Get the short key ID for an email address."""
    result = subprocess.run(
        ["gpg", "--list-secret-keys", "--keyid-format", "SHORT", email],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    # Parse output like: sec   rsa4096/3AF5F757 2024-03-28 [SC]
    for line in result.stdout.splitlines():
        if line.startswith("sec"):
            match = re.search(r"/([A-F0-9]+)", line)
            if match:
                return match.group(1)
    return None


def get_existing_emails() -> set[str]:
    """Get emails of existing GPG secret keys."""
    result = subprocess.run(
        ["gpg", "--list-secret-keys", "--with-colons"],
        capture_output=True,
        text=True,
    )
    emails = set()
    for line in result.stdout.splitlines():
        if line.startswith("uid:"):
            # Format: uid:u::::1234567890::Name <email>:::::::::0:
            parts = line.split(":")
            if len(parts) > 9:
                uid = parts[9]
                if "<" in uid and ">" in uid:
                    email = uid.split("<")[1].split(">")[0]
                    emails.add(email)
    return emails


def generate_key(name: str, email: str) -> bool:
    """Generate a GPG key non-interactively."""
    key_params = f"""\
Key-Type: RSA
Key-Length: 4096
Subkey-Type: RSA
Subkey-Length: 4096
Name-Real: {name}
Name-Email: {email}
Expire-Date: 0
%no-protection
%commit
"""
    result = subprocess.run(
        ["gpg", "--batch", "--generate-key"],
        input=key_params,
        text=True,
        capture_output=True,
    )
    return result.returncode == 0


def update_gitconfig(profile: str, key_id: str) -> bool:
    """Update the device-specific gitconfig with the signing key."""
    device_id_file = Path.home() / ".device_id"
    if not device_id_file.exists():
        print_warning("No ~/.device_id found, skipping gitconfig update")
        return False

    device_id = device_id_file.read_text().strip()
    if not device_id:
        return False

    gitconfig_file = Path.home() / f".gitconfig_{profile}.{device_id}"
    if not gitconfig_file.exists():
        print_warning(f"{gitconfig_file} not found, skipping")
        return False

    content = gitconfig_file.read_text()

    # Check if already configured with this key
    if f"signingkey = {key_id}" in content:
        print_step(f"{gitconfig_file.name} already has key {key_id}")
        return True

    # Replace commented placeholder or existing signingkey
    new_content = content
    if "# [user]" in content and "#   signingkey" in content:
        # Replace placeholder
        new_content = re.sub(
            r"# \[user\]\n#\s+signingkey\s*=\s*\S+",
            f"[user]\n  signingkey = {key_id}",
            content,
        )
    elif "[user]" in content and "signingkey" in content:
        # Replace existing
        new_content = re.sub(
            r"(signingkey\s*=\s*)\S+",
            f"\\g<1>{key_id}",
            content,
        )
    else:
        # Append
        new_content = content.rstrip() + f"\n\n[user]\n  signingkey = {key_id}\n"

    gitconfig_file.write_text(new_content)
    return True


def main() -> int:
    """Main entry point."""
    print_header("Setting up GPG keys")

    if not GPG_KEYS_MANIFEST.exists():
        print_warning(f"No GPG keys manifest found at {GPG_KEYS_MANIFEST}")
        return 0

    try:
        config = yaml.safe_load(GPG_KEYS_MANIFEST.read_text()) or {}
    except yaml.YAMLError as e:
        print_warning(f"Invalid YAML in {GPG_KEYS_MANIFEST}: {e}")
        return 1

    keys = config.get("keys", [])
    if not keys:
        print_step("No keys defined in manifest")
        return 0

    existing_emails = get_existing_emails()

    for key in keys:
        name = key.get("name")
        email = key.get("email")
        profile = key.get("profile")
        if not name or not email:
            print_warning(f"Skipping invalid key entry: {key}")
            continue

        # Generate if needed
        if email not in existing_emails:
            print_step(f"Generating key for {name} <{email}>...")
            if not generate_key(name, email):
                print_warning(f"Failed to generate key for {email}")
                continue
            print_success(f"Generated key for {email}")

        # Get and print key ID
        key_id = get_key_id_for_email(email)
        if key_id:
            print_success(f"Key for {email}: {key_id}")

            # Update gitconfig if profile specified
            if profile and key_id:
                if update_gitconfig(profile, key_id):
                    print_success(f"Updated .gitconfig_{profile} with key {key_id}")
        else:
            print_warning(f"Could not find key ID for {email}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
