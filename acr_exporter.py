#!/usr/bin/env python3

import subprocess
import threading
import time
import json
import re
import traceback
import sys
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta

PORT = 9101
_metrics_lock = threading.Lock()
_metrics_data = ""
_last_error = ""

def sanitize_repo_name(repo_name):
    return re.sub(r"[^a-zA-Z0-9_]", "_", repo_name)

def extract_root_repo(repo_path):
    return repo_path.split("/")[0] if "/" in repo_path else repo_path

def azure_sp_login():
    print("[INFO] Logging into Azure using service principal...")
    try:
        result = subprocess.run([
            "az", "login", "--service-principal",
            "-u", os.environ["AZURE_CLIENT_ID"],
            "-p", os.environ["AZURE_CLIENT_SECRET"],
            "--tenant", os.environ["AZURE_TENANT_ID"]
        ], capture_output=True, text=True, check=True)
        print("[INFO] Azure login successful.")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Azure login failed:\n{e.stderr}")
        sys.exit(1)
    except KeyError as e:
        print(f"[ERROR] Missing required environment variable: {e}")
        sys.exit(1)

def fetch_acr_metrics(acr_name, refresh_interval):
    global _metrics_data, _last_error

    while True:
        start_time = time.time()

        try:
            print(f"[INFO] Fetching ACR repository metrics from '{acr_name}'...")
            repos_cmd = ["az", "acr", "repository", "list", "--name", acr_name, "-o", "tsv"]
            repos_result = subprocess.run(repos_cmd, capture_output=True, text=True)
            if repos_result.returncode != 0:
                _last_error = f"az acr repository list failed: {repos_result.stderr.strip()}"
                print(f"[ERROR] {_last_error}")
                time.sleep(refresh_interval)
                continue

            repos = repos_result.stdout.strip().splitlines()
            repo_count = len(repos)

            current_metrics_lines = [
                '# HELP acr_repositories_count Total number of repositories in the ACR',
                '# TYPE acr_repositories_count gauge',
                f'acr_repositories_count {repo_count}',
                '',
                '# HELP acr_repository_storage_bytes Total storage used per ACR repository in bytes',
                '# TYPE acr_repository_storage_bytes gauge',
            ]

            with _metrics_lock:
                _metrics_data = "\n".join(current_metrics_lines) + "\n"

            for idx, full_repo_path in enumerate(repos, start=1):
                print(f"[INFO] Processing repo {idx}/{repo_count}: {full_repo_path}")

                manifests_cmd = [
                    "az", "acr", "manifest", "list-metadata",
                    "-r", acr_name,
                    "-n", full_repo_path,
                    "-o", "json"
                ]
                manifests_result = subprocess.run(manifests_cmd, capture_output=True, text=True)
                if manifests_result.returncode != 0:
                    print(f"[ERROR] Manifest fetch failed for '{full_repo_path}': {manifests_result.stderr.strip()}")
                    continue

                try:
                    manifests = json.loads(manifests_result.stdout)
                except json.JSONDecodeError as e:
                    print(f"[ERROR] Failed to parse JSON for '{full_repo_path}': {e}")
                    continue

                total_size = 0
                for manifest in manifests:
                    total_size += manifest.get("imageSize", 0)

                root_repo = sanitize_repo_name(extract_root_repo(full_repo_path))
                metric_line = f'acr_repository_storage_bytes{{repository="{root_repo}", path="{full_repo_path}"}} {total_size}'

                with _metrics_lock:
                    _metrics_data += metric_line + "\n"

            duration = time.time() - start_time
            print(f"[INFO] Completed metrics update in {duration:.2f} seconds.")
            next_run = datetime.now() + timedelta(seconds=refresh_interval)
            print(f"[INFO] Next metrics fetch scheduled at: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")

            scrape_duration_metric = [
                '# HELP acr_metrics_scrape_duration_seconds Duration of the last metrics scrape in seconds',
                '# TYPE acr_metrics_scrape_duration_seconds gauge',
                f'acr_metrics_scrape_duration_seconds {duration:.2f}'
            ]

            with _metrics_lock:
                _metrics_data += "\n" + "\n".join(scrape_duration_metric) + "\n"
                _last_error = ""

        except Exception:
            _last_error = traceback.format_exc()
            print(f"[ERROR] Unexpected error:\n{_last_error}")

        time.sleep(refresh_interval)

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            with _metrics_lock:
                data = _metrics_data.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404)
            self.end_headers()

def main():
    acr_name = os.getenv("ACR_NAME")
    refresh_interval_str = os.getenv("REFRESH_INTERVAL")

    if not acr_name:
        print("[ERROR] Environment variable ACR_NAME not set")
        sys.exit(1)

    try:
        refresh_interval = int(refresh_interval_str) if refresh_interval_str else 60
        if refresh_interval < 5:
            raise ValueError("Refresh interval must be >= 5")
    except ValueError as e:
        print(f"[ERROR] Invalid REFRESH_INTERVAL: {e}")
        sys.exit(1)

    azure_sp_login()

    thread = threading.Thread(target=fetch_acr_metrics, args=(acr_name, refresh_interval), daemon=True)
    thread.start()

    server = HTTPServer(("", PORT), MetricsHandler)
    print(f"[INFO] Serving metrics on http://0.0.0.0:{PORT}/metrics")
    server.serve_forever()

if __name__ == "__main__":
    main()
