import unittest

from watchfuleye.ingestion.url_utils import canonicalize_url, url_hash


class TestUrlCanonicalization(unittest.TestCase):
    def test_canonicalize_strips_tracking_params(self):
        raw = "https://Example.com/path/to/article?utm_source=x&utm_medium=y&id=123&gclid=AAA#section"
        canon = canonicalize_url(raw)
        self.assertEqual(canon, "https://example.com/path/to/article?id=123")

    def test_hash_is_stable_for_equivalent_urls(self):
        a = "https://example.com/a?utm_source=x&id=1"
        b = "https://example.com/a?id=1&utm_medium=y"
        self.assertEqual(url_hash(a), url_hash(b))


if __name__ == "__main__":
    unittest.main()


