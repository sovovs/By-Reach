# -*- coding: utf-8 -*-
"""LinkedIn — byCLI capability-backed channel."""

from ._bycli_site import ByCliSiteChannel


class LinkedInChannel(ByCliSiteChannel):
    name = "linkedin"
    description = "LinkedIn 职业社交"
    capability = "linkedin/search"
    tier = 2
    domains = ("linkedin.com",)
