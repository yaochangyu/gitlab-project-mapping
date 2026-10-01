# GitLab 專案管理整合工具 (GitLab Project Mapping Tool)

本工具旨在提供一個統一的介面，用於自動化管理 GitLab 專案的資訊同步、本地目錄對應及批次程式碼更新。

## 🚀 功能特點

- **整合管理**: 使用單一腳本 `manage_projects.py` 取代多個零散腳本。
- **glab 認證**: API 查詢與 git clone/pull 全部透過 `glab` 認證，不需要在 `.env` 存放 Private Token。
- **glab 為唯一來源**: 專案清單一律即時取自 GitLab API，不讀取 CSV；下載狀態一律以本地 `.git` 目錄為準。
- **CSV 為最終產出**: `project_mapping.csv` 是流程結束才寫出的狀態快照，可隨時刪除重建。
- **批次克隆 (Clone)**: 支援大批量專案的初次下載，具備逾時處理與自動重試機制。
- **批次更新 (Pull)**: 一鍵更新所有已下載專案的程式碼，並自動補齊尚未下載的新專案。
- **逾時容忍**: 針對大型專案，`clone` 逾時上限放寬至 1 小時，`pull` 上限為 10 分鐘。
- **斷點續傳**: 已有 `.git` 的專案自動跳過 clone，僅針對失敗或新專案進行處理。

## 🛠️ 安裝與設定

### 1. 安裝 Python 環境
本專案使用 [uv](https://github.com/astral-sh/uv) 管理相依套件：

```bash
uv sync
```

### 2. 安裝並登入 glab
本工具的認證完全依賴 `glab`，請先完成登入：

```bash
glab auth login --hostname 192.168.1.158
# 確認登入狀態
glab auth status
```

### 3. 配置環境變數
複製範例檔並依實際環境調整：

```bash
cp .env.example .env
```

`.env` 範例內容（**不需要 Token**）：
```env
GITLAB_URL=https://your-gitlab-url.com/
ROOT_DIR=/path/to/your/workspace
CSV_NAME=project_mapping.csv
CLONE_TIMEOUT=3600
PULL_TIMEOUT=600
```

## 📖 使用說明

使用 `manage_projects.py` 進行操作：

### 1. 初始化 (Init)
取得 GitLab 所有專案資訊並執行第一次的批次克隆：
```bash
uv run python manage_projects.py init
```

### 2. 更新 (Update)
所有指令都會先向 glab 取得最新專案清單，差別只在要不要動程式碼：

- **僅輸出 CSV（不動程式碼）**:
  ```bash
  uv run python manage_projects.py update --info
  ```
- **更新程式碼（pull + 補齊未下載的專案）**:
  ```bash
  uv run python manage_projects.py update --code
  ```
- **`--all`**: 等同 `--code`（清單本來就一律取自 glab）
  ```bash
  uv run python manage_projects.py update --all
  ```

### 3. 背景執行 (推薦)
由於專案數量可能較多，建議在背景執行並記錄日誌：
```bash
nohup uv run python manage_projects.py update --all > sync.log 2>&1 &
# 查看進度
tail -f sync.log
```

## 📂 專案結構
```text
gitlab-project-mapping/
├── manage_projects.py    # 核心管理工具 (唯一入口)
├── .env                  # 個人環境設定 (不入版控)
├── .env.example          # 環境設定範例
└── .archive/             # 舊有腳本封存區 (含已停用的 config.py)

<ROOT_DIR>/
└── project_mapping.csv   # 執行後產出的狀態快照（可刪除，下次執行重建）
```

## ⚠️ 注意事項
- **認證**: 請確保 `glab auth status` 對目標 GitLab 主機顯示已登入；Token 由 glab 自行保管，本專案不再讀取 `PRIVATE_TOKEN`。
- **SSL 驗證**: 本工具預設關閉 SSL 驗證，適用於內部自行架設（self-signed 憑證）的 GitLab 環境。
- **磁碟空間**: 執行全量克隆前，請確保目標磁碟有足夠的儲存空間。
