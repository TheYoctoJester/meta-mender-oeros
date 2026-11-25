# meta-mender-oeros

oeros on bootable containers (meta-bootc) with Mender as the deployment, fleet
management and remote access layer. The OS is a bootc OCI image managed by
ostree; ROS 2 lives in podman containers started by Quadlet. Mender does not
touch partitions: it delivers OS images and apps through two update modules and
provides inventory and Mender Connect.

Status: demo, verified on qemux86-64 (KVM, OVMF) against hosted.mender.io.

## Layers and setup

Collection `mender-oeros`, depends on `core bootc mender oeros
virtualization-layer`. The bitbake-setup configuration is
`conf/registry/oeros-wrynose-lyrical-bootc.conf.json` (upstream oeros JSON plus
meta-bootc master and this layer; fragments `bootc/base bootc/sysext
bootc/rm-work`). All layers float on their branches.

```
bitbake-setup init --non-interactive \
    https://raw.githubusercontent.com/TheYoctoJester/meta-mender-oeros/main/conf/registry/oeros-wrynose-lyrical-bootc.conf.json \
    distro/oeros machine/qemux86-64
```

To work on a local clone of this layer instead, add
`-L meta-mender-oeros /path/to/meta-mender-oeros`.

Every image records the layer revisions it was built from, with a
`-- modified` marker for uncommitted changes, in `/usr/lib/oeros/buildinfo`.
bitbake-setup keeps the resolved revisions of the whole setup in
`<setup>/config/sources-fixed-revisions.json`.

local.conf additions on top of the oeros defaults:

```
INHERIT += "mender-setup"
MENDER_FEATURES_ENABLE:append = " mender-auth-install mender-update-install mender-systemd"
MENDER_SERVER_URL = "https://hosted.mender.io"
MENDER_TENANT_TOKEN = "..."
MENDER_CONNECT_USER = "root"
BOOTC_KERNEL_ARGS:append = " panic=5"
```

No `mender-image*` feature: there is no A/B rootfs. `/var/lib/mender` is
persistent because `/var` is shared by all ostree deployments.

## Contents

- `oeros-bootc-host` image: bootc, ostree, podman, mender-update/auth/connect,
  both update modules. Deploys a wic (ESP + otaroot) and the OS update artifact
  `oeros-bootc-host-<machine>.bootc-mender`.
- `oeros-bootc-disk.bbclass`: one-shot boot counter in the ESP grub stub. The
  stub reads `EFI/BOOT/grubenv`; with `bootc_upgrade_available=1` the first boot
  sets `bootc_bootcount=1`, a second boot without a commit selects menu entry 1
  (the previous deployment). It `source`s the ostree generated grub.cfg and sets
  `default` afterwards.
- `oeros-bootc-mender.bbclass`: image type `bootc-mender` (module-image of type
  `bootc` carrying the OCI archive; provides `bootc.os.version`,
  `bootc.os.digest` in their own software filesystem). Also removes the A/B
  fstab entries mender-setup adds to every image.
- `oeros-bootc-var.bbclass`: seeds missing `/var/<dir>/<entry>` from
  `/usr/share/factory/var` (bootc-image.bbclass only seeds top-level dirs, so
  `/var/lib/mender` was never created).
- `oeros-bootc-module`: update module `bootc`. Download streams the archive to
  `/var/lib/oeros-bootc`, Install runs `bootc upgrade` (or `switch` when the
  origin differs) and arms the boot counter, VerifyReboot and Commit check that
  the new digest is booted and the system is healthy (no failed units, all
  Quadlet app health checks), Rollback drops a staged deployment or runs
  `bootc rollback`. Inventory: `bootc_{booted,staged,rollback}_{digest,version}`.
- `oeros-quadlet-module`: update module `oeros-quadlet` for apps (OCI archive,
  Quadlet `.container` unit, optional health check), no reboot, automatic
  rollback to the previous release when the health check fails.
- `oeros-app-ros-core`: builds the ros-core app artifact from
  `oeros-container-ros-core` (`OEROS_APP_VERSION`, `OEROS_APP_BROKEN`).
- Copied from meta-oeros-demo: Fast DDS UDPv4 profile, podman-restart mask for
  user managers, container image dependency fix.

## Test variants

`OEROS_BOOTC_OS_VERSION` sets the OS version (OCI label, artifact name,
`/usr/lib/oeros/os-version`). `OEROS_BOOTC_BROKEN = "1"` builds an image whose
init exits, so the kernel panics; with `panic=5` this exercises the grub
fallback.

## Known limitations

- A hang without a panic is not detected: nothing reboots the device. Needs a
  hardware watchdog armed early (firmware or initramfs) plus systemd
  `RuntimeWatchdogSec`. Not tested.
- Quadlet units live in the per-deployment `/etc`. A manual `bootc rollback`
  after later app updates brings back older units; Mender serializes
  deployments, so the modules themselves do not hit this.
- Every OS update carries the full OCI image (about 150 MB here); no deltas.
- Yocto's `/var/tmp` is tmpfs; do not stage artifacts there.
