import os
import sys
import json
import ctypes
from resources import ResourceManager, get_limits_from_config
from isolation import apply_isolation, set_container_hostname

# Flag for creating a new PID namespace
CLONE_NEWPID = 0x20000000

def get_full_config(container_id):
    """Reads the full OCI config from the user's home directory."""
    # Get the real user even if running with sudo
    real_user = os.getenv("SUDO_USER") or os.getenv("USER")
    config_path = f"/home/{real_user}/.zocker/containers/{container_id}/config.json"
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config not found at {config_path}")
        
    with open(config_path, 'r') as f:
        return json.load(f)

def apply_dynamic_mounts(config_data):
    """Mounts required filesystems defined in the configuration."""
    mounts = config_data.get('mounts', [])
    for m in mounts:
        source, destination, m_type = m.get('source'), m.get('destination'), m.get('type')
        print(f"[*] Mounting {source} to {destination}...")
        os.makedirs(destination, exist_ok=True)
        os.system(f"mount -t {m_type} {source} {destination}")

def start_container(container_id):
    try:
        # 1. Load config and set resource limits
        config_data = get_full_config(container_id)
        mem, cpu = get_limits_from_config(container_id)
        rm = ResourceManager(container_id)
        rm.create_limits(mem, cpu)

        # 2. Prepare namespaces (except PID)
        apply_isolation()
        
        # 3. Use libc to unshare PID namespace
        libc = ctypes.CDLL("libc.so.6")
        if libc.unshare(CLONE_NEWPID) != 0:
            raise OSError("Failed to unshare PID namespace")

        pid = os.fork()

        if pid == 0:
            # --- CHILD PROCESS (Inside Container) ---
            os.system("mount --make-rprivate /")
            apply_dynamic_mounts(config_data)
            set_container_hostname(f"zocker-{container_id[:6]}")
            
            # Attach child to cgroup
            rm.attach(os.getpid())

            # Set Environment
            os.environ["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
            os.environ["HOME"] = "/root"
            os.chdir(config_data.get('process', {}).get('cwd', '/'))

            print(f"\n[+] Container {container_id} is active (Internal PID: {os.getpid()})")
            os.execvp("/bin/bash", ["/bin/bash"])

        else:
            # --- PARENT PROCESS (Host System) ---
            # 4. Save state BEFORE waiting for the child
            real_user = os.getenv("SUDO_USER") or os.getenv("USER")
            container_dir = f"/home/{real_user}/.zocker/containers/{container_id}"
            os.makedirs(container_dir, exist_ok=True)

            state_data = {
                "id": container_id,
                "status": "running",
                "pid": pid, # Real Host PID
                "bundle": container_dir
            }

            state_path = os.path.join(container_dir, "state.json")
            with open(state_path, "w") as f:
                json.dump(state_data, f, indent=4)
            
            os.chmod(state_path, 0o666)
            print(f"[+] State file created at: {state_path}")
            print(f"[+] Container process started with Host PID: {pid}")

            # 5. Wait for container to exit
            os.wait()
            
            # Update state to stopped
            state_data["status"] = "stopped"
            with open(state_path, "w") as f:
                json.dump(state_data, f, indent=4)
            print(f"\n[-] Container {container_id} has stopped.")

    except Exception as e:
        print(f"Core Engine Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        start_container(sys.argv[1])
    else:
        print("Usage: sudo python3 core_engine.py <container_id>")