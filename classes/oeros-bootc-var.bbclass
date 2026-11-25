# Seed /var factory content one level deeper than bootc-image.bbclass does.
#
# bootc_prepare_rootfs moves /var/* to /usr/share/factory/var and emits one
# tmpfiles "C /var/<dir>" line per top-level entry. systemd-tmpfiles only
# copies a directory if the target does not exist or is empty; on first boot
# /var/lib already holds entries created by other tmpfiles.d lines and ostree
# (containers, cni, dbus, systemd), so e.g. /var/lib/mender is never seeded.
#
# Add a "C" line for every entry below each factory directory. Entries that
# already exist are left alone, missing ones are copied from the factory.

IMAGE_PREPROCESS_COMMAND += "oeros_bootc_var_seed;"

oeros_bootc_var_seed() {
    factory=${IMAGE_ROOTFS}/usr/share/factory/var
    tmpfiles=${IMAGE_ROOTFS}/usr/lib/tmpfiles.d/bootc-var.conf
    [ -d "$factory" ] && [ -f "$tmpfiles" ] || return 0
    out=${IMAGE_ROOTFS}/usr/lib/tmpfiles.d/oeros-bootc-var.conf
    echo "# Populate missing /var/<dir>/<entry> from the factory (oeros-bootc-var.bbclass)" > $out
    for d in $factory/*; do
        [ -d "$d" ] && [ ! -L "$d" ] || continue
        for e in $d/* $d/.[!.]*; do
            [ -e "$e" ] || [ -L "$e" ] || continue
            echo "C /var/$(basename "$d")/$(basename "$e") - - - - -" >> $out
        done
    done
}
