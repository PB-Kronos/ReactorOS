#!/bin/sh
set -eu

media=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
workdir=$(mktemp -d "${TMPDIR:-/tmp}/reactoros.XXXXXXXX")
cp "$media/local_server.py" "$media/database_service.py" "$media/workstation_programs.py" "$media/workstation_access.py" "$workdir/"
mkdir "$workdir/rbwr"
cp -r "$media/rbwr/dist" "$workdir/rbwr/"
cd "$workdir"
printf 'ReactorOS files and SQLite data for this session: %s\n' "$workdir"
printf 'Starting the local server at http://127.0.0.1:18765\n'
exec python3 -c '
import signal
from local_server import LocalServer

server = LocalServer()
try:
    signal.pause()
except KeyboardInterrupt:
    pass
finally:
    server.close()
'
