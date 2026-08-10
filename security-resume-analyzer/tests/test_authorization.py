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
        (
            "lifecycle",
            "Client-authorized pentest. Found authorization was revoked before testing "
            "a vulnerability.",
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
        "已获得书面授权，但授权是否生效不确定",
        "已获得书面授权，但授权是否生效未确认",
        "已获得书面授权，但不确定授权是否生效",
        "已获得书面授权，但允许测试到哪里尚不清楚",
        "已获得书面授权，但授权的法律效力不确定",
        "已获得书面授权，但无法确认授权范围",
        "已获得书面授权，但授权有效性待确认",
        "已获得书面授权，但授权生效与否不确定",
        "已获得书面授权，但授权有效性尚待确认",
        "已获得书面授权，但授权当前是否有效未知",
        "Client authorization was obtained, but whether the authorization is effective "
        "is uncertain",
        "Client authorization was obtained, but it remains uncertain whether permission "
        "is effective",
        "Client authorization was obtained, but authorization validity was not confirmed",
        "Unable to confirm the authorization scope",
        "The legal validity of the authorization is uncertain",
        "Authorization validity is pending confirmation",
    ),
)
def test_uncertain_authorization_effectiveness_is_a_global_denial(text: str) -> None:
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
        "不确定是否已授权",
        "尚不清楚授权范围",
        "Unclear whether authorized",
        "Uncertain whether permission was granted",
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
        "了解 CTF 规则",
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
    "text",
    (
        "负责 CTF 竞赛官网开发",
        "负责 CTF 竞赛赞助商对接",
        "负责 CTF 竞赛餐饮采购",
        "CTF 校园赛\n负责官网开发\n扫描死链并修复页面",
        "Developed the CTF competition website",
        "Coordinated CTF competition sponsors",
        "CTF competition\nDeveloped the website\nScanned dead links and fixed web pages",
    ),
)
def test_ctf_support_work_without_a_technical_action_is_not_authorization(text: str) -> None:
    assert not has_positive_authorization_signal(text)
    assert not source_is_authorized("ctf", text)
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


def test_defensive_unauthorized_device_alert_rule_is_not_illegal_activity() -> None:
    text = "在安全实验室使用 Sigma 测试未授权设备接入告警规则"
    assert not has_global_authorization_denial(text)
    assert not has_negative_authorization_signal(text)


@pytest.mark.parametrize(
    "continuation",
    (
        "后继续攻击该设备",
        "，并扫描该未授权设备",
        "，但随后入侵该设备",
    ),
)
def test_defensive_finding_cannot_mask_malicious_continuation(
    continuation: str,
) -> None:
    text = f"参与安全实验室演练。使用 Sigma 测试未授权设备接入告警规则{continuation}。"
    assert has_global_authorization_denial(text)
    assert has_negative_authorization_signal(text)
    assert not has_positive_authorization_signal(text)
    assert not source_is_authorized("lab", text)


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
        "参加 CTF 竞赛，修复授权法律效力不确定漏洞",
        "CTF competition\nfixed an authorization validity uncertain vulnerability",
        "参加 CTF 竞赛，修复授权生效与否不确定漏洞",
        "参加 CTF 竞赛，修复授权有效性尚待确认漏洞",
        "参加 CTF 竞赛，修复授权当前是否有效未知漏洞",
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


def test_multiple_authorization_findings_preserve_continuation_offsets() -> None:
    text = "参与安全实验室演练，发现授权范围未明确漏洞；修复授权已失效漏洞后继续测试"
    assert has_global_authorization_denial(text)
    assert has_negative_authorization_signal(text)
    assert not has_positive_authorization_signal(text)
    assert not source_is_authorized("lab", text)


def test_actual_unauthorized_access_activity_remains_denied() -> None:
    text = "Unauthorized access to an external website"
    assert has_negative_authorization_signal(text)
    assert not source_is_authorized("authorized", text)


@pytest.mark.parametrize(
    "illegal_activity",
    (
        "攻击未经授权的网站",
        "扫描未授权的目标",
        "入侵未获授权的系统",
        "对未经授权的服务器进行扫描",
        "attacked an unauthorized website",
        "scanning an unauthorized target",
        "Scanned an unapproved target",
        "Attacked a non-permitted host",
        "Exploited an unpermitted server",
        "Scanned a target without approval",
        "Attacked a host without consent",
        "Scanned an unapproved database",
        "Scanned an unapproved API",
        "Scanned an unapproved cloud account",
        "Scanned an unapproved Kubernetes cluster",
        "扫描未批准目标",
        "攻击未获许可主机",
        "利用未经批准服务器",
        "擅自扫描目标",
        "扫描未批准数据库",
        "扫描未批准应用",
        "扫描未批准 API",
        "扫描未批准服务",
        "扫描未批准集群",
        "扫描未批准账号",
    ),
)
def test_action_before_unauthorized_target_overrides_safe_context(
    illegal_activity: str,
) -> None:
    text = f"参与安全实验室演练。{illegal_activity}。"
    assert has_global_authorization_denial(text)
    assert has_negative_authorization_signal(text)
    assert not has_positive_authorization_signal(text)
    assert infer_authorization_environment(text) is None
    for environment in (None, "lab", "ctf", "bug_bounty", "authorized"):
        assert not source_is_authorized(environment, text)


