# Building and installing

## Windows SmartScreen warning

The Windows setup is not code-signed, because a code-signing certificate is an ongoing cost for a free hobby project. Windows SmartScreen therefore shows a "Windows protected your PC" popup the first time you run it. This is expected for any unsigned executable that is not yet widely downloaded, and it does not mean the file is malicious.

To run the setup anyway:

1. In the popup, click **More info**.
2. Click **Run anyway**.

If your organization blocks unsigned executables, or you simply prefer not to trust a binary, [build it yourself](#building-from-source): the result is the same installer.

## Verifying the download

The setups are built by the [GitHub Actions workflow](../.github/workflows/build.yml) from the public source, which also installs, starts and uninstalls the application before the files are produced. The built files are then uploaded to the release by hand. GitHub shows the SHA-256 digest of every release asset next to it on the release page, so you can check your download against it:

- Windows (PowerShell): `Get-FileHash .\ServiceNowDeveloperPanelSetup.exe -Algorithm SHA256`
- Linux: `sha256sum ServiceNowDeveloperPanelSetup-linux-x86_64.tar.gz`

## Building from source

Requirements: Python 3.14 and, on Linux, the Qt system libraries (see the workflow for the exact package list). The build tooling is PyInstaller, which is included in `requirements.txt`.

Create a virtual environment named `virtual_environment` in the project root and install the requirements:

```
python -m venv virtual_environment
virtual_environment/bin/python -m pip install -r requirements.txt
```

On Windows the interpreter is `virtual_environment/Scripts/python.exe`.

Then run the script for your system, from a bash shell (Git Bash on Windows):

```
./build_linux.sh
./build_windows.sh
```

Each script runs PyInstaller twice: first on `packaging/panel.spec` to build the application and the MCP server, then on `packaging/installer.spec` to wrap them into a single self-extracting setup. The result is in `dist/`:

- Linux: `dist/ServiceNowDeveloperPanelSetup`
- Windows: `dist/ServiceNowDeveloperPanelSetup.exe`

To use another interpreter, set the `PYTHON` environment variable before running the script.

## Installing and uninstalling

The setup opens a small installer window. It also supports unattended use:

```
ServiceNowDeveloperPanelSetup --silent --desktop
ServiceNowDeveloperPanelSetup --silent --uninstall --remove-data
```

`--desktop` adds a desktop shortcut, `--uninstall` removes the application and `--remove-data` also deletes the local database and cache.

The application installs per user, without administrator rights:

- Windows: `%LOCALAPPDATA%\Programs\ServiceNowDeveloperPanel`
- Linux: `~/.local/opt/ServiceNowDeveloperPanel`
