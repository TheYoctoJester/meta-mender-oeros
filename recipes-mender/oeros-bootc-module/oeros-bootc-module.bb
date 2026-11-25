SUMMARY = "Mender update module for bootc OS images"
DESCRIPTION = "Update module 'bootc' that stages a bootc OS image delivered in \
the Mender artifact (OCI archive) as a new ostree deployment, arms the grub \
boot counter and rolls back with bootc. Plus an inventory script."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = " \
    file://bootc \
    file://mender-inventory-bootc \
"
S = "${UNPACKDIR}"

inherit allarch

do_install() {
    install -d ${D}${datadir}/mender/modules/v3 ${D}${datadir}/mender/inventory
    install -m 0755 ${S}/bootc ${D}${datadir}/mender/modules/v3/
    install -m 0755 ${S}/mender-inventory-bootc ${D}${datadir}/mender/inventory/
}

FILES:${PN} += "${datadir}/mender"
# grub-editenv: boot counter on the ESP; util-linux-findmnt: ESP mount lookup;
# coreutils: timeout for the health check
RDEPENDS:${PN} = "mender-update bootc ostree jq grub-editenv util-linux-findmnt util-linux-mount coreutils tar systemd"
