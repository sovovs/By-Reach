# -*- coding: utf-8 -*-
"""By-Reach public package identity."""

from by_reach.core import ByReach
from by_reach.identity import (
    CONFIG_DIRNAME,
    DISPLAY_NAME,
    ENV_PREFIX,
    PROGRAM_NAME,
    SKILL_NAME,
)

__version__ = "2.0.0b1"
__author__ = "sovovs"

__all__ = [
    "ByReach",
    "CONFIG_DIRNAME",
    "DISPLAY_NAME",
    "ENV_PREFIX",
    "PROGRAM_NAME",
    "SKILL_NAME",
]
