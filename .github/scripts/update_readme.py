#!/usr/bin/env python3
import json
import os
import re
import time
from datetime import datetime
import requests

# Track the last successful BBS node
CURRENT_BBS_NODE = "nebbiolo2"  # Default starting node

def check_cran_archived(pkg):
    """Checks if a package has been archived on CRAN"""
    cranurl = f"https://cran.r-project.org/web/packages/{pkg}/index.html"
    try:
        r = requests.get(cranurl, timeout=10)
        retries = 0
        while retries <= 5 and r.status_code != 200:
            r = requests.get(cranurl, timeout=10)
            retries += 1
            time.sleep(2)
        if r.status_code == 200:
            crantext = r.content.decode("utf-8")
            for search in ["Archived on", "Removed on"]:
                if search in crantext:
                    archivetext = crantext[crantext.find(search):].split('\n')[0]
                    return f"[CRAN Package '{pkg}']({cranurl}) {archivetext.lower()}"
    except (requests.exceptions.RequestException, UnicodeDecodeError):
        pass
    return None

def get_bbs_status(pkg, bioc_version):
    """Get current BBS build status for package, trying different BBS nodes if needed"""
    global CURRENT_BBS_NODE
    
    # Define both possible BBS nodes
    bbs_nodes = ["nebbiolo1", "nebbiolo2"]
    
    # Try the current node first
    bbsurl = f"https://bioconductor.org/checkResults/{bioc_version}/bioc-LATEST/{pkg}"
    statusurl = f"{bbsurl}/raw-results/{CURRENT_BBS_NODE}/buildsrc-summary.dcf"
    
    try:
        r = requests.get(statusurl, timeout=10)
        # If we get a 404, try the other node
        if r.status_code == 404:
            # Get the alternate node
            alt_node = [node for node in bbs_nodes if node != CURRENT_BBS_NODE][0]
            alt_url = f"{bbsurl}/raw-results/{alt_node}/buildsrc-summary.dcf"
            alt_r = requests.get(alt_url, timeout=10)
            
            if alt_r.status_code == 200:
                # Remember this successful node for future requests
                CURRENT_BBS_NODE = alt_node
                r = alt_r  # Use the successful response
            else:
                # Both nodes failed
                return "Not Found"
        
        # Continue with retries if needed
        retries = 0
        while retries <= 5 and r.status_code != 200:
            r = requests.get(statusurl, timeout=10)
            retries += 1
            time.sleep(2)
            
        if r.status_code == 200:
            try:
                bbs_summary = r.content.decode("utf-8")
                status_line = next((line for line in bbs_summary.split('\n') if line.startswith('Status:')), '')
                if status_line:
                    status = status_line.split(':', 1)[1].strip()
                    return f"[{status}]({bbsurl})"
            except Exception:
                pass
    except (requests.exceptions.RequestException, UnicodeDecodeError):
        pass
    
    return "Not Found"

