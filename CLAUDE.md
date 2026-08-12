# CLAUDE.md

## GitLab 專案抓取規則

- 一律使用 `manage_projects.py` 作為唯一入口，不再使用舊的分散腳本。
- 取得 GitLab 全專案時，使用：`python3 manage_projects.py init`
- 更新專案資訊時，使用：`python3 manage_projects.py update --info`
- 更新專案程式碼時，使用：`python3 manage_projects.py update --code`
- 同步資訊與程式碼時，使用：`python3 manage_projects.py update --all`

## 環境變數

- `GITLAB_URL`
- `PRIVATE_TOKEN`
- `ROOT_DIR`
- `CSV_NAME`
- `CLONE_TIMEOUT`
- `PULL_TIMEOUT`

## 輸出

- CSV 預設輸出為 `project_mapping.csv`
- 位置由 `ROOT_DIR` 與 `CSV_NAME` 決定
