#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2015-2019 Mike Fährmann
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.

import os
import sys
import re
import json
import hashlib
import unittest
from gallery_dl import extractor, job, config, exception


# these don't work on Travis CI
TRAVIS_SKIP = {
    "exhentai", "kissmanga", "mangafox", "dynastyscans", "nijie", "bobx",
    "archivedmoe", "archiveofsins", "thebarchive", "fireden", "4plebs",
    "sankaku", "idolcomplex", "mangahere", "readcomiconline", "mangadex",
}

# temporary issues, etc.
BROKEN = {
    "acidimg",
    "mangapark",
}


class TestExtractorResults(unittest.TestCase):

    def setUp(self):
        setup_test_config()

    def tearDown(self):
        config.clear()

    def _run_test(self, extr, url, result):
        if result:
            if "options" in result:
                for key, value in result["options"]:
                    config.set(key.split("."), value)
            if "range" in result:
                config.set(("image-range",), result["range"])
                config.set(("chapter-range",), result["range"])
            content = "content" in result
        else:
            content = False

        tjob = ResultJob(url, content=content)
        self.assertEqual(extr, tjob.extractor.__class__)

        if not result:
            return
        if "exception" in result:
            self.assertRaises(result["exception"], tjob.run)
            return
        try:
            tjob.run()
        except exception.StopExtraction:
            pass
        except exception.HttpError as exc:
            if re.match(r"5\d\d: ", str(exc)):
                self.skipTest(exc)
            raise

        # test archive-id uniqueness
        self.assertEqual(len(set(tjob.list_archive)), len(tjob.list_archive))

        # test '_extractor' entries
        if tjob.queue:
            for url, kwdict in zip(tjob.list_url, tjob.list_keyword):
                if "_extractor" in kwdict:
                    extr = kwdict["_extractor"].from_url(url)
                    self.assertIsInstance(extr, kwdict["_extractor"])
                    self.assertEqual(extr.url, url)

        # test extraction results
        if "url" in result:
            self.assertEqual(result["url"], tjob.hash_url.hexdigest())

        if "content" in result:
            self.assertEqual(result["content"], tjob.hash_content.hexdigest())

        if "keyword" in result:
            keyword = result["keyword"]
            if isinstance(keyword, dict):
                for kwdict in tjob.list_keyword:
                    self._test_kwdict(kwdict, keyword)
            else:  # assume SHA1 hash
                self.assertEqual(keyword, tjob.hash_keyword.hexdigest())

        if "count" in result:
            count = result["count"]
            if isinstance(count, str):
                self.assertRegex(count, r"^ *(==|!=|<|<=|>|>=) *\d+ *$")
                expr = "{} {}".format(len(tjob.list_url), count)
                self.assertTrue(eval(expr), msg=expr)
            else:  # assume integer
                self.assertEqual(len(tjob.list_url), count)

        if "pattern" in result:
            self.assertGreater(len(tjob.list_url), 0)
            for url in tjob.list_url:
                self.assertRegex(url, result["pattern"])

    def _test_kwdict(self, kwdict, tests):
        for key, test in tests.items():
            if key.startswith("?"):
                key = key[1:]
                if key not in kwdict:
                    continue
            self.assertIn(key, kwdict)
            value = kwdict[key]

            if isinstance(test, dict):
                self._test_kwdict(value, test)
            elif isinstance(test, type):
                self.assertIsInstance(value, test, msg=key)
            elif isinstance(test, str) and test.startswith("re:"):
                self.assertRegex(value, test[3:], msg=key)
            else:
                self.assertEqual(value, test, msg=key)


class ResultJob(job.DownloadJob):
    """Generate test-results for extractor runs"""

    def __init__(self, url, parent=None, content=False):
        job.DownloadJob.__init__(self, url, parent)
        self.queue = False
        self.content = content
        self.list_url = []
        self.list_keyword = []
        self.list_archive = []
        self.hash_url = hashlib.sha1()
        self.hash_keyword = hashlib.sha1()
        self.hash_archive = hashlib.sha1()
        self.hash_content = hashlib.sha1()
        if content:
            self.fileobj = FakePathfmt(self.hash_content)
            self.get_downloader("http")._check_extension = lambda a, b: None

    def run(self):
        for msg in self.extractor:
            self.dispatch(msg)

    def handle_url(self, url, keywords):
        self.update_url(url)
        self.update_keyword(keywords)
        self.update_archive(keywords)
        self.update_content(url)

    def handle_directory(self, keywords):
        self.update_keyword(keywords, False)

    def handle_queue(self, url, keywords):
        self.queue = True
        self.update_url(url)
        self.update_keyword(keywords)

    def update_url(self, url):
        self.list_url.append(url)
        self.hash_url.update(url.encode())

    def update_keyword(self, kwdict, to_list=True):
        if to_list:
            self.list_keyword.append(kwdict)
        kwdict = self._filter(kwdict)
        self.hash_keyword.update(
            json.dumps(kwdict, sort_keys=True, default=str).encode())

    def update_archive(self, kwdict):
        archive_id = self.extractor.archive_fmt.format_map(kwdict)
        self.list_archive.append(archive_id)
        self.hash_archive.update(archive_id.encode())

    def update_content(self, url):
        if self.content:
            scheme = url.partition(":")[0]
            self.get_downloader(scheme).download(url, self.fileobj)


