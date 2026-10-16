# shellcheck shell=bash
# shellcheck disable=SC2034  # settings are read by the scripts that source this file
# docker/scripts/_common.sh — sourced by deploy.sh, rollback.sh and siiap.sh.
#
# Everything a deploy touches on the server lives under $PROJECT_DIR:
#   .deploy/active-color     blue | green (absent before the first blue-green deploy)
#   .deploy/current-image    image tag that is live
#   .deploy/previous-image   image tag that was live before it (rollback target)
#   .deploy/current-sha      full commit SHA that is live
#   .deploy/nginx/           upstream.conf, mounted into nginx
#   .deploy/static/<tag>/    static files extracted from each kept image
#   .deploy/deploy.lock      flock: one deploy or rollback at a time
#   backups/                 pg_dump taken before every migration
# Nothing outside $PROJECT_DIR is written.

PROJECT_DIR="${SIIAP_DIR:-/home/cuaderno/SIIAP}"
COMPOSE_FILE="docker/docker-compose.prod.yml"
STATE_DIR=".deploy"
BACKUP_DIR="backups"
IMAGE_REPO="siiap-app"
PUBLIC_PROBE_URL="http://127.0.0.1:8081/ready"
KEEP_IMAGES=5
KEEP_BACKUPS=10
NGINX_CONF="/etc/nginx/siiap/nginx.conf"

log() { printf '[%s %s] %s\n' "${LOG_TAG:-siiap}" "$(date +%H:%M:%S)" "$*"; }
die() { log "ERROR: $*"; exit 1; }

compose() { docker compose -f "$COMPOSE_FILE" "$@"; }

other_color() { if [ "$1" = "blue" ]; then echo green; else echo blue; fi; }

read_state() { cat "$STATE_DIR/$1" 2>/dev/null || true; }

write_state() { printf '%s\n' "$2" > "$STATE_DIR/$1.tmp" && mv "$STATE_DIR/$1.tmp" "$STATE_DIR/$1"; }

acquire_lock() {
    mkdir -p "$STATE_DIR/nginx" "$STATE_DIR/static" "$BACKUP_DIR"
    # deploy.sh already holds the lock on fd 9 (taken before `git reset`);
    # reopening it here would drop and re-take it.
    { true >&9; } 2>/dev/null || exec 9>"$STATE_DIR/deploy.lock"
    flock -n 9 || die "otro deploy o rollback está en curso ($STATE_DIR/deploy.lock)"
}

container_id() {  # container_id <color>
    compose --profile "$1" ps -q "web-$1" 2>/dev/null || true
}

is_running() {  # is_running <color>
    local cid
    cid=$(container_id "$1")
    [ -n "$cid" ] && [ "$(docker inspect -f '{{.State.Running}}' "$cid" 2>/dev/null)" = "true" ]
}

wait_healthy() {  # wait_healthy <color> <tries>
    local color=$1 tries=${2:-60} cid status=""
    for _ in $(seq 1 "$tries"); do
        cid=$(container_id "$color")
        if [ -n "$cid" ]; then
            status=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid" 2>/dev/null || echo missing)
            [ "$status" = "healthy" ] && return 0
            [ "$status" = "unhealthy" ] && break
        fi
        sleep 2
    done
    log "web-$color no llegó a healthy (último estado: ${status:-sin contenedor})"
    return 1
}

extract_static() {  # extract_static <tag>
    local tag=$1 dest="$STATE_DIR/static/$1" cid
    [ -d "$dest/static" ] && return 0
    rm -rf "$dest.tmp" && mkdir -p "$dest.tmp"
    cid=$(docker create "$IMAGE_REPO:$tag")
    docker cp "$cid:/app/app/static" "$dest.tmp/static" >/dev/null
    docker rm "$cid" >/dev/null
    rm -rf "$dest" && mv "$dest.tmp" "$dest"
}

write_upstream() {  # write_upstream <color> <tag>
    # The nginx runtime dir is a DIRECTORY mount, so replacing the file with
    # mv is safe (a single-file bind mount would keep the old inode).
    cat > "$STATE_DIR/nginx/upstream.conf.tmp" <<EOF
# Generado por docker/scripts/$(basename "$0") — $(date -Iseconds). No editar a mano.
upstream siiap_app {
    server web-$1:5000;
    keepalive 16;
}
map \$host \$static_release {
    default "$2";
}
EOF
    mv "$STATE_DIR/nginx/upstream.conf.tmp" "$STATE_DIR/nginx/upstream.conf"
}

nginx_apply() {
    # `up -d` is a no-op when nothing in the nginx service changed, and
    # recreates it when the compose definition did (first blue-green deploy).
    compose up -d --no-deps nginx >/dev/null
    for _ in $(seq 1 15); do
        compose exec -T nginx nginx -c "$NGINX_CONF" -t >/dev/null 2>&1 && break
        sleep 1
    done
    compose exec -T nginx nginx -c "$NGINX_CONF" -t || return 1
    compose exec -T nginx nginx -c "$NGINX_CONF" -s reload
}

probe_public() {  # probe_public <expected tag> <tries>
    local tag=$1 tries=${2:-15} body=""
    for _ in $(seq 1 "$tries"); do
        body=$(curl -s --max-time 5 -H 'Host: localhost' "$PUBLIC_PROBE_URL" || true)
        if printf '%s' "$body" | grep -Eq '"status": ?"ready"' \
           && printf '%s' "$body" | grep -Eq "\"version\": ?\"$tag\""; then
            return 0
        fi
        sleep 2
    done
    log "nginx no sirve la release $tag: ${body:-sin respuesta}"
    return 1
}

restart_workers() {  # restart_workers (uses exported IMAGE_TAG)
    compose up -d --no-deps --force-recreate celery-worker celery-beat
}

retire_color() {  # retire_color <color>
    local color=$1
    [ -n "$(container_id "$color")" ] || return 0
    compose --profile "$color" stop -t 30 "web-$color" || true
    compose --profile "$color" rm -f "web-$color" || true
}

retire_legacy_web() {
    # The single `web` service of the pre-blue-green compose. Once nginx points
    # at a color it serves nothing; scoped to this compose project by label.
    local ids
    ids=$(docker ps -aq --filter "label=com.docker.compose.project=siiap" \
                        --filter "label=com.docker.compose.service=web")
    [ -n "$ids" ] && printf '%s
' "$ids" | xargs docker rm -f >/dev/null && log "contenedor legado 'web' retirado"
    return 0
}

prune_releases() {
    local current previous keep tag
    current=$(read_state current-image)
    previous=$(read_state previous-image)
    keep=$(docker images "$IMAGE_REPO" --format '{{.CreatedAt}}\t{{.Tag}}' \
             | sort -r | cut -f2 | grep -v '^latest$' | head -n "$KEEP_IMAGES")
    for tag in $(docker images "$IMAGE_REPO" --format '{{.Tag}}'); do
        case " $keep $current $previous " in *" $tag "*) continue ;; esac
        docker rmi "$IMAGE_REPO:$tag" >/dev/null 2>&1 || true
    done
    for dir in "$STATE_DIR"/static/*/; do
        tag=$(basename "$dir")
        case " $keep $current $previous " in *" $tag "*) continue ;; esac
        rm -rf "$dir"
    done
    # Images of the pre-blue-green compose: one per service, all the same build.
    for legacy in siiap-web siiap-celery-worker siiap-celery-beat; do
        docker rmi "$legacy:latest" >/dev/null 2>&1 || true
    done
}
