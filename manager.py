#!/usr/bin/env python3
"""
Docker container manager with configuration driven workflow.
Reads configuration from config.yaml and provides pull, run, check and update actions.
"""

import os
import sys
import subprocess
import time

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")
import datetime
import configparser
import yaml
import shutil
import docker

# ----------------------------------------------------------------------
# Configuration loading
# ----------------------------------------------------------------------
# Load configuration from YAML file
with open(CONFIG_PATH) as fp:
    cfg_data = yaml.safe_load(fp)

general_cfg = cfg_data["general"]
BACKUP_DIR = general_cfg.get("backup_dir", "./backups").strip()
RUN_SCRIPTS_DIR = general_cfg.get("run_scripts_dir", "./run_scripts").strip()
LOG_DIR = general_cfg.get("log_dir", "./logs").strip()
UPDATE_TRACKER = general_cfg.get("update_tracker", "./updates.txt").strip()

# Build mapping of container short names to their details
containers = {}
for short_name, details in cfg_data["containers"].items():
    containers[short_name] = {
        "container_real_name": details.get("container_name", ""),
        "pull_location": details.get("pull_location", ""),
        # backup_targets used later as comma-separated list
        "backup_targets": details.get("backup_subdirs", []),
    }


# ----------------------------------------------------------------------
# Logging helpers (standard format)
# ----------------------------------------------------------------------
def _log_path():
    """Return path to the current month's log file."""
    now = datetime.datetime.now()
    filename = f"dockerlog-{now.year:04d}-{now.month:02d}.log"
    return os.path.join(LOG_DIR, filename)


def _ensure_log_dir():
    os.makedirs(LOG_DIR, exist_ok=True)


def log_entry(short_name: str, description: str):
    """Append a standard-formatted entry to the monthly log file."""
    _ensure_log_dir()
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y-%m-%d-%H-%M")
    line = f"{short_name}-{timestamp} - {description}\n"
    with open(_log_path(), "a", encoding="utf-8") as fp:
        fp.write(line)


def log_info(short_name: str, msg: str):
    print(f"{short_name.upper()} | {msg}")


# ----------------------------------------------------------------------
# Helper utilities
# ----------------------------------------------------------------------
def run_cmd(cmd: list, capture_output=False):
    """Run a subprocess command and return CompletedProcess."""
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE if capture_output else None,
            stderr=subprocess.STDOUT if capture_output else None,
            text=True,
            check=True,
        )
        return result
    except subprocess.CalledProcessError as e:
        # Return the failed process for inspection
        return e


