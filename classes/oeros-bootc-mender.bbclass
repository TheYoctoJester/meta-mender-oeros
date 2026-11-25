# Wrap the bootc OCI archive of an image into a Mender artifact for the
# "bootc" update module (image type bootc-mender).
#
# Provides bootc.os.version and bootc.os.digest under the "bootc" software
# filesystem, so OS updates never touch the provides of app artifacts.

OEROS_BOOTC_OS_VERSION ??= "1"
OEROS_BOOTC_ARTIFACT_NAME ??= "oeros-bootc-os-${OEROS_BOOTC_OS_VERSION}"
OEROS_BOOTC_DEVICE_TYPE ??= "${MENDER_DEVICE_TYPE}"

# bootc status reports this label as the image version
OCI_IMAGE_LABELS:append = " org.opencontainers.image.version=${OEROS_BOOTC_OS_VERSION}"

# mender-setup adds boot and data partition mounts of its A/B layout to every
# image's fstab (mender-setup-image.inc, unconditional). The bootc layout has
# neither; the stale /dev/mmcblk0p* entries drop the system to emergency mode.
ROOTFS_POSTPROCESS_COMMAND:remove = "mender_update_fstab_file"

IMAGE_FSTYPES += "bootc-mender"
IMAGE_TYPEDEP:bootc-mender = "oci"
do_image_bootc_mender[depends] += "mender-artifact-native:do_populate_sysroot"

IMAGE_CMD:bootc-mender() {
    oci_tar=${IMGDEPLOYDIR}/${IMAGE_NAME}${IMAGE_NAME_SUFFIX}-oci.tar
    [ -f "$oci_tar" ] || bbfatal "bootc-mender: $oci_tar not found (OCI_IMAGE_TAR_OUTPUT?)"
    digest=$(tar -xOf "$oci_tar" ./index.json | python3 -c "import json, sys; print(json.load(sys.stdin)['manifests'][0]['digest'])")
    mender-artifact write module-image \
        -T bootc \
        --software-filesystem bootc \
        --software-name os \
        --software-version ${OEROS_BOOTC_OS_VERSION} \
        -p bootc.os.digest:$digest \
        -t ${OEROS_BOOTC_DEVICE_TYPE} \
        -n ${OEROS_BOOTC_ARTIFACT_NAME} \
        --compression none \
        -f "$oci_tar" \
        -o ${IMGDEPLOYDIR}/${IMAGE_NAME}${IMAGE_NAME_SUFFIX}.bootc-mender
}
