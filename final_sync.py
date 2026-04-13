import os
import csv
import subprocess
import shutil
from config import ROOT_DIR, CSV_PATH, PRIVATE_TOKEN

CSV_FIELDS = ["project_id", "project_name", "project_map_path", "cloned", "timeout", "http_url"]

def final_sync():
    if not PRIVATE_TOKEN:
        print("錯誤：未設定 PRIVATE_TOKEN。")
        return

    if not os.path.exists(CSV_PATH):
        print(f"錯誤：找不到 {CSV_PATH}")
        return

    rows = []
    with open(CSV_PATH, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total = len(rows)
    changed = False

    for i, row in enumerate(rows):
        local_path = row["project_map_path"]
        
        # 檢查是否其實已經克隆好了
        if os.path.isdir(os.path.join(local_path, ".git")):
            if row["cloned"] != "true":
                row["cloned"] = "true"
                row["timeout"] = "false"
                changed = True
            continue

        # 如果沒下載好，嘗試下載
        p_name = row["project_name"]
        print(f"[{i+1}/{total}] 重新同步: {p_name}...")
        
        if os.path.exists(local_path):
            shutil.rmtree(local_path, ignore_errors=True)
        
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        auth_url = row["http_url"].replace("https://", f"https://oauth2:{PRIVATE_TOKEN}@")
        
        try:
            subprocess.run([
                "git", "-c", "http.sslVerify=false", 
                "-c", "http.postBuffer=1073741824",
                "clone", "--quiet", "--depth", "1", auth_url, local_path
            ], check=True)
            row["cloned"] = "true"
            row["timeout"] = "false"
            print("  [成功]")
        except Exception as e:
            print(f"  [失敗] {e}")
            row["cloned"] = "false"
            # 這裡不主動標記 timeout，讓使用者決定
        
        # 每次有變更就存檔
        with open(CSV_PATH, mode='w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    print("同步完成。")

if __name__ == "__main__":
    final_sync()
