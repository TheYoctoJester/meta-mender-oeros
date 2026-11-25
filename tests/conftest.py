"""QEMU test harness for meta-mender-oeros.

Boots base.wic from an artifact directory built by
scripts/oeros-build-test-artifacts and drives the device over ssh. The tests
in one module share a single VM and run in order; after the first failure the
remaining tests of the module are skipped, since they depend on the device
state.

The guest network is slirp with restrict=on: ssh port forwarding works, the
guest cannot reach any server (no Mender server traffic, no stray devices).
"""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest


def pytest_addoption(parser):
    parser.addoption("--artifacts", default=os.environ.get("OEROS_TEST_ARTIFACTS"),
                     help="artifact directory from oeros-build-test-artifacts")
    parser.addoption("--ssh-port", type=int, default=int(os.environ.get("OEROS_TEST_SSH_PORT", "2232")),
                     help="host port forwarded to the guest ssh port")
    parser.addoption("--keep-vm", action="store_true",
                     help="leave the VM running after the tests (debugging)")


# Incremental: skip the rest of a module after a failure
_failed = {}


def pytest_runtest_makereport(item, call):
    if call.excinfo is not None and call.when == "call":
        _failed.setdefault(item.module.__name__, item.name)


def pytest_runtest_setup(item):
    first = _failed.get(item.module.__name__)
    if first is not None:
        pytest.skip("previous test failed (%s)" % first)


class Vm:
    MAC = "52:54:00:0e:50:7e"

    def __init__(self, artifacts, workdir, port):
        self.artifacts = artifacts
        self.workdir = workdir
        self.port = port
        self.disk = workdir / "disk.img"
        self.vars = workdir / "ovmf.vars.qcow2"
        self.serial = workdir / "serial.log"
        self.proc = None

    def start(self):
        self.workdir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.artifacts / "base.wic", self.disk)
        os.truncate(self.disk, 16 * 1024 ** 3)  # bootc-growfs grows otaroot
        shutil.copyfile(self.artifacts / "ovmf.vars.qcow2", self.vars)
        accel = ["-enable-kvm", "-cpu", "host"] if os.access("/dev/kvm", os.R_OK | os.W_OK) else ["-cpu", "max"]
        cmd = ["qemu-system-x86_64", *accel, "-m", "4096", "-smp", "4",
               "-drive", "file=%s,if=pflash,format=qcow2,unit=0,readonly=on" % (self.artifacts / "ovmf.qcow2"),
               "-drive", "file=%s,if=pflash,format=qcow2,unit=1" % self.vars,
               "-drive", "file=%s,if=virtio,format=raw" % self.disk,
               "-netdev", "user,id=n0,restrict=on,hostfwd=tcp:127.0.0.1:%d-:22" % self.port,
               "-device", "virtio-net-pci,netdev=n0,mac=%s" % self.MAC,
               "-display", "none", "-monitor", "none",
               "-serial", "file:%s" % self.serial]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        self.wait_ssh(600)

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(30)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def ssh(self, command, check=True, timeout=900, stdin=None):
        cmd = ["ssh", "-p", str(self.port),
               "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
               "-o", "LogLevel=ERROR", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes",
               "root@127.0.0.1", command]
        r = subprocess.run(cmd, stdin=stdin, capture_output=True, text=True, timeout=timeout)
        if check and r.returncode != 0:
            raise AssertionError("'%s' failed (%d):\n%s%s" % (command, r.returncode, r.stdout, r.stderr))
        return r

    def out(self, command, **kw):
        return self.ssh(command, **kw).stdout.strip()

    def wait_ssh(self, timeout):
        end = time.time() + timeout
        while time.time() < end:
            if self.proc.poll() is not None:
                raise AssertionError("QEMU exited (%d), see %s" % (self.proc.returncode, self.serial))
            try:
                if self.ssh("true", check=False, timeout=20).returncode == 0:
                    return
            except subprocess.TimeoutExpired:
                pass
            time.sleep(5)
        raise AssertionError("no ssh within %d s, see %s" % (timeout, self.serial))

    def boot_id(self):
        return self.out("cat /proc/sys/kernel/random/boot_id")

    def serial_size(self):
        return self.serial.stat().st_size

    def serial_since(self, offset):
        with open(self.serial, "rb") as f:
            f.seek(offset)
            return f.read().decode(errors="replace")

    def reboot(self, timeout=600):
        old = self.boot_id()
        self.ssh("systemctl reboot", check=False, timeout=30)
        end = time.time() + timeout
        time.sleep(10)
        while time.time() < end:
            self.wait_ssh(end - time.time())
            try:
                if self.boot_id() != old:
                    return
            except AssertionError:
                pass
            time.sleep(5)
        raise AssertionError("device did not come back within %d s" % timeout)

    def push(self, local, remote):
        with open(local, "rb") as f:
            self.ssh("cat > %s" % remote, stdin=f, timeout=600)

    # Mender and bootc helpers

    def mender(self, args, timeout=900):
        return self.ssh("mender-update %s" % args, check=False, timeout=timeout)

    def install(self, name):
        """Copy an artifact from the artifact directory and install it."""
        remote = "/var/lib/oeros-test/%s" % name
        self.ssh("mkdir -p /var/lib/oeros-test")
        self.push(self.artifacts / name, remote)
        r = self.mender("install %s" % remote)
        self.ssh("rm -f %s" % remote)
        return r

    def provides(self):
        p = {}
        for line in self.out("mender-update show-provides").splitlines():
            k, _, v = line.partition("=")
            p[k] = v
        return p

    def bootc(self):
        return json.loads(self.out("bootc status --format json"))["status"]

    def booted_version(self):
        return self.bootc()["booted"]["image"]["version"]

    def grubenv(self):
        out = self.out("m=$(mktemp -d /run/oeros-test-esp.XXXXXX) && mount /dev/disk/by-label/esp $m && "
                       "grub-editenv $m/EFI/BOOT/grubenv list; rc=$?; umount $m; rmdir $m; exit $rc")
        return dict(line.split("=", 1) for line in out.splitlines() if "=" in line)

    def inventory(self):
        inv = {}
        for line in self.out("/usr/share/mender/inventory/mender-inventory-bootc").splitlines():
            k, _, v = line.partition("=")
            inv[k] = v
        return inv


@pytest.fixture(scope="session")
def artifacts(pytestconfig):
    path = pytestconfig.getoption("artifacts")
    if not path:
        pytest.exit("pass --artifacts <dir> or set OEROS_TEST_ARTIFACTS", 2)
    path = Path(path).resolve()
    if not (path / "artifacts.json").exists():
        pytest.exit("%s has no artifacts.json (run scripts/oeros-build-test-artifacts)" % path, 2)
    return path


@pytest.fixture(scope="session")
def meta(artifacts):
    return json.loads((artifacts / "artifacts.json").read_text())


@pytest.fixture(scope="module")
def vm(artifacts, pytestconfig):
    v = Vm(artifacts, artifacts / "vm", pytestconfig.getoption("ssh_port"))
    try:
        v.start()
        yield v
    finally:
        if not pytestconfig.getoption("keep_vm"):
            v.stop()
