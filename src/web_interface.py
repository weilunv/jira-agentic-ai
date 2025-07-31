import os
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv
from src.agent.natural_language_agent import NaturalLanguageAgent
from src.agent.jira_client import JiraClient

load_dotenv()

app = Flask(__name__)

# 初始化 Jira 客戶端和自然語言代理
JIRA_SERVER = os.getenv("JIRA_SERVER")
JIRA_USERNAME = os.getenv("JIRA_USERNAME")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not all([JIRA_SERVER, JIRA_USERNAME, JIRA_API_TOKEN]):
    print("錯誤: 請在 .env 檔案中配置 JIRA_SERVER, JIRA_USERNAME, JIRA_API_TOKEN")
    jira_client = None
else:
    try:
        jira_client = JiraClient(JIRA_SERVER, JIRA_USERNAME, JIRA_API_TOKEN)
    except Exception as e:
        print(f"Jira 客戶端初始化失敗: {e}")
        jira_client = None

# 修改環境變數檢查
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_DEPLOYMENT_NAME = os.getenv("AZURE_DEPLOYMENT_NAME")
OPENAI_API_VERSION = os.getenv("OPENAI_API_VERSION")

if not all([AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_DEPLOYMENT_NAME, OPENAI_API_VERSION]):
    print("警告: Azure OpenAI 設定未完整配置，部分 AI 功能（如 OKR 處理）將受限。")

try:
    agent = NaturalLanguageAgent(jira_client=jira_client, openai_api_key=AZURE_OPENAI_API_KEY)
except Exception as e:
    print(f"NaturalLanguageAgent 初始化失敗: {e}")
    agent = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/search', methods=['POST'])
def search():
    if not jira_client or not agent:
        return jsonify({'error': '服務未正確初始化，請檢查後端日誌或配置。'}), 500

    data = request.get_json()
    query = data.get('query')

    if not query:
        return jsonify({'error': '請提供查詢內容'}), 400

    try:
        # 使用代理來處理自然語言查詢
        results, jql_queries = agent.process_query(query)
        formatted_results = []
        for issue in results:
            formatted_results.append({
                'key': issue.key,
                'summary': issue.fields.summary,
                'project': issue.fields.project.name,
                'issuetype': issue.fields.issuetype.name,
                'status': issue.fields.status.name,
                'assignee': issue.fields.assignee.displayName if issue.fields.assignee else '未指派',
                'updated': issue.fields.updated,
                'url': f"{JIRA_SERVER}/browse/{issue.key}"
            })

        return jsonify({
            'query': query,
            'total_count': len(formatted_results),
            'results': formatted_results,
            'jql_queries': jql_queries
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # 嘗試從環境變量獲取端口，如果沒有則使用 8080
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=True, host='0.0.0.0', port=port)