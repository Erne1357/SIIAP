#!/usr/bin/env bash
# docker/scripts/rollback.sh [image-tag] [--ignore-schema]
#
# Code-only rollback to an image that is still on the server (the last 5 are
# kept). Default target: .deploy/previous-image.
#
# It does NOT revert the database. If the release being abandoned ran a
# migration, the old image's /ready reports schema=false and this script stops
# — that is on purpose: old code on a new schema is only safe when the
# migration was purely additive. When you know it was, pass --ignore-schema
# and the new color is accepted on /health instead of /ready. To undo a
# migration, restore the dump in backups/ (taken by every deploy).
#
# The git checkout is moved to the target commit too, so the compose file,
# nginx config and scripts match the code that is serving.
set -Eeuo pipefail

LOG_TAG="rollback"
PROJECT_DIR="${SIIAP_DIR:-/home/cuaderno/SIIAP}"
cd "$PROJECT_DIR"
# shellcheck source=docker/scripts/_common.sh
. docker/scripts/_common.sh
acquire_lock

TARGET=""
IGNORE_SCHEMA=0
for arg in "$@"; do
    case "$arg" in
        --ignore-schema) IGNORE_SCHEMA=1 ;;
        -*) die "opción desconocida: $arg" ;;
        *) TARGET=$arg ;;
    esac
done
TARGET=${TARGET:-$(read_state previous-image)}
[ -n "$TARGET" ] || die "no hay imagen previa registrada en $STATE_DIR/previous-image"
docker image inspect "$IMAGE_REPO:$TARGET" >/dev/null 2>&1 \
    || die "la imagen $IMAGE_REPO:$TARGET ya no está en el servidor"

CURRENT_IMAGE=$(read_state current-image)
ACTIVE=$(read_state active-color)
[ -n "$ACTIVE" ] || die "no hay color activo registrado; ¿se hizo ya un deploy blue-green?"
NEW=$(other_color "$ACTIVE")
export IMAGE_TAG="$TARGET"
log "rollback $CURRENT_IMAGE → $TARGET (web-$ACTIVE → web-$NEW)"

TARGET_SHA=$(git rev-parse -q --verify "${TARGET}^{commit}" || true)
[ -n "$TARGET_SHA" ] && git reset --hard --quiet "$TARGET_SHA"
# Re-source: the helpers of the target commit drive the rest.
. docker/scripts/_common.sh

extract_static "$TARGET"
compose --profile "$NEW" up -d --no-deps --force-recreate "web-$NEW"

if [ "$IGNORE_SCHEMA" = 1 ]; then
    ok=0
    for _ in $(seq 1 60); do
        if compose --profile "$NEW" exec -T "web-$NEW" curl -sf http://localhost:5000/health >/dev/null 2>&1; then
            ok=1; break
        fi
        sleep 2
    done
    [ "$ok" = 1 ] || { compose --profile "$NEW" rm -sf "web-$NEW"; die "web-$NEW no responde /health"; }
    PROBE_URL_NOTE="(esquema ignorado)"
else
    if ! wait_healthy "$NEW" 60; then
        compose --profile "$NEW" logs --tail=40 "web-$NEW" || true
        compose --profile "$NEW" rm -sf "web-$NEW"
        die "web-$NEW no está listo. Si la release abandonada migró la base, revisa backups/ o usa --ignore-schema"
    fi
    PROBE_URL_NOTE=""
fi

PREV_UPSTREAM=$(cat "$STATE_DIR/nginx/upstream.conf")
write_upstream "$NEW" "$TARGET"
if ! nginx_apply; then
    printf '%s\n' "$PREV_UPSTREAM" > "$STATE_DIR/nginx/upstream.conf"
    nginx_apply || true
    compose --profile "$NEW" rm -sf "web-$NEW"
    die "nginx -t falló; se restauró el upstream anterior"
fi
if [ "$IGNORE_SCHEMA" = 0 ]; then
    probe_public "$TARGET" 15 || log "AVISO: /ready por nginx no confirmó $TARGET"
fi

write_state active-color "$NEW"
write_state current-image "$TARGET"
[ -n "$TARGET_SHA" ] && write_state current-sha "$TARGET_SHA"
[ -n "$CURRENT_IMAGE" ] && write_state previous-image "$CURRENT_IMAGE"

restart_workers
sleep 10
retire_color "$ACTIVE"
compose --profile "$NEW" ps
log "OK: $TARGET vivo en web-$NEW $PROBE_URL_NOTE"
