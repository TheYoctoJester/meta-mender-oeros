# bootc disk image with a one-shot boot counter in the grub ESP stub.
#
# meta-bootc's ostree backend has no boot counting: a staged deployment
# that does not reach userspace (kernel panic, broken init) stays the
# default forever. This adds the mechanism Mender's grub integration uses
# for A/B rootfs updates, applied to ostree's deployment entries:
#
#   userspace (update module), after staging:  bootc_upgrade_available=1
#                                              bootc_bootcount=0
#   grub, first boot after staging:            bootc_bootcount=1 (saved),
#                                              boot entry 0 (new deployment)
#   grub, any later boot while still pending:  boot entry 1 (previous)
#   userspace, after commit or rollback:       bootc_upgrade_available=0
#
# The environment block lives on the ESP next to the grub binary
# (${cmdpath}/grubenv). ostree's generated /boot/loader/grub.cfg sets
# default=boot and its own timeout, so it is sourced (same context, unlike
# configfile) and default/timeout are set after it.
#
# A hang without a panic needs a watchdog to get to the next boot; the
# kernel argument panic=<s> covers panics.

inherit bootc-disk-image

OEROS_BOOTC_GRUBENV = "${BOOTC_ESP_DIR}${EFIDIR}/grubenv"

bootc_populate_esp:append() {
    cat > ${BOOTC_ESP_DIR}${EFIDIR}/grub.cfg <<GRUBEOF
set bootc_fallback=0
if load_env -f \${cmdpath}/grubenv bootc_upgrade_available bootc_bootcount; then
    if [ "\${bootc_upgrade_available}" = "1" ]; then
        if [ "\${bootc_bootcount}" = "1" ]; then
            set bootc_fallback=1
        else
            set bootc_bootcount=1
            save_env -f \${cmdpath}/grubenv bootc_bootcount
        fi
    fi
fi
set root=${BOOTC_GRUB_BOOT_ROOT}
search --no-floppy --set=root --label ${BOOTC_ROOT_LABEL}
source /boot/loader/grub.cfg
if [ "\${bootc_fallback}" = "1" ]; then
    set default=1
else
    set default=0
fi
set timeout=1
GRUBEOF

    # GRUB environment block: exactly 1024 bytes, padded with '#'
    python3 -c "import sys; s = '# GRUB Environment Block\nbootc_upgrade_available=0\nbootc_bootcount=0\n'; sys.stdout.write(s + '#' * (1024 - len(s)))" > ${OEROS_BOOTC_GRUBENV}
}
