# Deployment Concurrency Fix Patches

## Problem Summary
Your GitHub Actions workflows were experiencing queuing where "one action is running but others are paused" due to:
1. `cancel-in-progress: false` causing new workflow runs to queue instead of canceling stale runs
2. Lack of path filtering causing workflows to trigger on trivial changes (documentation, etc.)
3. Missing build optimizations that could reduce queue time

## Solution
These patches implement:
1. **Smart Concurrency Settings**: 
   - Dev/Staging: `cancel-in-progress: true` with granular grouping to cancel stale runs
   - Production: `cancel-in-progress: false` (safe) but with optimized triggering
2. **Intelligent Trigger Filters**: Workflows now only run on meaningful changes
3. **Build Optimization Guidance**: Comments for adding Docker layer caching
4. **Optional Debugging**: Steps to monitor queue status

## Files Created
- `.github/workflows/deploy-dev.yml.patch`
- `.github/workflows/deploy-staging.yml.patch`
- `.github/workflows/deploy-prod.yml.patch`

## How to Apply

### Method 1: Manual Application (Recommended for Review)
1. View each patch file to see the exact changes
2. Apply changes manually to your workflow files
3. Commit and push

### Method 2: Using Git Apply
```bash
# Apply all patches
git apply .github/workflows/deploy-dev.yml.patch
git apply .github/workflows/deploy-staging.yml.patch
git apply .github/workflows/deploy-prod.yml.patch

# Verify changes
git diff

# Commit and push
git add .github/workflows/*.yml
git commit -m "fix: optimize deployment concurrency and triggering"
git push
```

### Method 3: Using Patch Command
```bash
patch -p1 < .github/workflows/deploy-dev.yml.patch
patch -p1 < .github/workflows/deploy-staging.yml.patch
patch -p1 < .github/workflows/deploy-prod.yml.patch
```

## What Each Patch Does

### Dev/Staging Workflows (deploy-dev.yml & deploy-staging.yml)
- **Concurrency**: 
  ```yaml
  concurrency:
    group: ${{ github.workflow }}-${{ github.ref }}
    cancel-in-progress: true
  ```
  - Cancels previous runs when new one starts (prevents queuing)
  - Granular grouping prevents cross-branch blocking
- **Trigger Filtering**: Only runs on infrastructure/code changes
- **Build Optimization**: Comments showing where to add Docker layer caching

### Production Workflow (deploy-prod.yml)
- **Concurrency**: 
  ```yaml
  concurrency:
    group: demo-command-center-production
    cancel-in-progress: false
  ```
  - Keeps `false` for safety (don't cancel approved production deploys)
  - Simple group name for prod
- **Trigger Filtering**: Same intelligent filtering as dev/staging
- **Manual Trigger**: Preserved `workflow_dispatch` for controlled promotions

## Expected Results After Applying

**Before**: 
```
[Run #101] Deploy to dev: IN_PROGRESS (building...)
[Run #102] Deploy to dev: QUEUED (Waiting for concurrency slot)
[Run #103] Deploy to dev: QUEUED (Waiting for concurrency slot)
...
```

**After** (with dev/staging patches):
```
[Run #101] Deploy to dev: CANCELLED (by #103)
[Run #102] Deploy to dev: CANCELLED (by #103)
[Run #103] Deploy to dev: IN_PROGRESS (building...)
[Run #104] Deploy to dev: QUEUED (only if #103 still running when #104 triggered)
# Much faster feedback - no unnecessary queuing!
```

## Additional Recommendations

### 1. Terraform State Locking
Verify your Terraform backend has proper locking:
```hcl
terraform {
  backend "s3" {
    bucket = "your-terraform-stateBucket"
    key    = "env/${terraform.workspace}/terraform.tfstate"
    region = "ap-south-1"
    encrypt = true
    dynamodb_table = "terraform-locks"  # <-- CRITICAL
  }
}
```

### 2. Build Caching (Uncomment in Patches)
For faster builds, uncomment the caching sections:
```yaml
# In build-image action:
with:
  cache-from: type=registry,ref=${{ steps.ecr.outputs.registry }}/${{ vars.ECR_REPOSITORY }}:buildcache
```

### 3. Monitoring Queues
Uncomment the debugging steps to see queue status in action logs:
```yaml
- name: 🔍 Debug Concurrency Info
  run: |
    # ... (see patch files for full command)
```

## Verification Steps

1. **Test Trigger Filtering**:
   - Make a documentation change (edit README.md)
   - Confirm NO workflow runs are triggered
   - Make a code change (edit src/...)
   - Confirm workflow DOES trigger

2. **Test Concurrency Behavior** (Dev/Staging):
   - Trigger 3 rapid deployments via workflow_dispatch
   - Observe: First two get CANCELLED, last one runs
   - No more queued builds backing up

3. **Production Safety**:
   - Trigger multiple prod deployments
   - Observe: Runs queue but don't cancel each other (safe)
   - With trigger filtering, fewer unnecessary triggers occur

## Rollback Instructions
If needed, simply revert the commits:
```bash
git revert <commit-hash>
# or
git checkout HEAD -- .github/workflows/deploy-*.yml
```

These changes will significantly reduce queue times, improve feedback loops, and make your CI/CD pipeline more efficient while maintaining safety guarantees for production deployments.