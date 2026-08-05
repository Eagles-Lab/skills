"""Language-aware, deterministic software-development evidence matching."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterator, Sequence

from .models import DimensionName, Evidence, EvidenceLevel, Experience, Resume, SourceKind
from .security import is_instruction_like

DimensionConcepts = dict[str, dict[str, dict[str, tuple[str, ...]]]]

DIMENSION_CONCEPTS: DimensionConcepts = {
    "computer_science_software_foundation": {
        "data_structures_algorithms": {
            "algorithms": (
                "data structure",
                "algorithm",
                "complexity analysis",
                "数据结构",
                "算法",
                "时间复杂度",
                "空间复杂度",
                "动态规划",
                "图算法",
            ),
        },
        "operating_systems_concurrency": {
            "operating_systems": (
                "linux",
                "unix",
                "windows",
                "operating system",
                "操作系统",
                "进程",
                "线程",
                "文件系统",
                "虚拟内存",
                "系统调用",
            ),
            "concurrency": (
                "concurrency",
                "parallelism",
                "mutex",
                "lock-free",
                "协程",
                "并发",
                "并行",
                "互斥锁",
                "线程池",
            ),
        },
        "network_web_protocols": {
            "networking": (
                "tcp/ip",
                "tcp",
                "udp",
                "dns",
                "socket",
                "websocket",
                "网络协议",
                "网络编程",
            ),
            "web_protocols": (
                "http",
                "https",
                "tls",
                "http/2",
                "http/3",
                "grpc",
                "rest",
            ),
        },
        "database_storage": {
            "database": (
                "mysql",
                "postgresql",
                "sqlite",
                "mongodb",
                "redis",
                "database",
                "sql",
                "数据库",
                "事务",
                "索引",
            ),
            "storage": ("storage", "filesystem", "object storage", "存储", "对象存储"),
        },
        "language_runtime": {
            "runtime": (
                "garbage collection",
                "garbage collector",
                "jvm",
                "runtime",
                "compiler",
                "interpreter",
                "memory model",
                "垃圾回收",
                "运行时",
                "编译器",
                "解释器",
                "内存模型",
            ),
        },
    },
    "programming_code_quality": {
        "implementation": {
            "programming": (
                "python",
                "golang",
                "go",
                "java",
                "c",
                "c++",
                "c#",
                "rust",
                "kotlin",
                "swift",
                "javascript",
                "typescript",
                "dart",
                "php",
            ),
            "implementation": ("implemented", "developed", "编码", "实现", "开发"),
        },
        "abstraction_design": {
            "abstraction": (
                "object oriented",
                "functional programming",
                "design pattern",
                "domain model",
                "abstraction",
                "面向对象",
                "函数式编程",
                "设计模式",
                "领域模型",
                "抽象",
            ),
        },
        "api_contracts": {
            "api": (
                "api",
                "rest api",
                "graphql",
                "grpc",
                "openapi",
                "接口设计",
                "接口契约",
                "协议设计",
            ),
        },
        "error_handling_reliability": {
            "error_handling": (
                "error handling",
                "exception handling",
                "retry",
                "idempotency",
                "timeout",
                "circuit breaker",
                "异常处理",
                "错误处理",
                "重试",
                "幂等",
                "超时",
                "熔断",
            ),
        },
        "maintainability_refactoring": {
            "maintainability": (
                "maintainability",
                "clean code",
                "refactor",
                "technical debt",
                "code quality",
                "可维护性",
                "代码规范",
                "重构",
                "技术债",
                "代码质量",
            ),
        },
        "code_review_static_analysis": {
            "code_review": ("code review", "pull request", "merge request", "代码审查"),
            "static_analysis": (
                "static analysis",
                "lint",
                "ruff",
                "eslint",
                "sonarqube",
                "静态检查",
                "静态分析",
            ),
        },
    },
    "application_development_architecture": {
        "frontend_client": {
            "frontend": (
                "react",
                "vue",
                "angular",
                "next.js",
                "frontend",
                "html",
                "css",
                "前端",
                "组件化",
                "响应式",
            ),
            "client": (
                "android",
                "ios",
                "flutter",
                "react native",
                "desktop application",
                "客户端",
                "移动端",
                "小程序",
            ),
        },
        "backend_services": {
            "backend": (
                "backend",
                "spring boot",
                "django",
                "fastapi",
                "flask",
                "gin",
                "node.js",
                "server",
                "后端",
                "服务端",
                "微服务",
            ),
        },
        "data_modeling": {
            "data_modeling": (
                "data model",
                "schema design",
                "database design",
                "orm",
                "数据建模",
                "表结构设计",
                "数据库设计",
            ),
        },
        "integration_distributed": {
            "integration": (
                "message queue",
                "kafka",
                "rabbitmq",
                "rpc",
                "event driven",
                "service discovery",
                "消息队列",
                "事件驱动",
                "服务发现",
            ),
            "distributed": (
                "distributed system",
                "consensus",
                "high availability",
                "scalability",
                "分布式",
                "一致性",
                "高可用",
                "可扩展",
            ),
        },
        "security_authentication": {
            "security_auth": (
                "authentication",
                "authorization",
                "oauth",
                "oidc",
                "jwt",
                "rbac",
                "xss",
                "csrf",
                "sql injection",
                "认证",
                "鉴权",
                "权限控制",
                "安全编码",
            ),
        },
        "product_user_loop": {
            "product_delivery": (
                "user feedback",
                "a/b test",
                "conversion rate",
                "daily active user",
                "released",
                "launched",
                "用户反馈",
                "业务需求",
                "产品迭代",
                "上线",
                "发布",
                "日活",
            ),
        },
    },
    "debugging_performance_problem_solving": {
        "problem_decomposition": {
            "problem_decomposition": (
                "problem decomposition",
                "hypothesis",
                "trade-off",
                "technical investigation",
                "问题拆解",
                "假设",
                "技术调研",
                "方案对比",
                "权衡",
            ),
        },
        "logs_debugging": {
            "debugging": (
                "debug",
                "debugger",
                "breakpoint",
                "stack trace",
                "日志分析",
                "调试",
                "断点",
                "堆栈",
            ),
        },
        "root_cause_analysis": {
            "root_cause": (
                "root cause",
                "root cause analysis",
                "fault localization",
                "根因",
                "根因分析",
                "故障定位",
                "问题定位",
            ),
        },
        "profiling_performance": {
            "performance": (
                "profiling",
                "profiler",
                "flame graph",
                "benchmark",
                "latency",
                "throughput",
                "qps",
                "性能分析",
                "性能优化",
                "火焰图",
                "延迟",
                "吞吐",
            ),
        },
        "experimentation_validation": {
            "validation": (
                "experiment",
                "reproduce",
                "validation",
                "comparison test",
                "实验",
                "复现",
                "验证",
                "对照测试",
            ),
        },
        "remediation_regression": {
            "remediation": (
                "regression test",
                "postmortem",
                "fixed",
                "resolved",
                "回归测试",
                "修复",
                "解决",
                "复盘",
                "防止复发",
            ),
        },
    },
    "engineering_delivery_collaboration": {
        "testing": {
            "testing": (
                "unit test",
                "integration test",
                "end-to-end test",
                "property test",
                "test coverage",
                "pytest",
                "junit",
                "单元测试",
                "集成测试",
                "端到端测试",
                "测试覆盖率",
            ),
        },
        "version_control_collaboration": {
            "version_control": ("git", "github", "gitlab", "版本控制", "分支管理"),
            "collaboration": (
                "pull request",
                "merge request",
                "code review",
                "pair programming",
                "协作开发",
                "代码审查",
            ),
        },
        "build_cicd": {
            "build": ("maven", "gradle", "webpack", "vite", "cmake", "构建系统"),
            "cicd": (
                "ci/cd",
                "continuous integration",
                "github actions",
                "gitlab ci",
                "jenkins",
                "持续集成",
                "持续交付",
            ),
        },
        "deployment_environment": {
            "deployment": (
                "docker",
                "kubernetes",
                "k8s",
                "cloud deployment",
                "deployment",
                "release",
                "rollback",
                "容器",
                "部署",
                "发布",
                "回滚",
            ),
        },
        "documentation_observability": {
            "documentation": (
                "documentation",
                "readme",
                "design document",
                "api document",
                "技术文档",
                "设计文档",
                "接口文档",
            ),
            "observability": (
                "logging",
                "metrics",
                "tracing",
                "monitoring",
                "prometheus",
                "grafana",
                "可观测性",
                "监控",
                "指标",
                "链路追踪",
            ),
        },
        "team_open_source": {
            "team": (
                "cross-functional",
                "team collaboration",
                "mentor",
                "团队协作",
                "跨团队",
                "需求评审",
            ),
            "open_source": (
                "open source",
                "contributor",
                "maintainer",
                "开源贡献",
                "开源项目",
                "贡献者",
            ),
        },
    },
    "ai_assisted_development_ai_engineering": {
        "ai_coding_assistance": {
            "ai_coding": (
                "cursor",
                "github copilot",
                "copilot",
                "claude code",
                "chatgpt",
                "ai coding",
                "vibe coding",
                "ai 辅助编程",
                "代码生成",
            ),
        },
        "ai_testing_debugging": {
            "ai_testing": (
                "ai generated test",
                "ai test generation",
                "ai debugging",
                "ai root cause",
                "ai 生成测试",
                "ai 测试",
                "ai 调试",
                "ai 根因分析",
                "智能测试",
            ),
        },
        "llm_rag_application": {
            "llm_application": (
                "large language model",
                "llm application",
                "rag",
                "retrieval augmented generation",
                "embedding",
                "vector database",
                "大模型应用",
                "检索增强生成",
                "向量数据库",
            ),
        },
        "agent_tool_workflow": {
            "agent_workflow": (
                "ai agent",
                "agentic workflow",
                "tool calling",
                "function calling",
                "mcp server",
                "智能体",
                "工具调用",
                "工作流编排",
                "多智能体",
            ),
        },
        "evaluation": {
            "ai_evaluation": (
                "llm evaluation",
                "evaluation dataset",
                "benchmark",
                "accuracy",
                "hallucination rate",
                "模型评测",
                "评测集",
                "基准测试",
                "准确率",
                "幻觉率",
            ),
        },
        "controls_fallback": {
            "ai_controls": (
                "human approval",
                "human review",
                "permission boundary",
                "sandbox",
                "guardrail",
                "fallback",
                "rollback",
                "人工确认",
                "人工审核",
                "权限边界",
                "沙箱",
                "护栏",
                "降级",
                "回滚",
            ),
        },
    },
}

_SENTENCE = re.compile(r"[^\n。！？!?；;]+")
_CJK = re.compile(r"[\u3400-\u9fff]")
_QUANTIFIED = re.compile(
    r"\d+(?:\.\d+)?\s*(?:%|％|个|次|条|台|人|用户|小时|天|ms|s|x|倍|万|qps|rps)", re.I
)
_ACTION = re.compile(
    r"使用|分析|排查|验证|测试|调试|优化|编码|参与|维护|集成|发布|上线|"
    r"\b(?:used?|analy[sz]ed?|debug(?:ged)?|test(?:ed)?|optim(?:ize|ized)|coded?|maintain(?:ed)?|integrat(?:ed)?|released?|launched?)\b",
    re.I,
)
_IMPLEMENT = re.compile(
    r"实现|开发|构建|部署|配置|编写|设计|搭建|集成|重构|修复|"
    r"\b(?:implement(?:ed)?|develop(?:ed)?|build|built|deploy(?:ed)?|configur(?:ed)?|design(?:ed)?|refactor(?:ed)?|fixed?)\b",
    re.I,
)
_OWN = re.compile(r"主导|负责|独立完成|牵头|设计|\b(?:owned?|led|lead|designed?)\b", re.I)
_PRODUCTION = re.compile(
    r"生产|线上|真实业务|客户|用户|开源社区|\b(?:production|real[- ]world|customer|user|open source community)\b",
    re.I,
)
_OUTCOME = re.compile(
    r"提升|降低|减少|缩短|增加|优化|解决|修复|发布|上线|"
    r"\b(?:improved?|reduced?|decreased?|increased?|optimized?|resolved?|fixed|released?|launched?)\b",
    re.I,
)
_NEGATION_BEFORE = re.compile(
    r"(?:不熟悉|未使用|没有使用|没有用过|无经验|仅了解|只了解|学习中|尚未)[^，。;；\n]{0,20}$|"
    r"\b(?:no experience (?:with|in)?|not familiar (?:with)?|never used|without experience (?:with|in)?)\b[^.!?;]{0,24}$",
    re.I,
)
_NEGATION_AFTER = re.compile(
    r"^(?:方面)?(?:不熟悉|未使用|没有使用|无经验|仅了解|学习中)|"
    r"^\s*(?:was not used|not used|only learning)",
    re.I,
)


def normalize_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).lower()
    value = re.sub(r"[‐‑‒–—−]", "-", value)
    return re.sub(r"[\t\r ]+", " ", value).strip()


def term_pattern(term: str) -> re.Pattern[str]:
    term = normalize_text(term)
    escaped = re.escape(term).replace(r"\ ", r"\s+")
    if _CJK.search(term):
        return re.compile(escaped, re.I)
    return re.compile(r"(?<![A-Za-z0-9_])" + escaped + r"(?![A-Za-z0-9_])", re.I)


def is_quantified(text: str) -> bool:
    return bool(_QUANTIFIED.search(text))


def classify_evidence(text: str, mention_only: bool = False) -> EvidenceLevel:
    if mention_only:
        return EvidenceLevel.mention
    if is_quantified(text) and _OUTCOME.search(text):
        return EvidenceLevel.outcome
    if _PRODUCTION.search(text) and (_ACTION.search(text) or _IMPLEMENT.search(text)):
        return EvidenceLevel.production
    if _OWN.search(text):
        return EvidenceLevel.ownership
    if _IMPLEMENT.search(text):
        return EvidenceLevel.implementation
    if _ACTION.search(text):
        return EvidenceLevel.usage
    return EvidenceLevel.mention


@dataclass(frozen=True)
class TextRecord:
    source_kind: SourceKind
    source_id: str
    text: str
    mention_only: bool = False


def iter_resume_records(resume: Resume) -> Iterator[TextRecord]:
    for group, values in sorted(resume.skills.model_dump(mode="python").items()):
        for value in values:
            yield TextRecord("skills", f"skills:{group}", value, True)
    collections: tuple[tuple[SourceKind, Sequence[Experience]], ...] = (
        ("internship", resume.internships),
        ("project", resume.projects),
    )
    for kind, records in collections:
        for index, record in enumerate(records):
            source_id = f"{kind}:{index}"
            if record.name:
                yield TextRecord(kind, source_id, record.name, True)
            if record.role:
                yield TextRecord(kind, source_id, record.role, True)
            if record.description:
                yield TextRecord(kind, source_id, record.description)
            for value in record.achievements:
                yield TextRecord(kind, source_id, value)
            for value in record.tech_stack:
                yield TextRecord(kind, source_id, value, True)


def iter_sentences(text: str) -> Iterator[tuple[str, int]]:
    for match in _SENTENCE.finditer(text):
        value = match.group(0).strip(" ,，:\t")
        if value:
            yield value, match.start()


def _negated(text: str, start: int, end: int) -> bool:
    before = text[max(0, start - 48) : start]
    after = text[end : min(len(text), end + 24)]
    return bool(_NEGATION_BEFORE.search(before) or _NEGATION_AFTER.search(after))


class EvidenceMatcher:
    def __init__(self, concepts: DimensionConcepts | None = None) -> None:
        self.concepts = concepts or DIMENSION_CONCEPTS

    def find_evidence(self, resume: Resume, dimension: DimensionName) -> list[Evidence]:
        lookup: dict[str, tuple[str, tuple[str, ...]]] = {}
        for group, concepts in self.concepts[dimension].items():
            for concept, variants in concepts.items():
                lookup[concept] = (group, variants)
        best: dict[tuple[str, str], Evidence] = {}
        for record in iter_resume_records(resume):
            for sentence, offset in iter_sentences(record.text):
                normalized = normalize_text(sentence)
                if is_instruction_like(sentence):
                    continue
                for concept in sorted(lookup):
                    group, variants = lookup[concept]
                    positions: list[int] = []
                    for variant in sorted(set(variants), key=lambda value: (-len(value), value)):
                        for match in term_pattern(variant).finditer(normalized):
                            if not _negated(normalized, match.start(), match.end()):
                                positions.append(match.start())
                    if not positions:
                        continue
                    item = Evidence(
                        dimension=dimension,
                        concept=concept,
                        evidence_group=group,
                        source_kind=record.source_kind,
                        source_id=record.source_id,
                        context=sentence,
                        level=classify_evidence(sentence, record.mention_only),
                        position=offset + min(positions),
                        quantified=is_quantified(sentence),
                    )
                    key = (record.source_id, concept)
                    previous = best.get(key)
                    if previous is None or _strength(item) > _strength(previous):
                        best[key] = item
        order = {"skills": 0, "internship": 1, "project": 2}
        return sorted(
            best.values(),
            key=lambda item: (order[item.source_kind], item.source_id, item.position, item.concept),
        )


_LEVEL = {
    EvidenceLevel.mention: 2,
    EvidenceLevel.usage: 4,
    EvidenceLevel.implementation: 6,
    EvidenceLevel.ownership: 8,
    EvidenceLevel.production: 9,
    EvidenceLevel.outcome: 9,
}


def _strength(item: Evidence) -> tuple[int, int, int]:
    return (_LEVEL[item.level], int(item.quantified), -item.position)
