#!/bin/sh
set -e

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"

echo "Starting with UID=$PUID GID=$PGID"

# Remove the build-time placeholder so we can recreate with the correct IDs.
# Delete the user first (removes it from /etc/passwd and its primary group
# membership), then delete the group. Both use || true because they will
# produce harmless errors if the user/group never existed or was already
# cleaned up (e.g. a rebuilt image with no placeholder).
userdel appuser 2>/dev/null || true
groupdel appuser 2>/dev/null || true

# Reuse existing group if target GID already exists, otherwise create one.
GROUP_NAME=$(awk -F: -v gid="$PGID" '$3 == gid {print $1; exit}' /etc/group)
if [ -z "$GROUP_NAME" ]; then
    groupadd -g "$PGID" appuser
    GROUP_NAME="appuser"
fi

# Reuse existing user if target UID already exists, otherwise create one.
USER_NAME=$(awk -F: -v uid="$PUID" '$3 == uid {print $1; exit}' /etc/passwd)
if [ -z "$USER_NAME" ]; then
    useradd -M -d /app -s /usr/sbin/nologin -u "$PUID" -g "$GROUP_NAME" appuser
    USER_NAME="appuser"
fi

# Drop privileges and exec the application.
# exec replaces the shell so the app becomes PID 1 and receives SIGTERM directly.
exec gosu "$USER_NAME" "$@"
