# -*- coding: utf-8 -*-
"""Instagram — byCLI capability-backed channel."""

from ._bycli_site import ByCliSiteChannel


class InstagramChannel(ByCliSiteChannel):
    name = "instagram"
    description = "Instagram 用户、主页和指定用户帖子"
    capability = "instagram/search"
    domains = ("instagram.com", "instagr.am")
