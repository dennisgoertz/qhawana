#!/bin/bash
source ../.venv/bin/activate
export QT_API=PyQt6
export QT_LOGGING_RULES="*.ffmpeg.utils=false"
../.venv/bin/pyinstaller --clean --onefile --strip --optimize 2 --noconfirm --log-level WARN \
                --distpath ../dist \
                --workpath ../build \
                --specpath ../build \
                --name Qhawana \
	              --windowed \
	              --add-data ../assets/Qhawana_Logo.png:assets \
                ../qhawana/ui.py
