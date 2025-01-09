#!/bin/bash
source ../.venv/bin/activate
export QT_API=PyQt6

../.venv/bin/pyinstaller --clean --onefile --strip --optimize 2 --noconfirm --log-level WARN \
                --distpath ../dist \
                --workpath ../build \
                --specpath ../build \
                --hidden-import av \
                --collect-submodules av \
                --hidden-import hashlib \
                --collect-submodules hashlib \
                --hidden-import PIL.ImageQt \
                --hidden-import uuid \
                --collect-data qtmodern \
                --name Qhawana \
	              --windowed \
	              --add-data ../assets/Qhawana_Logo.png:assets \
                ../qhawana/ui.py
