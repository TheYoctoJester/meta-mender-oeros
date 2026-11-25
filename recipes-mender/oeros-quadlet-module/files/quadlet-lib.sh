# Shared functions for the oeros-quadlet update module, its inventory script
# and the bootc module's health check.

# All app state lives in /var (shared by every OS deployment). The active
# unit is placed in /run, never in /etc: /etc is per deployment, so an OS
# rollback would bring back the unit of an older release.
OEROS_APPS_DIR=/var/lib/oeros-apps
OEROS_QUADLET_DIR=/run/containers/systemd
# units of earlier versions of this module, removed on sight
OEROS_LEGACY_QUADLET_DIR=/etc/containers/systemd
OEROS_HEALTH_DEADLINE=300

oeros_log() {
    echo "oeros-quadlet: $*" >&2
}

# Field from a release's app.env: oeros_field <app> <current|new> <FIELD>
oeros_field() {
    f="$OEROS_APPS_DIR/$1/$2/app.env"
    [ -r "$f" ] || return 0
    (APP= VERSION= IMAGE= UNIT=; . "$f"; eval echo "\${$3}")
}

oeros_service() {
    u=$(oeros_field "$1" "$2" UNIT)
    echo "${u%.container}.service"
}

# Import an OCI archive into podman storage as <ref>. Pulling from an OCI
# archive also names the image after its ref annotation; drop names outside
# the app's repository (tags of other versions of the app stay).
oeros_import_image() {
    tar=$1
    ref=$2
    id=$(podman pull -q "oci-archive:$tar") || return 1
    podman tag "$id" "$ref" || return 1
    for n in $(podman image inspect --format '{{range .RepoTags}}{{.}} {{end}}' "$id"); do
        case "$n" in
            "${ref%:*}":*) ;;
            *) podman untag "$id" "$n" ;;
        esac
    done
}

# Place the release's unit for the Quadlet generator (no reload).
oeros_place_unit() {
    app=$1
    rel=$2
    unit=$(oeros_field "$app" "$rel" UNIT)
    [ -n "$unit" ] || return 1
    install -d "$OEROS_QUADLET_DIR"
    install -m 0644 "$OEROS_APPS_DIR/$app/$rel/$unit" "$OEROS_QUADLET_DIR/$unit" || return 1
    if [ -e "$OEROS_LEGACY_QUADLET_DIR/$unit" ]; then
        oeros_log "$app: removing legacy unit $OEROS_LEGACY_QUADLET_DIR/$unit"
        rm -f "$OEROS_LEGACY_QUADLET_DIR/$unit"
    fi
}

# Install the release's unit (and nothing else) and (re)start it.
oeros_activate() {
    oeros_place_unit "$1" "$2" || return 1
    systemctl daemon-reload || return 1
    systemctl restart "$(oeros_service "$1" "$2")"
}

oeros_deactivate() {
    app=$1
    rel=$2
    unit=$(oeros_field "$app" "$rel" UNIT)
    systemctl stop "$(oeros_service "$app" "$rel")" 2>/dev/null
    rm -f "$OEROS_QUADLET_DIR/$unit" "$OEROS_LEGACY_QUADLET_DIR/$unit"
    systemctl daemon-reload
}

oeros_app_healthcheck() {
    hc="$OEROS_APPS_DIR/$1/$2/healthcheck"
    if [ ! -x "$hc" ]; then
        systemctl is-active -q "$(oeros_service "$1" "$2")"
        return
    fi
    oeros_log "$1: running health check (deadline $OEROS_HEALTH_DEADLINE s)"
    timeout -k 10 "$OEROS_HEALTH_DEADLINE" "$hc"
}

# Remove tags of the app's image repository not used by the current or the
# pending release.
oeros_prune_images() {
    app=$1
    keep=""
    for rel in current new; do
        keep="$keep $(oeros_field "$app" "$rel" IMAGE)"
    done
    for ref in $keep; do
        repo=${ref%:*}
        for old in $(podman images --format '{{.Repository}}:{{.Tag}}' | grep "^$repo:"); do
            case " $keep " in
                *" $old "*) continue ;;
            esac
            oeros_log "$app: removing unused image $old"
            podman rmi "$old" >/dev/null 2>&1 || oeros_log "$app: could not remove $old"
        done
    done
    podman image prune -f >/dev/null 2>&1 || true
}
