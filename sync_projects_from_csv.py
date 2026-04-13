import os
import csv
import subprocess
import shutil
import time
from config import ROOT_DIR, CSV_PATH, PRIVATE_TOKEN

CSV_FIELDS = ["project_id", "project_name", "project_desc", "project_map_path", "cloned", "timeout", "http_url"]

def sync_clones():
    if not PRIVATE_TOKEN:
        print("錯誤：未設定 PRIVATE_TOKEN。")
        return

    if not os.path.exists(CSV_PATH):
        print(f"錯誤：找不到 {CSV_PATH}")
        return

    rows = []
    # 使用 utf-8-sig 讀取
    with open(CSV_PATH, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total = len(rows)
    for i, row in enumerate(rows):
        local_path = row["project_map_path"]
        if row.get("cloned", "").lower() == "true" and os.path.isdir(os.path.join(local_path, ".git")):
            continue
        
        if row.get("timeout", "").lower() == "true":
            continue

        p_id = row["project_id"]
        p_name = row["project_name"]
        http_url = row["http_url"]
        
        print(f"[{i+1}/{total}] 正在同步: {p_name}")
        auth_url = http_url.replace("https://", f"https://oauth2:{PRIVATE_TOKEN}@")
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        if os.path.exists(local_path) and not os.path.isdir(os.path.join(local_path, ".git")):
            shutil.rmtree(local_path, ignore_errors=True)
            
        success = False
        timed_out = False
        try:
            subprocess.run([
                "git", "-c", "http.sslVerify=false", 
                "-c", "http.postBuffer=1073741824",
                "clone", "--quiet", "--depth", "1", auth_url, local_path
            ], check=True, timeout=300)
            success = True
        except subprocess.TimeoutExpired:
            timed_out = True
        except Exception:
            pass

        row["cloned"] = "true" if success else "false"
        row["timeout"] = "true" if timed_out else "false"
        
        if success or timed_out:
            # 使用 utf-8-sig 寫入
            with open(CSV_PATH, mode='w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                writer.writeheader()
                writer.writerows(rows)

if __name__ == "__main__":
    sync_clones()
