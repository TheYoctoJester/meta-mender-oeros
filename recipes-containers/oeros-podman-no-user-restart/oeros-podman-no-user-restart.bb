SUMMARY = "Mask podman's podman-restart.service user unit"
DESCRIPTION = "podman enables podman-restart.service for all user managers. For root \
the user-session podman shares the system container storage, so when the last \
root session (ssh, Mender Connect terminal) ends and user@0 stops, its ExecStop \
'podman stop --all' also stops system containers run by Quadlet units. \
This host does not use rootless podman; mask the user unit globally."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

inherit allarch

do_install() {
    install -d ${D}${sysconfdir}/systemd/user
    ln -sf /dev/null ${D}${sysconfdir}/systemd/user/podman-restart.service
}

FILES:${PN} = "${sysconfdir}/systemd/user/podman-restart.service"
