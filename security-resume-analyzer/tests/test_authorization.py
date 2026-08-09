from __future__ import annotations

import pytest

from security_resume_analyzer.authorization import (
    has_global_authorization_denial,
    has_negative_authorization_signal,
    has_positive_authorization_signal,
    infer_authorization_environment,
    source_is_authorized,
)
from security_resume_analyzer.models import Resume
from security_resume_analyzer.scoring import ScoreCalculator

_CHINESE_CONTEXTS = (
    "CTF竞赛",
    "靶场",
    "安全实验环境",
    "漏洞赏金",
    "授权测试",
)
_CHINESE_NEGATIVE_TEMPLATES = (
    "未参与{}",
    "未做{}",
    "未进行{}",
    "不涉及{}",
    "不是{}",
    "并非{}",
    "与{}无关",
    "暂无{}经历",
    "{}无经验",
    "未接触{}",
    "从未参加{}",
    "{}经验为无",
)
_ENGLISH_CONTEXTS = (
    "CTF competition",
    "security lab",
    "bug bounty",
    "authorized security assessment",
)
_ENGLISH_NEGATIVE_TEMPLATES = (
    "none: {}",
    "zero {} experience",
    "never participated in {}",
)


@pytest.mark.parametrize("context", _CHINESE_CONTEXTS)
@pytest.mark.parametrize("template", _CHINESE_NEGATIVE_TEMPLATES)
def test_chinese_absence_never_becomes_authorization(template: str, context: str) -> None:
    text = template.format(context)
    assert has_negative_authorization_signal(text)
    assert not has_positive_authorization_signal(text)
    assert not source_is_authorized(None, text)


@pytest.mark.parametrize("context", _ENGLISH_CONTEXTS)
@pytest.mark.parametrize("template", _ENGLISH_NEGATIVE_TEMPLATES)
def test_english_absence_never_becomes_authorization(template: str, context: str) -> None:
    text = template.format(context)
    assert has_negative_authorization_signal(text)
    assert not has_positive_authorization_signal(text)
    assert not source_is_authorized(None, text)


@pytest.mark.parametrize(
    "text",
    (
        "授权范围",
        "讨论授权范围",
        "询问授权范围",
        "等待授权范围确认",
        "授权范围待确认",
        "授权信息缺失",
        "授权范围未定义",
        "可能获得授权",
        "authorized users",
        "authorized reseller",
        "chemistry lab",
        "chemistry lab environment",
        "lab equipment",
    ),
)
def test_generic_pending_or_non_security_phrases_are_not_authorization(text: str) -> None:
    assert not has_positive_authorization_signal(text)
    assert not source_is_authorized(None, text)


@pytest.mark.parametrize(
    "text",
    (
        "尚未获得授权开展渗透测试",
        "还未取得授权开展渗透测试",
        "并未得到授权开展渗透测试",
        "从未获得客户授权",
        "没有获得书面授权",
        "未能取得授权",
        "无法获得授权",
        "授权申请未通过",
        "授权申请被拒绝",
        "取消客户授权渗透测试",
        "not client-authorized penetration testing",
        "never client-authorized penetration testing",
        "non-authorized penetration testing",
        "not an authorized penetration test",
        "no client authorization for penetration testing",
        "without client authorization for penetration testing",
        "failed to obtain authorization for penetration testing",
        "permission was not granted",
        "authorization request was rejected",
    ),
)
def test_denied_or_unobtained_authorization_never_matches_positive_substrings(text: str) -> None:
    assert has_negative_authorization_signal(text)
    assert not has_positive_authorization_signal(text)
    assert not source_is_authorized("authorized", text)


@pytest.mark.parametrize(
    "text",
    (
        "获得伪造的书面授权后开展渗透测试",
        "已获得未生效的书面授权并开展安全测试",
        "已获得无效的书面授权后进行安全评估",
        "使用虚假客户授权开展渗透测试",
        "已获得书面授权后开展渗透测试，但授权是假的",
        "已获得书面授权后开展渗透测试，但授权系伪造",
        "Obtained forged written authorization for penetration testing",
        "Received invalid client authorization for a security assessment",
        "Used fake permission to conduct a security test",
        "Client-authorized penetration testing, but the authorization was forged",
        "Client-authorized penetration testing, but the authorization is fake",
        "Client-authorized penetration testing, but the permission was fraudulent",
    ),
)
def test_forged_or_ineffective_authorization_is_never_positive(text: str) -> None:
    assert has_global_authorization_denial(text)
    assert has_negative_authorization_signal(text)
    assert not has_positive_authorization_signal(text)
    assert not source_is_authorized("authorized", text)


