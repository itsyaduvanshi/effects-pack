#!/usr/bin/env bash
# One-time setup: Python env, face/person models and fonts.
# Prints READY, NEED_FFMPEG or NEED_PYTHON on the last line.
set -euo pipefail
cd "$(dirname "$0")/.."

command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null || { echo NEED_FFMPEG; exit 0; }

if [ ! -x .venv/bin/python ] && [ ! -x .venv/Scripts/python.exe ]; then
  if command -v uv >/dev/null; then
    uv venv --python 3.12 .venv >/dev/null
  else
    PY=""
    for c in python3.12 python3.11 python3.10 python3; do
      if command -v "$c" >/dev/null && "$c" -c 'import sys; sys.exit(0 if (3,9) <= sys.version_info[:2] <= (3,12) else 1)'; then PY="$c"; break; fi
    done
    [ -n "$PY" ] || { echo NEED_PYTHON; exit 0; }
    "$PY" -m venv .venv
  fi
fi
PYBIN=.venv/bin/python; [ -x "$PYBIN" ] || PYBIN=.venv/Scripts/python.exe

if command -v uv >/dev/null; then
  uv pip install --python "$PYBIN" -q -r requirements.txt
else
  "$PYBIN" -m pip install -q --upgrade pip
  "$PYBIN" -m pip install -q -r requirements.txt
fi

fetch() {  # url dest
  [ -s "$2" ] && return 0
  mkdir -p "$(dirname "$2")"
  curl -fsSL "$1" -o "$2.part" && mv "$2.part" "$2"
}

fetch https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx models/yunet.onnx
fetch https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite models/selfie_segmenter.tflite

G=https://raw.githubusercontent.com/google/fonts/main
fetch "$G/ofl/archivoblack/ArchivoBlack-Regular.ttf"          fonts/ArchivoBlack-Regular.ttf
fetch "$G/ofl/instrumentserif/InstrumentSerif-Regular.ttf"    fonts/InstrumentSerif-Regular.ttf
fetch "$G/ofl/instrumentserif/InstrumentSerif-Italic.ttf"     fonts/InstrumentSerif-Italic.ttf
fetch "$G/ofl/spacemono/SpaceMono-Bold.ttf"                   fonts/SpaceMono-Bold.ttf
fetch "$G/ofl/spacemono/SpaceMono-Regular.ttf"                fonts/SpaceMono-Regular.ttf
fetch "$G/ofl/inter/Inter%5Bopsz,wght%5D.ttf"                 fonts/Inter.ttf
fetch "$G/ofl/anton/Anton-Regular.ttf"                        fonts/Anton-Regular.ttf
fetch "$G/apache/permanentmarker/PermanentMarker-Regular.ttf" fonts/PermanentMarker-Regular.ttf
fetch "$G/ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf"  fonts/PlayfairDisplay.ttf
fetch "$G/ofl/playfairdisplay/PlayfairDisplay-Italic%5Bwght%5D.ttf" fonts/PlayfairDisplay-Italic.ttf
for f in archivoblack instrumentserif spacemono inter anton playfairdisplay; do
  fetch "$G/ofl/$f/OFL.txt" "fonts/licenses/OFL-$f.txt"
done
fetch "$G/apache/permanentmarker/LICENSE.txt" fonts/licenses/LICENSE-permanentmarker.txt

"$PYBIN" -c 'import cv2, mediapipe, PIL, numpy' && echo READY
