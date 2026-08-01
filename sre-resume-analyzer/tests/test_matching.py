from sre_resume_analyzer.matching import EvidenceMatcher, term_pattern
from sre_resume_analyzer.models import EvidenceLevel, Resume


def make_resume(project_descriptions, tech_stack=None, skills=None):
    projects = []
    for index, description in enumerate(project_descriptions):
        projects.append(
            {
                "name": f"project-{index}",
                "role": "engineer",
                "duration": "2025",
                "description": description,
                "tech_stack": list(tech_stack or []),
                "achievements": [],
            }
        )
    return Resume.model_validate(
        {
            "basic_info": {
                "name": "Candidate",
                "school": "Example University",
                "major": "Computer Science",
                "degree": "Bachelor",
                "graduation_year": 2026,
            },
            "internships": [],
            "projects": projects,
            "skills": skills
            or {
                "programming_languages": [],
                "monitoring_tools": [],
                "container_tech": [],
                "cloud_platforms": [],
                "cicd_tools": [],
            },
        }
    )


def test_cjk_adjacent_latin_terms_are_matched_without_spaces():
    resume = make_resume(["使用Prometheus和Grafana搭建监控体系"])

    evidence = EvidenceMatcher().find_evidence(resume, "monitoring")

    assert [item.keyword for item in evidence] == ["prometheus", "grafana"]
    assert {item.level for item in evidence} == {EvidenceLevel.implementation}


def test_latin_boundaries_do_not_match_substrings():
    assert term_pattern("go").search("Google") is None
    assert term_pattern("go").search("used Go for automation") is not None


def test_negated_and_weak_knowledge_statements_are_not_positive_evidence():
    resume = make_resume(
        [
            "No experience with Prometheus or Grafana.",
            "未使用Alertmanager\uff0c仅了解PagerDuty。",
        ]
    )
    matcher = EvidenceMatcher()

    assert matcher.find_evidence(resume, "monitoring") == []
    assert matcher.find_evidence(resume, "alerting") == []


def test_negation_scope_stops_at_contrast_boundaries():
    resume = make_resume(
        [
            "No experience with Prometheus, but implemented Grafana dashboards.",
            "未使用 Alertmanager, 但部署了 PagerDuty 值班流程。",
        ]
    )
    matcher = EvidenceMatcher()

    monitoring = matcher.find_evidence(resume, "monitoring")
    alerting = matcher.find_evidence(resume, "alerting")
    assert [item.keyword for item in monitoring] == ["grafana"]
    assert "pagerduty" in {item.keyword for item in alerting}
    assert "alertmanager" not in {item.keyword for item in alerting}


def test_repeated_keyword_is_deduplicated_per_source_and_stable():
    resume = make_resume(["部署Prometheus\uff1b使用Prometheus\uff1bPrometheus Prometheus"])
    matcher = EvidenceMatcher()

    first = matcher.find_evidence(resume, "monitoring")
    second = matcher.find_evidence(resume, "monitoring")

    assert first == second
    assert len(first) == 1
    assert first[0].level == EvidenceLevel.implementation


def test_outcome_requires_action_and_local_quantification():
    resume = make_resume(["使用Prometheus优化监控并将告警延迟降低30%"])

    evidence = EvidenceMatcher().find_evidence(resume, "monitoring")

    assert evidence[0].level == EvidenceLevel.outcome
    assert evidence[0].quantified is True
