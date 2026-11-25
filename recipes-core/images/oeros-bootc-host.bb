SUMMARY = "oeros bootc host with the Mender client"
DESCRIPTION = "Bootable container OS (meta-bootc) for running oeros ROS 2 \
containers with podman and Quadlet. Mender provides deployments, fleet \
management and remote access: the 'bootc' update module installs new OS \
images (OCI archive in the artifact), the 'oeros-quadlet' module installs \
apps without a reboot. No ROS in the OS; ROS lives in the app containers."
LICENSE = "MIT"

inherit core-image oeros-bootc-disk oeros-bootc-mender image-buildinfo

# Record the layer revisions (and uncommitted changes) the image was built
# from. /etc belongs to the device in the bootc model, so keep it in /usr.
IMAGE_BUILDINFO_FILE = "${nonarch_libdir}/oeros/buildinfo"
IMAGE_BUILDINFO_VARS = "DISTRO DISTRO_VERSION MACHINE OEROS_BOOTC_OS_VERSION"
# image-buildinfo reads the revisions at execution time only; make them part
# of a task signature so a layer change never leaves a stale record.
# - Signatures hash the unexpanded text of ${@...}, so the value is set as a
#   literal string at parse time.
# - A small carrier task before do_rootfs holds it. Putting it on do_image
#   directly (a fakeroot task) made bitbake abort with "basehash changed".
python __anonymous() {
    revs = ' '.join('%s:%s%s' % (r[1], r[3], r[4].replace(' -- ', '+'))
                    for r in oe.buildcfg.get_layer_revisions(d))
    d.setVar('OEROS_LAYER_REVISIONS', revs)
}
python do_oeros_layer_revisions() {
    bb.note("layer revisions: %s" % d.getVar("OEROS_LAYER_REVISIONS"))
}
do_oeros_layer_revisions[vardeps] += "OEROS_LAYER_REVISIONS"
addtask oeros_layer_revisions before do_rootfs
# A commit or a working tree change in a layer does not touch this recipe's
# files, so the parse cache would keep the old revisions: always reparse.
BB_DONT_CACHE = "1"

IMAGE_FEATURES += "ssh-server-openssh"

IMAGE_INSTALL = "\
    packagegroup-core-boot \
    kernel-image \
    kernel-modules \
    bootc \
    bootc-growfs \
    ostree \
    podman \
    e2fsprogs-e2fsck \
    dosfstools \
    mender-update \
    mender-auth \
    mender-connect \
    oeros-bootc-module \
    oeros-quadlet-module \
    oeros-demo-dds-config \
    oeros-podman-no-user-restart \
    ${CORE_IMAGE_EXTRA_INSTALL} \
"

IMAGE_ROOTFS_EXTRA_SPACE = "524288"

BOOTC_OSNAME = "oeros"
# Updates arrive through Mender as OCI archives; the bootc update module
# switches to each one with --transport oci-archive. The initial origin
# points at the same path.
BOOTC_IMAGE_REFERENCE = "ostree-unverified-image:oci-archive:/var/lib/oeros-bootc/staging.oci.tar"

# OS release marker, so consecutive builds differ in content
OEROS_BOOTC_OS_VERSION ??= "1"
# "1": deliberately unbootable variant (init exits, kernel panics) for
# testing the grub boot counter fallback
OEROS_BOOTC_BROKEN ??= "0"

ROOTFS_POSTPROCESS_COMMAND += "oeros_bootc_os_version;"
oeros_bootc_os_version() {
    install -d ${IMAGE_ROOTFS}${nonarch_libdir}/oeros
    echo "${OEROS_BOOTC_OS_VERSION}" > ${IMAGE_ROOTFS}${nonarch_libdir}/oeros/os-version
    if [ "${OEROS_BOOTC_BROKEN}" = "1" ]; then
        bbwarn "building a deliberately unbootable image (OEROS_BOOTC_BROKEN=1)"
        rm -f ${IMAGE_ROOTFS}${nonarch_libdir}/systemd/systemd
        printf '#!/bin/sh\necho "oeros: deliberately broken init" >&2\nexit 1\n' \
            > ${IMAGE_ROOTFS}${nonarch_libdir}/systemd/systemd
        chmod 0755 ${IMAGE_ROOTFS}${nonarch_libdir}/systemd/systemd
    fi
}
oeros_bootc_os_version[vardeps] += "OEROS_BOOTC_OS_VERSION OEROS_BOOTC_BROKEN"