def check_failure_reason(log_path):
    """Extract all possible failure reasons from log file"""
    if not os.path.exists(log_path):
        return ["Log file not found"]
    
    with open(log_path, 'r') as f:
        log_content = f.read()
    
    reasons = []
    # More comprehensive error patterns with all quote types
    patterns = [
        (r"there is no package called [\"'""''‘]([^\"'""''’]+)[\"'""''’]", "Missing R dependency"),
        (r"dependenc(?:y|ies) [\"'""''‘]([^\"'""''’]+)[\"'""''’] (?:is|are) not available", "Missing dependency"),
        (r"Warning: dependenc(?:y|ies) [\"'""''‘]([^\"'""''’]+)[\"'""''’] (?:is|are) not available", "Missing dependency"),
        (r"ERROR: dependencies? [\"'""''‘]([^\"'""''’]+)[\"'""''’] (?:is|are) not available", "Missing dependency"),
        (r"ERROR: package [\"'""''‘]([^\"'""''’]+)[\"'""''’] (?:is|was) not found", "Package not found"),
        (r"ERROR: System command error.*?:\n\s*([^\n]+)", "System command failed"),
        (r"Installation failed:[\r\n]+\s*([^\r\n]+)", "Installation failed"),
        (r"error: command .*? failed with exit status \d+[\r\n]+\s*([^\r\n]+)", "Command error"),
        (r"error: Error installing package.*?:\n\s*([^\n]+)", "Installation error"),
        (r"configure: error:.*?([^\n]+)", "Configure error"),
        (r"ERROR:\s+compilation failed for package.*?([^\n]+)", "Compilation failed")
    ]
    
    for pattern, msg in patterns:
        matches = re.findall(pattern, log_content, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            reason = f"{msg}: {match}"
            if reason not in reasons:  # Avoid duplicates
                reasons.append(reason)
                # Check CRAN status for failed dependency
                if any(x in msg.lower() for x in ["dependency", "package"]):
                    archived = check_cran_archived(match.strip())
                    if archived and archived not in reasons:
                        reasons.append(archived)
    
    if not reasons:
        # Check for common error keywords
        error_keywords = [
            "error:", "Error:", "ERROR:", 
            "failed", "Failed", "FAILED",
            "cannot find", "not found",
            "could not", "unable to"
        ]
        for line in log_content.split('\n'):
            if any(kw in line for kw in error_keywords):
                reasons.append(line.strip())
                break
        
        if not reasons:
            reasons.append("Build failed with unknown error")
    
    # Limit to first 3 most relevant reasons to keep README readable
    return reasons[:3]

def load_bbs_cache():
    """Load BBS status cache to avoid repeated API calls"""
    cache_dir = "cache"
    bbs_cache_file = f"{cache_dir}/bbs_status.json"
    verified_bbs_file = f"{cache_dir}/verified_bbs.txt"
    bbs_node_file = f"{cache_dir}/bbs_node.txt"
    
    bbs_cache = {}
    verified_bbs = set()
    
    os.makedirs(cache_dir, exist_ok=True)
    
    # Load BBS status cache
    if os.path.exists(bbs_cache_file):
        try:
            with open(bbs_cache_file) as f:
                bbs_cache = json.load(f)
        except:
            bbs_cache = {}
    
    # Load packages with verified BBS status
    if os.path.exists(verified_bbs_file):
        with open(verified_bbs_file) as f:
            verified_bbs = set(line.strip() for line in f if line.strip())
    
    # Load previously successful BBS node
    if os.path.exists(bbs_node_file):
        with open(bbs_node_file, 'r') as f:
            node = f.read().strip()
            if node in ["nebbiolo1", "nebbiolo2"]:
                global CURRENT_BBS_NODE
                CURRENT_BBS_NODE = node
    
    return {"bbs_cache": bbs_cache, "verified_bbs": verified_bbs}

def save_bbs_cache(bbs_cache, verified_bbs):
    """Save BBS status cache and verified packages list"""
    cache_dir = "cache"
    bbs_cache_file = f"{cache_dir}/bbs_status.json"
    verified_bbs_file = f"{cache_dir}/verified_bbs.txt"
    bbs_node_file = f"{cache_dir}/bbs_node.txt"
    
    os.makedirs(cache_dir, exist_ok=True)
    
    # Save BBS status cache
    with open(bbs_cache_file, 'w') as f:
        json.dump(bbs_cache, f)
    
    # Save verified BBS packages
    with open(verified_bbs_file, 'w') as f:
        for pkg in sorted(verified_bbs):
            f.write(f"{pkg}\n")
    
    # Save current BBS node
    with open(bbs_node_file, 'w') as f:
        f.write(CURRENT_BBS_NODE)

def main():
    """Generate README for build branch showing package build status"""
    
    # Check if we're on a build branch
    branch_name = os.environ.get('GITHUB_REF', '').replace('refs/heads/', '')
    if not branch_name.startswith('build/'):
        print("Not on a build branch, skipping README update")
        return
    
    # Extract build info from branch name
    build_id = branch_name.replace('build/', '')
    
    # Load package list from biocdeps.json
    if not os.path.exists('biocdeps.json'):
        print("biocdeps.json not found, skipping README update")
        return
    
    with open('biocdeps.json', 'r') as f:
        packages = json.load(f)
    
    total_packages = len(packages)
    
    # Get container image
    container_image = "Unknown"
    if os.path.exists('CONTAINER_BASE_IMAGE.bioc'):
        with open('CONTAINER_BASE_IMAGE.bioc', 'r') as f:
            container_image = f.read().strip()
    
    # Get bioc version
    bioc_version = "Unknown"
    if os.path.exists('bioc_version'):
        with open('bioc_version', 'r') as f:
            bioc_version = f.read().strip()
    
    # Get R version
    r_version = "Unknown"
    if os.path.exists('r_version'):
        with open('r_version', 'r') as f:
            r_version = f.read().strip()
    
    # Load BBS cache
    cache = load_bbs_cache()
    bbs_cache = cache["bbs_cache"]
    verified_bbs = cache["verified_bbs"]
    
    # Load successful packages
    successful = set()
    if os.path.exists('logs/successful-packages.txt'):
        with open('logs/successful-packages.txt', 'r') as f:
            successful = set(line.strip() for line in f if line.strip())
    
    # Load failed packages
    failed = set()
    if os.path.exists('logs/failed-packages.txt'):
        with open('logs/failed-packages.txt', 'r') as f:
            failed = set(line.strip() for line in f if line.strip())
    
    # Load dispatched packages
    dispatched = set()
    if os.path.exists('logs/dispatched-packages.txt'):
        with open('logs/dispatched-packages.txt', 'r') as f:
            dispatched = set(line.strip() for line in f if line.strip())
    
    # Calculate statistics
    success_count = len(successful)
    failed_count = len(failed)
    in_progress_count = len(dispatched - successful - failed)
    not_started_count = total_packages - len(dispatched)
    
    # Check if cycle is complete
    cycle_status = "In Progress"
    completion_time = None
    if os.path.exists('cycle_complete_time'):
        with open('cycle_complete_time', 'r') as f:
            completion_time = f.read().strip()
        cycle_status = "Complete"
    elif os.path.exists('PACKAGES'):
        cycle_status = "Complete"
    
    # Get indexed package count
    indexed_count = None
    if os.path.exists('indexed_packages_count'):
        with open('indexed_packages_count', 'r') as f:
            indexed_count = f.read().strip()
    
    # Generate README
    readme_content = []
    readme_content.append(f"# Build Cycle: {build_id}\n")
    readme_content.append(f"**Status:** {cycle_status}\n")
    readme_content.append(f"**Container:** `{container_image}`\n")
    readme_content.append(f"**Bioconductor Version:** {bioc_version}\n")
    readme_content.append(f"**R Version:** {r_version}\n")
    
    if completion_time:
        readme_content.append(f"**Completed:** {completion_time}\n")
    
    readme_content.append("\n## Summary\n")
    readme_content.append(f"- **Total Packages:** {total_packages}\n")
    readme_content.append(f"- **Successfully Built:** {success_count} ({success_count*100//total_packages if total_packages > 0 else 0}%)\n")
    readme_content.append(f"- **Failed:** {failed_count} ({failed_count*100//total_packages if total_packages > 0 else 0}%)\n")
    readme_content.append(f"- **In Progress:** {in_progress_count}\n")
    readme_content.append(f"- **Not Started:** {not_started_count}\n")
    
    if indexed_count:
        readme_content.append(f"- **Indexed in Repository:** {indexed_count}\n")
    
    # Add progress bar
    if total_packages > 0:
        progress_pct = (success_count + failed_count) * 100 // total_packages
        bar_length = 50
        filled = int(bar_length * progress_pct / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        readme_content.append(f"\n**Progress:** {progress_pct}%\n")
        readme_content.append(f"```\n{bar}\n```\n")
    
    # List successful packages (first 50)
    if successful:
        readme_content.append(f"\n## Successfully Built Packages ({len(successful)})\n")
        successful_sorted = sorted(successful)
        
        readme_content.append("\n| Package | Log | BBS Status |\n")
        readme_content.append("|---------|-----|------------|\n")
        
        if len(successful_sorted) <= 50:
            for pkg in successful_sorted:
                pkg_url = f"https://bioconductor.org/packages/{bioc_version}/bioc/html/{pkg}.html"
                pkg_link = f"[{pkg}]({pkg_url})"
                
                log_path = f"logs/{pkg}/build-success.log"
                if os.path.exists(log_path):
                    log_link = f"[log]({log_path})"
                else:
                    log_link = "N/A"
                
                # Check if we have a cached BBS status that's verified
                bbs = bbs_cache.get(pkg, "Not Found")
                if bioc_version != "Unknown" and (bbs == "Not Found" or pkg not in verified_bbs):
                    bbs = get_bbs_status(pkg, bioc_version)
                    bbs_cache[pkg] = bbs
                    if bbs != "Not Found":
                        verified_bbs.add(pkg)
                
                readme_content.append(f"| {pkg_link} | {log_link} | {bbs} |\n")
        else:
            for pkg in successful_sorted[:25]:
                pkg_url = f"https://bioconductor.org/packages/{bioc_version}/bioc/html/{pkg}.html"
                pkg_link = f"[{pkg}]({pkg_url})"
                
                log_path = f"logs/{pkg}/build-success.log"
                if os.path.exists(log_path):
                    log_link = f"[log]({log_path})"
                else:
                    log_link = "N/A"
                
                # Check if we have a cached BBS status that's verified
                bbs = bbs_cache.get(pkg, "Not Found")
                if bioc_version != "Unknown" and (bbs == "Not Found" or pkg not in verified_bbs):
                    bbs = get_bbs_status(pkg, bioc_version)
                    bbs_cache[pkg] = bbs
                    if bbs != "Not Found":
                        verified_bbs.add(pkg)
                
                readme_content.append(f"| {pkg_link} | {log_link} | {bbs} |\n")
            
            readme_content.append(f"\n*... and {len(successful_sorted) - 50} more ...*\n\n")
            readme_content.append("| Package | Log | BBS Status |\n")
            readme_content.append("|---------|-----|------------|\n")
            
            for pkg in successful_sorted[-25:]:
                pkg_url = f"https://bioconductor.org/packages/{bioc_version}/bioc/html/{pkg}.html"
                pkg_link = f"[{pkg}]({pkg_url})"
                
                log_path = f"logs/{pkg}/build-success.log"
                if os.path.exists(log_path):
                    log_link = f"[log]({log_path})"
                else:
                    log_link = "N/A"
                
                # Check if we have a cached BBS status that's verified
                bbs = bbs_cache.get(pkg, "Not Found")
                if bioc_version != "Unknown" and (bbs == "Not Found" or pkg not in verified_bbs):
                    bbs = get_bbs_status(pkg, bioc_version)
                    bbs_cache[pkg] = bbs
                    if bbs != "Not Found":
                        verified_bbs.add(pkg)
                
                readme_content.append(f"| {pkg_link} | {log_link} | {bbs} |\n")
    
    # List failed packages (all of them)
    if failed:
        readme_content.append(f"\n## Failed Packages ({len(failed)})\n")
        readme_content.append("\n| Package | Log | BBS Status | Failure Reasons |\n")
        readme_content.append("|---------|-----|------------|------------------|\n")
        
        for pkg in sorted(failed):
            pkg_url = f"https://bioconductor.org/packages/{bioc_version}/bioc/html/{pkg}.html"
            pkg_link = f"[{pkg}]({pkg_url})"
            
            log_path = f"logs/{pkg}/build-fail.log"
            if os.path.exists(log_path):
                log_link = f"[log]({log_path})"
            else:
                log_link = "N/A"
            
            # Check if we have a cached BBS status that's verified
            bbs = bbs_cache.get(pkg, "Not Found")
            if bioc_version != "Unknown" and (bbs == "Not Found" or pkg not in verified_bbs):
                bbs = get_bbs_status(pkg, bioc_version)
                bbs_cache[pkg] = bbs
                if bbs != "Not Found":
                    verified_bbs.add(pkg)
            
            # Analyze failure reasons
            reasons = check_failure_reason(log_path)
            reasons_str = "<br>".join(reasons)
            
            readme_content.append(f"| {pkg_link} | {log_link} | {bbs} | {reasons_str} |\n")
    
    # List in-progress packages (first 50)
    in_progress_pkgs = dispatched - successful - failed
    if in_progress_pkgs:
        readme_content.append(f"\n## In Progress ({len(in_progress_pkgs)})\n")
        in_progress_sorted = sorted(in_progress_pkgs)
        if len(in_progress_sorted) <= 50:
            for pkg in in_progress_sorted:
                readme_content.append(f"- ⏳ `{pkg}`\n")
        else:
            for pkg in in_progress_sorted[:50]:
                readme_content.append(f"- ⏳ `{pkg}`\n")
            readme_content.append(f"\n... and {len(in_progress_sorted) - 50} more ...\n")
    
    # List not started packages (first 50)
    not_started_pkgs = set(packages.keys()) - dispatched
    if not_started_pkgs:
        readme_content.append(f"\n## Not Yet Started ({len(not_started_pkgs)})\n")
        not_started_sorted = sorted(not_started_pkgs)
        if len(not_started_sorted) <= 50:
            for pkg in not_started_sorted:
                readme_content.append(f"- ⏸️ `{pkg}`\n")
        else:
            for pkg in not_started_sorted[:50]:
                readme_content.append(f"- ⏸️ `{pkg}`\n")
            readme_content.append(f"\n... and {len(not_started_sorted) - 50} more ...\n")
    
    # Add footer
    readme_content.append(f"\n---\n")
    readme_content.append(f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}*\n")
    if bioc_version != "Unknown":
        readme_content.append(f"*Packages with verified BBS status: {len(verified_bbs)}*\n")
    
    # Write README
    with open('README.md', 'w') as f:
        f.writelines(readme_content)
    
    # Save updated BBS cache
    if bioc_version != "Unknown":
        save_bbs_cache(bbs_cache, verified_bbs)
    
    print(f"README updated for build {build_id}")
    print(f"Success: {success_count}, Failed: {failed_count}, In Progress: {in_progress_count}, Not Started: {not_started_count}")
    if bioc_version != "Unknown":
        print(f"Packages with verified BBS status: {len(verified_bbs)}")

if __name__ == "__main__":
    main()
