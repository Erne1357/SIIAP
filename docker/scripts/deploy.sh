#!/usr/bin/env bash
# docker/scripts/deploy.sh <commit-sha>
#
# Blue-green deploy of SIIAP. Run by .github/workflows/deploy.yml over SSH,
# always from the copy of this file inside the commit being deployed
# (`git show <sha>:docker/scripts/deploy.sh`), so a change to the script ships
# in the same deploy that introduces it.
#
#  1. resolve the target  — refuse SHAs not on origin/main; no-op on a SHA
#                           older than what is live (a stale CI run).
#  2. git reset --hard     — checkout = release being deployed.
#  3. build                — one immutable image, siiap-app:<short sha>.
#  4. static release       — /app/app/static of that image → .deploy/static/<tag>.
#  5. backup               — pg_dump into backups/ (abort if it fails).
#  6. migrate              — `flask db upgrade` in a throwaway container of the
#                            NEW image, before any traffic moves. Migrations
#                            must be expand/contract: the old color keeps
#                            serving against the new schema for ~1 minute.
#  7. start new color      — wait until its /ready (DB + Redis + schema) is green.
#  8. switch               — rewrite upstream.conf, `nginx -t`, `nginx -s reload`.
#                            No nginx restart, no dropped connections.
#  9. verify via nginx     — /ready through 127.0.0.1:8081 must report the new tag;
#                            otherwise switch back and abort.
# 10. workers              — celery worker/beat recreated on the new image.
# 11. retire old color     — graceful stop after a short drain.
# 12. prune                — keep the last 5 images and their static releases.
set -Eeuo pipefail

TARGET_SHA="${1:-}"
LOG_TAG="deploy"
PROJECT_DIR="${SIIAP_DIR:-/home/cuaderno/SIIAP}"
cd "$PROJECT_DIR"

# One deploy or rollback at a time, taken BEFORE touching the checkout.
mkdir -p .deploy
exec 9>.deploy/deploy.lock
flock -n 9 || { echo "[deploy] ERROR: otro deploy o rollback está en curso."; exit 1; }

# >>> resolve_deploy_target
# resolve_deploy_target <sha> <live-sha>  → prints the full SHA to deploy.
#   exit 1  the SHA does not exist or is not on origin/main
#   exit 3  the SHA is strictly older than what is live (nothing to do)
resolve_deploy_target() {
    local target=$1 live=${2:-} full
    [ -n "$target" ] || target=origin/main
    full=$(git rev-parse -q --verify "${target}^{commit}") || return 1
    git merge-base --is-ancestor "$full" origin/main || return 1
    if [ -n "$live" ] && [ "$live" != "$full" ] \
       && git cat-file -e "${live}^{commit}" 2>/dev/null \
       && git merge-base --is-ancestor "$full" "$live"; then
        return 3
    fi
    printf '%s\n' "$full"
}
# <<< resolve_deploy_target

git fetch --quiet origin
set +e
DEPLOY_SHA=$(resolve_deploy_target "$TARGET_SHA" "$(cat .deploy/current-sha 2>/dev/null || true)")
rc=$?
set -e
case $rc in
    0) ;;
    3) echo "[deploy] $TARGET_SHA es anterior a lo que ya está en producción. Nada que desplegar."; exit 0 ;;
    *) echo "[deploy] ERROR: $TARGET_SHA no existe o no está en origin/main."; exit 1 ;;
esac

git reset --hard --quiet "$DEPLOY_SHA"
# From here on the checkout is the release, helpers included.
# shellcheck source=docker/scripts/_common.sh
. docker/scripts/_common.sh
acquire_lock

TAG=$(git rev-parse --short=12 HEAD)
export IMAGE_TAG="$TAG"
ACTIVE=$(read_state active-color)
if [ -n "$ACTIVE" ] && ! is_running "$ACTIVE"; then
    log "el color registrado ($ACTIVE) no está corriendo"
    ACTIVE=""
fi
NEW=$(other_color "${ACTIVE:-green}")
log "release $TAG — vivo: ${ACTIVE:-ninguno (primer blue-green)} → nuevo: $NEW"

