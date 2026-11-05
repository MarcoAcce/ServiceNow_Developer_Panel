# Building and installing

These instructions are for the standalone executable: a packaged copy of the application that runs without Python, either installed by the setup or built yourself. 

If you're comfortable with Python you can simply ignore them and run the application. See [Run from source](#run-from-source).

## Windows SmartScreen warning

The Windows setup is not code-signed, because a code-signing certificate is an ongoing cost for a free hobby project. Windows SmartScreen therefore shows a "Windows protected your PC" popup the first time you run it. This is expected for any unsigned executable and it does not mean the file is malicious.

To run the setup anyway:

1. In the popup, click **More info**.
2. Click **Run anyway**.

If your organization blocks unsigned executables, or you simply prefer not to trust a binary, you can [build it yourself](#building-from-source): the result is the same installer.

## Verifying the download

The setups are built by the [GitHub Actions workflow](../.github/workflows/build.yml) from the public source, which also installs, starts and uninstalls the application before the files are produced. The built files are then uploaded to the release by hand. GitHub shows the SHA-256 digest of every release asset next to it on the release page, so you can check your download against it:

- Windows (PowerShell): `Get-FileHash .\ServiceNowDeveloperPanelSetup.exe -Algorithm SHA256`
- Linux: `sha256sum ServiceNowDeveloperPanelSetup-linux-x86_64.tar.gz`

## Installing, updating and uninstalling

The setup opens a small installer window. When the chosen folder already holds an installation, the window offers **Update** and **Uninstall**. Update replaces the application files with the ones of the setup and keeps the data folder (instances, credentials and cache) and the shortcuts unchanged. To change the shortcuts, uninstall keeping the data, then install again. Close the application and the AI clients using its MCP server before updating or uninstalling.

The setup also supports unattended use:

```
ServiceNowDeveloperPanelSetup --silent --desktop
ServiceNowDeveloperPanelSetup --silent --update
ServiceNowDeveloperPanelSetup --silent --uninstall --remove-data
```

`--desktop` adds a desktop shortcut, `--update` updates an existing installation, `--uninstall` removes the application and `--remove-data` also deletes the local database and cache. `--target FOLDER` works on another install folder.

The application installs per user, without administrator rights:

- Windows: `%LOCALAPPDATA%\Programs\ServiceNowDeveloperPanel`
- Linux: `~/.local/opt/ServiceNowDeveloperPanel`

## Run from source

Install Python 3.14 and the packages in `requirements.txt` (for example in a virtual environemnt ass in [Building from source](#building-from-source)), then start the application from the project root:

```
python3 app.py
```

When started this way, the data folder is `data/` in the project root and the MCP server is `mcp_server.py`. In the MCP configuration of your client, the command must be a Python interpreter that has the requirements installed: the one of the virtual environment (`virtual_environment/bin/python`, or `virtual_environment/Scripts/python.exe` on Windows), or the global `python3` if you installed the packages globally. Pass the path of `mcp_server.py` as its argument, as in [`.mcp.json`](../.mcp.json).

## Building from source

Requirements: Python 3.14 and, on Linux, the Qt system libraries (see the workflow for the exact package list). The build tooling is PyInstaller, which is included in `requirements.txt`.

Create a virtual environment named `virtual_environment` in the project root and install the requirements:

```
python -m venv virtual_environment
virtual_environment/bin/python -m pip install -r requirements.txt
```

On Windows the interpreter is `virtual_environment/Scripts/python.exe`.

Then run one of the scripts for your system, from a bash shell (Git Bash on Windows). There are two sets: one builds only the application, the other builds the setup.

| Linux | Windows | Result |
| --- | --- | --- |
| `./build_app_linux.sh` | `./build_app_windows.sh` | The application, in `dist/ServiceNowDeveloperPanel/` |
| `./build_setup_linux.sh` | `./build_setup_windows.sh` | The setup, `dist/ServiceNowDeveloperPanelSetup` (`.exe` on Windows) |

To use another interpreter, set the `PYTHON` environment variable before running the script.

### Application only

The script runs PyInstaller on `packaging/panel.spec`. The resulting folder is portable and needs no setup: start `ServiceNowDeveloperPanel` from it, and the data folder is created next to it. Nothing else is created on your system: for the MCP server, point your client to `ServiceNowDeveloperPanelMcp` in the same folder. To update the application, run the script again: a `data` folder already in `dist/ServiceNowDeveloperPanel/` is kept.

### Setup

The script runs PyInstaller twice: first on `packaging/panel.spec`, which builds the application and the MCP server in `build/payload/`, then on `packaging/installer.spec`, which wraps them into a single self-extracting setup. It does not touch the application built in `dist/ServiceNowDeveloperPanel/`.