class FakePathfmt():
    """Minimal file-like interface"""

    def __init__(self, hashobj):
        self.hashobj = hashobj
        self.path = ""
        self.size = 0
        self.has_extension = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def open(self, mode):
        self.size = 0
        return self

    def write(self, content):
        """Update SHA1 hash"""
        self.size += len(content)
        self.hashobj.update(content)

    def tell(self):
        return self.size

    def part_size(self):
        return 0


def setup_test_config():
    name = "gallerydl"
    email = "gallerydl@openaliasbox.org"

    config.clear()
    config.set(("cache", "file"), ":memory:")
    config.set(("downloader", "part"), False)
    config.set(("extractor", "timeout"), 60)
    config.set(("extractor", "username"), name)
    config.set(("extractor", "password"), name)
    config.set(("extractor", "nijie", "username"), email)
    config.set(("extractor", "seiga", "username"), email)
    config.set(("extractor", "danbooru", "username"), None)
    config.set(("extractor", "twitter" , "username"), None)
    config.set(("extractor", "mangoxo" , "password"), "VZ8DL3983u")

    config.set(("extractor", "deviantart", "client-id"), "7777")
    config.set(("extractor", "deviantart", "client-secret"),
               "ff14994c744d9208e5caeec7aab4a026")

    config.set(("extractor", "tumblr", "api-key"),
               "0cXoHfIqVzMQcc3HESZSNsVlulGxEXGDTTZCDrRrjaa0jmuTc6")
    config.set(("extractor", "tumblr", "api-secret"),
               "6wxAK2HwrXdedn7VIoZWxGqVhZ8JdYKDLjiQjL46MLqGuEtyVj")
    config.set(("extractor", "tumblr", "access-token"),
               "N613fPV6tOZQnyn0ERTuoEZn0mEqG8m2K8M3ClSJdEHZJuqFdG")
    config.set(("extractor", "tumblr", "access-token-secret"),
               "sgOA7ZTT4FBXdOGGVV331sSp0jHYp4yMDRslbhaQf7CaS71i4O")


def generate_tests():
    """Dynamically generate extractor unittests"""
    def _generate_test(extr, tcase):
        def test(self):
            url, result = tcase
            print("\n", url, sep="")
            self._run_test(extr, url, result)
        return test

    # enable selective testing for direct calls
    if __name__ == '__main__' and len(sys.argv) > 1:
        if sys.argv[1].lower() == "all":
            fltr = lambda c, bc: True  # noqa: E731
        elif sys.argv[1].lower() == "broken":
            fltr = lambda c, bc: c in BROKEN  # noqa: E731
        else:
            argv = sys.argv[1:]
            fltr = lambda c, bc: c in argv or bc in argv  # noqa: E731
        del sys.argv[1:]
    else:
        skip = set(BROKEN)
        if "CI" in os.environ and "TRAVIS" in os.environ:
            skip |= set(TRAVIS_SKIP)
        if skip:
            print("skipping:", ", ".join(skip))
        fltr = lambda c, bc: c not in skip  # noqa: E731

    # filter available extractor classes
    extractors = [
        extr for extr in extractor.extractors()
        if fltr(extr.category, getattr(extr, "basecategory", None))
    ]

    # add 'test_...' methods
    for extr in extractors:
        name = "test_" + extr.__name__ + "_"
        for num, tcase in enumerate(extr._get_tests(), 1):
            test = _generate_test(extr, tcase)
            test.__name__ = name + str(num)
            setattr(TestExtractorResults, test.__name__, test)


generate_tests()
if __name__ == '__main__':
    unittest.main(warnings='ignore')
