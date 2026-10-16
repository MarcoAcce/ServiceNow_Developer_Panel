from pathlib import Path

ROOT = Path(SPECPATH).parent
NAME = "ServiceNowDeveloperPanel"
MCP_NAME = f"{NAME}Mcp"
ICON = str(ROOT / "assets" / "icon.ico")
DATAS = [(str(ROOT / "fonts"), "fonts"), (str(ROOT / "assets"), "assets")]

application = Analysis([str(ROOT / "app.py")], pathex=[str(ROOT)], datas=DATAS)
mcp = Analysis([str(ROOT / "mcp_server.py")], pathex=[str(ROOT)])

application_executable = EXE(
    PYZ(application.pure),
    application.scripts,
    [],
    exclude_binaries=True,
    name=NAME,
    console=False,
    icon=ICON,
)
mcp_executable = EXE(
    PYZ(mcp.pure),
    mcp.scripts,
    [],
    exclude_binaries=True,
    name=MCP_NAME,
    console=True,
    icon=ICON,
)

COLLECT(
    application_executable,
    application.binaries,
    application.datas,
    mcp_executable,
    mcp.binaries,
    mcp.datas,
    name=NAME,
)
