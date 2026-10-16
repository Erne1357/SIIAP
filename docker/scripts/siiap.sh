#!/usr/bin/env bash
# docker/scripts/siiap.sh <command...>
#
# Runs a command inside the LIVE web color. With blue-green there is no fixed
# `siiap-web-1` any more; this replaces `docker exec siiap-web-1 ...`:
#
#   docker/scripts/siiap.sh flask seed-permissions
#   docker/scripts/siiap.sh flask apply-patches --status
#   docker/scripts/siiap.sh flask shell
#   docker/scripts/siiap.sh status        # live color, image, sha
set -euo pipefail
cd "${SIIAP_DIR:-/home/cuaderno/SIIAP}"
# shellcheck source=docker/scripts/_common.sh
. docker/scripts/_common.sh

COLOR=$(read_state active-color)
[ -n "$COLOR" ] || die "no hay color activo registrado en $STATE_DIR/active-color"

if [ "${1:-}" = "status" ]; then
    echo "color:    $COLOR"
    echo "imagen:   $IMAGE_REPO:$(read_state current-image)"
    echo "commit:   $(read_state current-sha)"
    echo "anterior: $IMAGE_REPO:$(read_state previous-image)"
    exit 0
fi

export IMAGE_TAG
IMAGE_TAG=$(read_state current-image)
tty_flag="-T"
[ -t 0 ] && [ -t 1 ] && tty_flag=""
# shellcheck disable=SC2086
exec docker compose -f "$COMPOSE_FILE" --profile "$COLOR" exec $tty_flag "web-$COLOR" "$@"
