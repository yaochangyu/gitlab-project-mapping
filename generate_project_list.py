import os
import gitlab
import csv
import urllib3
from config import GITLAB_URL, PRIVATE_TOKEN, ROOT_DIR

CSV_PATH = os.path.join(ROOT_DIR, "project_mapping_v2.csv")

def load_existing_mapping():
    mapping = {}
    if os.path.exists(CSV_PATH):
        try:
            # 使用 utf-8-sig 讀取以支援 BOM
            with open(CSV_PATH, mode='r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("project_id"):
                        mapping[int(row["project_id"])] = row
        except Exception as e:
            print(f"讀取現有記錄失敗: {e}")
    return mapping

def generate_list():
    if not PRIVATE_TOKEN:
        print("錯誤：未設定 PRIVATE_TOKEN。")
        return

    os.makedirs(ROOT_DIR, exist_ok=True)
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    gl = gitlab.Gitlab(GITLAB_URL, private_token=PRIVATE_TOKEN, ssl_verify=False)
    
    existing_mapping = load_existing_mapping()
    print(f"載入現有記錄: {len(existing_mapping)} 筆")
    
    print(f"正在從 {GITLAB_URL} 獲取完整專案列表...")
    projects = gl.projects.list(all=True, iterator=True)
    
    project_list = []
    path_counts = {}

    for project in projects:
        group_path = project.path_with_namespace.split('/')[0]
        project_slug = project.path
        local_path = os.path.join(ROOT_DIR, group_path, project_slug)
        
        if local_path in path_counts:
            path_counts[local_path] += 1
            local_path = f"{local_path}_{path_counts[local_path]}"
        else:
            path_counts[local_path] = 0

        display_name = project.name_with_namespace
        project_desc = getattr(project, 'description', '') or ''

        cloned = "false"
        timeout = "false"
        if project.id in existing_mapping:
            cloned = existing_mapping[project.id].get("cloned", "false")
            timeout = existing_mapping[project.id].get("timeout", "false")
            if os.path.exists(os.path.join(local_path, ".git")):
                cloned = "true"

        project_list.append({
            "project_id": project.id,
            "project_name": display_name,
            "project_desc": project_desc,
            "project_map_path": local_path,
            "cloned": cloned,
            "timeout": timeout,
            "http_url": project.http_url_to_repo
        })

    fields = ["project_id", "project_name", "project_desc", "project_map_path", "cloned", "timeout", "http_url"]
    # 使用 utf-8-sig 寫入以解決 Excel 亂碼問題
    with open(CSV_PATH, mode='w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(project_list)
    
    print(f"成功更新專案清單：{CSV_PATH}，共 {len(project_list)} 筆。")

if __name__ == "__main__":
    generate_list()
