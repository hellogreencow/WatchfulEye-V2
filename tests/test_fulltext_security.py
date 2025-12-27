import unittest

from watchfuleye.extraction.fulltext import fetch_and_extract


class TestFulltextSecurity(unittest.TestCase):
    def test_blocks_localhost(self):
        r = fetch_and_extract("http://localhost:1234/")
        self.assertEqual(r.status, "blocked")

    def test_blocks_private_ip(self):
        r = fetch_and_extract("http://127.0.0.1:1234/")
        self.assertEqual(r.status, "blocked")

    def test_blocks_non_http_scheme(self):
        r = fetch_and_extract("file:///etc/passwd")
        self.assertEqual(r.status, "blocked")


if __name__ == "__main__":
    unittest.main()


