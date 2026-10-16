from pathlib import Path

ROOT = Path(SPECPATH).parent
NAME = "ServiceNowDeveloperPanelSetup"
PAYLOAD = ROOT / "dist" / "ServiceNowDeveloperPanel"
ICON = str(ROOT / "assets" / "icon.ico")

if not PAYLOAD.is_dir():
    raise SystemExit(f"Build packaging/panel.spec first, {PAYLOAD} is missing")

installer = Analysis(
    [str(ROOT / "install.py")],
    pathex=[str(ROOT)],
    datas=[
        (str(ROOT / "fonts"), "fonts"),
        (str(ROOT / "assets"), "assets"),
        (str(PAYLOAD), "payload"),
    ],
)

EXE(
    PYZ(installer.pure),
    installer.scripts,
    installer.binaries,
    installer.datas,
    [],
    name=NAME,
    console=False,
    icon=ICON,
)