@pytest.mark.parametrize(
    "text",
    (
        "不在授权范围内",
        "超出授权范围",
        "客户授权渗透测试，但授权不再有效",
        "客户授权渗透测试，但许可已到期",
        "客户授权渗透测试，但授权期限已结束",
        "客户授权渗透测试，但授权作废",
        "never within approved scope",
        "beyond the authorized scope",
        "client-authorized penetration testing, but permission is no longer valid",
    ),
)
def test_scope_or_lifecycle_denial_overrides_earlier_positive_text(text: str) -> None:
    assert has_negative_authorization_signal(text)
    assert not has_positive_authorization_signal(text)
    assert not source_is_authorized("authorized", text)


@pytest.mark.parametrize(
    ("denial_class", "text"),
    (
        ("lifecycle", "获得书面授权后测试，但授权后来失效"),
        ("lifecycle", "获得书面授权后测试，但许可已经不再生效"),
        ("lifecycle", "Client-authorized pentest, but permission was later revoked"),
        ("lifecycle", "Authorized assessment; authorization is no longer effective"),
        ("lifecycle", "Authorized assessment; permission had lapsed"),
        ("lifecycle", "书面授权并未生效，但在授权范围内开展渗透测试"),
        ("lifecycle", "书面授权从未生效，但在授权范围内开展渗透测试"),
        ("lifecycle", "书面授权尚未正式生效，但在授权范围内开展渗透测试"),
        (
            "lifecycle",
            "Client authorization has not become effective, but testing was within authorized scope",
        ),
        (
            "lifecycle",
            "Client authorization never became effective, but testing was within authorized scope",
        ),
        ("proven_false", "已获得书面授权，但该授权后来被证实为伪造"),
        ("proven_false", "已获得书面授权，但后来发现该授权是假的"),
        ("proven_false", "已获得书面授权后开展渗透测试，但授权已被伪造"),
        ("proven_false", "Authorization was later found to be fake"),
        ("proven_false", "Client-authorized pentest, but authorization turned out to be fake"),
        ("proven_false", "Client-authorized pentest, but authorization proved to be forged"),
        ("scope_unknown", "已获得书面授权，但授权范围未明确"),
        ("scope_unknown", "已获得书面授权，但许可范围不确定"),
        ("scope_unknown", "Client authorization exists, but authorization scope is unclear"),
        ("target_denied", "已获得书面授权，但并未获准测试该目标"),
        ("target_denied", "已获得书面授权，但该目标并未获准测试"),
        ("target_denied", "已获得书面授权，但授权未覆盖该目标"),
        ("target_denied", "Client-authorized pentest, but this target was not approved"),
        ("target_denied", "Client authorization did not cover this target"),
    ),
)
def test_global_lifecycle_and_scope_denial_table(
    denial_class: str,
    text: str,
) -> None:
    assert denial_class in {"lifecycle", "proven_false", "scope_unknown", "target_denied"}
    assert has_global_authorization_denial(text)
    assert has_negative_authorization_signal(text)
    assert not has_positive_authorization_signal(text)
    assert not source_is_authorized("authorized", text)


@pytest.mark.parametrize(
    "text",
    (
        "一旦获得授权后开展渗透测试",
        "待取得授权后开展渗透测试",
        "预计获得授权后开展渗透测试",
        "预期取得授权后开展渗透测试",
        "有望获得授权后开展渗透测试",
        "假如取得授权后开展渗透测试",
        "倘若获得授权后开展渗透测试",
    ),
)
def test_future_or_conditional_authorization_is_not_completed(text: str) -> None:
    assert has_negative_authorization_signal(text)
    assert not has_positive_authorization_signal(text)
    assert not source_is_authorized("authorized", text)


@pytest.mark.parametrize(
    "text",
    (
        "Authorized Penetration Testing course",
        "Authorized Penetration Testing certification",
        "客户授权渗透测试课程",
        "正式授权安全测试认证",
        "书面授权渗透测试培训",
        "课程：客户授权渗透测试",
        "Completed a course on authorized penetration testing",
        "Completed training in authorized security testing",
        "完成课程中的客户授权渗透测试学习",
        "了解客户授权渗透测试",
        "阅读安全实验室使用规则",
        "了解靶场使用方法",
        "熟悉安全实验室参与要求",
        "阅读 CTF 竞赛参与规则",
        "familiar with authorized penetration testing",
        "knowledge of security lab testing",
    ),
)
def test_course_certification_or_knowledge_is_not_applied_authorization(text: str) -> None:
    assert not has_positive_authorization_signal(text)
    assert not source_is_authorized(None, text)
    assert infer_authorization_environment(text) is None


