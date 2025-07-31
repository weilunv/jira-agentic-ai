# Jira Agentic AI

一個智能的 Jira 工作記錄查詢系統，支援自然語言查詢並自動生成 JQL。

## 功能特色

✅ **智能解析**: 支援中文自然語言查詢
✅ **時間識別**: 自動解析季度、月份、週等時間範圍
✅ **多樣查詢**: 生成多種 JQL 變體確保完整性
✅ **結果整理**: 自動去重和排序查詢結果
✅ **擴展性強**: 可整合 OpenAI 增強解析能力

## 快速開始

### 1. 安裝依賴

```bash
# 創建虛擬環境（推薦）
python3 -m venv venv
source venv/bin/activate

# 安裝依賴
pip install -r requirements.txt
```

### 2. 配置環境

複製 `.env.example` 為 `.env` 並填入您的配置：

```bash
cp .env.example .env
```

編輯 `.env` 檔案：
```bash
JIRA_SERVER_URL=https://your-company.atlassian.net
JIRA_USERNAME=your-email@company.com
JIRA_API_TOKEN=your-api-token

# 可選：OpenAI API 設定（用於增強 NLP）
OPENAI_API_KEY=your-openai-api-key
```

### 3. 取得 Jira API Token

1. 登入您的 Atlassian 帳戶
2. 前往 [https://id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
3. 點擊「Create API token」
4. 複製生成的 token 到 `.env` 檔案

### 4. 執行程式

```bash
python main.py
```

## 查詢範例

- "我 2025 Q1 的 Jira 工作記錄"
- "本月完成的任務"
- "我創建的 Bug"
- "專案 ABC 中我的工作"
- "上週我參與的所有工作"

## 專案結構

```
logline/
├── src/
│   ├── agent/
│   │   ├── query_parser.py    # 自然語言查詢解析
│   │   ├── jql_generator.py   # JQL 查詢生成器
│   │   └── jira_client.py     # Jira API 客戶端
│   ├── models/
│   └── utils/
├── tests/
├── main.py                    # 主程式入口
├── requirements.txt
└── README.md
```

## 開發

### 執行測試

```bash
pytest tests/
```

### 擴展功能

您可以通過以下方式擴展系統：

1. 在 `query_parser.py` 中添加新的時間格式解析
2. 在 `jql_generator.py` 中添加新的 JQL 生成規則
3. 整合更多 NLP 功能來提升解析準確度

## 故障排除

### 常見問題

1. **Python 命令找不到**
   - 使用 `python3` 替代 `python`
   - 或創建虛擬環境後使用 `python`

2. **Jira 連線失敗**
   - 檢查 `.env` 檔案中的配置
   - 確認 API Token 是否正確
   - 確認伺服器 URL 是否可訪問

3. **依賴安裝失敗**
   ```bash
   # 升級 pip
   python3 -m pip install --upgrade pip

   # 分別安裝核心依賴
   pip install jira python-dotenv pydantic arrow click
   ```

## 授權

MIT License
