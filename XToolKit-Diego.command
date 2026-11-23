#!/bin/sh
# Peluncur Finder/Terminal macOS untuk XToolKit-Diego.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec /bin/sh ./run-macos.sh "$@"
