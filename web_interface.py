#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from flask import Flask, render_template, request, jsonify, send_from_directory
from dotenv import load_dotenv
from src.agent.query_parser import NaturalLanguageQueryParser
from src.agent.jql_generator import JQLGenerator
from src.agent.jira_client import JiraClient
from datetime import datetime
import json

load_dotenv()

app = Flask(__name__)

class JiraAgenticAI:
    """Jira Agentic AI 主類"""

    def __init__(self):
        self.parser = NaturalLanguageQueryParser(
            openai_api_key=os.getenv('AZURE_OPENAI_API_KEY'),
            jira_username=os.getenv('JIRA_USERNAME')  # 傳入 Jira 用戶名
        )
        self.jql_generator = JQLGenerator()
        try:
            self.jira_client = JiraClient()
        except Exception as e:
            print(f"⚠️  Jira 客戶端初始化失敗: {e}")
            self.jira_client = None

    def process_query(self, query) -> dict:
        """處理自然語言查詢"""
        # 處理參數類型：字典或字串
        if isinstance(query, dict):
            query_text = query.get('text', '')
            year = query.get('year')
            user_conditions = query.get('user_conditions', {})
        else:
            query_text = str(query)
            year = None
            user_conditions = {}
        
        print(f"處理查詢: '{query_text}'")
        print(f"用戶條件: {user_conditions}")
        
        # 1. 解析查詢意圖
        if isinstance(query, dict):
            intent = self.parser.parse(query)  # 傳遞完整字典
        else:
            intent = self.parser.parse(query_text)
        
        print(f"解析結果 - 關鍵字: {intent.entities.get('keywords', [])}")
        print(f"解析結果 - 用戶條件: {intent.entities.get('user_conditions', [])}")

        # 2. 生成 JQL 查詢
        jql_queries = self.jql_generator.generate_variations(intent)

        # 3. 執行查詢
        all_results = []
        if self.jira_client:
            for jql in jql_queries:
                if self.jira_client.validate_jql(jql):
                    results = self.jira_client.search_issues(jql)
                    all_results.extend(results)

        # 去重
        unique_results = []
        seen_keys = set()
        for result in all_results:
            if result['key'] not in seen_keys:
                unique_results.append(result)
                seen_keys.add(result['key'])

        # 智能排序：根據查詢內容選擇排序方式
        def smart_sort(results, query_text):
            query_lower = query_text.lower()
            
            # 檢查是否是時間相關查詢
            if any(keyword in query_lower for keyword in ['最久', '處理最久', '持續最久', '最長時間', '最長']):
                # 按處理天數降序排序（未完成任務）
                def sort_key(x):
                    processing_days = x.get('processing_days')
                    duration_days = x.get('duration_days')
                    # 優先顯示未完成且處理時間長的任務
                    if processing_days is not None:
                        return (1, processing_days)  # 未完成任務，按處理天數排序
                    elif duration_days is not None:
                        return (0, duration_days)  # 已完成任務，按完成耗時排序
                    else:
                        return (-1, 0)  # 沒有時間資料的任務排在最後
                
                sorted_results = sorted(results, key=sort_key, reverse=True)
                print(f"按處理時間排序：找到 {len([r for r in results if r.get('processing_days') is not None])} 個未完成任務")
                
            elif any(keyword in query_lower for keyword in ['最新', '最近', '新建']):
                # 按創建時間降序排序
                sorted_results = sorted(results, key=lambda x: x.get('created', ''), reverse=True)
                print(f"按創建時間排序（最新先）")
                
            elif any(keyword in query_lower for keyword in ['留言數', '評論數', '討論', '留言', '評論']):
                # 按評論數降序排序
                sorted_results = sorted(results, key=lambda x: x.get('comment_count', 0), reverse=True)
                print(f"按評論數排序（最多先）：找到 {len([r for r in results if r.get('comment_count', 0) > 0])} 個有評論的任務")
                
            else:
                # 預設按更新時間降序排序
                sorted_results = sorted(results, key=lambda x: x.get('updated', ''), reverse=True)
                print(f"按更新時間排序（預設）")
            
            return sorted_results
        
        sorted_results = smart_sort(unique_results, query_text)

        # 5. 使用 LLM 篩選相關結果
        filtered_results = sorted_results
        print(f"檢查 LLM 篩選條件:")
        print(f"  sorted_results 數量: {len(sorted_results) if sorted_results else 0}")
        print(f"  hasattr(self.parser, 'llm'): {hasattr(self.parser, 'llm')}")
        print(f"  self.parser.llm 存在: {self.parser.llm if hasattr(self.parser, 'llm') else 'N/A'}")

        if sorted_results and hasattr(self.parser, 'llm') and self.parser.llm:
            try:
                # 準備任務摘要供 LLM 分析
                task_summaries = []
                for result in sorted_results[:50]:  # 限制分析數量以避免 token 過多
                    task_summaries.append({
                        "key": result["key"],
                        "summary": result["summary"],
                        "description": (result.get("description") or "")[:200],  # 限制描述長度，處理 None 值
                        "comments_text": (result.get("comments_text") or "")[:300],  # 新增評論內容，限制長度
                        "assignee": result.get("assignee", ""),
                        "status": result.get("status", ""),
                        "duration_days": result.get("duration_days"),
                        "timespent_hours": result.get("timespent_hours"),
                        "originalestimate_hours": result.get("originalestimate_hours"),
                        "created": result.get("created", ""),
                        "resolutiondate": result.get("resolutiondate"),
                        "comment_count": result.get("comment_count", 0)  # 新增評論數量
                    })

                # 任務狀態統計
                status_counts = {}
                completed_count = 0
                for task in task_summaries:
                    status = task.get("status", "")
                    if status in status_counts:
                        status_counts[status] += 1
                    else:
                        status_counts[status] = 1
                    if task.get("resolutiondate"):
                        completed_count += 1

                print(f"任務狀態分布: {status_counts}")
                print(f"已完成任務數量: {completed_count}, 未完成任務數量: {len(task_summaries) - completed_count}")

                # 使用 LLM 篩選相關任務
                filter_prompt = f"""
                原始查詢: {query}

                請仔細分析查詢意圖，從以下任務中篩選出與查詢最相關的任務。

                重要篩選規則：
                1. 如果查詢包含特定關鍵字（如 "Android", "iOS", "Web", "WEB View" 等）：
                   - 優先在任務的標題(summary)、描述(description)和評論內容(comments_text)中搜尋完整的關鍵字組合
                   - 對於複合關鍵字（如 "WEB View"），如果找不到完整匹配，可以考慮包含部分關鍵字（如 "WEB"）但在評論或描述中提到完整概念的任務
                   - 例如：標題是 "[WEB]" 但描述或評論中提到 "WEB View" 的任務應該被包含
                2. 如果查詢包含排除性語言（如「以外」、「除了」、「不包括」），請嚴格排除相關內容
                3. 如果查詢涉及時間相關條件：
                   - 「花費超過一週」：篩選 duration_days > 7 或 timespent_hours > 40 的任務
                   - 「快速完成」：篩選 duration_days <= 3 或 timespent_hours <= 8 的任務
                   - 「長期項目」：篩選 duration_days > 30 的任務
                   - 「時間追蹤」相關：查看 timespent_hours 和 originalestimate_hours 字段
                4. 如果查詢涉及任務狀態條件：
                   - 「還沒結束」、「進行中」、「未完成」：篩選 status 不是 "Done"、"Closed"、"Resolved" 的任務
                   - 「已完成」、「已結束」：篩選 status 是 "Done"、"Closed"、"Resolved" 的任務
                   - 「沒有進度」：篩選 status 是 "To Do"、"Open"、"New" 的任務
                   - 「進行中」：篩選 status 是 "In Progress"、"In Review" 的任務
                   - 重要：如果 resolutiondate 為 null，表示任務未完成；如果有值，表示任務已完成
                5. 如果查詢涉及評論相關條件：
                   - 「最多評論」：按 comment_count 降序排列，選擇評論數最多的任務
                   - 「討論熱烈」：篩選 comment_count > 5 的任務
                   - 「無人討論」：篩選 comment_count = 0 的任務
                   - 「評論超過X個」：篩選 comment_count > X 的任務
                6. 例如「Android 相關工作」只保留包含 "Android" 的任務
                7. 例如「排行榜以外的工作」要排除所有與排行榜、榜單、CHART 相關的任務
                8. 相關性分數範圍 0-1，只返回分數 > 0.3 的高相關任務

                任務字段說明：
                - duration_days: 任務從創建到完成的天數
                - timespent_hours: 實際花費的工時（小時）
                - originalestimate_hours: 原始估計工時（小時）
                - comment_count: 任務評論數量
                - status: 任務狀態（如 "To Do", "In Progress", "Done", "Closed" 等）
                - resolutiondate: 完成日期（null 表示未完成）

                任務列表：
                {json.dumps(task_summaries, ensure_ascii=False, indent=2)}

                請返回 JSON 格式，包含相關任務的 key 和相關性分數：
                {{
                    "relevant_tasks": [
                        {{"key": "TASK-123", "relevance_score": 0.9, "reason": "狀態為 In Progress，符合未完成條件"}},
                        {{"key": "TASK-456", "relevance_score": 0.8, "reason": "狀態為 To Do，沒有進度且未完成"}}
                    ]
                }}

                注意：請嚴格按照查詢條件匹配，不相關的任務不要包含。
                """

                from langchain.schema import HumanMessage
                print(f"開始 LLM 篩選，任務數量: {len(task_summaries)}")

                try:
                    filter_result = self.parser.llm.invoke([HumanMessage(content=filter_prompt)])
                    print(f"LLM 調用成功，結果類型: {type(filter_result)}")

                    if hasattr(filter_result, 'content'):
                        print(f"LLM 內容存在，類型: {type(filter_result.content)}")
                    else:
                        print("LLM 結果沒有 content 屬性")

                except Exception as llm_error:
                    print(f"LLM 調用失敗: {llm_error}")
                    filter_result = None

                # 解析篩選結果
                if not filter_result or not hasattr(filter_result, 'content') or not filter_result.content:
                    print("LLM 篩選失敗: 沒有返回有效內容")
                    filtered_results = sorted_results
                else:
                    filter_content = filter_result.content.strip()
                    print(f"LLM 原始回應: {filter_content[:200]}...")  # 調試輸出

                    if filter_content.startswith('```'):
                        filter_content = '\n'.join(filter_content.split('\n')[1:-1])

                    try:
                        parsed_filter = json.loads(filter_content)
                        relevant_tasks = parsed_filter.get("relevant_tasks", [])

                        # 根據相關性重新排序結果
                        if relevant_tasks:
                            task_relevance = {task["key"]: task.get("relevance_score", 0) for task in relevant_tasks if task.get("relevance_score") is not None}
                            filtered_results = [
                                result for result in sorted_results
                                if result["key"] in task_relevance and task_relevance.get(result["key"], 0) > 0.3
                            ]
                            filtered_results.sort(key=lambda x: task_relevance.get(x["key"], 0), reverse=True)

                            print(f"LLM 篩選結果: 從 {len(sorted_results)} 個任務中篩選出 {len(filtered_results)} 個相關任務")
                            for task in relevant_tasks:
                                score = task.get("relevance_score", 0)
                                if score and score > 0.3:
                                    print(f"  - {task.get('key', 'N/A')}: {score:.2f} - {task.get('reason', 'N/A')}")
                        else:
                            print("LLM 篩選結果: 沒有找到相關任務")
                            filtered_results = sorted_results
                    except json.JSONDecodeError as e:
                        print(f"LLM 回應解析失敗: {e}")
                        print(f"原始內容: {filter_content}")
                        filtered_results = sorted_results
            except Exception as e:
                print(f"LLM 篩選失敗，使用原始結果: {e}")
                import traceback
                print(f"詳細錯誤信息: {traceback.format_exc()}")
                filtered_results = sorted_results

        return {
            'query': query_text,
            'intent': intent.model_dump(),
            'jql_queries': jql_queries,
            'results': filtered_results[:20],  # 限制結果數量
            'total_count': len(filtered_results)
        }

# 初始化 AI 系統
ai = JiraAgenticAI()

@app.route('/')
def index():
    """主頁"""
    return render_template('index.html')

@app.route('/api/search', methods=['POST'])
def search():
    """處理搜尋請求"""
    data = request.get_json()
    query = data.get('query', '').strip()
    year = data.get('year', datetime.now().year)  # 從前端獲取年份
    user_conditions = {
        "assignee": True,  # 預設包含所有用戶條件
        "reporter": True,
        "commenter": True
    }

    if not query:
        return jsonify({'error': '請輸入查詢內容'}), 400

    try:
        # 構建完整的查詢上下文
        full_query = {
            "text": query,
            "year": str(year),
            "user_conditions": user_conditions
        }

        # 將完整的查詢上下文傳遞給 agent
        result = ai.process_query(full_query)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # 創建 templates 目錄
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)

    print("啟動 Jira Agentic AI Web 介面...")
    print("請開啟瀏覽器，前往: http://localhost:8080")
    print("按 Ctrl+C 停止服務")

    app.run(debug=True, host='127.0.0.1', port=8080)