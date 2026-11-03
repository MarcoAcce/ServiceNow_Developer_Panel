import os
import sys
import threading
from multiprocessing.connection import Connection

from core.core_channel import MCP_CLIENT, CoreRejected, CoreUnavailable, open_core

RELAY_THREAD_NAME: str = "core-relay"
FAILURE_EXIT_CODE: int = 1
CORE_CLOSED_MESSAGE: str = "the ServiceNow Developer Panel core closed the connection"


def relay_from_core(connection: Connection, finished: threading.Event) -> None:
    output = sys.stdout.buffer
    try:
        while True:
            output.write(connection.recv_bytes())
            output.flush()
    except (OSError, EOFError):
        if finished.is_set():
            return
        print(CORE_CLOSED_MESSAGE, file=sys.stderr, flush=True)
    os._exit(FAILURE_EXIT_CODE)


def relay_to_core(connection: Connection) -> None:
    try:
        for line in sys.stdin.buffer:
            connection.send_bytes(line)
    except (OSError, EOFError):
        return


def main() -> int:
    try:
        connection = open_core(MCP_CLIENT)
    except (CoreUnavailable, CoreRejected) as error:
        print(error, file=sys.stderr, flush=True)
        return FAILURE_EXIT_CODE
    finished = threading.Event()
    threading.Thread(
        target=relay_from_core,
        args=(connection, finished),
        name=RELAY_THREAD_NAME,
        daemon=True,
    ).start()
    relay_to_core(connection)
    finished.set()
    connection.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