@pytest.mark.parametrize(
    "text",
    (
        "负责安全实验室设备管理",
        "负责网络安全实验室日常管理",
        "在安全实验室完成设备盘点",
        "参与安全实验室参观活动",
        "使用安全实验室会议室",
        "完成CTF竞赛报名",
        "负责CTF竞赛裁判",
        "负责CTF竞赛摄影",
        "参与漏洞赏金项目运营",
        "Completed CTF registration",
        "Served as a CTF referee",
        "Photographed a CTF competition",
        "Handled event operations for a bug bounty program",
        "Managed security lab equipment inventory",
    ),
)
def test_lab_administration_or_ctf_registration_is_not_authorization(text: str) -> None:
    assert not has_positive_authorization_signal(text)
    assert not source_is_authorized(None, text)
    assert infer_authorization_environment(text) is None


@pytest.mark.parametrize(
    "safe_finding",
    (
        "Fixed an unauthorized access vulnerability",
        "Detected unauthorized API calls",
        "修复未授权访问漏洞",
        "检测未经授权的 API 调用",
        "阻断未授权用户访问",
        "修复未授权数据访问漏洞",
        "Fixed unauthorized code execution",
        "Prevented unauthorized login",
        "Detected unauthorized file access",
    ),
)
def test_unauthorized_security_object_is_not_tester_authorization_denial(
    safe_finding: str,
) -> None:
    text = f"Client-authorized penetration testing; {safe_finding}"
    assert not has_global_authorization_denial(text)
    assert not has_negative_authorization_signal(text)
    assert has_positive_authorization_signal(text)
    assert source_is_authorized("authorized", text)


@pytest.mark.parametrize(
    "text",
    (
        "参与安全实验室演练，复现授权范围未确认导致的权限绕过漏洞",
        "参加 CTF 竞赛，修复授权范围未明确导致的越权漏洞",
        "在公开漏洞赏金项目中发现授权范围未定义漏洞并负责披露",
        "completed a security lab exercise and fixed an authorization scope unknown vulnerability",
    ),
)
def test_authorization_scope_vulnerability_is_not_testing_permission_denial(
    text: str,
) -> None:
    assert not has_global_authorization_denial(text)
    assert not has_negative_authorization_signal(text)
    assert has_positive_authorization_signal(text)
    assert source_is_authorized(None, text)
    assert infer_authorization_environment(text) in {"lab", "ctf", "bug_bounty"}


@pytest.mark.parametrize(
    "text",
    (
        "参与安全实验室演练，复现授权未生效导致的权限绕过漏洞",
        "参加CTF竞赛，修复授权已失效导致的越权漏洞",
        "completed a security lab exercise and reproduced an authorization not effective "
        "vulnerability",
        "fixed a permission revoked bypass in a security lab exercise",
    ),
)
def test_authorization_lifecycle_vulnerability_is_not_testing_permission_denial(
    text: str,
) -> None:
    assert not has_global_authorization_denial(text)
    assert not has_negative_authorization_signal(text)
    assert has_positive_authorization_signal(text)
    assert source_is_authorized(None, text)
    assert infer_authorization_environment(text) in {"lab", "ctf"}


@pytest.mark.parametrize(
    "text",
    (
        "在安全实验室修复漏洞",
        "在安全实验室检测并分析权限绕过漏洞",
        "validated and remediated a vulnerability in a security lab exercise",
        "resolved a security flaw in a cyber lab",
    ),
)
def test_completed_hands_on_lab_actions_are_positive(text: str) -> None:
    assert not has_global_authorization_denial(text)
    assert not has_negative_authorization_signal(text)
    assert has_positive_authorization_signal(text)
    assert source_is_authorized(None, text)
    assert infer_authorization_environment(text) == "lab"


