#!/usr/bin/env python3
"""
从 sre_keywords.yaml 生成 sre_keywords.md 和 keywords_core.json
确保三份文件内容一致,YAML 作为唯一数据源
"""

import yaml
import json
from pathlib import Path


def load_yaml(yaml_path):
    """加载 YAML 配置文件"""
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def generate_markdown(data, output_path):
    """生成 Markdown 文档"""
    md_content = []

    # 文档头部
    md_content.append("# SRE 技术关键词库")
    md_content.append("")
    md_content.append("本文档整理了 SRE 岗位相关的技术关键词,用于简历内容分析和评分。")
    md_content.append("")
    md_content.append("---")
    md_content.append("")

    # 1. AI 和智能运维
    md_content.append("## 1. AI 和智能运维 (AI & Intelligent Ops)")
    md_content.append("")

    ai_categories = {
        'llm': '大语言模型 (LLM)',
        'ai_agents': 'AI Agent',
        'ai_ide': 'AI IDE',
        'ml_ops': 'ML Ops',
        'aiops': 'AIOps',
        'nlp': '自然语言处理 (NLP)',
        'computer_vision': '计算机视觉 (Computer Vision)'
    }

    for key, title in ai_categories.items():
        if key in data['ai_and_intelligent_ops']:
            md_content.append(f"### {title}")
            md_content.append("")
            for keyword in data['ai_and_intelligent_ops'][key]:
                md_content.append(f"- {keyword}")
            md_content.append("")

    md_content.append("---")
    md_content.append("")

    # 2. 监控
    md_content.append("## 2. 监控 (Monitoring)")
    md_content.append("")

    monitoring_categories = {
        'tools': '监控工具',
        'concepts': '监控概念',
        'indicators': '监控指标'
    }

    for key, title in monitoring_categories.items():
        if key in data['monitoring']:
            md_content.append(f"### {title}")
            md_content.append("")
            for keyword in data['monitoring'][key]:
                md_content.append(f"- {keyword}")
            md_content.append("")

    md_content.append("---")
    md_content.append("")

    # 3. 告警
    md_content.append("## 3. 告警 (Alerting)")
    md_content.append("")

    if 'tools' in data['alerting']:
        md_content.append("### 告警工具")
        md_content.append("")
        for keyword in data['alerting']['tools']:
            md_content.append(f"- {keyword}")
        md_content.append("")

    if 'concepts' in data['alerting']:
        md_content.append("### 告警概念")
        md_content.append("")
        for keyword in data['alerting']['concepts']:
            md_content.append(f"- {keyword}")
        md_content.append("")

    md_content.append("---")
    md_content.append("")

    # 4. 自动化
    md_content.append("## 4. 自动化 (Automation)")
    md_content.append("")

    automation_categories = {
        'languages': '编程语言',
        'cicd': 'CI/CD 工具',
        'iac': '配置管理 & IaC',
        'concepts': '自动化概念'
    }

    for key, title in automation_categories.items():
        if key in data['automation']:
            md_content.append(f"### {title}")
            md_content.append("")
            for keyword in data['automation'][key]:
                md_content.append(f"- {keyword}")
            md_content.append("")

    md_content.append("---")
    md_content.append("")

    # 5. 容器化和云原生
    md_content.append("## 5. 容器化 & 云原生 (Containerization & Cloud Native)")
    md_content.append("")

    container_categories = {
        'container_runtime': '容器运行时',
        'orchestration': '容器编排',
        'cloud_native': '云原生生态',
        'cloud_platforms': '云平台',
        'concepts': '容器化概念'
    }

    for key, title in container_categories.items():
        if key in data['containerization']:
            md_content.append(f"### {title}")
            md_content.append("")
            for keyword in data['containerization'][key]:
                md_content.append(f"- {keyword}")
            md_content.append("")

    md_content.append("---")
    md_content.append("")

    # 6. 故障处理
    md_content.append("## 6. 故障处理 (Incident Handling)")
    md_content.append("")

    incident_categories = {
        'tools': '故障响应工具',
        'concepts': '故障处理概念',
        'debugging_tools': '调试工具'
    }

    for key, title in incident_categories.items():
        if key in data['incident_handling']:
            md_content.append(f"### {title}")
            md_content.append("")
            for keyword in data['incident_handling'][key]:
                md_content.append(f"- {keyword}")
            md_content.append("")

    md_content.append("---")
    md_content.append("")

    # 7. 数据库和存储
    md_content.append("## 7. 数据库 & 存储")
    md_content.append("")

    db_categories = {
        'relational': '关系型数据库',
        'nosql': 'NoSQL 数据库',
        'messaging': '消息队列',
        'storage': '存储'
    }

    for key, title in db_categories.items():
        if key in data['database']:
            md_content.append(f"### {title}")
            md_content.append("")
            for keyword in data['database'][key]:
                md_content.append(f"- {keyword}")
            md_content.append("")

    md_content.append("---")
    md_content.append("")

    # 8. 网络
    md_content.append("## 8. 网络")
    md_content.append("")

    network_categories = {
        'protocols': '协议',
        'load_balancers': '负载均衡',
        'dns': 'DNS',
        'concepts': '网络概念'
    }

    for key, title in network_categories.items():
        if key in data['networking']:
            md_content.append(f"### {title}")
            md_content.append("")
            for keyword in data['networking'][key]:
                md_content.append(f"- {keyword}")
            md_content.append("")

    md_content.append("---")
    md_content.append("")

    # 9. 安全
    md_content.append("## 9. 安全")
    md_content.append("")

    security_categories = {
        'auth': '认证授权',
        'tools': '安全工具',
        'concepts': '安全概念'
    }

    for key, title in security_categories.items():
        if key in data['security']:
            md_content.append(f"### {title}")
            md_content.append("")
            for keyword in data['security'][key]:
                md_content.append(f"- {keyword}")
            md_content.append("")

    md_content.append("---")
    md_content.append("")

    # 10. 版本控制
    md_content.append("## 10. 版本控制")
    md_content.append("")

    if 'tools' in data['version_control']:
        md_content.append("### 版本控制工具")
        md_content.append("")
        for keyword in data['version_control']['tools']:
            md_content.append(f"- {keyword}")
        md_content.append("")

    if 'concepts' in data['version_control']:
        md_content.append("### 版本控制概念")
        md_content.append("")
        for keyword in data['version_control']['concepts']:
            md_content.append(f"- {keyword}")
        md_content.append("")

    md_content.append("---")
    md_content.append("")

    # 11. 其他工具
    md_content.append("## 11. 其他工具")
    md_content.append("")

    other_categories = {
        'collaboration': '协作工具',
        'documentation': '文档'
    }

    for key, title in other_categories.items():
        if key in data['others']:
            md_content.append(f"### {title}")
            md_content.append("")
            for keyword in data['others'][key]:
                md_content.append(f"- {keyword}")
            md_content.append("")

    md_content.append("---")
    md_content.append("")

    # 关键词权重说明
    md_content.append("## 关键词权重说明")
    md_content.append("")
    md_content.append("**高权重关键词** (表明深度经验):")
    md_content.append("")
    for keyword in data['keyword_weights']['high']:
        md_content.append(f"- {keyword}")
    md_content.append("")

    md_content.append("**中权重关键词** (表明实际使用):")
    md_content.append("")
    for keyword in data['keyword_weights']['medium']:
        md_content.append(f"- {keyword}")
    md_content.append("")

    md_content.append("**低权重关键词** (表明了解):")
    md_content.append("")
    for keyword in data['keyword_weights']['low']:
        md_content.append(f"- {keyword}")
    md_content.append("")

    md_content.append("---")
    md_content.append("")

    # 技术栈映射
    md_content.append("## 技术栈映射")
    md_content.append("")

    stack_names = {
        'monitoring_stack': '监控技术栈',
        'cicd_stack': 'CI/CD 技术栈',
        'cloud_native_stack': '云原生技术栈',
        'automation_stack': '自动化技术栈'
    }

    for stack_key, stack_name in stack_names.items():
        if stack_key in data['tech_stack_mapping']:
            md_content.append(f"**{stack_name}**:")
            md_content.append("")
            for item in data['tech_stack_mapping'][stack_key]:
                md_content.append(f"- {item}")
            md_content.append("")

    md_content.append("---")
    md_content.append("")

    # 使用建议
    md_content.append("## 使用建议")
    md_content.append("")
    md_content.append("### 简历分析时")
    md_content.append("")
    md_content.append("1. **提取关键词**: 从简历中提取所有相关技术关键词")
    md_content.append("2. **分类归纳**: 将关键词归入上述类别")
    md_content.append("3. **评估深度**: 根据关键词组合和上下文判断经验深度")
    md_content.append("4. **匹配评分**: 对照评分标准进行打分")
    md_content.append("")
    md_content.append("### 生成建议时")
    md_content.append("")
    md_content.append("1. **补充缺失关键词**: 识别简历中缺失的重要关键词")
    md_content.append("2. **优化关键词使用**: 建议如何更好地使用技术术语")
    md_content.append("3. **避免堆砌**: 提醒不要简单罗列关键词,要结合具体经验")
    md_content.append("")
    md_content.append("---")
    md_content.append("")

    # 版本信息
    md_content.append("## 版本信息")
    md_content.append("")
    md_content.append(f"- **版本**: {data['version']}")
    md_content.append(f"- **最后更新**: {data['last_updated']}")

    # 统计关键词数量
    keyword_count = 0
    for section in ['ai_and_intelligent_ops', 'monitoring', 'alerting', 'automation',
                   'containerization', 'incident_handling', 'database', 'networking',
                   'security', 'version_control', 'others']:
        if section in data:
            for subsection in data[section]:
                keyword_count += len(data[section][subsection])

    md_content.append(f"- **关键词数量**: {keyword_count}+")
    md_content.append("")

    # 写入文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_content))

    print(f"✅ 已生成 Markdown 文档: {output_path}")
    print(f"   关键词总数: {keyword_count}+")


