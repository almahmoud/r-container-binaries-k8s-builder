# Quick Reference Guide

## Starting a New Build

1. Go to **Actions** → **Start New Build Cycle**
2. Click **Run workflow**
3. Enter container image (e.g., `ghcr.io/bioconductor/bioconductor_docker:RELEASE_3_20`)
4. Click **Run workflow**

A new branch will be created: `build/YYYY-MM-DD-HHMMSS-container-tag`

## Enabling Automatic Builds on Build Branch

After the branch is created:

1. Switch to the build branch
2. Edit `.github/workflows/run.yaml`
3. Uncomment these lines (around line 6-7):
   ```yaml
   schedule:
     - cron: '*/5 * * * *'
   ```
4. Commit and push

Builds will now run automatically every 5 minutes.

## Monitoring Build Progress

Check these files on the build branch:

- `logs/successful-packages.txt` - Completed packages
- `logs/failed-packages.txt` - Failed packages  
- `logs/dispatched-packages.txt` - All dispatched packages
- `remaining-packages.json` - Packages still waiting
- `logs/PackageName/build-*.log` - Individual package logs

## Finishing a Build

When all packages are done:

1. Switch to the build branch in GitHub
2. Go to **Actions** → **Finish Build Cycle**
3. Click **Run workflow**

This creates the PACKAGES index and syncs to the repository.

## File Reference

| File | Purpose |
|------|---------|
| `CONTAINER_BASE_IMAGE.bioc` | Docker image used for builds |
| `biocdeps.json` | Package dependency graph |
| `ready_packages.txt` | Packages ready to build now |
| `bioc_version` | Bioconductor version |
| `r_version` | R version |
| `null_push_counter` | No-activity cycle counter |
| `PACKAGES` | Final package index (after finish) |
| `cycle_complete_time` | Build completion timestamp |

## Kubernetes Resources

Each build creates:
- Namespace: `ns-YYYY-MM-DD-HHMMSS-container-tag`
- PVC: `bioc-pvc-YYYY-MM-DD-HHMMSS-container-tag`
- Jobs: One per package with label `app=bioc-builder`

## Common Commands

### Check build branch status
```bash
git checkout build/2025-10-30-123456-container-tag
cat logs/successful-packages.txt | wc -l  # Count successful builds
cat logs/failed-packages.txt | wc -l      # Count failures
```

### View a package log
```bash
cat logs/PackageName/build-success.log
# or
cat logs/PackageName/build-fail.log
```

### Check Kubernetes jobs
```bash
kubectl get jobs -n ns-YYYY-MM-DD-HHMMSS-container-tag -l app=bioc-builder
```

### Clean up old build branches
```bash
git branch -d build/2025-05-28-142558-container-tag
git push origin --delete build/2025-05-28-142558-container-tag
```

## Troubleshooting

### Build seems stuck
- Check `null_push_counter` - if high, builds may be waiting on dependencies
- Check Kubernetes jobs: `kubectl get jobs -n ns-...`
- Look for failed packages: `cat logs/failed-packages.txt`

### Need to restart a build
Option 1: Create a new branch with the start_cycle workflow
Option 2: Manually reset files on current branch and re-run workflow

### Package keeps failing
1. Check the log: `logs/PackageName/build-fail.log`
2. Look for dependency issues
3. Check if package is archived on CRAN

## Important Notes

- **Main branch**: Does not run builds automatically (schedule is commented out)
- **Build branches**: Edit workflow to uncomment schedule for automatic builds
- **Keep branches**: Don't delete build branches until you're sure you don't need them
- **Log sizes**: Large logs are gitignored to keep repo size manageable
