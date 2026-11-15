#!/bin/zsh
# Doppelklick im Finder: oeffnet das Terminal und laedt die MODIS-Daten.
cd "$(dirname "$0")"

# Anaconda-Python suchen (ein Doppelklick-Skript laedt die .zshrc nicht automatisch)
PY=""
for c in /opt/anaconda3/bin/python "$HOME/anaconda3/bin/python" "$HOME/opt/anaconda3/bin/python" \
         /opt/miniconda3/bin/python "$HOME/miniconda3/bin/python" /opt/homebrew/bin/python3 /usr/local/bin/python3; do
  if [ -x "$c" ]; then PY="$c"; break; fi
done
[ -z "$PY" ] && PY="$(command -v python3)"
echo "Verwende Python: $PY"

"$PY" -m pip install --quiet --upgrade earthaccess || { echo "pip install fehlgeschlagen"; read -k1 "?Taste druecken zum Schliessen"; exit 1; }
"$PY" earth/download_modis.py

echo
read -k1 "?Fertig. Taste druecken zum Schliessen."