def is_container_running(real_name: str) -> bool:
    """Check whether a container with the given real name is currently running."""
    try:
        ps = subprocess.run(
            ["docker", "ps", "--filter", f"name={real_name}", "--format", "{{.ID}}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return ps.stdout.strip() != ""
    except Exception:
        return False


def colored(text: str, color_code: int) -> str:
    """Wrap text in ANSI color codes."""
    return f"\033[{color_code}m{text}\033[0m"


# ----------------------------------------------------------------------
# Core actions
# ----------------------------------------------------------------------
def pull_container(short: str):
    cfg = containers.get(short)
    if not cfg:
        sys.exit(f"ERROR: No container definition for '{short}'")
    real_name = cfg["container_real_name"]
    pull_loc = cfg["pull_location"]

    log_info(short, "Pull started")

    if is_container_running(real_name):
        warning = colored(
            f"⚠️ Container '{real_name}' ({short}) is currently RUNNING. "
            "Stop it before pulling.",
            94,
        )
        print(warning)
        # Optionally exit or continue
    else:
        run_cmd(["docker", "pull", real_name], capture_output=True)

    log_entry(short, f"Pull completed for {real_name}")


def run_container_script(short: str):
    script_path = os.path.join(RUN_SCRIPTS_DIR, f"run-{short}.sh")
    if not os.path.isfile(script_path):
        sys.exit(f"ERROR: Run script not found at {script_path}")

    log_info(short, "Run script executed")
    run_cmd([script_path], capture_output=True)
    log_entry(short, "Container started via run script")


def check_latest(short: str):
    cfg = containers.get(short)
    if not cfg:
        sys.exit(f"ERROR: No container definition for '{short}'")
    real_name = cfg["container_real_name"]

    # Check the local image digest against the remote latest digest

    cfg = containers.get(short)
    if not cfg:
        sys.exit(f"ERROR: No container definition for '{short}'")
    real_name = cfg["container_real_name"]

    try:
        # Get local image digest
        result = subprocess.run(
            [
                "docker",
                "image",
                "inspect",
                real_name,
                "--format",
                "{{index .RepoDigests 0}}",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        local_digest = result.stdout.strip()
    except subprocess.CalledProcessError:
        log_info(short, "Could not retrieve local image digest – assuming not latest")
        log_entry(short, "Checked if container is latest (failed to get local digest)")
        return

    # Query remote registry for latest digest
    import requests

    try:
        registry_api = f"https://registry-1.docker.io/v2/{real_name.replace(':', '%3A')}/manifests/latest"
        headers = {"Accept": "application/vnd.docker.distribution.manifest.v2+json"}
        resp = requests.get(registry_api, headers=headers, timeout=10)
        resp.raise_for_status()
        remote_digest = resp.headers.get("Docker-Content-Digest")
    except Exception as e:
        log_info(short, f"Error retrieving remote digest: {e}")
        log_entry(
            short, f"Checked if container is latest (failed to get remote digest)"
        )
        return

    if local_digest == remote_digest:
        log_info(short, "Container image is up to date")
        log_entry(short, "Checked if container is latest – up to date")
    else:
        log_info(short, "Container image is outdated – please update")
        log_entry(short, "Checked if container is latest – outdated")


def backup_target(src_path: str, dest_dir: str, short: str, suffix: str):
    """Create a tar.gz archive of src_path under dest_dir with naming pattern."""
    os.makedirs(dest_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d")
    archive_name = f"{short}-{timestamp}.tar.gz"
    archive_path = os.path.join(dest_dir, archive_name)

    # Using tar to compress the source directory
    if not os.path.isdir(src_path):
        print(colored(f"⚠️ Backup source does not exist: {src_path}", 31))
        return

    cmd = [
        "tar",
        "-czf",
        archive_path,
        "-C",
        src_path,
        ".",
    ]
    run_cmd(cmd)
    log_entry(short, f"Backed up to {archive_path}")


def update_container(short: str):
    cfg = containers.get(short)
    if not cfg:
        sys.exit(f"ERROR: No container definition for '{short}'")
    real_name = cfg["container_real_name"]

    # 1️⃣ Stop container
    if is_container_running(real_name):
        log_info(short, "Stopping container")
        run_cmd(["docker", "stop", real_name])
        while is_container_running(real_name):
            print(colored("⏳ Waiting for container to stop...", 90))
            time.sleep(1)
    else:
        log_info(short, "Container already stopped")

    # 2️⃣ Remove container
    try:
        run_cmd(["docker", "rm", real_name])
    except Exception as e:
        print(colored(f"Error removing container: {e}", 31))

    # 3️⃣ Backup each target directory
    for target in cfg["backup_targets"]:
        src_dir = f"/data/docker/{real_name}/{target}"
        backup_target(src_dir, BACKUP_DIR, short, target)

    # 4️⃣ Pull new image
    pull_container(short)

    # 5️⃣ Run the run script again
    run_container_script(short)

    log_info(short, "Update cycle completed")


# ----------------------------------------------------------------------
# CLI handling
# ----------------------------------------------------------------------
def main():
    import argparse

    parser = argparse.ArgumentParser(description="Docker container manager")
    parser.add_argument(
        "--container",
        help='Short container name (or "all" to process every defined container)',
        default="all",
    )
    parser.add_argument(
        "action",
        choices=["pull", "run", "check", "update"],
        help="Operation to perform",
    )
    args = parser.parse_args()

    target_names = (
        [args.container] if args.container.lower() != "all" else list(containers.keys())
    )

    for short in target_names:
        if args.action == "pull":
            pull_container(short)
        elif args.action == "run":
            run_container_script(short)
        elif args.action == "check":
            check_latest(short)
        elif args.action == "update":
            update_container(short)


if __name__ == "__main__":
    main()
