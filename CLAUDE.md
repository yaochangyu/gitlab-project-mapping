# CLAUDE.md

## GitLab 專案抓取規則

- 一律使用 `manage_projects.py` 作為唯一入口，不再使用舊的分散腳本。
- 認證一律透過 `glab`（`glab auth login --hostname <host>`），不使用 `PRIVATE_TOKEN`。
- 執行需透過 uv（系統 `python3` 沒有 `python-dotenv`）：
  - 取得 GitLab 全專案：`uv run python manage_projects.py init`
  - 更新專案資訊：`uv run python manage_projects.py update --info`
  - 更新專案程式碼：`uv run python manage_projects.py update --code`
  - 同步資訊與程式碼：`uv run python manage_projects.py update --all`

## 環境變數

- `GITLAB_URL`
- `ROOT_DIR`
- `CSV_NAME`
- `CLONE_TIMEOUT`
- `PULL_TIMEOUT`

## 資料來源原則

- **glab 是唯一權威來源**：專案清單一律即時來自 `glab api projects`，任何指令都不讀取 CSV。
- **本地 `.git` 目錄是唯一下載狀態依據**：`cloned` 欄位為執行當下的偵測結果，不是歷史記憶。
- **CSV 是最後的產出**：流程結束才寫出一次，代表該次執行的實際狀態快照。

## 輸出

- CSV 預設輸出為 `project_mapping.csv`
- 位置由 `ROOT_DIR` 與 `CSV_NAME` 決定
- 可直接刪除，下次執行會重新產生
