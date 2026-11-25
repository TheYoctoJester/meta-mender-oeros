SUMMARY = "Mender artifact for the oeros ros-core app (oeros-quadlet update module)"
DESCRIPTION = "Deploys a Mender artifact of type oeros-quadlet carrying the OCI \
archive of oeros-container-ros-core, a Quadlet unit running a /chatter \
publisher and a health check. Nothing is installed into any image."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = " \
    file://oeros-ros-core.container.in \
    file://healthcheck.in \
"
S = "${UNPACKDIR}"

inherit deploy nopackages

OEROS_APP_NAME = "ros-core"
OEROS_APP_VERSION ??= "1"
OEROS_APP_MESSAGE ??= "hello from oeros app ${OEROS_APP_VERSION}"
# "1": deliberately broken app (publishes on the wrong topic, so the health
# check fails) for rollback tests
OEROS_APP_BROKEN ??= "0"
OEROS_APP_TOPIC = "${@'/chatter_typo' if d.getVar('OEROS_APP_BROKEN') == '1' else '/chatter'}"
OEROS_APP_IMAGE = "localhost/oeros-ros-core:${OEROS_APP_VERSION}"
OEROS_APP_UNIT = "oeros-ros-core.container"
OEROS_APP_ARTIFACT_NAME ??= "oeros-app-ros-core-v${OEROS_APP_VERSION}${@'-broken' if d.getVar('OEROS_APP_BROKEN') == '1' else ''}"

PV = "${OEROS_APP_VERSION}"
PACKAGE_ARCH = "${MACHINE_ARCH}"

OCI_TAR = "${DEPLOY_DIR_IMAGE}/oeros-container-ros-core-latest-oci.tar"

do_compile[depends] += "oeros-container-ros-core:do_image_complete mender-artifact-native:do_populate_sysroot"
do_compile[vardeps] += "OEROS_APP_MESSAGE OEROS_APP_TOPIC OEROS_APP_IMAGE OEROS_APP_ARTIFACT_NAME"
do_compile[cleandirs] = "${B}/art"

do_compile() {
    art=${B}/art
    [ -f ${OCI_TAR} ] || bbfatal "${OCI_TAR} not found"
    cp -L ${OCI_TAR} $art/image.oci.tar
    for f in ${OEROS_APP_UNIT} healthcheck; do
        sed -e 's|@VERSION@|${OEROS_APP_VERSION}|g' \
            -e 's|@IMAGE@|${OEROS_APP_IMAGE}|g' \
            -e 's|@MESSAGE@|${OEROS_APP_MESSAGE}|g' \
            -e 's|@TOPIC@|${OEROS_APP_TOPIC}|g' \
            ${S}/$f.in > $art/$f
    done
    chmod 0755 $art/healthcheck
    printf 'APP=%s\nVERSION=%s\nIMAGE=%s\nUNIT=%s\n' ${OEROS_APP_NAME} ${OEROS_APP_VERSION} \
        ${OEROS_APP_IMAGE} ${OEROS_APP_UNIT} > $art/app.env

    mender-artifact write module-image \
        -T oeros-quadlet \
        --software-filesystem oeros-quadlet \
        --software-name ${OEROS_APP_NAME} \
        --software-version ${OEROS_APP_VERSION} \
        -t ${MENDER_DEVICE_TYPE} \
        -n ${OEROS_APP_ARTIFACT_NAME} \
        --compression none \
        -f $art/app.env -f $art/image.oci.tar -f $art/${OEROS_APP_UNIT} -f $art/healthcheck \
        -o ${B}/${OEROS_APP_ARTIFACT_NAME}.mender
}

do_deploy() {
    install -m 0644 ${B}/${OEROS_APP_ARTIFACT_NAME}.mender ${DEPLOYDIR}/
}
addtask deploy after do_compile before do_build
