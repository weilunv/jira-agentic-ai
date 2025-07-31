from typing import Dict, List, Optional
import os
from dotenv import load_dotenv

try:
    from jira import JIRA
    JIRA_AVAILABLE = True
except ImportError:
    JIRA_AVAILABLE = False

load_dotenv()

class JiraClient:
    """Jira API 客戶端"""

    def __init__(self, server_url: str = None, username: str = None, api_token: str = None):
        if not JIRA_AVAILABLE:
            raise ImportError("請安裝 jira 套件: pip install jira")

        self.server_url = server_url or os.getenv('JIRA_SERVER_URL')
        self.username = username or os.getenv('JIRA_USERNAME')
        self.api_token = api_token or os.getenv('JIRA_API_TOKEN')

        if not all([self.server_url, self.username, self.api_token]):
            raise ValueError("需要提供 Jira 伺服器 URL、用戶名和 API Token")

        self.jira = JIRA(
            server=self.server_url,
            basic_auth=(self.username, self.api_token)
        )

    def search_issues(self, jql: str, max_results: int = 50) -> List[Dict]:
        """執行 JQL 查詢"""
        try:
            # 擴展 changelog 和 comments 來獲取評論信息
            issues = self.jira.search_issues(jql, maxResults=max_results, expand='changelog,comments')
            results = []

            for issue in issues:
                # 計算任務持續時間
                from datetime import datetime, timezone
                duration_days = None
                processing_days = None
                
                if issue.fields.created:
                    created = datetime.fromisoformat(str(issue.fields.created).replace('Z', '+00:00'))
                    now = datetime.now(timezone.utc)
                    
                    if issue.fields.resolutiondate:
                        # 已完成任務：計算從創建到完成的時間
                        resolved = datetime.fromisoformat(str(issue.fields.resolutiondate).replace('Z', '+00:00'))
                        duration_days = (resolved - created).days
                    else:
                        # 未完成任務：計算從創建到現在的時間
                        processing_days = (now - created).days

                # 獲取時間追蹤信息
                timetracking = getattr(issue.fields, 'timetracking', None)
                timespent_seconds = getattr(issue.fields, 'timespent', None)
                originalestimate_seconds = getattr(issue.fields, 'originalestimate', None)

                # 轉換秒數為小時
                timespent_hours = timespent_seconds / 3600 if timespent_seconds else None
                originalestimate_hours = originalestimate_seconds / 3600 if originalestimate_seconds else None

                # 獲取評論數量和評論內容
                comment_count = 0
                comments_text = ""
                if hasattr(issue.fields, 'comment') and issue.fields.comment:
                    comment_count = len(issue.fields.comment.comments)
                    # 收集所有評論內容（限制長度避免 token 過多）
                    comments_list = []
                    for comment in issue.fields.comment.comments:
                        if hasattr(comment, 'body') and comment.body:
                            # 每個評論限制 100 字符，總共限制 500 字符
                            comment_text = comment.body[:100]
                            comments_list.append(comment_text)
                            if len('\n'.join(comments_list)) > 500:
                                break
                    comments_text = '\n'.join(comments_list)

                issue_data = {
                    'key': issue.key,
                    'summary': issue.fields.summary,
                    'status': issue.fields.status.name,
                    'assignee': issue.fields.assignee.displayName if issue.fields.assignee else None,
                    'reporter': issue.fields.reporter.displayName if issue.fields.reporter else None,
                    'created': str(issue.fields.created),
                    'updated': str(issue.fields.updated),
                    'resolutiondate': str(issue.fields.resolutiondate) if issue.fields.resolutiondate else None,
                    'priority': issue.fields.priority.name if issue.fields.priority else None,
                    'issuetype': issue.fields.issuetype.name,
                    'project': issue.fields.project.name,
                    'description': issue.fields.description[:200] + '...' if issue.fields.description and len(issue.fields.description) > 200 else issue.fields.description,
                    'url': f"{self.server_url}/browse/{issue.key}",
                    # 時間追蹤相關字段
                    'timespent_hours': timespent_hours,
                    'originalestimate_hours': originalestimate_hours,
                    'duration_days': duration_days,  # 已完成任務的持續天數
                    'processing_days': processing_days,  # 未完成任務的處理天數
                    'comment_count': comment_count,
                    'comments_text': comments_text,  # 新增評論內容
                    'timetracking': {
                        'originalEstimate': getattr(timetracking, 'originalEstimate', None) if timetracking else None,
                        'remainingEstimate': getattr(timetracking, 'remainingEstimate', None) if timetracking else None,
                        'timeSpent': getattr(timetracking, 'timeSpent', None) if timetracking else None
                    } if timetracking else None
                }
                results.append(issue_data)

            return results
        except Exception as e:
            print(f"JQL 查詢失敗: {e}")
            return []

    def get_user_projects(self) -> List[Dict]:
        """取得用戶可存取的專案"""
        try:
            projects = self.jira.projects()
            return [{'key': p.key, 'name': p.name} for p in projects]
        except Exception as e:
            print(f"取得專案列表失敗: {e}")
            return []

    def validate_jql(self, jql: str) -> bool:
        """驗證 JQL 語法"""
        try:
            self.jira.search_issues(jql, maxResults=1)
            return True
        except Exception:
            return False