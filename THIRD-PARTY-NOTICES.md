# Third party notices

ServiceNow Developer Panel is distributed under the MIT License, reproduced in
[LICENSE](LICENSE). That license applies to the code in this repository only.

This document lists the third party components the application depends on, their licenses
and where to obtain their sources. Components are grouped by whether they are distributed
inside the built application or only used to build it.

Versions refer to the releases pinned in [requirements.txt](requirements.txt) and to the
font files committed under `fonts/`.

## Distributed with the application

### Qt and Qt for Python (PySide6, shiboken6)

- Version: 6.12.0
- License: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only
- Copyright: The Qt Company Ltd. and other contributors
- Homepage: https://www.qt.io
- Sources: https://download.qt.io/official_releases/QtForPython/ and https://code.qt.io
- License texts: https://www.gnu.org/licenses/lgpl-3.0.txt and
  https://www.gnu.org/licenses/gpl-3.0.txt

The packages installed from PyPI are the Qt for Python Community Edition. This application
uses them under the terms of the GNU Lesser General Public License version 3, and links
against the Qt libraries dynamically. The Qt modules used are QtCore, QtGui and QtWidgets.

Under LGPL-3.0 a recipient of a built application is entitled to replace the Qt libraries
with their own versions. A build produced in one directory mode keeps the Qt shared
libraries as separate files next to the executable, which is the form that allows this
replacement; a single file build embeds them in the executable instead.

No modifications have been made to Qt or to Qt for Python.

### Lato (font)

- License: SIL Open Font License, Version 1.1
- Copyright: Copyright (c) 2010-2014 by tyPoland Lukasz Dziedzic (team@latofonts.com) with
  Reserved Font Name "Lato"
- Homepage: https://www.latofonts.com
- Source: https://github.com/google/fonts/tree/main/ofl/lato
- License text: [fonts/OFL.txt](fonts/OFL.txt), distributed with the font files

The font files in `fonts/` are the unmodified Google Fonts releases of Lato Regular, Bold,
Italic and Bold Italic. The license text is packaged alongside them in the built
application, as the SIL Open Font License requires.

### Material Design icons

- License: Apache-2.0
- Copyright: Google LLC
- Homepage: https://fonts.google.com/icons
- Source: https://github.com/google/material-design-icons
- License text: https://www.apache.org/licenses/LICENSE-2.0

The home, settings, refresh and delete glyphs drawn in the sidebar and in the response tabs
are the unmodified 24dp outlines of the Material Design icon set, embedded as SVG path data
in `icons.py` and recoloured at runtime to follow the selected theme.

### cryptography

- Version: 50.0.2
- License: Apache-2.0 OR BSD-3-Clause
- Copyright: The Python Cryptographic Authority and individual contributors
- Homepage: https://cryptography.io
- Source: https://github.com/pyca/cryptography
- License texts: https://www.apache.org/licenses/LICENSE-2.0 and
  https://opensource.org/license/bsd-3-clause

Used to encrypt stored authentication details. The binary wheels of this package include a
statically linked copy of OpenSSL (version 4.0.3 in the pinned release), which is licensed
under the Apache License 2.0. OpenSSL is copyright The OpenSSL Project Authors and its
source is available at https://github.com/openssl/openssl.

### PyInstaller bootloader

- Version: 6.22.3
- License: GPL-2.0-or-later, with the exception described below
- Copyright: PyInstaller Development Team
- Homepage: https://pyinstaller.org
- Source: https://github.com/pyinstaller/pyinstaller
- License text: https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt

Executables produced by the build scripts embed the PyInstaller bootloader. PyInstaller is
licensed under the GNU General Public License version 2 or later, with a special exception
that permits using it to build and distribute applications under any license, including
proprietary ones. That exception is what allows this MIT licensed application to be shipped
as a PyInstaller executable.

## Used to build the application only

These are required to produce a build and are not distributed with the application, except
for the bootloader noted above.

- PyInstaller 6.22.3, GPL-2.0-or-later with the bootloader exception, and its dependencies
  altgraph (MIT), packaging (Apache-2.0 OR BSD-2-Clause), pyinstaller-hooks-contrib
  (Apache-2.0 AND GPL-2.0-or-later) and setuptools (MIT).
- cffi and pycparser (both BSD-3-Clause), installed as dependencies of cryptography.

## Reporting an omission

If a component is missing from this file or an attribution is inaccurate, please open an
issue on the project repository.
