from pathlib import Path

ROOT = Path(SPECPATH).parent
NAME = "ServiceNowDeveloperPanelSetup"
PAYLOAD = ROOT / "build" / "payload" / "ServiceNowDeveloperPanel"
ICON = str(ROOT / "assets" / "icon.ico")

if not PAYLOAD.is_dir():
    raise SystemExit(f"Build packaging/panel.spec into build/payload first, {PAYLOAD} is missing")
if (PAYLOAD / "data").exists():
    raise SystemExit(f"{PAYLOAD / 'data'} must not be packaged, rebuild the payload")

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