@pytest.mark.parametrize(
    "text",
    (
        "已获得书面授权，但发现授权范围未明确问题后仍开展渗透测试",
        "已获得书面授权，但识别到授权范围未定义风险后继续扫描目标",
        "Client-authorized penetration testing; found authorization scope was unclear issue "
        "and continued testing",
        "已获得书面授权，但发现授权范围未明确漏洞后仍开展渗透测试",
        "Client-authorized penetration testing; found an authorization scope unknown "
        "vulnerability and continued testing",
    ),
)
def test_scope_finding_language_cannot_mask_continued_testing_without_clear_permission(
    text: str,
) -> None:
    assert has_global_authorization_denial(text)
    assert has_negative_authorization_signal(text)
    assert not has_positive_authorization_signal(text)
    assert not source_is_authorized("authorized", text)
    assert infer_authorization_environment(text) is None


def test_actual_unauthorized_access_activity_remains_denied() -> None:
    text = "Unauthorized access to an external website"
    assert has_negative_authorization_signal(text)
    assert not source_is_authorized("authorized", text)


@pytest.mark.parametrize(
    "disclaimer",
    (
        "未授权攻击不作为项目内容",
        "项目内容不涉及未经授权渗透测试",
        "Unauthorized attacks were not part of the project",
    ),
)
def test_unauthorized_activity_disclaimer_does_not_override_separate_authorization(
    disclaimer: str,
) -> None:
    text = f"{disclaimer}。经书面授权后开展渗透测试。"
    assert not has_global_authorization_denial(text)
    assert has_positive_authorization_signal(text)
    assert source_is_authorized("authorized", text)


@pytest.mark.parametrize(
    "text",
    (
        "已授权测试",
        "书面授权测试",
        "客户授权测试",
        "书面授权生效后，在授权范围内开展安全测试",
        "授权已生效",
        "授权已经生效",
        "授权当前生效",
        "在授权范围内开展渗透测试",
        "client-authorized pentest",
        "authorized security assessment",
        "已获得课程教师书面授权，授权当前仍有效，并在明确授权范围内完成安全测试",
        "参与安全实验室演练",
        "completed a security lab exercise",
        "参加 CTF competition",
        "负责CTF解题",
        "完成 CTF 夺旗挑战",
        "Performed CTF flag capture challenges",
        "accepted bug bounty",
    ),
)
def test_explicit_completed_security_contexts_are_authorized(text: str) -> None:
    assert has_positive_authorization_signal(text)
    assert source_is_authorized(None, text)


@pytest.mark.parametrize(
    ("environment", "text"),
    (
        ("lab", "安全实验室"),
        ("lab", "靶场项目"),
        ("lab", "security lab"),
        ("ctf", "CTF 竞赛"),
        ("ctf", "CTF challenge"),
        ("bug_bounty", "漏洞赏金计划中"),
    ),
)
def test_bare_safe_context_is_not_participation(environment: str, text: str) -> None:
    assert not has_positive_authorization_signal(text)
    assert not source_is_authorized(environment, text)
    assert infer_authorization_environment(text) is None


@pytest.mark.parametrize(
    ("environment", "text"),
    (
        ("ctf", "未参与CTF竞赛"),
        ("lab", "未接触靶场"),
        ("lab", "安全实验环境经验为无"),
        ("bug_bounty", "漏洞赏金无经验"),
        ("authorized", "授权测试：无"),
        ("authorized", "可能获得授权"),
        ("authorized", "没有授权"),
        ("authorized", "未经授权"),
        ("authorized", "without permission"),
        ("authorized", "not authorized"),
    ),
)
def test_structured_environment_does_not_override_an_explicit_denial(
    environment: str, text: str
) -> None:
    assert not source_is_authorized(environment, text)


@pytest.mark.parametrize("environment", ("academic", "open_source", "production_defense"))
def test_classification_only_environments_do_not_prove_offensive_authorization(
    environment: str,
) -> None:
    assert not source_is_authorized(environment, "复现未说明授权的 SSRF 攻击")


@pytest.mark.parametrize("environment", (None, "unknown", "lab", "ctf", "bug_bounty", "authorized"))
def test_structured_environment_never_overrides_explicit_illegal_text(
    environment: str | None,
) -> None:
    text = "在安全实验室完成练习。未经授权攻击外部网站。"
    assert has_global_authorization_denial(text)
    assert not has_positive_authorization_signal(text)
    assert infer_authorization_environment(text) is None
    assert not source_is_authorized(environment, text)


