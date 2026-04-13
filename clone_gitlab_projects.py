import os
import gitlab
import subprocess
import csv
import urllib3
import shutil
import time
from config import GITLAB_URL, PRIVATE_TOKEN, ROOT_DIR, CSV_PATH

def load_existing_mapping():
    """讀取現有的 CSV 對應表，以便續傳"""
    mapping = {}
    if os.path.exists(CSV_PATH):
        try:
            with open(CSV_PATH, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    mapping[int(row["project id"])] = row
        except Exception:
            pass
    return mapping

def write_csv(mapping_list):
    """將目前的對應列表完整寫入 CSV"""
    with open(CSV_PATH, mode='w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["project id", "project name", "project local path"])
        writer.writeheader()
        writer.writerows(mapping_list)

def clone_projects():
    if not PRIVATE_TOKEN:
        print("錯誤：未設定 PRIVATE_TOKEN。請在 .env 中設定或傳入環境變數。")
        return

    os.makedirs(ROOT_DIR, exist_ok=True)
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    gl = gitlab.Gitlab(GITLAB_URL, private_token=PRIVATE_TOKEN, ssl_verify=False)
    
    # 載入已完成的進度
    existing_mapping = load_existing_mapping()
    mapping_list = list(existing_mapping.values())
    print(f"已載入 {len(existing_mapping)} 個現有記錄，準備續傳...")
    
    try:
        print(f"正在從 {GITLAB_URL} 獲取完整專案列表...")
        projects = gl.projects.list(all=True, iterator=True)
    except Exception as e:
        print(f"無法連線到 GitLab: {e}")
        return

    count = 0
    for project in projects:
        # 如果 ID 已在 CSV 且目錄存在，則快速跳過
        if project.id in existing_mapping:
            local_path = existing_mapping[project.id]["project local path"]
            if os.path.exists(os.path.join(local_path, ".git")):
                continue

        full_path_parts = project.path_with_namespace.split('/')
        group_name = full_path_parts[0]
        project_slug = project.path
        
        local_path = os.path.join(ROOT_DIR, group_name, project_slug)
        parent_dir = os.path.dirname(local_path)
        
        print(f"處理: {group_name}/{project_slug} (ID: {project.id})...")
        
        # 執行克隆 (若不存在)
        if not os.path.exists(os.path.join(local_path, ".git")):
            os.makedirs(parent_dir, exist_ok=True)
            auth_url = project.http_url_to_repo.replace("https://", f"https://oauth2:{PRIVATE_TOKEN}@")
            
            # 如果目錄已存在但非 git repo，清理它
            if os.path.exists(local_path):
                shutil.rmtree(local_path, ignore_errors=True)
                
            try:
                # 設定 120 秒超時，避免卡死在超大型專案
                subprocess.run([
                    "git", "-c", "http.sslVerify=false", 
                    "clone", "--quiet", "--depth", "1", auth_url, local_path
                ], check=True, timeout=120)
                print(f"  [成功]")
            except Exception as e:
                print(f"  [跳過/失敗] {e}")
                if os.path.exists(local_path):
                    shutil.rmtree(local_path, ignore_errors=True)
        
        # 不論克隆成功與否，都記錄到 CSV 中以標記已處理
        if project.id not in existing_mapping:
            new_row = {
                "project id": project.id,
                "project name": project.name,
                "project local path": local_path
            }
            mapping_list.append(new_row)
            existing_mapping[project.id] = new_row
            write_csv(mapping_list)
            count += 1

    print(f"\n任務執行完畢！本次新增 {count} 筆記錄。")
    print(f"總記錄數: {len(mapping_list)}")

if __name__ == "__main__":
    clone_projects()
