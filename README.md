# R Binaries Kubernetes Builder

A branch-based system for building Bioconductor R package binaries using Kubernetes.

## Overview

This system uses a **branch-based approach** where each build cycle runs on its own Git branch. This keeps the main branch clean with only the core code, while build branches contain all build state and artifacts.

## How It Works

### 1. Starting a New Build Cycle

Run the **Start New Build Cycle** workflow from the GitHub Actions UI:

1. Go to Actions → Start New Build Cycle
2. Click "Run workflow"
3. Enter the container image (e.g., `ghcr.io/bioconductor/bioconductor_docker:RELEASE_3_20`)
4. Click "Run workflow"

This will:
- Create a new branch named `build/YYYY-MM-DD-HHMMSS-container-tag`
- Initialize all required files and directories
- Set up the build environment
- Automatically trigger the first build run

### 2. Build Process

The **Build R Packages** workflow runs automatically on build branches:

- **On main branch**: Schedule is disabled (commented out)
- **On build branches**: Schedule is active (runs every 5 minutes)
  - Edit the workflow on the build branch to uncomment the schedule trigger

The build workflow:
1. Sets up Kubernetes resources (namespace, PVC, init container for dependencies)
2. Identifies packages that are ready to build (dependencies satisfied)
3. Dispatches Kubernetes jobs for each ready package
4. Monitors job completion and updates package status
5. Commits progress to the branch

### 3. Finishing a Build Cycle

When all packages are built, run the **Finish Build Cycle** workflow:

1. Switch to the build branch in GitHub
2. Go to Actions → Finish Build Cycle
3. Click "Run workflow"

This will:
- Create the PACKAGES index file
- Preserve old packages from previous builds
- Sync packages to the remote repository (via rclone)
- Mark the cycle as complete

## Branch Structure

### Main Branch
- Contains only the core code and workflows
- No build artifacts or state files
- Clean and minimal

### Build Branches (build/*)
```
build/2025-10-30-123456-bioconductor-docker-release-3-20/
├── .gitignore                    # Ignores large log files
├── CONTAINER_BASE_IMAGE.bioc     # Container image used
├── biocdeps.json                 # Package dependencies
├── uniquedeps.json               # Unique dependency list
├── ready_packages.txt            # Packages ready to build
├── remaining-packages.json       # Remaining dependency graph
├── bioc_version                  # Bioconductor version
├── r_version                     # R version
├── container_name                # Container name
├── null_push_counter             # Counter for no-activity cycles
├── reset_attempts_counter        # Counter for reset attempts
├── logs/                         # Package build logs
│   ├── dispatched-packages.txt   # Packages sent to build
│   ├── successful-packages.txt   # Successfully built packages
│   ├── failed-packages.txt       # Failed packages
│   └── PackageName/              # Per-package logs
│       ├── build-success.log     # Success log (committed)
│       └── build-fail.log        # Failure log (committed)
├── cache/                        # Build cache (not committed)
├── PACKAGES                      # Final package index (after finish)
├── indexed_packages_count        # Total packages in index
└── cycle_complete_time           # Completion timestamp
```

## Key Files

- **CONTAINER_BASE_IMAGE.bioc**: The Docker container image used for builds
- **biocdeps.json**: Complete dependency graph for all packages
- **ready_packages.txt**: Packages with satisfied dependencies, ready to build
- **logs/dispatched-packages.txt**: All packages that have been dispatched
- **logs/successful-packages.txt**: Successfully built packages
- **logs/failed-packages.txt**: Failed packages
- **PACKAGES**: Final package index (created by finish_cycle)

## Workflows

### start_cycle.yaml
Creates a new build branch and initializes the build environment.

**Trigger**: Manual (workflow_dispatch)

**Inputs**:
- `container_image`: Docker container image for the build

### run.yaml
Main build orchestration workflow.

**Triggers**:
- Manual (workflow_dispatch)
- Schedule (every 5 minutes) - **Commented out on main, active on build branches**
- Push to logs files (triggers next iteration)

**On main branch**: Does not run automatically  
**On build branches**: Edit to uncomment the schedule trigger

### finish_cycle.yaml
Finalizes the build cycle and publishes packages.

**Trigger**: Manual (workflow_dispatch)

## Kubernetes Resources

Each build cycle creates:
- **Namespace**: `ns-YYYY-MM-DD-HHMMSS-container-tag`
- **PVC**: `bioc-pvc-YYYY-MM-DD-HHMMSS-container-tag` (500Gi NFS)
- **Init Pod**: Runs deps_json.R to generate dependency graphs
- **Build Jobs**: One job per package, labeled with `app=bioc-builder`

## Monitoring Progress

1. Check the build branch for updated files
2. View logs in `logs/PackageName/`
3. Check `logs/successful-packages.txt` for completed packages
4. Check `logs/failed-packages.txt` for failures

## Tips

- Keep build branches until you're sure you don't need them
- Delete old build branches to clean up the repository
- The `null_push_counter` tracks cycles with no activity (helps identify stuck builds)
- Build artifacts (logs) are committed to preserve history
- Large log files are gitignored to keep branch size manageable

## Quick Start

See [QUICKSTART.md](QUICKSTART.md) for a quick reference guide.

## Migration Guide

Migrating from the old subdirectory-based system? See [MIGRATION.md](MIGRATION.md) for detailed instructions.