@pytest.mark.parametrize(
    "disclaimer",
    (
        "未授权攻击不作为项目内容",
        "项目内容不涉及未经授权渗透测试",
        "攻击未经授权的网站不作为项目内容",
        "项目内容不涉及扫描未授权的目标",
        "Unauthorized attacks were not part of the project",
        "Attacking an unauthorized website was not part of the project",
        "Scanning an unapproved target was not part of the project",
        "Scanning a target without approval was not part of the project",
        "Scanning an unapproved database was not part of the project",
        "Scanning an unapproved cloud account was not part of the project",
        "Scanning an unapproved Kubernetes cluster was not part of the project",
        "扫描未批准目标不属于项目内容",
        "扫描未批准数据库不属于项目内容",
        "项目内容不包含扫描未批准应用",
        "项目内容不包含扫描未批准 API",
        "擅自扫描目标不属于项目内容",
        "项目内容不包含擅自扫描目标",
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
        "负责CTF解题",
        "完成 CTF 夺旗挑战",
        "Performed CTF flag capture challenges",
        "Solved a CTF challenge",
        "Completed a CTF challenge",
        "完成 CTF 挑战",
        "参加 CTF 竞赛并完成题目",
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
        ("ctf", "参加 CTF competition"),
        ("bug_bounty", "漏洞赏金计划中"),
    ),
)
def test_bare_safe_context_is_not_participation(environment: str, text: str) -> None:
    assert not has_positive_authorization_signal(text)
    assert not source_is_authorized(environment, text)
    assert infer_authorization_environment(text) is None


@pytest.mark.parametrize(
    "record_text",
    (
        "CTF 校园赛\n复现 SSRF 漏洞并提交 flag",
        "CTF competition\nReproduced an SSRF vulnerability and submitted a flag",
    ),
)
def test_ctf_record_combines_context_and_technical_action_across_fields(
    record_text: str,
) -> None:
    assert has_positive_authorization_signal(record_text)
    assert source_is_authorized("ctf", record_text)
    assert infer_authorization_environment(record_text) == "ctf"


@pytest.mark.parametrize(
    ("environment", "context"),
    (
        ("lab", "Participated in a security lab exercise."),
        ("ctf", "Participated in a CTF event."),
        ("bug_bounty", "Participated in a bug bounty program."),
        ("authorized", "Authorized security assessment."),
    ),
)
def test_isolated_safe_marker_cannot_authorize_customer_production_target(
    environment: str,
    context: str,
) -> None:
    text = f"{context} Reproduced SSRF on a customer production system and validated a PoC."
    assert not has_positive_authorization_signal(text)
    assert not source_is_authorized(environment, text)
    assert infer_authorization_environment(text) is None


@pytest.mark.parametrize(
    ("environment", "text"),
    (
        (
            "ctf",
            "Participated in a CTF event. Exploited SQL injection on a customer production database.",
        ),
        (
            "lab",
            "Participated in a security lab exercise. Exploited SQL injection on a client "
            "production database.",
        ),
        ("ctf", "参加 CTF 竞赛并解题；对客户生产数据库进行 SQL 注入测试。"),
        ("lab", "参加安全靶场演练；扫描第三方生产应用。"),
        ("ctf", "Participated in a CTF event. Scanned a customer prod server."),
        ("lab", "Participated in a security lab exercise. Tested a third-party prod API."),
        ("ctf", "Participated in a CTF event. Exploited an external database."),
        ("lab", "Participated in a security lab exercise. Tested a customer cloud account."),
        ("ctf", "Participated in a CTF event. Scanned a customer Kubernetes cluster."),
        ("lab", "Participated in a security lab exercise. Tested a third-party SaaS application."),
        ("lab", "参加安全靶场演练；扫描客户云账号。"),
        ("ctf", "参加 CTF 竞赛并解题；测试外部 API 接口。"),
        ("lab", "参加安全靶场演练；扫描第三方 Kubernetes 集群。"),
    ),
)
def test_extended_external_target_vocabulary_cannot_borrow_safe_environment(
    environment: str,
    text: str,
) -> None:
    assert not has_positive_authorization_signal(text)
    assert not source_is_authorized(environment, text)
    assert infer_authorization_environment(text) is None


def test_bound_customer_production_authorization_remains_valid() -> None:
    text = (
        "Authorized customer production pentest. Reproduced SSRF on the customer production "
        "system and validated a PoC."
    )
    assert has_positive_authorization_signal(text)
    assert source_is_authorized("authorized", text)
    assert infer_authorization_environment(text) == "authorized"


