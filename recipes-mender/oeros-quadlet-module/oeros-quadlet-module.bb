SUMMARY = "Mender update module for podman/Quadlet apps"
DESCRIPTION = "Update module 'oeros-quadlet' that installs an app (OCI archive, \
Quadlet unit, optional health check) into podman without a reboot, with \
rollback to the previous release. Plus an inventory script and a health check \
over all apps for the bootc OS update module."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = " \
    file://quadlet-lib.sh \
    file://oeros-quadlet \
    file://oeros-quadlet-healthcheck-all \
    file://mender-inventory-oeros-quadlet \
"
S = "${UNPACKDIR}"

inherit allarch

do_install() {
    install -d ${D}${nonarch_libdir}/oeros ${D}${datadir}/mender/modules/v3 \
        ${D}${datadir}/mender/inventory ${D}${libexecdir}
    install -m 0644 ${S}/quadlet-lib.sh ${D}${nonarch_libdir}/oeros/
    install -m 0755 ${S}/oeros-quadlet ${D}${datadir}/mender/modules/v3/
    install -m 0755 ${S}/mender-inventory-oeros-quadlet ${D}${datadir}/mender/inventory/
    install -m 0755 ${S}/oeros-quadlet-healthcheck-all ${D}${libexecdir}/
}

FILES:${PN} += "${nonarch_libdir}/oeros ${datadir}/mender ${libexecdir}"
# coreutils: timeout with process-group kill for health checks
RDEPENDS:${PN} = "mender-update podman coreutils systemd"
