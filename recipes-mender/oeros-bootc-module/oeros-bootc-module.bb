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

# Units that must be active after an OS update before it is committed. Other
# failed units are reported in the inventory only. A device can replace the
# list with /etc/oeros/health-units.
OEROS_HEALTH_UNITS ?= "systemd-networkd.service mender-authd.service mender-updated.service mender-connect.service"

do_install() {
    install -d ${D}${datadir}/mender/modules/v3 ${D}${datadir}/mender/inventory
    install -m 0755 ${S}/bootc ${D}${datadir}/mender/modules/v3/
    install -m 0755 ${S}/mender-inventory-bootc ${D}${datadir}/mender/inventory/
    install -d ${D}${nonarch_libdir}/oeros
    printf '# Units required after an OS update (OEROS_HEALTH_UNITS)\n' > ${D}${nonarch_libdir}/oeros/health-units
    for u in ${OEROS_HEALTH_UNITS}; do
        echo "$u" >> ${D}${nonarch_libdir}/oeros/health-units
    done
}

FILES:${PN} += "${datadir}/mender ${nonarch_libdir}/oeros/health-units"
# grub-editenv: boot counter on the ESP; util-linux-findmnt: ESP mount lookup;
# coreutils: timeout for the health check
RDEPENDS:${PN} = "mender-update bootc ostree jq grub-editenv util-linux-findmnt util-linux-mount coreutils tar systemd"
