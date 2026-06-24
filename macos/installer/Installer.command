#!/bin/bash
# Togpuls Installer — fullfører installasjonen ved å fjerne macOS sin
# quarantine-merking på Togpuls.app og starte appen. Kjøres etter at
# Togpuls er dratt til Applications.

set -uo pipefail

APP_NAME="Togpuls.app"
CANDIDATES=("/Applications/$APP_NAME" "$HOME/Applications/$APP_NAME")

printf '\n  \033[1mTogpuls — fullfør installasjon\033[0m\n\n'

APP_PATH=""
for c in "${CANDIDATES[@]}"; do
    if [ -d "$c" ]; then
        APP_PATH="$c"
        break
    fi
done

if [ -z "$APP_PATH" ]; then
    cat <<'EOF'
  ✗ Fant ikke Togpuls.app i Applications.

    Dra først Togpuls til Applications-mappen i dette DMG-vinduet,
    og dobbeltklikk på Installer.command på nytt.

EOF
    read -n 1 -s -r -p "  Trykk en tast for å lukke …"
    echo
    exit 1
fi

echo "  Fant: $APP_PATH"
echo

echo "  → Fjerner quarantine-flagget …"
if xattr -dr com.apple.quarantine "$APP_PATH" 2>/dev/null; then
    echo "    OK"
else
    echo "    Ingen quarantine å fjerne (det er greit)"
fi

echo
echo "  → Starter Togpuls …"
open "$APP_PATH"

echo
echo "  Ferdig. Togpuls ligger nå i menylinjen øverst til høyre."
echo "  Du kan trygt lukke DMG-vinduet og kaste DMG-fila."
echo
read -n 1 -s -r -p "  Trykk en tast for å lukke dette vinduet …"
echo
