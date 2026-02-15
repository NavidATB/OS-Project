import os
import json
import shutil
from pathlib import Path
import time
import subprocess
import core_engine

def get_base_path():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parts = current_dir.split(os.sep)
    if 'home' in parts:
        home_index = parts.index('home')
        user_home = os.sep + os.path.join(parts[home_index], parts[home_index + 1])
        return os.path.join(user_home, ".zocker", "containers")
    return os.path.expanduser("~/.zocker/containers")

BASE_PATH = get_base_path()
SYSTEMD_PATH = "/etc/systemd/system"


def remove_container(container_id, force=False):
    container_dir = os.path.join(BASE_PATH, container_id)
    state_path = os.path.join(container_dir, "state.json")
    rootfs_path = os.path.join(container_dir, "rootfs")
    
    if os.path.exists(state_path):
        with open(state_path, 'r') as f:
            state = json.load(f)
        if state['status'] == 'running' and not force:
            return False, "Error: Container is running. Use -f to force remove."

    print(f"[*] Stopping service zocker-{container_id}...")
    os.system(f"sudo systemctl stop zocker-{container_id} > /dev/null 2>&1")
    
    service_link = os.path.join(SYSTEMD_PATH, f"zocker-{container_id}.service")
    if os.path.exists(service_link):
        os.system(f"sudo rm {service_link}")
        os.system("sudo systemctl daemon-reload")

    print(f"[*] Unmounting rootfs for {container_id}...")
    core_engine.manage_rootfs(rootfs_path, action="cleanup")
    
    time.sleep(1)

    if os.path.exists(container_dir):
        exit_code = os.system(f"sudo rm -rf {container_dir}")
        if exit_code == 0:
            return True, "Container removed successfully."
        else:
            return False, "Failed to remove directory even with sudo rm -rf."
        

def exec_in_container(container_id, command):
    base_dir = os.path.join(BASE_PATH, container_id)
    state_path = os.path.join(base_dir, "state.json")
    rootfs_path = os.path.join(base_dir, "rootfs")
    
    if not os.path.exists(state_path):
        print("Error: Container state not found.")
        return
    with open(state_path, 'r') as f:
        state = json.load(f)
    pid = state.get('pid')
    
    if state['status'] != 'running':
        print("Error: Container is not running.")
        return
    ns_cmd = f"sudo nsenter -t {pid} -m -u -i -n -p chroot {rootfs_path} {command}"
    
    os.system(ns_cmd)

def exec_in_container_V2(container_id, command):
    container_dir = os.path.join(BASE_PATH, container_id)
    state_path = os.path.join(container_dir, "state.json")
    
    with open(state_path, 'r') as f:
        state = json.load(f)
        pid = state.get('pid')
    
    rootfs_path = os.path.join(container_dir, "rootfs")
    ns_cmd = f"sudo nsenter -t {pid} -m -u -i -n -p chroot {rootfs_path} {command} 2>&1"
    
    try:
        output = subprocess.check_output(ns_cmd, shell=True, stderr=subprocess.STDOUT)
        return output.decode('utf-8').strip()
    except subprocess.CalledProcessError as e:
        return f"Error (Code {e.returncode}): {e.output.decode('utf-8').strip()}"
    except Exception as e:
        return f"Manager Error: {str(e)}"

def create_and_start_service(container_id):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    exec_path = os.path.join(current_dir, "core_engine.py")
    container_dir = os.path.join(BASE_PATH, container_id)
    state_file_path = os.path.join(container_dir, "state.json")
    
    home_dir = os.path.abspath(os.path.join(BASE_PATH, "..", ".."))

    stop_post_cmd = (
        f"/usr/bin/python3 -c "
        f"\"import json, time; "
        f"p='{state_file_path}'; "
        f"s=json.load(open(p)); "
        f"s.update({{'status':'stopped', 'pid':0, 'finished_at':time.time()}}); "
        f"json.dump(s, open(p,'w'))\""
    )

    content = f"""[Unit]
Description=Zocker Container {container_id}
After=network.target

[Service]
Type=simple
Environment=HOME={home_dir}
ExecStart=/usr/bin/python3 {exec_path} {container_id}
ExecStopPost={stop_post_cmd}
Restart=on-failure
RestartSec=3
User=root
WorkingDirectory={current_dir}

[Install]
WantedBy=multi-user.target
"""
    service_file = os.path.join(container_dir, f"zocker-{container_id}.service")
    os.makedirs(container_dir, exist_ok=True)
    with open(service_file, "w") as f:
        f.write(content)

    target_link = os.path.join(SYSTEMD_PATH, f"zocker-{container_id}.service")
    os.system(f"sudo ln -sf {service_file} {target_link}")
    os.system("sudo systemctl daemon-reload")
    os.system(f"sudo systemctl start zocker-{container_id}")

def get_all_container_states():
    containers = []
    if not os.path.exists(BASE_PATH): return containers
    for c_id in os.listdir(BASE_PATH):
        p = os.path.join(BASE_PATH, c_id, "state.json")
        if os.path.exists(p):
            with open(p, 'r') as f:
                try: containers.append(json.load(f))
                except: pass
    return containers