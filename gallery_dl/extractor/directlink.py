# -*- coding: utf-8 -*-

# Copyright 2017 Mike Fährmann
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.

"""Direct link handling"""

from .common import Extractor, Message
from .. import text


class DirectlinkExtractor(Extractor):
    """Extractor for direct links to images and other media files"""
    category = "directlink"
    filename_fmt = "{domain}/{path}"
    pattern = [r"https?://([^/]+)/([^?&#]+\."
               r"(?:jpe?g|jpe|png|gif|web[mp]|mp4|mkv|og[gmv]|opus))"]
    test = [(("https://photos.smugmug.com/The-World/Hawaii/"
              "i-SWz2K6n/2/X3/IMG_0311-X3.jpg"), {
        "url": "32ee1045881e17ef3f13a9958595afa42421ec6c",
        "keyword": "1abd2f2c115cdf2cf2671d2611349b4213c3ab3e",
    })]

    def __init__(self, match):
        Extractor.__init__(self)
        self.domain, self.path = match.groups()
        self.url = match.string

    def items(self):
        data = {"domain": self.domain, "path": self.path}
        text.nameext_from_url(self.url, data)
        yield Message.Version, 1
        yield Message.Directory, data
        yield Message.Url, self.url, data