def generate_core_json(data, output_path):
    """生成精简的核心关键词 JSON"""

    # 提取高权重关键词,按 6+1 维度组织
    core_data = {
        "high_weight_keywords": {
            "monitoring": [],
            "alerting": [],
            "automation": [],
            "containerization": [],
            "incident_handling": [],
            "ai_sre": []
        },
        "medium_weight_keywords": {
            "monitoring": [],
            "alerting": [],
            "automation": [],
            "containerization": [],
            "incident_handling": [],
            "ai_sre": []
        },
        "keyword_weights": {
            "high": 10,
            "medium": 7,
            "low": 4
        }
    }

    # 映射关系: 将 YAML 分类映射到 6+1 维度
    # 监控维度
    core_data["high_weight_keywords"]["monitoring"] = [
        "Prometheus", "Grafana", "Exporter", "自定义监控",
        "分布式追踪", "SLI/SLO", "监控体系设计"
    ]

    # 告警维度
    core_data["high_weight_keywords"]["alerting"] = [
        "Alertmanager", "On-call", "告警降噪", "智能告警",
        "Runbook", "告警体系设计"
    ]

    # 自动化维度
    core_data["high_weight_keywords"]["automation"] = [
        "CI/CD", "Terraform", "Ansible", "自动化平台",
        "基础设施即代码", "IaC", "LLM 辅助"
    ]

    # 容器化维度
    core_data["high_weight_keywords"]["containerization"] = [
        "Kubernetes", "Docker", "微服务架构", "Service Mesh",
        "Istio", "Helm", "生产环境 K8s"
    ]

    # 故障处理维度
    core_data["high_weight_keywords"]["incident_handling"] = [
        "RCA", "Postmortem", "根因分析", "故障演练",
        "应急预案", "故障响应", "预测性维护"
    ]

    # AI 维度
    core_data["high_weight_keywords"]["ai_sre"] = [
        "LLM", "AI Agent", "AIOps", "智能监控",
        "异常检测", "时序预测", "Cursor",
        "GitHub Copilot", "RAG", "LangChain"
    ]

    # 中权重关键词
    core_data["medium_weight_keywords"]["monitoring"] = [
        "Zabbix", "ELK Stack", "监控配置", "告警规则"
    ]

    core_data["medium_weight_keywords"]["alerting"] = [
        "告警分级", "阈值调优", "告警处理"
    ]

    core_data["medium_weight_keywords"]["automation"] = [
        "Jenkins", "GitLab CI", "Python", "Shell", "脚本编写"
    ]

    core_data["medium_weight_keywords"]["containerization"] = [
        "Docker", "容器编排", "阿里云", "AWS", "GCP"
    ]

    core_data["medium_weight_keywords"]["incident_handling"] = [
        "故障排查", "问题定位", "复盘"
    ]

    core_data["medium_weight_keywords"]["ai_sre"] = [
        "machine learning", "TensorFlow", "PyTorch", "prompt engineering"
    ]

    # 写入文件
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(core_data, f, ensure_ascii=False, indent=2)

    print(f"✅ 已生成核心关键词 JSON: {output_path}")
    print(f"   高权重关键词: {sum(len(v) for v in core_data['high_weight_keywords'].values())} 个")
    print(f"   中权重关键词: {sum(len(v) for v in core_data['medium_weight_keywords'].values())} 个")


def main():
    """主函数"""
    # 设置路径
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    skill_dir = project_root / ".claude/skills/sre-resume-analyzer"

    yaml_path = skill_dir / "config/sre_keywords.yaml"
    md_output_path = skill_dir / "references/sre_keywords.md"
    json_output_path = skill_dir / "config/keywords_core.json"

    print("🔄 从 YAML 生成关键词文档...")
    print(f"   输入: {yaml_path}")
    print(f"   输出 1: {md_output_path}")
    print(f"   输出 2: {json_output_path}")
    print()

    # 加载 YAML
    data = load_yaml(yaml_path)

    # 生成 Markdown
    generate_markdown(data, md_output_path)
    print()

    # 生成 JSON
    generate_core_json(data, json_output_path)
    print()

    print("✨ 生成完成!")
    print()
    print("📝 建议:")
    print("   1. 检查生成的 Markdown 文档格式是否正确")
    print("   2. 验证 JSON 文件内容是否符合预期")
    print("   3. 提交时只保留 YAML 作为数据源")
    print("   4. 将生成脚本加入 CI/CD 流程")


if __name__ == "__main__":
    main()
