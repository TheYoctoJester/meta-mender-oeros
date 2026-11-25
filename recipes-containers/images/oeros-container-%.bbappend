# Work around meta-virtualization image-oci.bbclass (wrynose and master):
# for OCI_BASE_IMAGE recipes it adds do_image_oci[depends] on
# "<base>:do_build". do_build is not an sstate task, so extend_recipe_sysroot
# collapses it into its dependencies and stages do_populate_sysroot of nearly
# every recipe in the base image's closure into do_image_oci's sysroot. That
# fails with "The file /usr/share/aclocal/glib-2.0.m4 is installed by both
# glib-2.0 and glib-2.0-initial" once gobject-introspection is in the closure.
#
# do_image_oci only needs the base image's deployed OCI layout, which
# do_image_complete (an sstate task, so not expanded) provides.
python __anonymous() {
    base = d.getVar('_OCI_BASE_RECIPE')
    if not base:
        return
    deps = d.getVarFlag('do_image_oci', 'depends') or ''
    old = '%s:do_build' % base
    if old in deps.split():
        d.setVarFlag('do_image_oci', 'depends',
                     ' '.join(x if x != old else '%s:do_image_complete' % base
                              for x in deps.split()))
}

# The mender-*-install features append mender-auth and mender-update (plus grub,
# kernel, dbus via their dependencies) to IMAGE_INSTALL of every image.
# Containers are not Mender devices.
MENDER_FEATURES_DISABLE:append = " mender-auth-install mender-update-install mender-image mender-image-uefi"
