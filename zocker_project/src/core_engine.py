import os
import sys
import json
import ctypes
from resources import ResourceManager, get_limits_from_config
from isolation import apply_isolation, set_container_hostname

# --- Flags & System Constants ---
CLONE_NEWPID = 0x20000000
CLONE_NEWNS  = 0x00020000
CLONE_NEWUTS = 0x04000000
MS_REC = 16384
MS_PRIVATE = 262144

# --- Helper Logic: Filesystem & Config ---

def manage_rootfs(rootfs_path, action="setup"):
    """Handles the container's jail environment."""
    dirs = ['bin', 'lib', 'lib64', 'usr', 'etc', 'proc', 'sys', 'dev']
    if action == "setup":
        for d in dirs: os.makedirs(os.path.join(rootfs_path, d), exist_ok=True)
        # Using bind mounts for performance as discussed before
        for d in ['bin', 'lib', 'lib64', 'usr', 'etc']:
            target = os.path.join(rootfs_path, d)
            if not os.path.ismount(target):
                os.system(f"mount --bind -o ro /{d} {target}")
    elif action == "cleanup":
        for d in reversed(['bin', 'lib', 'lib64', 'usr', 'etc']):
            target = os.path.join(rootfs_path, d)
            if os.path.ismount(target): os.system(f"umount {target}")

def get_container_env(container_id):
    """Prepares paths and loads OCI config."""
    real_user = os.getenv("SUDO_USER") or os.getenv("USER")
    base_dir = f"/home/{real_user}/.zocker/containers/{container_id}"
    with open(os.path.join(base_dir, "config.json"), 'r') as f:
        return base_dir, json.load(f)

# --- Core Logic: Execution ---

def run_container_process(container_id, rootfs_path, config_data, rm):
    """The internal logic of the jailed process."""
    libc = ctypes.CDLL("libc.so.6")

    # 1. Isolation: Mount Private & Chroot
    libc.mount(None, b"/", None, MS_REC | MS_PRIVATE, None)
    os.chroot(rootfs_path)
    os.chdir("/")

    # 2. Setup internal mounts (like /proc)
    for m in config_data.get('mounts', []):
        os.makedirs(m['destination'], exist_ok=True)
        os.system(f"mount -t {m['type']} {m['source']} {m['destination']}")

    # 3. Finalize Identity & Resource attachment
    set_container_hostname(f"zocker-{container_id[:6]}")
    rm.attach(os.getpid())

    # 4. Exec
    os.environ["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    os.chdir(config_data.get('process', {}).get('cwd', '/'))
    os.execvp("/bin/bash", ["/bin/bash"])

def start_container(container_id):
    """Main entry point for starting the container."""
    try:
        base_dir, config_data = get_container_env(container_id)
        rootfs_path = os.path.join(base_dir, "rootfs")
        
        # Resource management
        mem, cpu = get_limits_from_config(container_id)
        rm = ResourceManager(container_id)
        rm.create_limits(mem, cpu)

        # Prepare Environment
        manage_rootfs(rootfs_path, "setup")
        apply_isolation() #

        # Namespace Unshare
        libc = ctypes.CDLL("libc.so.6")
        if libc.unshare(CLONE_NEWPID | CLONE_NEWNS | CLONE_NEWUTS) != 0:
            raise OSError("Unshare failed")

        pid = os.fork()
        if pid == 0:
            run_container_process(container_id, rootfs_path, config_data, rm)
        else:
            # Parent: State management and cleanup
            print(f"[+] Container {container_id} started (Host PID: {pid})")
            os.wait()
            manage_rootfs(rootfs_path, "cleanup")
            print(f"[-] Container {container_id} stopped and cleaned up.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1: start_container(sys.argv[1])