"""
自然語言查詢解析器
"""
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
import re
from datetime import datetime, timedelta
from pydantic import BaseModel
import arrow
import os
import json # Added for JSON parsing
try:
    from langchain.llms import AzureOpenAI  # 改用 AzureOpenAI
    from langchain.prompts import PromptTemplate
    from langchain.chains import LLMChain
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

from langchain_community.chat_models import AzureChatOpenAI  # 改用 chat models
from langchain.schema import HumanMessage
from langchain.prompts import ChatPromptTemplate  # 改用 chat prompt


class QueryIntentType(Enum):
    """查詢意圖類型"""
    SEARCH_ISSUES = "search_issues"
    GET_USER_ISSUES = "get_user_issues"
    FILTER_BY_STATUS = "filter_by_status"
    FILTER_BY_PROJECT = "filter_by_project"
    FILTER_BY_DATE = "filter_by_date"
    UNKNOWN = "unknown"


class QueryIntent(BaseModel):
    """查詢意圖數據模型"""
    intent_type: str = "search_issues"
    confidence: float = 0.5
    entities: Dict[str, Any] = {}

    def model_dump(self):  # 替換 dict() 方法
        return {
            "intent_type": self.intent_type,
            "confidence": self.confidence,
            "entities": self.entities
        }


class NaturalLanguageQueryParser:
    """自然語言查詢解析器"""

    def __init__(self, openai_api_key: str = None, jira_username: str = None):
        self.llm = None
        self.jira_username = jira_username or os.getenv("JIRA_USERNAME")  # 獲取 Jira 用戶名

        try:
            self.llm = AzureChatOpenAI(
                deployment_name=os.getenv("AZURE_DEPLOYMENT_NAME"),
                temperature=0,  # 降低溫度以獲得更確定的回應
                openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                api_version=os.getenv("OPENAI_API_VERSION")
            )

            self.analysis_prompt = ChatPromptTemplate.from_messages([
                ("system", """你是一個專門分析 Jira 查詢的助手。你的任務是從用戶查詢中提取精確的搜索條件。
請特別注意：
1. 年份信息（例如 2025）必須被識別並包含在結果中
2. 用戶相關的條件（指派、創建、評論）必須被正確識別
3. 關鍵詞必須保持原始大小寫
4. **重要：必須忽略排序相關的詞語（如：最久、最新、最近、最長時間、處理最久、持續最久等），這些不是搜索關鍵詞**"""),
                ("human", """請分析這個查詢：{query}

請提取以下信息並以 JSON 格式返回（不要包含任何 markdown 標記）：
{{
    "keywords": {{
        "main": ["CHART", "排行榜"],     # 示例關鍵詞
        "related": ["工作"]              # 示例相關詞
    }},
    "project": null,                    # 項目名稱（如果查詢中提到）
    "time": {{
        "year": "2025",                  # 必須提取查詢中的年份
        "start": "2025-01-01",           # 根據年份自動設定
        "end": "2025-12-31"              # 根據年份自動設定
    }},
    "user_conditions": {{
        "assignee": true,                # 是否包含指派給用戶的條件
        "reporter": true,                # 是否包含用戶創建的條件
        "commenter": true                # 是否包含用戶評論的條件
    }}
}}

注意：
1. 如果查詢中提到年份（如 2025），必須在 time 中設置對應的值
2. 如果查詢涉及用戶任務，相應的 user_conditions 必須設為 true
3. **項目名稱提取規則**：
   - "In the KFC project" → 提取 "KFC"
   - "KFC project" → 提取 "KFC" 
   - "在 KFC 專案中" → 提取 "KFC"
   - "KFC 專案" → 提取 "KFC"
   - 只提取項目的核心名稱，不包含 "project" 或 "專案" 等詞
4. 關鍵詞必須準確匹配查詢中的大小寫
5. **排序詞語不是關鍵詞**：例如查詢 '跟 iOS 有關且處理最久的'，只提取 'iOS' 作為關鍵詞，忽略 '處理最久'

項目名稱提取示例：
- "In the KFC project, I participated in tasks" → project: "KFC"
- "Show me tasks in ABC project" → project: "ABC"
- "在 XYZ 專案中的工作" → project: "XYZ""")
            ])

            self.chain = self.analysis_prompt | self.llm

        except Exception as e:
            print(f"Azure OpenAI 初始化失敗: {e}")
            self.llm = None

        self.time_patterns = self._get_dynamic_time_patterns()

        self.intent_patterns = {
            "search": ["找", "搜尋", "查詢", "search", "find"],
            "user": ["我的", "用戶", "使用者", "user", "assignee", "我", "我做"],
            "status": ["狀態", "status", "進行中", "完成", "待辦", "完成的", "進行中的", "待辦的"],
            "project": ["專案", "project", "項目"],
            "date": ["日期", "時間", "date", "created", "updated"],
            "okr": ["okr", "目標", "關鍵結果", "key result", "objectives"]
        }

        self.intent_patterns.update({
            "chart": ["chart", "圖表", "排行榜", "統計", "dashboard", "報表"],
            "feature": ["feature", "功能", "特性"],
            "bug": ["bug", "錯誤", "問題", "修復"],
            "task": ["task", "任務", "工作項目"],
        })

    def _get_dynamic_time_patterns(self) -> Dict[str, Any]:
        """動態生成時間模式，只包含當年和去年"""
        now = datetime.now()
        current_year = now.year
        last_year = now.year - 1

        patterns = {
            r'(\d{4})\s*Q([1-4])': self._parse_quarter,
            r'(\d{4})\s*年\s*(\d{1,2})\s*月': self._parse_year_month,
            r'(\d{1,2})\s*月': self._parse_month,
            r'今天': self._parse_today,
            r'昨天': self._parse_yesterday,
            r'這週|本週': self._parse_this_week,
            r'上週': self._parse_last_week,
            r'這個月|本月': self._parse_this_month,
            r'上個月': self._parse_last_month,
            r'今年|本年': self._parse_this_year,
            r'去年': self._parse_last_year,
        }

        # 動態添加當前年份和去年份的單獨解析
        patterns[str(current_year)] = lambda: self._parse_specific_year(current_year)
        patterns[str(last_year)] = lambda: self._parse_specific_year(last_year)

        return patterns

    def _parse_today(self, groups: Tuple = ()) -> Tuple[str, str]:
        now = datetime.now()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')

    def _parse_yesterday(self, groups: Tuple = ()) -> Tuple[str, str]:
        yesterday = datetime.now() - timedelta(days=1)
        start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')

    def _parse_quarter(self, groups: Tuple[str, ...]) -> Tuple[str, str]:
        """解析季度"""
        year, quarter = int(groups[0]), int(groups[1])
        now_year = datetime.now().year
        if year not in [now_year, now_year - 1]:
            return None # 只允許當年和去年

        quarter_starts = {
            1: (1, 1), 2: (4, 1), 3: (7, 1), 4: (10, 1)
        }
        quarter_ends = {
            1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)
        }

        start_month, start_day = quarter_starts[quarter]
        end_month, end_day = quarter_ends[quarter]

        start_date = f"{year}-{start_month:02d}-{start_day:02d}"
        end_date = f"{year}-{end_month:02d}-{end_day:02d}"

        return start_date, end_date

    def _parse_year_month(self, groups: Tuple[str, ...]) -> Tuple[str, str]:
        """解析年月"""
        year, month = int(groups[0]), int(groups[1])
        now_year = datetime.now().year
        if year not in [now_year, now_year - 1]:
            return None # 只允許當年和去年

        start = arrow.get(year, month, 1)
        end = start.ceil('month')
        return start.format('YYYY-MM-DD'), end.format('YYYY-MM-DD')

    def _parse_month(self, groups: Tuple[str, ...]) -> Tuple[str, str]:
        """解析月份（當前年或去年）"""
        month = int(groups[0])
        current_year = datetime.now().year

        # 嘗試解析為當前年份
        start_current = arrow.get(current_year, month, 1)
        end_current = start_current.ceil('month')
        if datetime.now().date() >= start_current.date(): # 如果月份在當前年份是合理的
             return start_current.format('YYYY-MM-DD'), end_current.format('YYYY-MM-DD')

        # 嘗試解析為去年份
        last_year = current_year - 1
        start_last = arrow.get(last_year, month, 1)
        end_last = start_last.ceil('month')
        return start_last.format('YYYY-MM-DD'), end_last.format('YYYY-MM-DD')

    def _parse_this_year(self, groups: Tuple = ()) -> Tuple[str, str]:
        """解析今年"""
        current_year = datetime.now().year
        return f"{current_year}-01-01", f"{current_year}-12-31"

    def _parse_last_year(self, groups: Tuple = ()) -> Tuple[str, str]:
        """解析去年"""
        last_year = datetime.now().year - 1
        return f"{last_year}-01-01", f"{last_year}-12-31"

    def _parse_specific_year(self, year: int) -> Tuple[str, str]:
        """解析特定年份（當年或去年）"""
        now_year = datetime.now().year
        if year not in [now_year, now_year - 1]:
            return None
        return f"{year}-01-01", f"{year}-12-31"

    def _parse_this_month(self, groups: Tuple = ()) -> Tuple[str, str]:
        """解析本月"""
        now = arrow.now()
        start = now.floor('month')
        end = now.ceil('month')
        return start.format('YYYY-MM-DD'), end.format('YYYY-MM-DD')

    def _parse_last_month(self, groups: Tuple = ()) -> Tuple[str, str]:
        """解析上月"""
        now = arrow.now().shift(months=-1)
        start = now.floor('month')
        end = now.ceil('month')
        return start.format('YYYY-MM-DD'), end.format('YYYY-MM-DD')

    def _parse_this_week(self, groups: Tuple = ()) -> Tuple[str, str]:
        """解析本週"""
        now = arrow.now()
        start = now.floor('week')
        end = now.ceil('week')
        return start.format('YYYY-MM-DD'), end.format('YYYY-MM-DD')

    def _parse_last_week(self, groups: Tuple = ()) -> Tuple[str, str]:
        """解析上週"""
        now = arrow.now().shift(weeks=-1)
        start = now.floor('week')
        end = now.ceil('week')
        return start.format('YYYY-MM-DD'), end.format('YYYY-MM-DD')

    def _extract_time_range(self, query: str) -> Optional[Tuple[str, str]]:
        """提取時間範圍"""
        query_lower = query.lower()

        for pattern_str, parser_func in self.time_patterns.items():
            if re.search(pattern_str, query_lower):
                time_range = parser_func(re.search(pattern_str, query_lower).groups() if re.search(pattern_str, query_lower).groups() else ())
                if time_range:
                    return time_range
        return None

    def _get_llm_expanded_keywords(self, text: str) -> List[str]:
        """使用 LLM 處理文本，生成相關的關鍵字或 JQL 片段"""
        if not self.llm:
            print("警告: OpenAI API key 未配置或 LangChain 不可用，無法進行智能關鍵字擴展。")
            return [text] # 返回原始文本作為關鍵字

        prompt_template = PromptTemplate(
            input_variables=["text"],
            template="""
            根據以下查詢，提取相關的 Jira 任務關鍵字。
            注意：請忽略排序相關的詞語（如：最久、最新、最近、最長時間、處理最久等）。
            只提取與任務內容相關的技術關鍵字。

            範例：
            輸入: "跟 iOS 有關且處理最久的"
            輸出: "iOS, iPhone, iPad, Swift, Objective-C, Xcode, 手機, app, 移動開發"

            輸入: "排行榜以外的工作"
            輸出: "用戶管理, 登入, 註冊, 設定, 支付, 通知, 數據分析, API, 後台管理"

            輸入: "提升用戶留存率"
            輸出: "用戶留存, 用戶體驗, 活躍用戶, 產品優化, 數據分析, 報告, 行為分析, 儀表板, 忠誠度, app, 功能改進"

            目標/任務/查詢: {text}

            關鍵字:"""
        )

        chain = LLMChain(llm=self.llm, prompt=prompt_template)
        try:
            response = chain.run(text=text)
            keywords = [k.strip() for k in response.split(',') if k.strip()]
            return keywords
        except Exception as e:
            print(f"LLM 處理關鍵字失敗: {e}")
            return [text] # 失敗時返回原始文本作為關鍵字

    def parse(self, query: str | dict) -> QueryIntent:
        """解析查詢意圖"""
        if isinstance(query, dict):
            query_text = query["text"]
            year = query.get("year")
            user_conditions = query.get("user_conditions", {})
        else:
            query_text = query
            year = None
            user_conditions = {}

        if not self.llm:
            return self._basic_parse(query_text)

        try:
            # 構建包含完整上下文的提示
            context = f"""查詢內容: {query_text}
年份: {year if year else '未指定'}
需要包含:
- 指派給用戶的任務: {user_conditions.get('assignee', False)}
- 用戶創建的任務: {user_conditions.get('reporter', False)}
- 用戶評論過的任務: {user_conditions.get('commenter', False)}"""

            # 使用 LLM 分析查詢
            analysis_result = self.chain.invoke({"query": context})
            content = analysis_result.content.strip()
            if content.startswith('```'):
                content = '\n'.join(content.split('\n')[1:-1])

            print(f"清理後的 LLM 分析結果: {content}")

            parsed = json.loads(content)
            print(f"解析後的 JSON 結果: {parsed}")

            # 確保使用傳入的年份
            if year:
                parsed["time"] = {
                    "year": year,
                    "start": f"{year}-01-01",
                    "end": f"{year}-12-31"
                }

            # 確保使用傳入的用戶條件
            parsed["user_conditions"] = user_conditions

            # 構建查詢條件
            def generate_flexible_keyword_conditions(keywords):
                """為關鍵字生成靈活的搜尋條件，JQL 階段使用寬鬆搜尋，重點搜尋單個關鍵詞"""
                conditions = []
                all_words = set()  # 收集所有單詞
                
                for keyword in keywords:
                    # 如果是複合關鍵字，拆分成單詞
                    if ' ' in keyword:
                        words = keyword.split()
                        for word in words:
                            if len(word) > 2:  # 只處理長度大於2的詞
                                all_words.add(word)
                    else:
                        # 單個關鍵字
                        if len(keyword) > 2:
                            all_words.add(keyword)
                
                # 為每個單詞生成大小寫變體的搜尋條件
                for word in all_words:
                    word_variants = [
                        word,
                        word.upper(),
                        word.lower(),
                        word.capitalize(),
                        word.title()
                    ]
                    
                    # 去重
                    word_variants = list(set(word_variants))
                    
                    # 生成搜尋條件（使用 text ~ 搜尋所有內容）
                    variant_conditions = []
                    for variant in word_variants:
                        variant_conditions.append(f"text ~ '{variant}'")
                    
                    # 將所有變體用 OR 連接
                    if variant_conditions:
                        conditions.append(f"({' OR '.join(variant_conditions)})")
                
                print(f"關鍵字搜尋單詞: {list(all_words)}")
                return conditions

            conditions = {
                "main_keyword_conditions": generate_flexible_keyword_conditions(
                    parsed.get("keywords", {}).get("main", [])
                ),
                "related_keyword_conditions": generate_flexible_keyword_conditions(
                    parsed.get("keywords", {}).get("related", [])
                ),
                "user_conditions": [],
                "time_range": parsed.get("time"),
                "project": parsed.get("project") # 新增項目名稱條件
            }

            print(f"構建的關鍵字條件:")
            print(f"  main_keyword_conditions: {conditions['main_keyword_conditions']}")
            print(f"  related_keyword_conditions: {conditions['related_keyword_conditions']}")

            # 添加用戶條件
            if user_conditions.get("assignee"):
                conditions["user_conditions"].append(f"assignee = '{self.jira_username}'")
            if user_conditions.get("reporter"):
                conditions["user_conditions"].append(f"reporter = '{self.jira_username}'")
            # 移除 commentedBy 因為 Jira 實例不支持此語法
            # if user_conditions.get("commenter"):
            #     conditions["user_conditions"].append(f"commentedBy = '{self.jira_username}'")

            return QueryIntent(
                intent_type="search_issues",
                confidence=0.9,
                entities=conditions
            )

        except Exception as e:
            print(f"查詢分析失敗: {e}")
            return self._basic_parse(query_text)

    def filter_results(self, original_query: str, jira_results: List[Dict]) -> List[Dict]:
        if not self.llm or not jira_results:
            return jira_results

        try:
            formatted_results = "\n".join([
                f"項目 {i+1}:\n"
                f"Key: {item['key']}\n"
                f"標題: {item['summary']}\n"
                f"描述: {item.get('description', 'N/A')}\n"
                for i, item in enumerate(jira_results)
            ])

            filter_result = self.filter_chain.invoke({
                "original_query": original_query,
                "jira_results": formatted_results
            })

            parsed_filter = json.loads(filter_result.content)  # 從 chat response 獲取內容
            relevant_issues = parsed_filter.get("relevant_issues", [])

            # 根據相關性分數排序結果
            sorted_results = sorted(
                relevant_issues,
                key=lambda x: x.get("relevance_score", 0),
                reverse=True
            )

            # 重新組織結果
            filtered_results = []
            for relevant in sorted_results:
                issue_key = relevant["key"]
                original_item = next(
                    (item for item in jira_results if item["key"] == issue_key),
                    None
                )
                if original_item:
                    original_item["relevance_score"] = relevant["relevance_score"]
                    original_item["relevance_reason"] = relevant["reason"]
                    filtered_results.append(original_item)

            return filtered_results

        except Exception as e:
            print(f"結果篩選失敗: {e}")
            return jira_results

    def _basic_parse(self, query: str) -> QueryIntent:
        """基本的查詢解析（作為備用）"""
        query_lower = query.lower()
        entities = {}
        intent_type = "search_issues"
        confidence = 0.5

        # 1. 提取時間範圍
        time_range = self._extract_time_range(query)
        if time_range:
            entities['time_range'] = time_range
            intent_type = "filter_by_date"
            confidence = 0.7 # 提高置信度

        # 2. 檢測用戶相關查詢
        if any(keyword in query_lower for keyword in self.intent_patterns["user"]):
            entities['assignee'] = 'currentUser()'
            intent_type = "get_user_issues"
            confidence = max(confidence, 0.7)

        # 3. 檢測狀態過濾
        if any(keyword in query_lower for keyword in self.intent_patterns["status"]):
            # 更精確地判斷狀態
            if "完成" in query_lower or "done" in query_lower:
                entities['status'] = ["Done"]
            elif "進行中" in query_lower or "in progress" in query_lower:
                entities['status'] = ["In Progress"]
            elif "待辦" in query_lower or "to do" in query_lower:
                entities['status'] = ["To Do"]

            intent_type = "filter_by_status"
            confidence = max(confidence, 0.7)

        # 4. 檢測專案名稱
        project_match = re.search(r'專案\s*(\w+)|project\s*(\w+)', query, re.I)
        if project_match:
            entities['project'] = project_match.group(1) or project_match.group(2)
            intent_type = "filter_by_project"
            confidence = max(confidence, 0.8)

        # 5. 根據當前檢測到的意圖，決定是否進行 LLM 關鍵字擴展
        # 如果沒有強烈指向其他特定意圖（如日期、用戶、狀態、專案），則視為一般搜尋，使用 LLM 擴展關鍵字
        if intent_type == "search_issues": # 只有當沒有明確篩選條件時才進行 LLM 擴展
            generated_keywords = self._get_llm_expanded_keywords(query) # 將整個查詢傳給 LLM
            entities['keywords'] = entities.get('keywords', []) + generated_keywords
            confidence = max(confidence, 0.8) # 提高置信度，因為經過 LLM 處理

        # 6. 提取一般關鍵字 (移除原有簡單關鍵字提取，因為現在會透過 LLM 處理)
        # 由於 LLM 處理已涵蓋，這裡不需要再進行簡單的單詞拆分，除非 LLM 不可用
        if not self.llm and not entities.get('keywords'): # LLM 不可用且沒有其他關鍵字時，才做簡單的單詞拆分
            all_keywords = []
            words = query.split()
            excluded_keywords = set()
            for pattern in self.time_patterns.keys():
                cleaned_pattern = re.sub(r'[^w\s]', '', pattern)
                excluded_keywords.update(set(cleaned_pattern.lower().split()))

            for pattern_list in self.intent_patterns.values():
                excluded_keywords.update(set(k.lower() for k in pattern_list))

            for word in words:
                if word.lower() not in excluded_keywords and len(word) > 1:
                    all_keywords.append(word)

            if 'keywords' in entities:
                entities['keywords'].extend(all_keywords)
            else:
                entities['keywords'] = all_keywords

        return QueryIntent(
            intent_type=intent_type,
            confidence=confidence,
            entities=entities
        )