SUMMARY = "Podman drop-in forcing Fast DDS to UDPv4 for all containers on the host"
DESCRIPTION = "ROS 2 containers in separate IPC namespaces cannot use Fast DDS shared-memory \
transport; this containers.conf.d drop-in makes every podman container use UDPv4 instead."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://50-fastdds-udp.conf"

S = "${UNPACKDIR}"

inherit allarch

do_install() {
    install -d ${D}${sysconfdir}/containers/containers.conf.d
    install -m 0644 ${UNPACKDIR}/50-fastdds-udp.conf ${D}${sysconfdir}/containers/containers.conf.d/
}

FILES:${PN} = "${sysconfdir}/containers/containers.conf.d/50-fastdds-udp.conf"
RDEPENDS:${PN} = "podman"
