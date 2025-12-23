# app/prompts/__init__.py
"""
Prompts Module
وحدة إنشاء Prompts للذكاء الاصطناعي
"""

from .policy_matcher import get_policy_matcher_prompt
from .compliance_analyzer import get_compliance_analyzer_prompt
from .compliance_rules import COMPLIANCE_RULES

__all__ = [
    "get_policy_matcher_prompt",
    "get_compliance_analyzer_prompt",
    "COMPLIANCE_RULES"
]