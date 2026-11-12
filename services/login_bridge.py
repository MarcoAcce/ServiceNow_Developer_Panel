import threading
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QGuiApplication

from configuration.config_repository import Authentication
from core.oauth import LoginRequired
from core.request_model import RequestTarget

OFFSCREEN_PLATFORM: str = "offscreen"
LOGIN_WAIT_SECONDS: float = 60.0
LOGIN_PENDING_MESSAGE: str = (
    "the ServiceNow Developer Panel opened the login page of {name} in the browser of the "
    "user and is still waiting for the user to allow the access: ask the user to finish, "
    "then call login_oauth again to keep waiting"
)
LOGIN_CANCELLED_MESSAGE: str = (
    "the user cancelled the login to {name} in the ServiceNow Developer Panel"
)
NO_DISPLAY_MESSAGE: str = (
    "the ServiceNow Developer Panel core runs without a display and cannot open the login: "
    "ask the user to start the ServiceNow Developer Panel and to log in to {name} from "
    "Configuration"
)


@dataclass
class LoginTicket:
    target: RequestTarget
    reason: str
    done: threading.Event = field(default_factory=threading.Event)
    result: Authentication | None = None

    @property
    def authentication_id(self) -> int:
        authentication = self.target.authentication
        return authentication.id if authentication is not None else 0


class LoginBridge(QObject):

    loginRequested = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._lock: threading.Lock = threading.Lock()
        self._pending: LoginTicket | None = None

    def request_login(self, target: RequestTarget, reason: str) -> Authentication | None:
        if not self.has_display():
            raise LoginRequired(NO_DISPLAY_MESSAGE.format(name=target.label))
        ticket = self._ticket(target, reason)
        if not ticket.done.wait(LOGIN_WAIT_SECONDS):
            raise LoginRequired(LOGIN_PENDING_MESSAGE.format(name=target.label))
        if ticket.result is None:
            raise LoginRequired(LOGIN_CANCELLED_MESSAGE.format(name=target.label))
        return ticket.result

    def has_display(self) -> bool:
        return QGuiApplication.platformName() != OFFSCREEN_PLATFORM

    def complete(self, ticket: LoginTicket, result: Authentication | None) -> None:
        with self._lock:
            if self._pending is ticket:
                self._pending = None
        ticket.result = result
        ticket.done.set()

    def _ticket(self, target: RequestTarget, reason: str) -> LoginTicket:
        ticket = LoginTicket(target, reason)
        with self._lock:
            pending = self._pending
            if (
                pending is not None
                and not pending.done.is_set()
                and pending.authentication_id == ticket.authentication_id
            ):
                return pending
            self._pending = ticket
        self.loginRequested.emit(ticket)
        return ticket
