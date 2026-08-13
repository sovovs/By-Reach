# -*- coding: utf-8 -*-
"""Tests for ByReach core class."""

import pytest

from by_reach.config import Config
from by_reach.core import ByReach


@pytest.fixture
def eyes(tmp_path):
    config = Config(config_path=tmp_path / "config.yaml")
    return ByReach(config=config)


class TestByReach:
    def test_init(self, eyes):
        assert eyes.config is not None

    def test_doctor(self, eyes):
        results = eyes.doctor()
        assert isinstance(results, dict)
        assert "web" in results
        assert "github" in results

    def test_doctor_report(self, eyes):
        report = eyes.doctor_report()
        assert isinstance(report, str)
        assert "By-Reach" in report
