from dataclasses import dataclass

from request_hints import RequestHintRepository
from response_repository import ResponseRepository
from service import RequestService


@dataclass(frozen=True)
class ResponseContext:
    service: RequestService
    responses: ResponseRepository
    hints: RequestHintRepository
