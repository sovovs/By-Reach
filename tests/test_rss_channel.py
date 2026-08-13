"""RSS retains feed recognition and explicit dependency health reporting."""

import builtins
import sys
import types

from by_reach.channels.rss import RSSChannel


def test_rss_recognises_feed_urls_and_rejects_regular_pages():
    channel = RSSChannel()

    assert channel.can_handle("https://example.com/feed.xml")
    assert channel.can_handle("https://example.com/Atom.XML")
    assert not channel.can_handle("https://github.com/sovovs/By-Reach")


def test_rss_marks_feedparser_as_the_active_backend(monkeypatch):
    monkeypatch.setitem(sys.modules, "feedparser", types.ModuleType("feedparser"))
    channel = RSSChannel()

    status, _ = channel.check()

    assert status == "ok"
    assert channel.active_backend == "feedparser"


def test_rss_missing_dependency_clears_stale_backend(monkeypatch):
    monkeypatch.setitem(sys.modules, "feedparser", None)
    channel = RSSChannel()
    channel.active_backend = "feedparser"

    status, message = channel.check()

    assert status == "off"
    assert channel.active_backend is None
    assert "pip install feedparser" in message


def test_rss_import_failure_reports_reinstall_hint(monkeypatch):
    real_import = builtins.__import__

    def fail_feedparser(name, *args, **kwargs):
        if name == "feedparser":
            raise RuntimeError("broken install")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_feedparser)

    status, message = RSSChannel().check()

    assert status == "error"
    assert "--force-reinstall" in message
