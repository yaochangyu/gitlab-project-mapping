import os
import csv
import subprocess
import shutil
import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
from dotenv import load_dotenv
from urllib.parse import urlparse

# 載入 .env 檔案
load_dotenv()

# GitLab 設定（認證一律由 glab 負責，不需要 PRIVATE_TOKEN）
GITLAB_URL = os.getenv("GITLAB_URL", "https://192.168.1.158/").rstrip('/')

# 專案路徑設定 (本地根目錄)
ROOT_DIR = os.getenv("ROOT_DIR", "/mnt/d/lab/gitlab-work")
CSV_NAME = os.getenv("CSV_NAME", "project_mapping.csv")
CSV_PATH = os.path.join(ROOT_DIR, CSV_NAME)

# 逾時設定 (秒)
CLONE_TIMEOUT = int(os.getenv("CLONE_TIMEOUT", "3600"))
PULL_TIMEOUT = int(os.getenv("PULL_TIMEOUT", "600"))
STALE_LOCK_SECONDS = int(os.getenv("STALE_LOCK_SECONDS", "3600"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "10"))

CSV_FIELDS = ["project_id", "project_name", "project_desc", "project_map_path", "cloned", "timeout", "http_url", "branch"]

# 已知工具暫存資料夾，判斷未提交變更時排除
IGNORED_UNTRACKED_DIRS = (".omc", ".omo", ".claude", ".code-review-graph", ".obsidian", "graphify-out")


def _gitlab_hostname() -> str:
    parsed = urlparse(GITLAB_URL)
    return parsed.hostname or GITLAB_URL


def _git_credential_helper() -> str:
    hostname = _gitlab_hostname()
    return f"!f() {{ GITLAB_HOST={hostname} glab auth git-credential \"$@\"; }}; f"

def get_all_gitlab_projects() -> List[Dict]:
    """從 GitLab API 抓取所有專案資訊"""
    projects = []
    hostname = _gitlab_hostname()

    print(f"正在從 {GITLAB_URL} 抓取專案資訊...")

    cmd = ["glab", "api", "--hostname", hostname, "--paginate", "--output", "ndjson", "projects?simple=true"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"抓取失敗: {result.stderr.strip()}")
        return projects

    try:
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            projects.append(json.loads(line))
    except json.JSONDecodeError as e:
        print(f"抓取失敗: 無法解析 glab 輸出 ({e})")
        return projects

    print(f"已抓取 {len(projects)} 個專案...")
    return projects

def local_path_for(project_name: str) -> str:
    return os.path.join(ROOT_DIR, project_name.lower().replace(" / ", "/"))


def is_cloned(local_path: str) -> bool:
    return os.path.isdir(os.path.join(local_path, ".git"))


def _first_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _index_lock_path(local_path: str) -> str:
    return os.path.join(local_path, ".git", "index.lock")


def _is_stale_index_lock(local_path: str) -> bool:
    lock_path = _index_lock_path(local_path)
    if not os.path.exists(lock_path):
        return False
    return (time.time() - os.path.getmtime(lock_path)) > STALE_LOCK_SECONDS


def _merge_ff_only(local_path: str, ref: str = "@{u}") -> subprocess.CompletedProcess[str]:
    """對已 fetch 過的本地 repo 做 fast-forward merge，不再重複 fetch。"""
    return subprocess.run(
        ["git", "-C", local_path, "merge", "--ff-only", "--quiet", ref],
        capture_output=True,
        check=False,
        text=True,
        timeout=PULL_TIMEOUT,
    )


