from dataclasses import dataclass

from storage.request_hints import RequestHintRepository
from storage.response_repository import ResponseRepository
from services.service import RequestService


@dataclass(frozen=True)
class ResponseContext:
    service: RequestService
    responses: ResponseRepository
    hints: RequestHintRepository
