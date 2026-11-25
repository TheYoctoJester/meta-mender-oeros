"""End to end tests of the bootc and oeros-quadlet update modules in QEMU.

All tests share one device and run in order (standalone mender-update, no
server). Expect about 13 minutes with KVM: the broken app and the
required-unit test each wait for the 300 s health deadline.
"""

REBOOT_EXIT = 4  # mender-update: installed, reboot required
APP_PROVIDE = "oeros-quadlet.ros-core.version"
OS_PROVIDE = "bootc.os.version"


def assert_os_installed(r):
    assert r.returncode in (0, REBOOT_EXIT), r.stdout + r.stderr
    assert "Installed, but not committed" in r.stdout + r.stderr


def assert_rolled_back(r):
    assert r.returncode not in (0, REBOOT_EXIT), r.stdout + r.stderr
    assert "Rolled back" in r.stdout + r.stderr


def running_image(vm):
    return vm.out("podman ps --filter name=oeros-ros-core --format '{{.Image}}'")


def test_first_boot(vm, meta):
    state = vm.out("systemctl is-system-running --wait", check=False)
    assert state == "running", vm.out("systemctl --failed --no-legend", check=False)
    assert vm.ssh("test -s /var/lib/mender/device_type", check=False).returncode == 0
    for unit in ("mender-authd", "mender-updated", "mender-connect"):
        assert vm.ssh("systemctl is-active -q %s" % unit, check=False).returncode == 0, unit
    assert vm.booted_version() == meta["os"]["base"]
    buildinfo = vm.out("cat /usr/lib/oeros/buildinfo")
    assert "OEROS_BOOTC_OS_VERSION = %s" % meta["os"]["base"] in buildinfo
    assert "Layer Revisions" in buildinfo
    assert "panic=5" in vm.out("cat /proc/cmdline").split()
    assert vm.out("podman info --format '{{.Store.GraphDriverName}}'") == "overlay"
    assert vm.grubenv() == {"bootc_upgrade_available": "0", "bootc_bootcount": "0"}


def test_app_install(vm, meta):
    r = vm.install("app-v1.mender")
    assert r.returncode == 0, r.stdout + r.stderr
    assert vm.mender("commit").returncode == 0
    assert vm.provides()[APP_PROVIDE] == meta["app"]["v1"]
    assert running_image(vm) == "localhost/oeros-ros-core:1"


def test_app_update_without_reboot(vm, meta):
    boot = vm.boot_id()
    r = vm.install("app-v2.mender")
    assert r.returncode == 0, r.stdout + r.stderr
    assert vm.mender("commit").returncode == 0
    assert vm.boot_id() == boot
    assert vm.provides()[APP_PROVIDE] == meta["app"]["v2"]
    assert running_image(vm) == "localhost/oeros-ros-core:2"
    images = vm.out("podman images --format '{{.Repository}}:{{.Tag}}'").split()
    assert "localhost/oeros-ros-core:1" not in images


def test_broken_app_rolls_back(vm, meta):
    r = vm.install("app-broken.mender")
    assert r.returncode != 0
    assert "Rolled back" in r.stdout + r.stderr
    assert vm.provides()[APP_PROVIDE] == meta["app"]["v2"]
    assert running_image(vm) == "localhost/oeros-ros-core:2"


def test_os_rollback_before_reboot(vm, meta):
    assert_os_installed(vm.install("os-next.mender"))
    assert vm.bootc()["staged"]["image"]["version"] == meta["os"]["next"]
    assert vm.grubenv()["bootc_upgrade_available"] == "1"
    assert vm.mender("rollback").returncode == 0
    assert vm.bootc()["staged"] is None
    assert vm.grubenv() == {"bootc_upgrade_available": "0", "bootc_bootcount": "0"}
    vm.reboot()
    assert vm.booted_version() == meta["os"]["base"]


def test_os_update(vm, meta):
    assert_os_installed(vm.install("os-next.mender"))
    assert vm.grubenv() == {"bootc_upgrade_available": "1", "bootc_bootcount": "0"}
    vm.reboot()
    assert vm.booted_version() == meta["os"]["next"]
    assert vm.grubenv()["bootc_bootcount"] == "1"
    r = vm.mender("commit")
    assert r.returncode == 0, r.stdout + r.stderr
    provides = vm.provides()
    assert provides[OS_PROVIDE] == meta["os"]["next"]
    assert provides[APP_PROVIDE] == meta["app"]["v2"]
    assert vm.grubenv() == {"bootc_upgrade_available": "0", "bootc_bootcount": "0"}
    assert vm.bootc()["rollback"]["image"]["version"] == meta["os"]["base"]
    assert running_image(vm) == "localhost/oeros-ros-core:2"


FAIL_UNIT = "oeros-test-fail.service"


def test_unrelated_failed_unit_does_not_block_update(vm, meta):
    vm.ssh("printf '[Service]\\nType=oneshot\\nExecStart=/bin/false\\n[Install]\\n"
           "WantedBy=multi-user.target\\n' > /etc/systemd/system/%s && systemctl enable %s"
           % (FAIL_UNIT, FAIL_UNIT))
    # back to the base image (the rollback deployment) as a regular update
    assert_os_installed(vm.install("os-base.mender"))
    vm.reboot()
    assert vm.booted_version() == meta["os"]["base"]
    assert vm.out("systemctl is-system-running --wait", check=False) == "degraded"
    r = vm.mender("commit")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "outside the allow-list" in r.stdout + r.stderr
    assert FAIL_UNIT in vm.inventory()["system_failed_units"]
    vm.ssh("systemctl disable %s && rm /etc/systemd/system/%s && systemctl daemon-reload && "
           "systemctl reset-failed" % (FAIL_UNIT, FAIL_UNIT))


def test_required_unit_failure_rolls_back(vm, meta):
    vm.ssh("systemctl mask mender-connect.service")
    assert_os_installed(vm.install("os-next.mender"))
    vm.reboot()
    assert vm.booted_version() == meta["os"]["next"]
    r = vm.mender("commit")
    assert_rolled_back(r)
    assert "required units not active: mender-connect.service" in r.stdout + r.stderr
    vm.reboot()
    assert vm.booted_version() == meta["os"]["base"]
    vm.ssh("systemctl unmask mender-connect.service && systemctl start mender-connect.service")
    assert vm.grubenv() == {"bootc_upgrade_available": "0", "bootc_bootcount": "0"}


def test_broken_os_falls_back(vm, meta):
    assert_os_installed(vm.install("os-broken.mender"))
    mark = vm.serial_size()
    vm.reboot(timeout=900)
    # the broken image panicked, grub booted the previous deployment
    assert "Kernel panic" in vm.serial_since(mark)
    assert vm.booted_version() == meta["os"]["base"]
    assert vm.bootc()["rollbackQueued"] is True
    assert vm.grubenv() == {"bootc_upgrade_available": "1", "bootc_bootcount": "1"}
    assert_rolled_back(vm.mender("commit"))
    assert vm.bootc()["rollbackQueued"] is False
    assert vm.grubenv() == {"bootc_upgrade_available": "0", "bootc_bootcount": "0"}
    vm.reboot()
    assert vm.booted_version() == meta["os"]["base"]
    assert vm.provides()[OS_PROVIDE] == meta["os"]["base"]
    assert running_image(vm) == "localhost/oeros-ros-core:2"
