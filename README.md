# Docker Container Manager

A Python‑driven manager for Docker containers that uses a declarative **YAML** configuration to:

* Pull images on demand  
* Execute per‑container launch scripts  
* Perform health checks and scheduled updates  
* Back up important container data before each update  
* Write logs in a **standard, timestamped format**

All operations record their activity in monthly log files (`logs/dockerlog-YYYY-MM.log`).

--- 

## Table of Contents
1. [Prerequisites](#prerequisites)  
2. [Project Layout](#project-layout)  
3. [Configuration File (`config.yaml`)](#configuration-file-configyaml)  
4. [Run Scripts](#run-scripts)  
5. [CLI Overview](#cli-overview)  
6. [Supported Actions](#supported-actions)  
7. [Logging Format](#logging-format)  
8. [Backup Mechanism](#backup-mechanism)  
9. [Running the Manager](#running-the-manager)  
10. [Extending / Customising](#extending--customising)  

--- 

## Prerequisites
* **Python 3.8+** – only built‑in modules are used.  
* **Docker Engine** installed and available in `$PATH`.  
* Write permissions for the project directory (folders are auto‑created on first run).  

--- 

## Project Layout
```text
docker_manager/
├─ config.yaml          # Declarative configuration (YAML)
├─ manager.py           # Entry point; implements pull, run, check, update
├─ backups/             # Tar.gz archives of container data
├─ logs/                # Monthly log files (dockerlog-YYYY-MM.log)
└─ run_scripts/
   ├─ run-moviepy.sh
   ├─ run-plex.sh
   └─ run-sonarr.sh
```

`run_scripts/` contains per‑container shell scripts that the manager executes. Edit these scripts to launch containers with your own options.

--- 

## Configuration File (`config.yaml`)
The file is parsed at runtime with `yaml.safe_load`. It consists of two primary sections:

### General Section
| Key                | Description |
|--------------------|-------------|
| `backup_dir`       | Directory where backup archives are stored (default: `./backups`). |
| `run_scripts_dir`  | Root directory that holds all per‑container run scripts (default: `./run_scripts`). |
| `log_dir`          | Where log entries are written; one file per month (`dockerlog-YYYY-MM.log`). Default: `./logs`. |
| `update_tracker`   | Reserved for future expansion; currently unused. |

**Example**
```
[general]
backup_dir: "./backups"
run_scripts_dir: "./run_scripts"
log_dir: "./logs"
update_tracker: "./updates.txt"
```

### Container Sections
Each container is defined under a short key (e.g., `[moviepy]`). The keys map to:

| Field               | Description |
|---------------------|-------------|
| `container_real_name` | Docker image/container name used with `docker run`, `docker stop`. |
| `pull_location`     | Optional location string for pulling images; may be left blank. |
| `backup_targets`    | List of sub‑directories (inside `/data/docker/<short>/`) that should be archived before an update. |

**Example – moviepy container**
```yaml
[moviepy]
container_real_name = moviepy_service
pull_location = /data/docker/moviepy/pull
backup_targets = clips, thumbnails
```

You can define as many containers as needed (`[plex]`, `[sonarr]`, …).

--- 

## Run Scripts
Scripts live in `run_scripts/` and must be named `run-<short_name>.sh`. They are executed by the manager during a **run** or **update** action.

Current placeholder scripts:
```bash
# run-moviepy.sh
#!/bin/bash
echo "Running moviepy container..."
```

All scripts are expected to be executable (`chmod +x run_scripts/*.sh`). Replace their bodies with your own Docker `run` commands, environment variable exports, or other setup steps.

#### Adding a New Script
```bash
cat > ./run_scripts/run-watchtower.sh <<'EOS'
#!/bin/bash
echo "Launching Watchtower container..."
docker run -d --name watchtower \
  -v /etc/wt:/config \
  watchtower:latest
EOS

chmod +x ./run_scripts/run-watchtower.sh
```

--- 

## CLI Overview
The manager is invoked with `python3 manager.py` (or `./manager.py` after making it executable). The built‑in `argparse` parser understands:

| Argument | Meaning |
|----------|---------|
| `--container <name>` | **Short container name** (`moviepy`, `plex`, …). Use `"all"` to address every defined container sequentially. Default is `"all"`. |
| `action` (positional) | One of: `pull`, `run`, `check`, `update`. |

### Full Syntax
```bash
python3 manager.py --container <name> [action]
```

If `--container` is omitted, the default (`all`) is used. Omitting `action` displays help.

#### Example Invocations
```bash
# Pull images for Plex only
python3 manager.py --container plex pull

# Run a launch script for Sonarr
python3 manager.py --container sonarr run

# Perform a quick placeholder check (currently a no‑op) for all containers
python3 manager.py --container all check   # alias: "all" processes every defined container

# Full update cycle on Watchtower
python3 manager.py --container watchtower update
```

Run `python3 manager.py -h` to see automatically generated help text.

--- 

## Logging Format
Logs are appended to monthly files (`log_dir/dockerlog-YYYY-MM.log`). Each entry follows this pattern:

```
<short-name>-<YYYY-MM-DD-HH-MM> - <description of event / outcome>
```

**Examples**
```
moviepy-2026-02-16-14-35 - Pull completed for moviepy_service
plex-2026-02-16-14-36 - Run script executed
sonarr-2026-02-16-14-37 - Backed up to ./backups/sonarr-backup-2026-02-16.tar.gz
moviepy-2026-02-16-14-38 - Update cycle completed
```

The timestamp guarantees ordering per minute, and the description precisely captures what was performed.

--- 

## Backup Mechanism (used by `update`)
When an **update** action is requested for a container:

1. **Stop** the running container if it exists.  
2. **Remove** the stopped container (`docker rm`).  
3. **Archive** each target directory listed under `backup_targets` into `BACKUP_DIR`.  
   * Archive name: `{short}-YYYY-MM-DD.tar.gz` (e.g., `moviepy-2026-02-16.tar.gz`).  
4. **Pull** the latest image for the container.  
5. **Run** the corresponding launch script (`run-<short>.sh`).

The `backup_target()` function handles tar‑gz creation and logs a single entry when the archive is written.

--- 

## Running the Manager – Step‑by‑Step
1. **Create required directories** (run once):
   ```bash
   mkdir -p ./backups ./logs ./run_scripts
   chmod +x run_scripts/*.sh   # ensure scripts are executable
   ```
2. **(Optional) Edit `config.yaml`** – add or modify container definitions, real names, and backup targets.  
3. **Execute actions**. Example workflow for a single container named `plex`:
   ```bash
   # 1️⃣ Pull latest image (skips if container is already running)
   python3 manager.py --container plex pull

   # 2️⃣ Run the prepared launch script
   python3 manager.py --container plex run

   # 3️⃣ Perform a quick check (placeholder at present)
   python3 manager.py --container plex check

   # 4️⃣ Full update cycle (stop → backup → remove → pull → run)
   python3 manager.py --container plex update
   ```
   Every action generates both console output and a log entry.

--- 

## Extending / Customising
* **Add New Containers** – create a new section in `config.yaml` with `container_real_name`, `pull_location`, and/or `backup_targets`.  
* **Custom Run Scripts** – place or edit scripts under `run_scripts/run-<short>.sh`; make them executable.  
* **Advanced Backup Logic** – modify the `backup_target()` function in `manager.py` to change compression options, archive naming, or add encryption.  
* **Real Version Checks** – replace the placeholder logic in `check_latest()` with image/tag comparison (e.g., using Docker SDK).  
* **More Granular Logging** – adjust `_log_path()` and timestamp formatting if you need a different granularity (seconds, micro‑seconds, etc.).  

--- 

### That's it!
You now have an up‑to‑date Docker manager backed by a declarative YAML configuration, safe stop/backup/restore cycles, consistent logging, and clear extension points. Feel free to open an issue or submit a pull request when adding new features! 🚀