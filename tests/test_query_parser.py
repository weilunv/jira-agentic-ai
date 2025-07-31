import pytest
from src.agent.query_parser import NaturalLanguageQueryParser

def test_quarter_parsing():
    parser = NaturalLanguageQueryParser()
    intent = parser.parse("我 2025 Q1 的 Jira 工作記錄")

    assert intent.time_range is not None
    assert intent.time_range[0] == "2025-01-01"
    assert intent.time_range[1] == "2025-03-31"
    assert intent.assignee == "currentUser()"

def test_month_parsing():
    parser = NaturalLanguageQueryParser()
    intent = parser.parse("我 2024年12月的任務")

    assert intent.time_range is not None
    assert "2024-12" in intent.time_range[0]
    assert intent.issue_type == ["Task"]

def test_project_parsing():
    parser = NaturalLanguageQueryParser()
    intent = parser.parse("專案 ABC 中我的工作")

    assert intent.project == "ABC"
    assert intent.assignee == "currentUser()"

def test_status_parsing():
    parser = NaturalLanguageQueryParser()
    intent = parser.parse("我完成的工作")

    assert intent.status == ["Done"]
    assert intent.assignee == "currentUser()"