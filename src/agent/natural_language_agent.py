from src.agent.query_parser import NaturalLanguageQueryParser, QueryIntent
from src.agent.jql_generator import JQLGenerator
from src.agent.jira_client import JiraClient
from typing import List, Tuple, Any

class NaturalLanguageAgent:
    """自然語言代理，協調查詢解析、JQL 生成和 Jira 互動"""

    def __init__(self, jira_client: JiraClient, openai_api_key: str = None):
        self.query_parser = NaturalLanguageQueryParser(openai_api_key=openai_api_key)
        self.jql_generator = JQLGenerator()
        self.jira_client = jira_client

    def process_query(self, query: str) -> Tuple[List[Any], List[str]]:
        """
        處理自然語言查詢，返回 Jira 任務和使用的 JQL 查詢列表。
        """
        if not self.jira_client or not self.jira_client.jira:
            raise Exception("Jira 客戶端未初始化或連接失敗。")

        # 1. 解析自然語言查詢，獲取意圖和實體
        intent: QueryIntent = self.query_parser.parse(query)
        print(f"解析到的意圖: {intent.intent_type}, 實體: {intent.entities}")

        # 2. 根據意圖生成 JQL 查詢
        jql_queries = self.jql_generator.generate_variations(intent)
        print(f"生成的 JQL 查詢變體: {jql_queries}")

        all_issues = []
        unique_issue_keys = set()

        # 3. 執行 JQL 查詢並獲取結果
        for jql in jql_queries:
            try:
                issues = self.jira_client.search_issues(jql)
                for issue in issues:
                    if issue.key not in unique_issue_keys:
                        all_issues.append(issue)
                        unique_issue_keys.add(issue.key)
            except Exception as e:
                print(f"執行 JQL 查詢失敗: {jql} - {e}")
                # 可以在這裡選擇是否繼續執行其他 JQL 變體

        # 對結果進行排序 (例如按更新時間倒序)
        all_issues.sort(key=lambda issue: issue.fields.updated, reverse=True)

        return all_issues, jql_queries