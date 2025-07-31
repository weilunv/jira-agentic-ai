#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from typing import Dict
from dotenv import load_dotenv
from src.agent.query_parser import NaturalLanguageQueryParser
from src.agent.jql_generator import JQLGenerator
from src.agent.jira_client import JiraClient

load_dotenv()

class JiraAgenticAI:
    """Jira Agentic AI 主類"""

    def __init__(self):
        self.parser = NaturalLanguageQueryParser(
            openai_api_key=os.getenv('AZURE_OPENAI_API_KEY')
        )
        self.jql_generator = JQLGenerator()
        try:
            self.jira_client = JiraClient()
        except Exception as e:
            print(f"⚠️  Jira 客戶端初始化失敗: {e}")
            print("請檢查 .env 檔案中的 Jira 配置")
            self.jira_client = None

    def process_query(self, query: str) -> Dict:
        """處理自然語言查詢"""
        print(f"🔍 正在處理查詢: {query}")

        # 1. 解析查詢意圖
        intent = self.parser.parse(query)
        print(f"📝 解析意圖: {intent}")

        # 2. 生成 JQL 查詢
        jql_queries = self.jql_generator.generate_variations(intent)
        print(f"🔧 生成 JQL: {jql_queries}")

        # 3. 執行查詢
        all_results = []
        if self.jira_client:
            for jql in jql_queries:
                if self.jira_client.validate_jql(jql):
                    results = self.jira_client.search_issues(jql)
                    all_results.extend(results)
                else:
                    print(f"⚠️  無效的 JQL: {jql}")
        else:
            print("⚠️  無法執行 Jira 查詢，請檢查 Jira 客戶端配置")

        # 4. 使用 LLM 篩選和排序結果
        filtered_results = self.parser.filter_results(query, all_results)

        return {
            'query': query,
            'intent': intent.dict(),
            'jql_queries': jql_queries,
            'results': filtered_results[:20],  # 限制結果數量
            'total_count': len(filtered_results)
        }

    def format_results(self, response: Dict) -> str:
        """格式化查詢結果"""
        output = []
        output.append(f"🎯 查詢: {response['query']}")
        output.append(f"📊 找到 {response['total_count']} 個工作項目")
        output.append("")

        if response['jql_queries']:
            output.append("🔧 使用的 JQL 查詢:")
            for i, jql in enumerate(response['jql_queries'], 1):
                output.append(f"  {i}. {jql}")
            output.append("")

        if response['results']:
            output.append("📋 查詢結果:")
            for i, issue in enumerate(response['results'][:10], 1):
                output.append(f"{i:2d}. [{issue['key']}] {issue['summary']}")
                output.append(f"    📁 專案: {issue['project']} | 🏷️  類型: {issue['issuetype']}")
                output.append(f"    👤 指派: {issue['assignee'] or '未指派'} | 📅 更新: {issue['updated'][:10]}")
                output.append(f"    🔗 {issue['url']}")
                output.append("")

        return "\n".join(output)

def main():
    """主程式入口"""
    print("🤖 Jira Agentic AI 啟動！")
    print("輸入 'exit' 或 'quit' 結束程式")
    print("=" * 50)

    try:
        ai = JiraAgenticAI()
    except Exception as e:
        print(f"❌ 系統初始化失敗: {e}")
        return

    while True:
        try:
            query = input("\n💬 請輸入您的查詢: ").strip()

            if query.lower() in ['exit', 'quit', '退出']:
                print("👋 再見！")
                break

            if not query:
                continue

            response = ai.process_query(query)
            formatted_output = ai.format_results(response)
            print("\n" + formatted_output)

        except KeyboardInterrupt:
            print("\n\n👋 程式已中斷，再見！")
            break
        except Exception as e:
            print(f"❌ 發生錯誤: {e}")

if __name__ == "__main__":
    main()