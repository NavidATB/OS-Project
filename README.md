# Zocker: A Daemonless Container Engine

Zocker is a lightweight, OCI-compliant container management system developed as a core operating systems project. It focuses on low-level Linux kernel features to provide true process isolation, resource management, and distributed container orchestration across multiple Virtual Machines (VMs).

---

## Key Features

### 🚫 Daemonless Architecture
Unlike Docker, Zocker does not rely on a central background daemon. It leverages `systemd` to manage container lifecycles, ensuring high availability and system integration.

### 🔒 True Isolation
Implements Linux Namespaces (PID, Mount, Network, UTS, IPC) via `libc.unshare` to isolate container environments from the host.

### ⚙️ Resource Control (Cgroup v2)
Hardware-level resource limiting for CPU and RAM using the latest Linux Control Groups (v2) hierarchy.

### 📦 OCI Standard Compliance
Uses `config.json` for container specifications and `state.json` for runtime status tracking.

### 🌐 Distributed Orchestration (Zocker Proxy)
A centralized proxy that schedules containers across multiple VMs using a **Least Loaded algorithm**.

### 🔌 VSOCK Communication
High-performance Host-to-Guest communication using the `AF_VSOCK` protocol for orchestration commands and telemetry.

### 🌉 Advanced Networking
Supports:
- Local Bridge networking with `veth` pairs
- Cross-VM communication using **VXLAN Tunneling**

---

## Project Structure

- **`zocker.py`**: The primary CLI tool for local container management  
- **`manager.py`**: The orchestrator responsible for systemd service generation and networking setup  
- **`core_engine.py`**: The low-level engine that handles `fork`, `unshare`, and `chroot`  
- **`resources.py`**: Interface for managing Cgroup v2 resource limits  
- **`zocker-proxy.py`**: The scheduler that manages container distribution across the cluster  
- **`zocker-agent.py`**: The agent running inside VMs to execute commands and report resource stats  

---

# 🚀 Getting Started

## Prerequisites

- Linux Kernel 5.15+ (Support for Cgroup v2 is mandatory)
- Python 3.10+
- `psutil` library:

```bash
pip install psutil
```

## Installation

Clone the repository and set up the working directory:

```bash
mkdir -p ~/.zocker/containers
```
## Usage (Local Mode)

Run a container with resource limits:
```bash
sudo python3 zocker.py run --memory 512 --cpu 1024 config.json
```
Lists all containers (running and stopped):
```bash
sudo python3 zocker.py ps -a
```

## Distributed Setup (Scalability)
### On the Host Machine
Run the proxy to manage the cluster:
```bash
sudo python3 zocker-proxy.py
```
### On the Guest VMs
Start the agent to register with the host: 
```bash
sudo python3 zocker-agent.py
```
## Networking
Zocker supports Overlay Networking. By using VXLAN, containers on separate VMs can communicate as if they were on the same local switch.

---
## Academic Context

Developed as a final project for the **Operating Systems** course.

This project demonstrates practical implementation of:

- Process Lifecycle & Forking
- Linux Kernel Namespaces & Security
- Cgroups Resource Scheduling
- Virtual Networking & Tunneling Protocols
- Distributed Systems Communication (VSOCK)

## Author
***Navid Atashinbar***
