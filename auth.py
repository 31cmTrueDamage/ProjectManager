"""
Google OAuth via direct authorization code flow.
Bypasses Firebase createAuthUri — builds the Google OAuth URL directly,
catches the callback on localhost:9001, exchanges code for tokens,
then signs into Firebase with the id_token.
"""

import os, sys, json, threading, urllib.parse, urllib.request, webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BASE_DIR, ".env"))

SESSION_FILE  = os.path.join(BASE_DIR, "session.json")
REDIRECT_URI  = "http://localhost:9001/callback"
CALLBACK_PORT = 9001


def _env(key):
    v = os.getenv(key, "")
    if not v:
        raise RuntimeError(f"{key} not set in .env")
    return v


# ── Session ───────────────────────────────────────────────────────────────────
def load_session():
    try:
        with open(SESSION_FILE) as f:
            return json.load(f)
    except Exception:
        return None

def save_session(data):
    with open(SESSION_FILE, "w") as f:
        json.dump(data, f, indent=2)

def clear_session():
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)


# ── Build Google OAuth URL directly ──────────────────────────────────────────
def build_auth_url() -> str:
    params = urllib.parse.urlencode({
        "client_id":     _env("FIREBASE_CLIENT_ID"),
        "redirect_uri":  REDIRECT_URI,
        "response_type": "code",
        "scope":         "openid email profile",
        "access_type":   "offline",
        "prompt":        "select_account",
    })
    return f"https://accounts.google.com/o/oauth2/v2/auth?{params}"


# ── Token exchange ────────────────────────────────────────────────────────────
def _exchange_code(code: str) -> dict:
    # Step 1: code → Google tokens
    body = urllib.parse.urlencode({
        "code":          code,
        "client_id":     _env("FIREBASE_CLIENT_ID"),
        "client_secret": _env("FIREBASE_CLIENT_SECRET"),
        "redirect_uri":  REDIRECT_URI,
        "grant_type":    "authorization_code",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=body)
    with urllib.request.urlopen(req, timeout=10) as resp:
        tokens = json.loads(resp.read())

    id_token = tokens.get("id_token", "")
    if not id_token:
        raise RuntimeError(f"No id_token in response: {tokens}")

    # Step 2: sign into Firebase with id_token
    url  = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key={_env('FIREBASE_API_KEY')}"
    body2 = json.dumps({
        "postBody":            f"id_token={id_token}&providerId=google.com",
        "requestUri":          REDIRECT_URI,
        "returnIdpCredential": True,
        "returnSecureToken":   True,
    }).encode()
    req2 = urllib.request.Request(url, data=body2,
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req2, timeout=10) as resp2:
        user = json.loads(resp2.read())

    session = {
        "uid":           user.get("localId", ""),
        "display_name":  user.get("displayName", "User"),
        "email":         user.get("email", ""),
        "photo_url":     user.get("photoUrl", ""),
        "id_token":      user.get("idToken", ""),
        "refresh_token": user.get("refreshToken", ""),
    }
    save_session(session)
    return session


# ── Local callback server ─────────────────────────────────────────────────────
_server_instance = [None]

def start_callback_server(on_success, on_error):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)

            if "code" in params:
                self._respond(_success_html())
                code = params["code"][0]
                threading.Thread(target=self._exchange, args=(code,), daemon=True).start()
            elif "error" in params:
                err = params.get("error", ["unknown"])[0]
                self._respond(_error_html(err))
                threading.Thread(target=lambda: on_error("Sign-in was cancelled."),
                                 daemon=True).start()
                _stop_server()
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Not found")

        def _respond(self, html):
            body = html.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _exchange(self, code):
            try:
                session = _exchange_code(code)
                on_success(session)
            except Exception as e:
                on_error(str(e))
            finally:
                _stop_server()

    def _run():
        try:
            srv = HTTPServer(("localhost", CALLBACK_PORT), Handler)
            _server_instance[0] = srv
            srv.handle_request()
        except Exception as e:
            on_error(str(e))

    threading.Thread(target=_run, daemon=True).start()


def _stop_server():
    srv = _server_instance[0]
    if srv:
        try: srv.server_close()
        except Exception: pass
        _server_instance[0] = None


def open_google_login(on_success, on_error):
    try:
        start_callback_server(on_success, on_error)
        webbrowser.open(build_auth_url())
    except Exception as e:
        on_error(str(e))


# ── Browser pages ─────────────────────────────────────────────────────────────
def _success_html():
    return """<!DOCTYPE html><html><head><meta charset="utf-8">
<style>*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,sans-serif;background:#0F172A;color:#F1F5F9;
display:flex;align-items:center;justify-content:center;height:100vh}
.card{background:#1E293B;border:1px solid #334155;border-radius:16px;
padding:48px 56px;text-align:center}
h1{font-size:22px;font-weight:700;margin:16px 0 8px}
p{color:#94A3B8;font-size:14px}</style></head>
<body><div class="card"><div style="font-size:48px">✅</div>
<h1>Signed in successfully</h1>
<p>You can close this tab and return to the app.</p>
</div></body></html>"""

def _error_html(error):
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,sans-serif;background:#0F172A;color:#F1F5F9;
display:flex;align-items:center;justify-content:center;height:100vh}}
.card{{background:#1E293B;border:1px solid #334155;border-radius:16px;
padding:48px 56px;text-align:center}}
h1{{font-size:22px;font-weight:700;margin:16px 0 8px}}
p{{color:#94A3B8;font-size:14px}}</style></head>
<body><div class="card"><div style="font-size:48px">❌</div>
<h1>Sign-in failed</h1><p>{error}</p>
</div></body></html>"""