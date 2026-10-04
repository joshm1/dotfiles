from pathlib import Path

import pytest

from dotfiles_scripts import setup_utils


def _set_home(monkeypatch: pytest.MonkeyPatch, home: Path) -> None:
    def fake_home(_path_type: type[Path]) -> Path:
        return home

    monkeypatch.setattr(Path, "home", classmethod(fake_home))


def test_symlink_home_dir_renders_device_template_with_generated_header(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_home = tmp_path / "private-home"
    target_home = tmp_path / "target-home"
    source_home.mkdir()
    target_home.mkdir()
    (target_home / ".gitignore").write_text(".DS_Store\n", encoding="utf-8")
    (source_home / ".dotfiles.yaml").write_text(
        """templates:
  .gitignore_${device_id}:
    use: .gitignore_local.${device_id}.j2
    comment: "#"
""",
        encoding="utf-8",
    )
    template = source_home / ".gitignore_local.mac.mutiny.j2"
    template.write_text(
        '{% include ".gitignore" %}\ndocs/adr/\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(setup_utils, "_read_device_id", lambda: "mac.mutiny")
    _set_home(monkeypatch, target_home)

    assert setup_utils.symlink_home_dir(source_home)

    generated = target_home / ".gitignore_mac.mutiny"
    assert not generated.is_symlink()
    assert generated.read_text(encoding="utf-8") == (
        f"# Generated file. Edit {template} instead.\n.DS_Store\ndocs/adr/\n"
    )
    assert not (target_home / template.name).exists()


def test_symlink_home_dir_skips_missing_optional_device_template(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_home = tmp_path / "private-home"
    target_home = tmp_path / "target-home"
    source_home.mkdir()
    target_home.mkdir()
    (source_home / ".dotfiles.yaml").write_text(
        """templates:
  .gitignore_${device_id}:
    use: .gitignore_local.${device_id}.j2
    comment: "#"
    optional: true
""",
        encoding="utf-8",
    )
    (source_home / ".gitignore_local.mac.mutiny.j2").write_text(
        "docs/adr/\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(setup_utils, "_read_device_id", lambda: "mac.primary")
    _set_home(monkeypatch, target_home)

    assert setup_utils.symlink_home_dir(source_home)
    assert not (target_home / ".gitignore_mac.primary").exists()
    assert not (target_home / ".gitignore_local.mac.mutiny.j2").exists()


def test_symlink_home_dir_replaces_existing_symlink_without_writing_through_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_home = tmp_path / "private-home"
    target_home = tmp_path / "target-home"
    source_home.mkdir()
    target_home.mkdir()
    (target_home / ".gitignore").write_text(".DS_Store\n", encoding="utf-8")
    (source_home / ".dotfiles.yaml").write_text(
        """templates:
  .gitignore_${device_id}:
    use: .gitignore_local.${device_id}.j2
    comment: "#"
""",
        encoding="utf-8",
    )
    template = source_home / ".gitignore_local.mac.mutiny.j2"
    template.write_text(
        '{% include ".gitignore" %}\ndocs/adr/\n',
        encoding="utf-8",
    )
    previous_source = source_home / ".gitignore_local.mac.mutiny"
    previous_source.write_text("legacy-pattern/\n", encoding="utf-8")
    generated = target_home / ".gitignore_mac.mutiny"
    generated.symlink_to(previous_source)
    monkeypatch.setattr(setup_utils, "_read_device_id", lambda: "mac.mutiny")
    _set_home(monkeypatch, target_home)
    monkeypatch.setattr(setup_utils, "_backup_dir", None)

    assert setup_utils.symlink_home_dir(source_home)

    assert previous_source.read_text(encoding="utf-8") == "legacy-pattern/\n"
    assert not generated.is_symlink()
    assert generated.read_text(encoding="utf-8").startswith("# Generated file.")


def test_symlink_home_dir_backs_up_file_with_different_generated_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_home = tmp_path / "private-home"
    target_home = tmp_path / "target-home"
    source_home.mkdir()
    target_home.mkdir()
    (source_home / ".dotfiles.yaml").write_text(
        """templates:
  .gitignore_${device_id}:
    use: .gitignore_local.${device_id}.j2
    comment: "#"
""",
        encoding="utf-8",
    )
    (source_home / ".gitignore_local.mac.mutiny.j2").write_text(
        "docs/adr/\n",
        encoding="utf-8",
    )
    previous = "# Generated file. Edit /different/source.j2 instead.\nhand-written-pattern/\n"
    generated = target_home / ".gitignore_mac.mutiny"
    generated.write_text(previous, encoding="utf-8")
    monkeypatch.setattr(setup_utils, "_read_device_id", lambda: "mac.mutiny")
    _set_home(monkeypatch, target_home)
    monkeypatch.setattr(setup_utils, "_backup_dir", None)

    assert setup_utils.symlink_home_dir(source_home)

    backups = list(target_home.glob(".dotfiles.*.bck/.gitignore_mac.mutiny"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == previous


def test_symlink_home_dir_rejects_malformed_template_without_linking_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_home = tmp_path / "private-home"
    target_home = tmp_path / "target-home"
    source_home.mkdir()
    target_home.mkdir()
    (source_home / ".dotfiles.yaml").write_text(
        """templates:
  .gitignore_${device_id}:
    use: .gitignore_local.${device_id}.j2
    comment: 1
""",
        encoding="utf-8",
    )
    template = source_home / ".gitignore_local.mac.mutiny.j2"
    template.write_text("docs/adr/\n", encoding="utf-8")
    monkeypatch.setattr(setup_utils, "_read_device_id", lambda: "mac.mutiny")
    _set_home(monkeypatch, target_home)

    assert not setup_utils.symlink_home_dir(source_home)
    assert not (target_home / template.name).exists()
    assert not (target_home / ".gitignore_mac.mutiny").exists()


@pytest.mark.parametrize("templates_value", ["[]", "bad", "null"])
def test_symlink_home_dir_rejects_non_mapping_templates_block(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    templates_value: str,
) -> None:
    source_home = tmp_path / "private-home"
    target_home = tmp_path / "target-home"
    source_home.mkdir()
    target_home.mkdir()
    (source_home / ".dotfiles.yaml").write_text(
        f"templates: {templates_value}\n",
        encoding="utf-8",
    )
    template = source_home / ".gitignore_local.mac.mutiny.j2"
    template.write_text("docs/adr/\n", encoding="utf-8")
    monkeypatch.setattr(setup_utils, "_read_device_id", lambda: "mac.mutiny")
    _set_home(monkeypatch, target_home)

    assert not setup_utils.symlink_home_dir(source_home)
    assert not (target_home / template.name).exists()
