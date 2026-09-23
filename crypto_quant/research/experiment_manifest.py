# -*- coding: utf-8 -*-
"""
Automated Quantitative Experiment Manifest Generator
=====================================================
Generates reproducible, machine-readable manifest capturing:
- Git Commit Hash & Git Dirty Status (exact code snapshot).
- SHA256 Hashes of all input market data parquets (data immutability verification).
- Strategy parameters, cost assumptions, universe definition.
- Exact CLI invocation command line.
- Formal Experiment Classification Role:
  - OFFICIAL_BASELINE: Core-4 1.0x Spot with standard frictions.
  - HYPOTHESIS_EXPERIMENT: Controlled parameter/universe ablation.
  - DEVELOPMENT_STRESS_TEST: Observed development and stress intervals (e.g. 2026).
"""

import sys
import os
import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
import json


def get_git_info() -> Dict[str, Any]:
    """Retrieves current Git commit hash, branch, and working tree dirty status."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        commit = "UNKNOWN_NO_GIT"

    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        branch = "UNKNOWN"

    try:
        status = subprocess.check_output(
            ["git", "status", "--porcelain", "-uno"], stderr=subprocess.DEVNULL
        ).decode().strip()
        is_dirty = bool(status)
    except Exception:
        is_dirty = False

    return {
        "commit_hash": commit,
        "branch": branch,
        "is_dirty": is_dirty,
    }


def compute_file_sha256(filepath: str) -> Optional[str]:
    """Computes SHA256 checksum of a given file."""
    p = Path(filepath)
    if not p.is_file():
        return None
    hasher = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_environment_dependencies() -> Dict[str, str]:
    """Captures versions of key installed packages and environment snapshot."""
    import importlib.metadata
    packages = {}
    key_pkgs = [
        "pandas", "numpy", "scipy", "pyarrow", "pytest", "flask", 
        "requests", "pydantic", "matplotlib", "fastapi", "uvicorn"
    ]
    for pkg in key_pkgs:
        try:
            packages[pkg] = importlib.metadata.version(pkg)
        except Exception:
            pass
    return packages


def compute_output_hashes(output_dir: str, filenames: Optional[List[str]] = None) -> Dict[str, str]:
    """Computes SHA256 checksums of generated output files in the experiment output directory."""
    out_path = Path(output_dir)
    if not out_path.exists():
        return {}
    if filenames is None:
        filenames = ["trades.csv", "bar_ledger.csv", "summary.json", "data_admission_report.json"]
    hashes = {}
    for fname in filenames:
        fpath = out_path / fname
        if fpath.exists():
            hashes[fname] = compute_file_sha256(str(fpath))
    return hashes


def finalize_manifest_with_outputs(manifest_path: str, output_hashes: Dict[str, str]) -> None:
    """Updates the saved manifest with output file hashes."""
    p = Path(manifest_path)
    if not p.exists():
        return
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["output_hashes"] = output_hashes
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def generate_experiment_manifest(
    experiment_id: str,
    universe: List[str],
    data_files: Dict[str, str],
    parameters: Dict[str, Any],
    eval_start_dt: str,
    eval_end_dt: str,
    role: str = "HYPOTHESIS_EXPERIMENT",
    description: str = "",
    hypothesis: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Constructs a comprehensive experiment manifest dictionary.
    Enforces research disciplines:
    - If role is OFFICIAL_BASELINE, git_dirty MUST be False.
    - Captures environment dependencies snapshot.
    - Records pre-registered hypothesis.
    """
    valid_roles = ["OFFICIAL_BASELINE", "HYPOTHESIS_EXPERIMENT", "DEVELOPMENT_STRESS_TEST"]
    if role not in valid_roles:
        raise ValueError(f"Invalid experiment role '{role}'. Must be one of {valid_roles}")

    git_info = get_git_info()
    if role == "OFFICIAL_BASELINE" and git_info["is_dirty"]:
        raise ValueError(
            "Research Discipline Violation: An OFFICIAL_BASELINE experiment can only be generated "
            "from a clean Git working tree (git_dirty == False). Please commit or stash your changes before running."
        )

    data_hashes = {sym: compute_file_sha256(path) for sym, path in data_files.items()}
    dependencies = get_environment_dependencies()

    manifest = {
        "manifest_version": "1.1.0",
        "experiment_id": experiment_id,
        "experiment_role": role,
        "description": description,
        "pre_registered_hypothesis": hypothesis,
        "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "command_line": " ".join(sys.argv),
        "code_environment": {
            "git_commit": git_info["commit_hash"],
            "git_branch": git_info["branch"],
            "git_dirty": git_info["is_dirty"],
            "python_version": sys.version.split()[0],
            "dependencies": dependencies,
        },
        "universe": universe,
        "data_input_hashes": data_hashes,
        "output_hashes": {},
        "time_interval": {
            "eval_start_dt": eval_start_dt,
            "eval_end_dt": eval_end_dt,
            "semantics": "[eval_start_dt, eval_end_dt) UTC half-open interval",
        },
        "parameters": parameters,
        "extra_metadata": extra_metadata or {},
    }
    return manifest


def save_manifest(manifest: Dict[str, Any], output_path: str) -> None:
    """Saves manifest to JSON formatted file."""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

