# -*- coding: utf-8 -*-
"""Facebook — byCLI capability-backed channel."""

from ._bycli_site import ByCliSiteChannel


class FacebookChannel(ByCliSiteChannel):
    name = "facebook"
    description = "Facebook 帖子、主页和群组"
    capability = "facebook/search"
    domains = ("facebook.com", "fb.com", "fb.watch")
