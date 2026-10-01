import os
from dotenv import load_dotenv

# 載入 .env 檔案
load_dotenv()

# GitLab 設定
GITLAB_URL = os.getenv("GITLAB_URL", "https://192.168.1.158/")
PRIVATE_TOKEN = os.getenv("PRIVATE_TOKEN", "")

# 專案路徑設定
ROOT_DIR = os.getenv("ROOT_DIR", "/mnt/d/gitlab")
CSV_NAME = os.getenv("CSV_NAME", "project_mapping.csv")
CSV_PATH = os.path.join(ROOT_DIR, CSV_NAME)

# 驗證必要設定
if not PRIVATE_TOKEN:
    print("警告：未設定 PRIVATE_TOKEN，請在 .env 檔案中設定或匯入環境變數。")
