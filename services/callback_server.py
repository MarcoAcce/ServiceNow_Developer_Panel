import html
import socket
import threading
from collections.abc import Callable
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from core.oauth import CallbackResult, parse_callback

HTTP_SCHEME: str = "http"
DEFAULT_HTTP_PORT: int = 80
LOCALHOST: str = "localhost"
IPV4_LOOPBACK: str = "127.0.0.1"
IPV6_LOOPBACK: str = "::1"
LOOPBACK_HOSTS: frozenset[str] = frozenset({LOCALHOST, IPV4_LOOPBACK, IPV6_LOOPBACK})
SERVER_THREAD_NAME: str = "oauth-callback"
POLL_INTERVAL_SECONDS: float = 0.1
STOP_TIMEOUT_SECONDS: float = 1.0
CONTENT_TYPE_HEADER: str = "Content-Type"
CONTENT_LENGTH_HEADER: str = "Content-Length"
CACHE_CONTROL_HEADER: str = "Cache-Control"
HTML_CONTENT_TYPE: str = "text/html; charset=utf-8"
NO_STORE: str = "no-store"
NOT_HTTP_MESSAGE: str = "{uri} is not a plain http address"
NOT_LOOPBACK_MESSAGE: str = "{uri} is not an address of this computer"
INVALID_ADDRESS_MESSAGE: str = "{uri} is not a valid address"
BIND_MESSAGE: str = "{uri} could not be served, {reason}"
PAGE_TITLE: str = "ServiceNow Developer Panel"
COMPLETED_TEXT: str = (
    "The login was sent to the panel: its login dialog completes on its own."
)
OTHER_ATTEMPT_TEXT: str = (
    "This answer does not belong to the login in progress in the panel: start the login "
    "again from the panel, or paste the code below in its login dialog."
)
REFUSED_TEXT: str = "The instance refused the login: {reason}."
NO_CODE_TEXT: str = "The instance sent no authorization code."
NOT_FOUND_TEXT: str = "There is nothing at this address."
CODE_LABEL: str = "Authorization code"
COPY_LABEL: str = "Copy code"
COPIED_LABEL: str = "Copied"
CLOSE_HINT: str = (
    "If the login did not complete on its own, paste the code in the login dialog of the "
    "panel. You can close this page."
)
PAGE_TEMPLATE: str = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
body {{ margin: 0; background: #f7f7f8; color: #292b2e; font-family: system-ui, sans-serif; }}
main {{ max-width: 640px; margin: 48px auto; padding: 0 24px; }}
header {{ background: #1f6e54; color: #f0f8f4; padding: 14px 24px; font-weight: bold; }}
h1 {{ font-size: 1.3rem; margin: 24px 0 8px; }}
p {{ line-height: 1.5; }}
.label {{ color: #5c5f66; margin-bottom: 4px; }}
.code {{ display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }}
code {{ flex: 1; background: #fff; border: 1px solid #c9cbcf; border-radius: 4px;
  padding: 10px 12px; font-size: 1rem; word-break: break-all; }}
button {{ background: #4f52bd; color: #fff; border: 0; border-radius: 4px; padding: 10px 16px;
  font-size: 1rem; cursor: pointer; }}
button:hover {{ background: #3f41a7; }}
.hint {{ color: #5c5f66; }}
</style>
</head>
<body>
<header>{title}</header>
<main>
<h1>{heading}</h1>
<p>{message}</p>
{code_section}
</main>
<script>
const button = document.getElementById("copy");
if (button) {{
  button.addEventListener("click", async () => {{
    const code = document.getElementById("code");
    try {{
      await navigator.clipboard.writeText(code.textContent);
    }} catch (error) {{
      const range = document.createRange();
      range.selectNodeContents(code);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      document.execCommand("copy");
    }}
    button.textContent = "{copied}";
  }});
}}
</script>
</body>
</html>
"""
CODE_SECTION_TEMPLATE: str = """<p class="label">{label}</p>
<div class="code">
<code id="code">{code}</code>
<button id="copy" type="button">{copy}</button>
</div>
<p class="hint">{hint}</p>"""
LOGIN_HEADING: str = "Login"
NOT_FOUND_HEADING: str = "Not found"

CallbackListener = Callable[[str], None]


class CallbackServerError(Exception):
    pass


@dataclass(frozen=True)
class RedirectEndpoint:
    uri: str
    host: str
    port: int
    path: str


def redirect_endpoint(redirect_uri: str) -> RedirectEndpoint:
    uri = redirect_uri.strip()
    parts = urlsplit(uri)
    if parts.scheme.lower() != HTTP_SCHEME:
        raise CallbackServerError(NOT_HTTP_MESSAGE.format(uri=uri))
    host = (parts.hostname or "").lower()
    if host not in LOOPBACK_HOSTS:
        raise CallbackServerError(NOT_LOOPBACK_MESSAGE.format(uri=uri))
    try:
        port = parts.port or DEFAULT_HTTP_PORT
    except ValueError:
        raise CallbackServerError(INVALID_ADDRESS_MESSAGE.format(uri=uri)) from None
    return RedirectEndpoint(
        uri=f"{parts.scheme}://{parts.netloc}{parts.path}",
        host=host,
        port=port,
        path=parts.path or "/",
    )


def callback_page(callback: CallbackResult | None, state: str) -> str:
    code = ""
    if callback is None:
        message = NO_CODE_TEXT
    elif callback.error:
        message = REFUSED_TEXT.format(reason=callback.description or callback.error)
    elif not callback.code:
        message = NO_CODE_TEXT
    elif callback.state != state:
        message = OTHER_ATTEMPT_TEXT
        code = callback.code
    else:
        message = COMPLETED_TEXT
        code = callback.code
    return _page(LOGIN_HEADING, message, code)


def not_found_page() -> str:
    return _page(NOT_FOUND_HEADING, NOT_FOUND_TEXT, "")


def _page(heading: str, message: str, code: str) -> str:
    code_section = ""
    if code:
        code_section = CODE_SECTION_TEMPLATE.format(
            label=CODE_LABEL, code=html.escape(code), copy=COPY_LABEL, hint=CLOSE_HINT
        )
    return PAGE_TEMPLATE.format(
        title=PAGE_TITLE,
        heading=html.escape(heading),
        message=html.escape(message),
        code_section=code_section,
        copied=COPIED_LABEL,
    )


class CallbackHandler(BaseHTTPRequestHandler):

    server: "CallbackHttpServer"

    def do_GET(self) -> None:
        parts = urlsplit(self.path)
        endpoint = self.server.endpoint
        if parts.path.rstrip("/") != endpoint.path.rstrip("/"):
            self._respond(HTTPStatus.NOT_FOUND, not_found_page())
            return
        url = f"{endpoint.uri}?{parts.query}" if parts.query else endpoint.uri
        callback = parse_callback(url)
        self._respond(HTTPStatus.OK, callback_page(callback, self.server.state))
        if callback is not None:
            self.server.deliver(url)

    def log_message(self, format: str, *args: object) -> None:
        return None

    def _respond(self, status: HTTPStatus, page: str) -> None:
        payload = page.encode("utf-8")
        self.send_response(status)
        self.send_header(CONTENT_TYPE_HEADER, HTML_CONTENT_TYPE)
        self.send_header(CONTENT_LENGTH_HEADER, str(len(payload)))
        self.send_header(CACHE_CONTROL_HEADER, NO_STORE)
        self.end_headers()
        self.wfile.write(payload)


class CallbackHttpServer(ThreadingHTTPServer):

    allow_reuse_address = True
    daemon_threads = True

    def __init__(
        self,
        address: str,
        family: socket.AddressFamily,
        endpoint: RedirectEndpoint,
        state: str,
        listener: CallbackListener,
    ) -> None:
        self.address_family = family
        self.endpoint: RedirectEndpoint = endpoint
        self.state: str = state
        self.started: threading.Event = threading.Event()
        self._listener: CallbackListener = listener
        super().__init__((address, endpoint.port), CallbackHandler)

    def serve_forever(self, poll_interval: float = POLL_INTERVAL_SECONDS) -> None:
        self.started.set()
        super().serve_forever(poll_interval)

    def deliver(self, url: str) -> None:
        try:
            self._listener(url)
        except RuntimeError:
            return


class CallbackServer:

    def __init__(self, redirect_uri: str, state: str, listener: CallbackListener) -> None:
        self._endpoint: RedirectEndpoint = redirect_endpoint(redirect_uri)
        self._state: str = state
        self._listener: CallbackListener = listener
        self._servers: list[CallbackHttpServer] = []

    @property
    def uri(self) -> str:
        return self._endpoint.uri

    def start(self) -> None:
        for family, address, optional in self._bindings():
            try:
                server = CallbackHttpServer(
                    address, family, self._endpoint, self._state, self._listener
                )
            except OSError as error:
                if optional:
                    continue
                self.stop()
                raise CallbackServerError(
                    BIND_MESSAGE.format(uri=self._endpoint.uri, reason=error.strerror or error)
                ) from None
            self._servers.append(server)
            threading.Thread(
                target=server.serve_forever, name=SERVER_THREAD_NAME, daemon=True
            ).start()

    def stop(self) -> None:
        servers = self._servers
        self._servers = []
        for server in servers:
            closer = threading.Thread(target=_close, args=(server,), daemon=True)
            closer.start()
            _poke(server)
            closer.join(STOP_TIMEOUT_SECONDS)

    def _bindings(self) -> list[tuple[socket.AddressFamily, str, bool]]:
        host = self._endpoint.host
        if host == IPV6_LOOPBACK:
            return [(socket.AF_INET6, IPV6_LOOPBACK, False)]
        bindings = [(socket.AF_INET, IPV4_LOOPBACK, False)]
        if host == LOCALHOST and socket.has_ipv6:
            bindings.append((socket.AF_INET6, IPV6_LOOPBACK, True))
        return bindings


def _close(server: CallbackHttpServer) -> None:
    if server.started.wait(STOP_TIMEOUT_SECONDS):
        server.shutdown()
    server.server_close()


def _poke(server: CallbackHttpServer) -> None:
    address = server.server_address
    try:
        with socket.create_connection((str(address[0]), int(address[1])), POLL_INTERVAL_SECONDS):
            return
    except OSError:
        return