cleanup_new() {
    log "retirando web-$NEW fallido; producción sigue en ${ACTIVE:-la configuración anterior}"
    compose --profile "$NEW" logs --tail=60 "web-$NEW" || true
    compose --profile "$NEW" rm -sf "web-$NEW" >/dev/null 2>&1 || true
    # Put the checkout back on the release that is serving: nginx re-reads
    # docker/nginx/ from it on the next reload, and rollback.sh/siiap.sh source
    # their helpers from it.
    local live_sha
    live_sha=$(read_state current-sha)
    if [ -n "$live_sha" ] && git cat-file -e "${live_sha}^{commit}" 2>/dev/null; then
        git reset --hard --quiet "$live_sha"
    fi
}
SWITCHED=0
trap 'rc=$?; if [ "$SWITCHED" = 0 ]; then cleanup_new; fi; log "falló: $BASH_COMMAND (código $rc)"' ERR

log "[1/9] infraestructura"
compose up -d --no-recreate db redis
# Single quotes on purpose: $POSTGRES_* expand inside the db container.
# shellcheck disable=SC2016
for _ in $(seq 1 30); do
    compose exec -T db sh -c 'pg_isready -q -U "$POSTGRES_USER" -d "$POSTGRES_DB"' && \
    compose exec -T redis redis-cli ping >/dev/null && break
    sleep 2
done

log "[2/9] imagen $IMAGE_REPO:$TAG"
if docker image inspect "$IMAGE_REPO:$TAG" >/dev/null 2>&1; then
    log "la imagen ya existe; no se reconstruye"
else
    compose --profile "$NEW" build "web-$NEW"
fi

log "[3/9] estáticos de la release"
extract_static "$TAG"

log "[4/9] respaldo previo a migrar"
BACKUP="$BACKUP_DIR/predeploy_$(date +%Y%m%d_%H%M%S)_$TAG.dump"
# shellcheck disable=SC2016
if ! compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$BACKUP.tmp" \
   || [ ! -s "$BACKUP.tmp" ]; then
    rm -f "$BACKUP.tmp"
    die "pg_dump falló; no se migra sin respaldo"
fi
mv "$BACKUP.tmp" "$BACKUP"
# shellcheck disable=SC2012  # names are ours: predeploy_<date>_<tag>.dump
ls -1t "$BACKUP_DIR"/predeploy_*.dump 2>/dev/null | tail -n +$((KEEP_BACKUPS + 1)) | xargs -r rm -f
log "respaldo: $BACKUP ($(du -h "$BACKUP" | cut -f1))"

log "[5/9] migraciones (imagen nueva, contenedor desechable)"
compose --profile "$NEW" run --rm --no-deps -T "web-$NEW" flask db upgrade

log "[6/9] arrancando web-$NEW"
compose --profile "$NEW" up -d --no-deps --force-recreate "web-$NEW"
if ! wait_healthy "$NEW" 60; then
    cleanup_new
    die "web-$NEW no está listo"
fi

log "[7/9] cambiando nginx a web-$NEW"
PREV_UPSTREAM=""
[ -f "$STATE_DIR/nginx/upstream.conf" ] && PREV_UPSTREAM=$(cat "$STATE_DIR/nginx/upstream.conf")
write_upstream "$NEW" "$TAG"
if ! nginx_apply || ! probe_public "$TAG" 15; then
    if [ -n "$PREV_UPSTREAM" ] && [ -n "$ACTIVE" ]; then
        printf '%s\n' "$PREV_UPSTREAM" > "$STATE_DIR/nginx/upstream.conf"
        nginx_apply || true
    fi
    cleanup_new
    die "nginx no quedó sirviendo $TAG; se restauró el upstream anterior"
fi

SWITCHED=1
PREV_IMAGE=$(read_state current-image)
write_state active-color "$NEW"
write_state current-sha "$DEPLOY_SHA"
write_state current-image "$TAG"
[ -n "$PREV_IMAGE" ] && [ "$PREV_IMAGE" != "$TAG" ] && write_state previous-image "$PREV_IMAGE"

log "[8/9] celery en la imagen nueva"
restart_workers

log "[9/9] retirando el color anterior"
sleep 10
[ -n "$ACTIVE" ] && retire_color "$ACTIVE"
retire_legacy_web
prune_releases

compose --profile "$NEW" ps
log "OK: $TAG vivo en web-$NEW"
