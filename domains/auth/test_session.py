import unittest
from domains.auth.session import AuthSession


class TestAuthSession(unittest.TestCase):
    def setUp(self):
        self.auth = AuthSession()
        self.auth.init_tokens()

    def test_tokens_non_empty(self):
        self.assertTrue(len(self.auth.token) > 0)
        self.assertTrue(len(self.auth.session_token) > 0)

    def test_tokens_differ(self):
        self.assertNotEqual(self.auth.token, self.auth.session_token)

    def test_init_rotates_tokens(self):
        old = self.auth.session_token
        self.auth.init_tokens()
        self.assertNotEqual(self.auth.session_token, old)

    def test_check_session_valid(self):
        cookie = f"session={self.auth.session_token}"
        self.assertTrue(self.auth.check_session(cookie))

    def test_check_session_wrong_value(self):
        self.assertFalse(self.auth.check_session("session=wrong"))

    def test_check_session_missing_cookie(self):
        self.assertFalse(self.auth.check_session(""))

    def test_check_session_malformed_header(self):
        self.assertFalse(self.auth.check_session(";;;"))

    def test_make_set_cookie_contains_token(self):
        header = self.auth.make_set_cookie()
        self.assertIn(self.auth.session_token, header)

    def test_make_set_cookie_httponly(self):
        header = self.auth.make_set_cookie().lower()
        self.assertIn("httponly", header)

    def test_make_set_cookie_samesite_strict(self):
        header = self.auth.make_set_cookie().lower()
        self.assertIn("samesite=strict", header)

    def test_check_url_token_valid(self):
        self.assertTrue(self.auth.check_url_token(self.auth.token))

    def test_check_url_token_invalid(self):
        self.assertFalse(self.auth.check_url_token("bad"))


if __name__ == "__main__":
    unittest.main()