def test_explicit_illegal_activity_keeps_offensive_depth_capped() -> None:
    resume = Resume.model_validate(
        {
            "security_activities": [
                {
                    "environment": "unknown",
                    "description": (
                        "参与安全实验室演练；未经授权攻击外部网站。"
                        "负责设计渗透测试方法，复现 SSRF PoC，验证修复并回归测试。"
                    ),
                }
            ]
        }
    )
    item = (
        ScoreCalculator()
        .calculate(resume)
        .dimension_scores["vulnerability_research_security_assessment"]
    )
    assert item.depth_score == 4.0


@pytest.mark.parametrize(
    "scope",
    (
        "未参与CTF竞赛",
        "未接触靶场",
        "安全实验环境经验为无",
        "漏洞赏金无经验",
        "授权测试：无",
        "none: CTF competition",
        "zero security lab experience",
        "never participated in bug bounty",
        "authorized users",
        "chemistry lab equipment",
        "安全实验室",
        "靶场项目",
        "security lab",
        "CTF 竞赛",
        "CTF challenge",
        "漏洞赏金计划中",
    ),
)
def test_false_authorization_contexts_keep_offensive_depth_capped(scope: str) -> None:
    resume = Resume.model_validate(
        {
            "security_activities": [
                {
                    "environment": "unknown",
                    "description": (
                        f"{scope}。负责设计渗透测试方法，复现 SSRF PoC，验证并修复后回归测试。"
                    ),
                }
            ]
        }
    )
    item = (
        ScoreCalculator()
        .calculate(resume)
        .dimension_scores["vulnerability_research_security_assessment"]
    )
    assert item.depth_score == 4.0


def test_lab_facilities_management_cannot_lift_offensive_depth_cap() -> None:
    resume = Resume.model_validate(
        {
            "security_activities": [
                {
                    "environment": "unknown",
                    "description": (
                        "负责安全实验室设备管理。负责设计渗透测试方法，复现 SSRF PoC，"
                        "验证并修复后回归测试。"
                    ),
                }
            ]
        }
    )
    item = (
        ScoreCalculator()
        .calculate(resume)
        .dimension_scores["vulnerability_research_security_assessment"]
    )
    assert item.depth_score == 4.0


@pytest.mark.parametrize(
    "scope",
    (
        "Authorized Penetration Testing course",
        "客户授权渗透测试课程",
        "familiar with authorized penetration testing",
        "了解客户授权渗透测试",
        "client-authorized penetration testing, but permission is no longer valid",
        "已获得书面授权，但授权范围未明确",
        "已获得书面授权，但并未获准测试该目标",
        "client-authorized penetration testing, but permission was later revoked",
        "client-authorized penetration testing, but authorization was later found to be fake",
    ),
)
def test_structured_authorized_enum_cannot_lift_non_applied_or_revoked_evidence(
    scope: str,
) -> None:
    resume = Resume.model_validate(
        {
            "security_activities": [
                {
                    "environment": "authorized",
                    "name": scope,
                    "description": ("负责设计渗透测试方法，复现 SSRF PoC，验证并修复后回归测试。"),
                }
            ]
        }
    )
    item = (
        ScoreCalculator()
        .calculate(resume)
        .dimension_scores["vulnerability_research_security_assessment"]
    )
    assert item.depth_score == 4.0


def test_authorized_assessment_with_unauthorized_access_finding_keeps_applied_evidence() -> None:
    resume = Resume.model_validate(
        {
            "security_activities": [
                {
                    "environment": "authorized",
                    "role": "Client-authorized penetration testing",
                    "description": (
                        "Designed the assessment method, reproduced an SSRF PoC, fixed an "
                        "unauthorized access vulnerability, validated remediation, and retested."
                    ),
                }
            ]
        }
    )
    item = (
        ScoreCalculator()
        .calculate(resume)
        .dimension_scores["vulnerability_research_security_assessment"]
    )
    assert item.depth_score > 4.0


def test_negative_clause_does_not_hide_separate_positive_lab_evidence() -> None:
    text = "未参与CTF竞赛；在 security lab 完成安全测试。"
    assert has_positive_authorization_signal(text)
    assert source_is_authorized(None, text)


@pytest.mark.parametrize(
    ("environment", "text"),
    (
        ("authorized", "参加 CTF 竞赛"),
        ("ctf", "了解 CTF 规则"),
        ("lab", "阅读靶场介绍"),
        ("bug_bounty", "学习 bug bounty 概念"),
    ),
)
def test_environment_kind_requires_its_own_completed_context(
    environment: str,
    text: str,
) -> None:
    assert not source_is_authorized(environment, text)
