from multiprocessing.connection import Connection

import anyio
import anyio.to_thread
from mcp.server import MCPServer
from mcp.server.stdio import stdio_server

TEXT_ENCODING: str = "utf-8"


class ConnectionStream:

    def __init__(self, connection: Connection) -> None:
        self._connection: Connection = connection

    def __aiter__(self) -> "ConnectionStream":
        return self

    async def __anext__(self) -> str:
        try:
            data = await anyio.to_thread.run_sync(self._connection.recv_bytes)
        except (OSError, EOFError):
            raise StopAsyncIteration from None
        return data.decode(TEXT_ENCODING, errors="replace")

    async def write(self, text: str) -> None:
        await anyio.to_thread.run_sync(self._connection.send_bytes, text.encode(TEXT_ENCODING))

    async def flush(self) -> None:
        return None


def serve_connection(server: MCPServer, connection: Connection) -> None:
    anyio.run(_serve, server, ConnectionStream(connection))


async def _serve(server: MCPServer, stream: ConnectionStream) -> None:
    lowlevel = server._lowlevel_server
    async with stdio_server(stream, stream) as (read_stream, write_stream):
        await lowlevel.run(read_stream, write_stream, lowlevel.create_initialization_options())
