import json
import subprocess
import sys
from typing import Any

PROTOCOL_VERSION: str = "2025-06-18"
SHUTDOWN_TIMEOUT_SECONDS: int = 10
EXPECTED_TOOLS: frozenset[str] = frozenset(
    {
        "list_instances",
        "describe_table",
        "request_table",
        "request_tables",
        "add_tables",
        "query_cache",
        "export_cache",
        "verify_acl",
        "list_cached_responses",
    }
)
LOCAL_TOOLS: tuple[str, ...] = ("list_instances", "list_cached_responses")


class McpClient:

    def __init__(self, executable: str) -> None:
        self._process: subprocess.Popen[str] = subprocess.Popen(
            [executable], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
        )
        self._next_id: int = 0

    def notify(self, method: str) -> None:
        self._send({"jsonrpc": "2.0", "method": method})

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._next_id += 1
        self._send(
            {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params}
        )
        while True:
            line = self._process.stdout.readline() if self._process.stdout else ""
            if not line:
                raise RuntimeError(f"The server closed the connection during {method}")
            message = json.loads(line)
            if message.get("id") != self._next_id:
                continue
            if "error" in message:
                raise RuntimeError(f"{method} failed: {message['error']}")
            return message["result"]

    def close(self) -> None:
        if self._process.stdin:
            self._process.stdin.close()
        try:
            self._process.wait(timeout=SHUTDOWN_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            self._process.kill()

    def _send(self, message: dict[str, Any]) -> None:
        if self._process.stdin is None:
            raise RuntimeError("The server input is closed")
        self._process.stdin.write(json.dumps(message) + "\n")
        self._process.stdin.flush()


def check(client: McpClient) -> None:
    initialized = client.request(
        "initialize",
        {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "smoke-test", "version": "1"},
        },
    )
    print(f"Server {initialized['serverInfo']['name']}")
    client.notify("notifications/initialized")

    tools = {tool["name"] for tool in client.request("tools/list", {})["tools"]}
    missing = EXPECTED_TOOLS - tools
    if missing:
        raise RuntimeError(f"Missing tools: {', '.join(sorted(missing))}")
    print(f"Tools {', '.join(sorted(tools))}")

    for name in LOCAL_TOOLS:
        result = client.request("tools/call", {"name": name, "arguments": {}})
        if result.get("isError"):
            raise RuntimeError(f"{name} failed: {result['content']}")
        print(f"Called {name}")


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Usage: mcp_smoke_test.py MCP_EXECUTABLE")
    client = McpClient(sys.argv[1])
    try:
        check(client)
    except (RuntimeError, ValueError, KeyError) as error:
        sys.exit(str(error))
    finally:
        client.close()


if __name__ == "__main__":
    main()