def _current_branch(local_path: str) -> str:
    result = subprocess.run(
        ["git", "-C", local_path, "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _has_uncommitted_changes(local_path: str) -> bool:
    result = subprocess.run(
        ["git", "-C", local_path, "status", "--porcelain"],
        capture_output=True,
        text=True,
    )
    for line in result.stdout.splitlines():
        status, _, rest = line.partition(" ")
        path = rest.strip()
        if status == "??" and path.split("/")[0] in IGNORED_UNTRACKED_DIRS:
            continue
        if line.strip():
            return True
    return False


def _fetch(local_path: str, cred_helper: str) -> bool:
    result = subprocess.run(
        [
            "git", "-c", "http.sslVerify=false",
            "-c", f"credential.https://{_gitlab_hostname()}.helper={cred_helper}",
            "-C", local_path, "fetch", "--quiet", "origin",
        ],
        capture_output=True,
        text=True,
        timeout=PULL_TIMEOUT,
    )
    return result.returncode == 0


def _resolve_target_branch(local_path: str) -> str:
    """main 優先，其次 master，再其次 Main；本地或 origin 任一存在即可。找不到回傳空字串。"""
    for branch in ("main", "master", "Main"):
        local_ref = subprocess.run(
            ["git", "-C", local_path, "rev-parse", "--verify", "--quiet", branch],
            capture_output=True, text=True,
        )
        remote_ref = subprocess.run(
            ["git", "-C", local_path, "rev-parse", "--verify", "--quiet", f"origin/{branch}"],
            capture_output=True, text=True,
        )
        if local_ref.returncode == 0 or remote_ref.returncode == 0:
            return branch
    return ""


def _checkout_target_branch(local_path: str, target_branch: str) -> bool:
    has_local = subprocess.run(
        ["git", "-C", local_path, "rev-parse", "--verify", "--quiet", target_branch],
        capture_output=True, text=True,
    ).returncode == 0

    if has_local:
        result = subprocess.run(
            ["git", "-C", local_path, "checkout", target_branch],
            capture_output=True, text=True,
        )
    else:
        result = subprocess.run(
            ["git", "-C", local_path, "checkout", "-b", target_branch, f"origin/{target_branch}"],
            capture_output=True, text=True,
        )
    return result.returncode == 0


def ensure_target_branch(local_path: str, p_name: str) -> str:
    """
    依 AGENTS.md「各子專案取分支規則」切到 main/master（找不到條件就跳過，不強制）。
    只負責切換，不 pull。呼叫前必須已完成 fetch。
    回傳用於後續 merge 的 ref："origin/<branch>"，找不到就回傳空字串（呼叫端改用 @{u}）。
    """
    target_branch = _resolve_target_branch(local_path)
    if not target_branch:
        return ""

    if _current_branch(local_path) != target_branch:
        if not _checkout_target_branch(local_path, target_branch):
            print(f"  切換分支失敗: {p_name} -> {target_branch}")
            return ""

    return f"origin/{target_branch}"


def build_rows(projects: List[Dict]) -> List[Dict]:
    rows = []
    for p in projects:
        p_name = p["path_with_namespace"]
        local_path = local_path_for(p_name)
        rows.append({
            "project_id": str(p["id"]),
            "project_name": p_name,
            "project_desc": (p.get("description") or "").replace("\r\n", " ").replace("\n", " "),
            "project_map_path": local_path,
            "cloned": "true" if is_cloned(local_path) else "false",
            "timeout": "false",
            "http_url": p["http_url_to_repo"],
            "branch": _current_branch(local_path) if is_cloned(local_path) else "",
        })
    return rows


def write_csv(rows: List[Dict]) -> None:
    with open(CSV_PATH, mode='w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    cloned_count = sum(1 for r in rows if r["cloned"] == "true")
    print(f"CSV 已輸出：{CSV_PATH}（共 {len(rows)} 個專案，已下載 {cloned_count} 個）")

def _clone_row(row: Dict) -> None:
    local_path = row["project_map_path"]
    p_name = row["project_name"]
    http_url = row["http_url"]
    cred_helper = _git_credential_helper()

    if is_cloned(local_path):
        row["cloned"] = "true"
        row["timeout"] = "false"
        return

    print(f"正在 Clone: {p_name}")
    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    # 目錄存在但不是 git 庫，代表上次 clone 中斷，殘骸會讓 git clone 失敗
    if os.path.exists(local_path):
        shutil.rmtree(local_path, ignore_errors=True)

    try:
        subprocess.run([
            "git", "-c", "http.sslVerify=false",
            "-c", f"credential.https://{_gitlab_hostname()}.helper={cred_helper}",
            "clone", "--quiet", "--depth", "1", http_url, local_path
        ], check=True, timeout=CLONE_TIMEOUT)
        row["cloned"] = "true"
        row["timeout"] = "false"
        row["branch"] = _current_branch(local_path)
    except subprocess.TimeoutExpired:
        print(f"  逾時: {p_name}")
        row["timeout"] = "true"
    except Exception as e:
        print(f"  失敗: {p_name} ({e})")
        row["cloned"] = "false"


def _pull_row(row: Dict, pull_failures: list, lock: threading.Lock) -> None:
    local_path = row["project_map_path"]
    p_name = row["project_name"]
    cred_helper = _git_credential_helper()

    if not is_cloned(local_path):
        return

    has_head = subprocess.run(
        ["git", "-C", local_path, "rev-parse", "--verify", "HEAD"],
        capture_output=True,
        text=True,
    )
    if has_head.returncode != 0:
        print(f"  跳過 Pull（尚未有提交）: {p_name}")
        row["timeout"] = "false"
        row["cloned"] = "true"
        row["branch"] = _current_branch(local_path)
        return

    if _has_uncommitted_changes(local_path):
        print(f"  跳過（未提交變更）: {p_name}")
        row["branch"] = _current_branch(local_path)
        return

    if not _fetch(local_path, cred_helper):
        print(f"  Fetch 失敗: {p_name}")
        with lock:
            pull_failures.append((p_name, "fetch failed"))
        row["branch"] = _current_branch(local_path)
        return

    merge_ref = ensure_target_branch(local_path, p_name) or "@{u}"

    print(f"正在更新: {p_name}")
    try:
        result = _merge_ff_only(local_path, merge_ref)
        if result.returncode != 0 and "index.lock" in (result.stderr or "") and _is_stale_index_lock(local_path):
            try:
                os.remove(_index_lock_path(local_path))
            except FileNotFoundError:
                pass
            result = _merge_ff_only(local_path, merge_ref)

        if result.returncode == 0:
            row["timeout"] = "false"  # 成功則清除逾時標記
        else:
            detail = _first_line(result.stderr or result.stdout or "")
            if not detail:
                detail = "pull failed"
            print(f"  Pull 失敗: {p_name} ({detail})")
            with lock:
                pull_failures.append((p_name, detail))
    except subprocess.TimeoutExpired:
        print(f"  Pull 逾時: {p_name}")
        row["timeout"] = "true"
    finally:
        row["branch"] = _current_branch(local_path)


def git_batch_op(rows: List[Dict], op_type: str = "clone"):
    """
    op_type: "clone" 或 "pull"。MAX_WORKERS 個執行緒平行處理各專案（I/O bound）。
    """
    pull_failures: list = []
    lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        if op_type == "clone":
            futures = [executor.submit(_clone_row, row) for row in rows]
        else:
            futures = [executor.submit(_pull_row, row, pull_failures, lock) for row in rows]

        for future in as_completed(futures):
            future.result()  # 讓 worker 例外在主執行緒拋出，而非靜默吞掉

    if op_type == "pull" and pull_failures:
        print(f"\nPull 失敗摘要：共 {len(pull_failures)} 個專案")
        for p_name, detail in pull_failures:
            print(f"- {p_name}: {detail}")

def main():
    parser = argparse.ArgumentParser(description="GitLab 專案管理整合工具")
    subparsers = parser.add_subparsers(dest="command", help="子指令")

    # Init 指令
    subparsers.add_parser("init", help="初始化：從 API 取得資訊並 Clone 所有專案")

    # Update 指令
    update_parser = subparsers.add_parser("update", help="更新專案資訊或程式碼")
    update_parser.add_argument("--info", action="store_true", help="僅輸出 CSV，不動程式碼")
    update_parser.add_argument("--code", action="store_true", help="對所有專案執行 git pull 並補齊未下載的專案")
    update_parser.add_argument("--all", action="store_true", help="等同 --code（專案清單一律取自 glab）")

    args = parser.parse_args()

    if args.command == "init":
        rows = build_rows(get_all_gitlab_projects())
        git_batch_op(rows, op_type="clone")
        write_csv(rows)
    
    elif args.command == "update":
        rows = build_rows(get_all_gitlab_projects())
        if args.code or args.all:
            git_batch_op(rows, op_type="pull")
            git_batch_op(rows, op_type="clone")
        write_csv(rows)
    else:
        parser.print_help()

if __name__ == "__main__":
    # 停用 SSL 警告
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
