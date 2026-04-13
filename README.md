# GitLab Project Mapping Tool

這個工具組旨在自動化管理 GitLab 專案的克隆（Clone）與目錄對應，並產生結構化的專案列表。

## 功能特點
- **自動克隆**：遍歷 GitLab 上的所有專案並自動執行克隆。
- **續傳支援**：透過 CSV 對應表記錄進度，支援中斷後續傳。
- **目錄組織**：依據 GitLab 的 Namespace 自動建立本地目錄結構。
- **對應表管理**：產生並同步 `project_id`, `project_name`, `local_path` 的對應表。
- **uv 管理**：使用 [uv](https://github.com/astral-sh/uv) 進行快速且可靠的 Python 專案管理。

## 快速開始

### 1. 安裝環境
確保您已安裝 `uv`，然後執行：
```bash
uv sync
```

### 2. 設定環境變數
複製 `.env.example` 為 `.env` 並填入您的資訊：
```bash
cp .env.example .env
```

### 3. 執行腳本
使用 `uv run` 執行對應的任務：
- **初次克隆所有專案**：
  ```bash
  uv run clone_gitlab_projects.py
  ```
- **產生詳細專案清單**：
  ```bash
  uv run generate_project_list.py
  ```
- **同步遺漏的克隆任務**：
  ```bash
  uv run sync_projects_from_csv.py
  ```

## 注意事項
- **機敏資料**：請勿將 `project_mapping.csv` 或 `.env` 檔案上傳至版控。
- **SSL 驗證**：本工具預設關閉 SSL 驗證，適用於內部自行架設的 GitLab。
- **Token 權限**：請確保您的 Private Token 具有讀取專案（api）的權限。

## 專案結構
```text
gitlab-project-mapping/
├── pyproject.toml             # uv 專案定義
├── uv.lock                    # uv 鎖定檔
├── clone_gitlab_projects.py   # 核心克隆邏輯
├── generate_project_list.py   # 產生詳細對應清單
├── sync_projects_from_csv.py  # 依據清單同步克隆
├── final_sync.py              # 最後檢查與補齊
├── config.py                  # 設定讀取模組
├── .env.example               # 環境變數範例
└── .gitignore                 # 版控排除規則
```
