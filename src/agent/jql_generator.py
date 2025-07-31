from typing import List, Optional, Any
from .query_parser import QueryIntent

class JQLGenerator:
    """JQL 查詢語句生成器"""

    def generate(self, intent: QueryIntent) -> str:
        """根據查詢意圖生成 JQL"""
        jql_parts = []
        entities = intent.entities

        # 時間範圍
        if 'time_range' in entities:
            start_date, end_date = entities['time_range']
            jql_parts.append(f"created >= '{start_date}' AND created <= '{end_date}'")

        # 指派人
        if 'assignee' in entities:
            if entities['assignee'] == 'currentUser()':
                jql_parts.append("assignee = currentUser()")
            else:
                jql_parts.append(f"assignee = '{entities['assignee']}'")

        # 報告人
        if 'reporter' in entities:
            if entities['reporter'] == 'currentUser()':
                jql_parts.append("reporter = currentUser()")
            else:
                jql_parts.append(f"reporter = '{entities['reporter']}'")

        # 專案
        if 'project' in entities:
            print(f"JQL 生成器接收到項目條件: {entities['project']}")
            jql_parts.append(f"project = '{entities['project']}'")
        else:
            print("JQL 生成器未接收到項目條件")

        # 工作項目類型
        if 'issue_type' in entities:
            issue_types = entities['issue_type']
            if isinstance(issue_types, str):
                jql_parts.append(f"issuetype = '{issue_types}'")
            elif len(issue_types) == 1:
                jql_parts.append(f"issuetype = '{issue_types[0]}'")
            else:
                types = "', '".join(issue_types)
                jql_parts.append(f"issuetype IN ('{types}')")

        # 狀態
        if 'status' in entities:
            statuses = entities['status']
            if isinstance(statuses, str):
                jql_parts.append(f"status = '{statuses}'")
            elif len(statuses) == 1:
                jql_parts.append(f"status = '{statuses[0]}'")
            else:
                status_list = "', '".join(statuses)
                jql_parts.append(f"status IN ('{status_list}')")

        # 優先級
        if 'priority' in entities:
            jql_parts.append(f"priority = '{entities['priority']}'")

        # 關鍵字搜尋
        if 'keywords' in entities:
            keywords = entities['keywords']
            if isinstance(keywords, str):
                keywords = [keywords]
            keyword_conditions = []
            for keyword in keywords:
                keyword_conditions.append(f"text ~ '{keyword}'")
            if keyword_conditions:
                jql_parts.append(f"({' OR '.join(keyword_conditions)})")

        # 根據意圖類型添加預設條件
        if intent.intent_type == "get_user_issues" and 'assignee' not in entities:
            jql_parts.append("assignee = currentUser()")

        # 預設排序
        jql = " AND ".join(jql_parts)
        if jql:
            jql += " ORDER BY created DESC"
        else:
            jql = "assignee = currentUser() ORDER BY created DESC" # Fallback to current user's issues

        return jql

    def generate_variations(self, intent: QueryIntent) -> List[str]:
        """生成 JQL 查詢變體 - 使用簡化策略：先查所有相關任務，再用 LLM 篩選"""
        jql_queries = []
        entities = intent.entities

        # 構建基本條件
        base_conditions = []

        # 添加項目條件（最重要的過濾條件）
        if 'project' in entities and entities['project']:
            print(f"JQL 生成器接收到項目條件: {entities['project']}")
            base_conditions.append(f"project = '{entities['project']}'")
        else:
            print("JQL 生成器未接收到項目條件")

        # 添加時間範圍
        time_range = entities.get("time_range")
        if time_range and time_range.get("start") and time_range.get("end"):
            base_conditions.append(
                f"created >= '{time_range['start']}' AND created <= '{time_range['end']}'"
            )

        # 添加用戶條件（用 OR 連接，表示「我參與的任務」）
        user_conditions = entities.get("user_conditions", [])
        if user_conditions:
            if len(user_conditions) == 1:
                base_conditions.append(user_conditions[0])
            else:
                # 多個用戶條件用 OR 連接
                user_query = f"({' OR '.join(user_conditions)})"
                base_conditions.append(user_query)
                print(f"用戶條件（OR 連接）: {user_query}")

        # 排除性查詢處理：如果是排除性查詢，不添加關鍵字搜尋條件
        if intent.is_exclusion:
            print(f"檢測到排除性查詢，不添加關鍵字搜尋條件。排除關鍵字: {intent.excluded_keywords}")
        else:
            # 添加關鍵字條件
            main_keyword_conditions = entities.get("main_keyword_conditions", [])
            related_keyword_conditions = entities.get("related_keyword_conditions", [])
            
            keyword_conditions = []
            keyword_conditions.extend(main_keyword_conditions)
            keyword_conditions.extend(related_keyword_conditions)
            
            if keyword_conditions:
                # 將關鍵字條件用 OR 連接
                keyword_query = f"({' OR '.join(keyword_conditions)})"
                base_conditions.append(keyword_query)
                print(f"添加關鍵字條件: {keyword_query}")

        # 構建最終查詢
        if base_conditions:
            final_query = " AND ".join(base_conditions) + " ORDER BY updated DESC"
            jql_queries.append(final_query)
            print(f"生成的 JQL 查詢: {final_query}")
        else:
            # 最基本的查詢 - 測試連接
            basic_query = "project IS NOT EMPTY ORDER BY updated DESC"
            jql_queries.append(basic_query)
            print(f"基本連接測試查詢: {basic_query}")

        return jql_queries