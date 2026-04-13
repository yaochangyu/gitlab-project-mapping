# GitLab 專案管理整合工具 (GitLab Project Mapping Tool)

本工具旨在提供一個統一的介面，用於自動化管理 GitLab 專案的資訊同步、本地目錄對應及批次程式碼更新。

## 🚀 功能特點

- **整合管理**: 使用單一腳本 `manage_projects.py` 取代多個零散腳本。
- **資訊同步**: 自動從 GitLab API 抓取所有專案描述，並同步至本地 `project_mapping.csv`。
- **批次克隆 (Clone)**: 支援大批量專案的初次下載，具備逾時處理與自動重試機制。
- **批次更新 (Pull)**: 一鍵更新所有已下載專案的程式碼。
- **逾時容忍**: 針對大型專案，`clone` 逾時上限放寬至 1 小時，`pull` 上限為 10 分鐘。
- **斷點續傳**: 記錄同步狀態，執行時自動跳過已成功的專案，僅針對失敗或新專案進行處理。

## 🛠️ 安裝與設定

### 1. 安裝環境
確保您的系統已安裝 Python 3。本工具依賴 `requests` 與 `python-dotenv`：

```bash
# Ubuntu/Debian 系統
sudo apt-get update
sudo apt-get install -y python3-dotenv python3-requests
```

### 2. 配置環境變數
在專案根目錄建立 `.env` 檔案，並填入您的 GitLab 認證資訊：

```bash
cp .env.example .env
# 編輯 .env 填入您的 PRIVATE_TOKEN
```

`.env` 範例內容：
```env
GITLAB_URL=https://your-gitlab-url.com/
PRIVATE_TOKEN=your_private_token_here
ROOT_DIR=/path/to/your/workspace
CLONE_TIMEOUT=3600
PULL_TIMEOUT=600
```

## 📖 使用說明

使用 `manage_projects.py` 進行操作：

### 1. 初始化 (Init)
取得 GitLab 所有專案資訊並執行第一次的批次克隆：
```bash
python3 manage_projects.py init
```

### 2. 更新 (Update)
您可以根據需求選擇更新資訊或程式碼：

- **僅更新專案資訊 (CSV)**:
  ```bash
  python3 manage_projects.py update --info
  ```
- **僅更新程式碼 (git pull)**:
  ```bash
  python3 manage_projects.py update --code
  ```
- **全量更新 (資訊 + 程式碼)**:
  ```bash
  python3 manage_projects.py update --all
  ```

### 3. 背景執行 (推薦)
由於專案數量可能較多，建議在背景執行並記錄日誌：
```bash
nohup python3 manage_projects.py update --all > sync.log 2>&1 &
# 查看進度
tail -f sync.log
```

## 📂 專案結構
```text
/
├── manage_projects.py    # 核心管理工具 (整合後)
├── project_mapping.csv   # 專案對應與狀態記錄表
├── .env                  # 個人設定與 Token (不入版控)
├── .archive/             # 舊有腳本封存區
└── gitlab-project-mapping/ # 本工具的 Git 儲存庫
```

## ⚠️ 注意事項
- **Token 權限**: 請確保您的 Private Token 具有 `api` 與 `read_repository` 權限。
- **SSL 驗證**: 本工具預設關閉 SSL 驗證，適用於內部自行架設的 GitLab 環境。
- **磁碟空間**: 執行全量克隆前，請確保目標磁碟有足夠的儲存空間。
