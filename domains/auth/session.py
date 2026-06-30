import http.cookies
import secrets


class AuthSession:
    def __init__(self):
        self.token = ""
        self.session_token = ""

    def init_tokens(self):
        self.token = secrets.token_urlsafe(32)
        self.session_token = secrets.token_urlsafe(32)

    def check_session(self, cookie_header):
        jar = http.cookies.SimpleCookie()
        try:
            jar.load(cookie_header or "")
        except http.cookies.CookieError:
            return False
        morsel = jar.get("session")
        value = morsel.value if morsel else ""
        return secrets.compare_digest(value, self.session_token)

    def check_url_token(self, token):
        return secrets.compare_digest(token or "", self.token)

    def make_set_cookie(self):
        jar = http.cookies.SimpleCookie()
        jar["session"] = self.session_token
        jar["session"]["httponly"] = True
        jar["session"]["samesite"] = "Strict"
        jar["session"]["path"] = "/"
        jar["session"]["max-age"] = 86400
        return jar["session"].OutputString()


# Module-level singleton
auth = AuthSession()
