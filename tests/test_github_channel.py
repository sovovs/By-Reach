"""Current read-only GitHub health checks retain their credential boundaries."""

from pathlib import Path

from by_reach.channels import github as github_module
from by_reach.channels.github import GitHubChannel
from by_reach.probe import ProbeResult


def test_github_broken_shim_reports_recovery_hint(monkeypatch):
    monkeypatch.setattr(
        github_module,
        "probe_command",
        lambda *_args, **_kwargs: ProbeResult("broken"),
    )

    status, message = GitHubChannel().check()

    assert status == "error"
    assert "brew reinstall gh" in message


def test_github_env_auth_is_not_disclosed_and_remains_unverified(monkeypatch):
    secret = "configured-secret"
    monkeypatch.setenv("GH_TOKEN", secret)
    monkeypatch.setattr(
        github_module,
        "probe_command",
        lambda *_args, **_kwargs: ProbeResult("ok", output="gh version 2"),
    )
    channel = GitHubChannel()

    status, message = channel.check()

    assert status == "warn"
    assert channel.active_backend is None
    assert "显式认证配置" in message
    assert secret not in message


def test_github_hosts_metadata_is_read_without_disclosing_identity_or_token(
    isolated_home, monkeypatch
):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    hosts = Path(isolated_home) / ".config" / "gh" / "hosts.yml"
    hosts.parent.mkdir(parents=True)
    hosts.write_text(
        "github.com:\n  user: alice\n  oauth_token: super-secret-token\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        github_module,
        "probe_command",
        lambda *_args, **_kwargs: ProbeResult("ok", output="gh version 2"),
    )

    status, message = GitHubChannel().check()

    assert status == "warn"
    assert "显式认证配置" in message
    assert "alice" not in message
    assert "super-secret-token" not in message


def test_github_hosts_reader_refuses_ancestor_symlink(isolated_home, monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    real_config = Path(isolated_home) / "real-config"
    hosts = real_config / "gh" / "hosts.yml"
    hosts.parent.mkdir(parents=True)
    hosts.write_text(
        "github.com:\n  oauth_token: do-not-read\n", encoding="utf-8"
    )
    config_dir = Path(isolated_home) / ".config"
    try:
        config_dir.symlink_to(real_config, target_is_directory=True)
    except OSError:
        return
    monkeypatch.setattr(
        github_module,
        "probe_command",
        lambda *_args, **_kwargs: ProbeResult("ok", output="gh version 2"),
    )

    status, message = GitHubChannel().check()

    assert status == "warn"
    assert "无法安全确认" in message
    assert "do-not-read" not in message
