import os
import csv
import subprocess
import shutil
import requests
import argparse
from typing import List, Dict
from dotenv import load_dotenv

# 載入 .env 檔案
load_dotenv()

# GitLab 設定
GITLAB_URL = os.getenv("GITLAB_URL", "https://192.168.1.158/").rstrip('/')
PRIVATE_TOKEN = os.getenv("PRIVATE_TOKEN", "")

# 專案路徑設定 (本地根目錄)
ROOT_DIR = os.getenv("ROOT_DIR", "/mnt/d/lab/gitlab-work")
CSV_NAME = os.getenv("CSV_NAME", "project_mapping.csv")
CSV_PATH = os.path.join(ROOT_DIR, CSV_NAME)

# 逾時設定 (秒)
CLONE_TIMEOUT = int(os.getenv("CLONE_TIMEOUT", "3600"))
PULL_TIMEOUT = int(os.getenv("PULL_TIMEOUT", "600"))

CSV_FIELDS = ["project_id", "project_name", "project_desc", "project_map_path", "cloned", "timeout", "http_url"]

def get_all_gitlab_projects() -> List[Dict]:
    """從 GitLab API 抓取所有專案資訊"""
    projects = []
    page = 1
    per_page = 100
    
    print(f"正在從 {GITLAB_URL} 抓取專案資訊...")
    while True:
        api_url = f"{GITLAB_URL}/api/v4/projects"
        headers = {"PRIVATE-TOKEN": PRIVATE_TOKEN}
        params = {"page": page, "per_page": per_page, "simple": "true", "membership": "true"}
        
        response = requests.get(api_url, headers=headers, params=params, verify=False)
        if response.status_code != 200:
            print(f"抓取失敗: {response.status_code} - {response.text}")
            break
            
        batch = response.json()
        if not batch:
            break
            
        projects.extend(batch)
        print(f"已抓取 {len(projects)} 個專案...")
        page += 1
        
    return projects

def sync_csv_with_api(projects: List[Dict], overwrite: bool = False):
    """將 API 抓取的專案資訊與 CSV 同步"""
    existing_rows = {}
    if os.path.exists(CSV_PATH) and not overwrite:
        with open(CSV_PATH, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_rows[row["project_id"]] = row

    rows = []
    for p in projects:
        p_id = str(p["id"])
        p_name = p["path_with_namespace"]
        p_desc = (p.get("description") or "").replace("\r\n", " ").replace("\n", " ")
        http_url = p["http_url_to_repo"]
        
        # 決定本地存放路徑邏輯 (保持原有層級結構)
        if p_id in existing_rows:
            local_path = existing_rows[p_id]["project_map_path"]
            cloned = existing_rows[p_id]["cloned"]
            timeout = existing_rows[p_id]["timeout"]
        else:
            # 預設路徑規則: ROOT_DIR / namespace / project_name
            # 但根據 project_mapping.csv 現況調整
            rel_path = p_name.lower().replace(" / ", "/")
            local_path = os.path.join(ROOT_DIR, rel_path)
            cloned = "false"
            timeout = "false"

        rows.append({
            "project_id": p_id,
            "project_name": p_name,
            "project_desc": p_desc,
            "project_map_path": local_path,
            "cloned": cloned,
            "timeout": timeout,
            "http_url": http_url
        })

    with open(CSV_PATH, mode='w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"CSV 已更新，共有 {len(rows)} 個專案。")
    return rows

def git_batch_op(rows: List[Dict], op_type: str = "clone"):
    """
    op_type: "clone" 或 "pull"
    """
    total = len(rows)
    for i, row in enumerate(rows):
        local_path = row["project_map_path"]
        p_name = row["project_name"]
        http_url = row["http_url"]
        
        # 設定認證 URL
        auth_url = http_url.replace("https://", f"https://oauth2:{PRIVATE_TOKEN}@")
        
        if op_type == "clone":
            # 如果已經有 .git 目錄，表示已下載成功，跳過
            if os.path.isdir(os.path.join(local_path, ".git")):
                row["cloned"] = "true"
                row["timeout"] = "false"
                continue
            
            print(f"[{i+1}/{total}] 正在 Clone: {p_name}")
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # 若目錄存在但非 git 庫，先刪除
            if os.path.exists(local_path) and not os.path.isdir(os.path.join(local_path, ".git")):
                shutil.rmtree(local_path, ignore_errors=True)
            
            try:
                subprocess.run([
                    "git", "-c", "http.sslVerify=false", 
                    "clone", "--quiet", "--depth", "1", auth_url, local_path
                ], check=True, timeout=CLONE_TIMEOUT)
                row["cloned"] = "true"
                row["timeout"] = "false"
            except subprocess.TimeoutExpired:
                print(f"  逾時: {p_name}")
                row["timeout"] = "true"
            except Exception as e:
                print(f"  失敗: {p_name} ({e})")
                row["cloned"] = "false"
        
        elif op_type == "pull":
            if not os.path.isdir(os.path.join(local_path, ".git")):
                continue
            
            print(f"[{i+1}/{total}] 正在 Pull: {p_name}")
            try:
                subprocess.run([
                    "git", "-c", "http.sslVerify=false", 
                    "-C", local_path, "pull", "--quiet"
                ], check=True, timeout=PULL_TIMEOUT)
                row["timeout"] = "false" # 成功則清除逾時標記
            except subprocess.TimeoutExpired:
                print(f"  Pull 逾時: {p_name}")
                row["timeout"] = "true"
            except Exception as e:
                print(f"  Pull 失敗: {p_name} ({e})")

    # 最後統一回寫 CSV 狀態 (針對 cloned/timeout)
    with open(CSV_PATH, mode='w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

def main():
    parser = argparse.ArgumentParser(description="GitLab 專案管理整合工具")
    subparsers = parser.add_subparsers(dest="command", help="子指令")

    # Init 指令
    subparsers.add_parser("init", help="初始化：從 API 取得資訊並 Clone 所有專案")

    # Update 指令
    update_parser = subparsers.add_parser("update", help="更新專案資訊或程式碼")
    update_parser.add_argument("--info", action="store_true", help="從 API 更新 CSV 資訊")
    update_parser.add_argument("--code", action="store_true", help="對所有專案執行 git pull")
    update_parser.add_argument("--all", action="store_true", help="更新資訊並更新程式碼")

    args = parser.parse_args()

    if args.command == "init":
        projects = get_all_gitlab_projects()
        rows = sync_csv_with_api(projects, overwrite=True)
        git_batch_op(rows, op_type="clone")
    
    elif args.command == "update":
        rows = []
        if args.info or args.all:
            projects = get_all_gitlab_projects()
            rows = sync_csv_with_api(projects)
        else:
            # 讀取現有 CSV
            if os.path.exists(CSV_PATH):
                with open(CSV_PATH, mode='r', encoding='utf-8-sig') as f:
                    rows = list(csv.DictReader(f))
        
        if args.code or args.all:
            if not rows:
                 if os.path.exists(CSV_PATH):
                    with open(CSV_PATH, mode='r', encoding='utf-8-sig') as f:
                        rows = list(csv.DictReader(f))
            git_batch_op(rows, op_type="pull")
            # 補齊漏掉的 clone (新專案)
            git_batch_op(rows, op_type="clone")
    else:
        parser.print_help()

if __name__ == "__main__":
    # 停用 SSL 警告
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()
