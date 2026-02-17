import os
import json

class ResourceManager:
    def __init__(self, container_id):
        self.container_id = container_id
        self.path = os.path.join("/sys/fs/cgroup/system.slice", f"zocker-{container_id}.scope")

    def create_limits(self, mem_limit, cpu_shares):
        os.makedirs(self.path, exist_ok=True)
        
        try:
            with open(os.path.join(self.path, "memory.max"), "w") as f:
                f.write(str(mem_limit) if int(mem_limit) > 0 else "max")
        except Exception as e:
            print(f"Cgroup Mem Error: {e}")

        try:
            with open(os.path.join(self.path, "cpu.max"), "w") as f:
                f.write(f"{cpu_shares} 100000")
        except Exception as e:
            print(f"Cgroup CPU Error: {e}")

    def attach(self, pid):
        try:
            with open(os.path.join(self.path, "cgroup.procs"), "w") as f:
                f.write(str(pid))
        except Exception as e:
            print(f"Cgroup Attach Error: {e}")

def get_limits_from_config(container_id):
    home_dir = os.path.expanduser("~")
    config_path = os.path.join(home_dir, ".zocker", "containers", container_id, "config.json")
    if not os.path.exists(config_path):
        config_path = f"/root/.zocker/containers/{container_id}/config.json"
    
    with open(config_path, 'r') as f:
        data = json.load(f)
    mem = data['linux']['resources']['memory']['limit']
    cpu = data['linux']['resources']['cpu']['shares']
    return mem, cpu