@pytest.mark.parametrize(
    "text",
    (
        "Authorized customer production database pentest. Exploited SQL injection on the "
        "customer production database.",
        "Authorized third-party SaaS application pentest. Tested the third-party SaaS application.",
        "Authorized customer cloud account pentest. Tested the customer cloud account.",
        "Authorized customer Kubernetes cluster pentest. Scanned the customer Kubernetes cluster.",
        "Client-authorized security assessment of the client prod API. Reproduced SSRF on the "
        "client prod API.",
        "Authorized security assessment on the customer production database. Exploited SQL "
        "injection on the customer production database.",
        "Approved penetration testing against the customer cloud account. Tested the customer "
        "cloud account.",
        "Authorized security testing of the customer Kubernetes cluster. Scanned the customer "
        "Kubernetes cluster.",
        "经书面授权对客户生产应用开展渗透测试；在客户生产应用复现 SQL 注入漏洞。",
        "经书面授权对客户生产 API 开展安全评估；在客户生产 API 复现 SSRF。",
    ),
)
def test_bound_extended_target_authorization_remains_valid(text: str) -> None:
    assert has_positive_authorization_signal(text)
    assert source_is_authorized("authorized", text)
    assert infer_authorization_environment(text) == "authorized"


def test_bound_customer_authorization_cannot_cover_third_party_target() -> None:
    text = (
        "Authorized customer production pentest. Reproduced SSRF on a third-party production "
        "system and validated a PoC."
    )
    assert not has_positive_authorization_signal(text)
    assert not source_is_authorized("authorized", text)
    assert infer_authorization_environment(text) is None


def test_action_before_customer_authorization_cannot_cover_third_party_target() -> None:
    text = (
        "Client-authorized security assessment of the client prod API. Attacked a third-party "
        "production API and validated a PoC."
    )
    assert not has_positive_authorization_signal(text)
    assert not source_is_authorized("authorized", text)
    assert infer_authorization_environment(text) is None


@pytest.mark.parametrize("subject", ("甲方", "乙方", "丙方"))
@pytest.mark.parametrize(
    "template",
    (
        "获得授权对{subject}生产系统开展安全测试；随后扫描{subject}生产系统。",
        "获得{subject}授权测试{subject}生产系统；随后验证{subject}生产系统漏洞。",
        "经{subject}授权测试{subject}生产系统；随后验证{subject}生产系统漏洞。",
        "在{subject}授权范围内测试{subject}生产系统；随后验证{subject}生产系统漏洞。",
    ),
)
def test_chinese_named_party_authorization_remains_bound_to_same_subject(
    subject: str,
    template: str,
) -> None:
    text = template.format(subject=subject)
    assert has_positive_authorization_signal(text)
    assert source_is_authorized("authorized", text)
    assert infer_authorization_environment(text) == "authorized"


@pytest.mark.parametrize(
    ("authorized_subject", "activity_subject"),
    (
        ("甲方", "乙方"),
        ("甲方", "丙方"),
        ("乙方", "甲方"),
        ("乙方", "丙方"),
        ("丙方", "甲方"),
        ("丙方", "乙方"),
    ),
)
@pytest.mark.parametrize(
    "template",
    (
        "获得授权对{authorized_subject}生产系统开展安全测试；随后扫描{activity_subject}生产系统。",
        "获得{authorized_subject}授权测试{activity_subject}生产系统；"
        "随后验证{activity_subject}生产系统漏洞。",
        "经{authorized_subject}授权测试{activity_subject}生产系统；"
        "随后验证{activity_subject}生产系统漏洞。",
        "在{authorized_subject}授权范围内测试{activity_subject}生产系统；"
        "随后验证{activity_subject}生产系统漏洞。",
    ),
)
def test_chinese_named_party_authorization_cannot_cover_another_subject(
    authorized_subject: str,
    activity_subject: str,
    template: str,
) -> None:
    text = template.format(
        authorized_subject=authorized_subject,
        activity_subject=activity_subject,
    )
    assert not has_positive_authorization_signal(text)
    assert not source_is_authorized("authorized", text)
    assert infer_authorization_environment(text) is None


@pytest.mark.parametrize(
    "text",
    (
        "获得甲方授权测试甲方生产系统；随后攻击丙方生产系统。",
        "获得乙方授权测试乙方生产系统；随后扫描甲方生产系统。",
        "Authorized security testing of the customer production system. Attack a third-party "
        "production system.",
        "Authorized security testing of the customer production system. Scan an external "
        "production system.",
    ),
)
def test_active_offensive_verb_cannot_borrow_authorization_for_another_subject(
    text: str,
) -> None:
    assert not has_positive_authorization_signal(text)
    assert not source_is_authorized("authorized", text)
    assert infer_authorization_environment(text) is None


@pytest.mark.parametrize(
    "text",
    (
        "获得甲方授权测试甲方生产系统；随后攻击甲方生产系统。",
        "获得乙方授权测试乙方生产系统；随后扫描乙方生产系统。",
        "获得丙方授权测试丙方生产系统；随后利用丙方生产系统。",
        "Authorized security testing of the customer production system. Attack the customer "
        "production system.",
    ),
)
def test_active_offensive_verb_preserves_same_subject_authorization(text: str) -> None:
    assert has_positive_authorization_signal(text)
    assert source_is_authorized("authorized", text)
    assert infer_authorization_environment(text) == "authorized"


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
