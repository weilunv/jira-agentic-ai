#!/usr/bin/env python3
"""
測試 Jira 連接和用戶信息
"""

import os
from dotenv import load_dotenv
from src.agent.jira_client import JiraClient

def test_jira_connection():
    """測試 Jira 連接和基本查詢"""
    load_dotenv()

    # 初始化 Jira 客戶端
    jira_client = JiraClient()

    if not jira_client.jira:
        print("❌ Jira 連接失敗")
        return

    print("✅ Jira 連接成功")

    # 測試當前用戶信息
    try:
        current_user = jira_client.jira.current_user()
        print(f"當前用戶: {current_user}")

        # 獲取用戶詳細信息
        user_info = jira_client.jira.user(current_user)
        print(f"用戶詳細信息:")
        print(f"  - 用戶名: {user_info.name}")
        print(f"  - 顯示名稱: {user_info.displayName}")
        print(f"  - 郵箱: {user_info.emailAddress}")
        print(f"  - 活躍狀態: {user_info.active}")

    except Exception as e:
        print(f"❌ 獲取用戶信息失敗: {e}")

    # 測試基本查詢
    test_queries = [
        "project IS NOT EMPTY ORDER BY updated DESC",
        f"assignee = '{os.getenv('JIRA_USERNAME')}' ORDER BY updated DESC",
        f"reporter = '{os.getenv('JIRA_USERNAME')}' ORDER BY updated DESC",
        f"assignee = currentUser() ORDER BY updated DESC",
        f"reporter = currentUser() ORDER BY updated DESC",
        # 測試組合查詢
        f"(assignee = '{os.getenv('JIRA_USERNAME')}' OR reporter = '{os.getenv('JIRA_USERNAME')}') ORDER BY updated DESC",
        # 測試 commentedBy 語法
        f"commentedBy = '{os.getenv('JIRA_USERNAME')}' ORDER BY updated DESC",
        f"commentedBy = currentUser() ORDER BY updated DESC",
        # 測試時間範圍
        f"created >= '2024-01-01' AND assignee = '{os.getenv('JIRA_USERNAME')}' ORDER BY updated DESC",
        f"created >= '2025-01-01' AND assignee = '{os.getenv('JIRA_USERNAME')}' ORDER BY updated DESC",
        # 測試完整組合查詢
        f"created >= '2024-01-01' AND (assignee = '{os.getenv('JIRA_USERNAME')}' OR reporter = '{os.getenv('JIRA_USERNAME')}') ORDER BY updated DESC",
        f"created >= '2025-01-01' AND created <= '2025-12-31' AND (assignee = '{os.getenv('JIRA_USERNAME')}' OR reporter = '{os.getenv('JIRA_USERNAME')}') ORDER BY updated DESC",
    ]

    for query in test_queries:
        print(f"\n測試查詢: {query}")
        try:
            if jira_client.validate_jql(query):
                results = jira_client.search_issues(query, max_results=5)
                print(f"  ✅ 查詢成功，找到 {len(results)} 個結果")
                if results:
                    for result in results[:2]:  # 顯示前2個結果
                        print(f"    - {result['key']}: {result['summary']}")
            else:
                print(f"  ❌ JQL 語法無效")
        except Exception as e:
            print(f"  ❌ 查詢失敗: {e}")

if __name__ == "__main__":
    test_jira_connection()
