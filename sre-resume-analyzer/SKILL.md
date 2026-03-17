---
name: sre-resume-analyzer
description: |
  分析和评估 SRE (Site Reliability Engineer) 岗位简历的技能。

  使用 "6+1" 评分体系进行多维度评估,生成个性化优化建议。

  **When to use this skill**:
  - 分析/评估 SRE、DevOps、运维工程师简历
  - 为 SRE 岗位简历提供评分和建议
  - 批量处理 SRE 工程师简历
  - 评估简历中的监控、告警、自动化、容器化、故障处理能力
  - 评估 AI 技术在 SRE 场景的应用

  **Trigger examples**:
  - "分析这份 SRE 简历: path/to/resume.pdf"
  - "为这份 DevOps 工程师简历评分: path/to/cv.pdf"
  - "评估这份简历的运维能力: path/to/resume.pdf"
  - "批量处理 input/ 目录下的 SRE 简历"
  - "请帮我分析这份简历是否符合 SRE 岗位要求"

  **Do NOT use for**:
  - 后端开发、前端开发、产品经理等非SRE岗位
  - 学术简历、研究型简历
  - 数据分析师简历
  - UI/UX 设计师简历
---

# SRE Resume Analyzer

## Metadata

- **Version**: 2.2.0
- **Description**: 分析和评估 SRE (Site Reliability Engineer) 岗位简历,基于 "6+1" 评分体系进行多维度评估,生成个性化面试题
- **Created**: 2026-03-05
- **Last Updated**: 2026-03-09
- **Target**: 2027届本科/硕士毕业生
- **Target Roles**: SRE 工程师、运维工程师、DevOps 工程师、AIOps 工程师

### Prerequisites

- PDF 处理:  document-skills:pdf skill 或 pdfplumber Python 库
- Python 环境: venv (`.venv/bin/python3`)
- 配置文件: `config/sre_keywords.yaml` (唯一数据源，位于 skill 目录)
- 生成脚本: `scripts/generate_keyword_docs.py` (按需生成文档)

---

## Trigger Conditions

### Should Trigger

- "分析这份 SRE 简历"
- "评估简历是否符合 SRE 岗位要求"
- "为 SRE 工程师简历提供优化建议"
- "批量处理 SRE 简历"
- "给这份运维简历打分"

### Should NOT Trigger

- "分析前端开发简历"
- "修改 Java 后端简历"
- "产品经理简历优化"
- 非 SRE/运维/DevOps 相关岗位

---

## Quick Reference

### "6+1" 评分体系

总分范围: **1.0 ~ 11.5 分**

| 维度          | 权重   | 核心关键词                             |
| ------------- | ------ | -------------------------------------- |
| 监控相关经验  | 20%    | Prometheus, Grafana, Exporter, SLI/SLO |
| 告警设计能力  | 15%    | Alertmanager, On-call, 告警降噪        |
| 自动化能力    | 20%    | CI/CD, Terraform, Ansible, 脚本        |
| 容器化/云原生 | 15%    | Docker, Kubernetes, 云平台             |
| 故障处理经验  | 15%    | RCA, Postmortem, 应急预案              |
| 简历整体质量  | 15%    | STAR 原则, 量化成果                    |
| AI 加分维度   | +0~1.5 | LLM, AI Agent, ML Ops, AIOps           |

### 等级划分

| 总分     | 等级 | 描述              | 建议                   |
| -------- | ---- | ----------------- | ---------------------- |
| 9.5-11.5 | A+   | 卓越,突出 AI 技术 | 直接投递,冲击顶级公司  |
| 8.5-9.4  | A    | 优秀              | 直接投递,保持优势      |
| 7.0-8.4  | B    | 良好              | 针对性改进薄弱项       |
| 5.5-6.9  | C    | 中等              | 重点关注高优先级改进项 |
| 4.0-5.4  | D    | 需改进            | 建议全面重构           |
| <4.0     | F    | 需大幅改进        | 从零重新编写           |

### 输出文件清单

每份简历生成 5 个文件:

1. `extracted.json` - 结构化数据(基本信息、项目、技能)
2. `score.json` - 详细评分(6+1 维度得分、证据、等级)
3. `analysis.json` - 优势、劣势、亮点、问题
4. `suggestions.md` - 优化建议(按优先级分类)
5. `interview_questions.md` - 面试题(基于简历内容的个性化题目)

### 高权重关键词 (9-10分级别)

**监控**: Prometheus, Grafana, Exporter, 自定义监控, 分布式追踪
**告警**: Alertmanager, On-call, 告警降噪, 智能告警
**自动化**: CI/CD 流水线, IaC, 运维平台开发, LLM 辅助
**容器化**: K8s 生产环境, 微服务架构, Service Mesh
**故障处理**: RCA, Postmortem, 故障演练, 预测性维护

### 内嵌配置快速参考

**评分权重** (详见 `config/scoring_weights.json`):

```
monitoring: 20% | alerting: 15% | automation: 20%
containerization: 15% | incident_handling: 15% | resume_quality: 15%
AI 加分上限: +1.5
```

**等级阈值**:

```
A+: 9.5-11.5 | A: 8.5-9.4 | B: 7.0-8.4
C: 5.5-6.9  | D: 4.0-5.4 | F: <4.0
```

---

## Workflow

### Step 1: PDF 提取

**优先方案**: 使用 document-skills:pdf skill

```
Skill(skill="document-skills:pdf", args="extract text from {pdf_path}")
```

**备选方案**: 使用 Python 脚本

```bash
.venv/bin/python3 scripts/extract_pdf.py "{pdf_path}"
```

**重要**: 不要直接使用 Read 工具读取 PDF (提取质量不足)

### Step 2: 信息提取

提取以下结构化数据到 `extracted.json`:

```json
{
  "resume_id": "string",
  "basic_info": {
    "name": "string",
    "school": "string",
    "major": "string",
    "degree": "string",
    "graduation_year": "number",
    "contact": { "phone": "string", "email": "string" }
  },
  "internships": [
    {
      "company": "string",
      "role": "string",
      "duration": "string",
      "description": "string",
      "tech_stack": ["string"],
      "achievements": ["string"]
    }
  ],
  "projects": [
    {
      "name": "string",
      "role": "string",
      "duration": "string",
      "description": "string",
      "tech_stack": ["string"],
      "achievements": ["string"]
    }
  ],
  "skills": {
    "programming_languages": ["string"],
    "monitoring_tools": ["string"],
    "container_tech": ["string"],
    "cloud_platforms": ["string"],
    "cicd_tools": ["string"]
  }
}
```

### Step 3: 评分分析

**评分公式**:

```
基础分 = (监控 × 0.20) + (告警 × 0.15) + (自动化 × 0.20) +
         (容器化 × 0.15) + (故障处理 × 0.15) + (简历质量 × 0.15)

最终总分 = 基础分 + AI 加分 (0 ~ +1.5)
```

**评分原则**:

1. 基于 `config/sre_keywords.yaml` 匹配关键词
2. 每个维度至少 2 个证据项
3. 考虑上下文 (学生项目 vs 生产环境)
4. 所有评分必须有具体证据支撑

### Step 4: 生成建议

生成 `suggestions.md`,包含:

- 基本信息和综合评分
- 六大维度得分和 AI 加分
- 优势亮点 (Top 2-3 维度)
- 待改进项 (按高/中/低优先级)
- 各维度详细分析(评分依据+改进建议)
- 项目经历优化 (使用 STAR 原则)
- AI 技术应用建议 (可选)

**模板文件**: `templates/suggestions_template.md`

### Step 5: 生成面试题

基于 `extracted.json` 中的 internships、projects、skills 三个字段，生成个性化面试题。

**生成原则**:

1. **数量控制**: 总共 10 题以内
2. **优先级策略**:
   - 如果有实习经历，优先针对实习项目生成 3-4 题
   - 如果有项目经历，针对项目生成 3-4 题
   - 针对技能列表生成 2-3 题验证题
3. **题目类型**: 混合类型
   - 技术深度题（考察理解深度）
   - 项目经验题（考察实战能力）
   - 技能验证题（考察基础知识）
4. **适应性**: 如果学生缺少实习或项目，则重点考察技能掌握情况和课程项目

**题目示例**:

- **实习类**: "你在 XX 公司实习期间，提到使用了 Prometheus 监控系统。能详细说说你们是如何设计告警规则的？遇到过哪些挑战？"
- **项目类**: "在你的 XX 项目中，你负责容器化部署。能解释一下你们是如何处理配置管理的？用了哪些最佳实践？"
- **技能类**: "你提到熟悉 Kubernetes，能说说 Pod 的生命周期吗？如何实现零停机部署？"

**输出模板**: `templates/interview_questions_template.md`

### Step 6: 输出文件

**目录结构**:

```
processing/{resume_id}/
├── extracted.json         # 结构化数据
├── score.json             # 评分详情
├── analysis.json          # 分析结果
├── suggestions.md         # 优化建议
└── interview_questions.md # 面试题
```

**文件命名规范**:

- resume*id: `{姓名}*{学校}_{专业}_{批次}`
- 例如: `张三_北京大学_计算机_27届云计算`

---

## 面试题生成指南

### 题目生成策略

**基于简历内容的动态分配**:

1. **有实习 + 有项目 + 有技能**: 实习 3 题 + 项目 4 题 + 技能 3 题
2. **无实习 + 有项目 + 有技能**: 项目 6 题 + 技能 4 题
3. **无实习 + 无项目 + 有技能**: 技能 10 题（深入考察基础）
4. **有实习 + 无项目 + 有技能**: 实习 5 题 + 技能 5 题

### 题目类型分布

**实习类题目** (针对 internships):
- 30% 技术深度题（工具/平台的使用细节）
- 40% 问题解决题（遇到的挑战和解决方案）
- 30% 团队协作题（跨部门合作、沟通能力）

**项目类题目** (针对 projects):
- 40% 架构设计题（技术选型、系统设计）
- 40% 实施细节题（具体实现、遇到的坑）
- 20% 优化改进题（性能优化、可扩展性）

**技能类题目** (针对 skills):
- 50% 基础概念题（原理、机制）
- 30% 应用场景题（何时使用、最佳实践）
- 20% 对比分析题（工具选型、技术对比）

### 题目质量标准

✅ **好题目示例**:
- "你在项目中提到使用了 Docker 和 Kubernetes。能说说你们是如何处理容器镜像版本管理的？在生产环境中如何保证镜像的安全性？"
- "你提到熟悉 Prometheus，能解释一下它的数据模型吗？在监控微服务时，你们是如何设计指标标签的？遇到过什么性能问题？"

❌ **避免的题目**:
- 过于宽泛：说说你做过什么项目？
- 过于简单：Docker 是什么？
- 脱离简历：你对微服务架构怎么看？（未提及）

### 题目生成流程

1. **读取 extracted.json** 的三个字段
2. **分析内容密度**：
   - 统计实习数量和质量
   - 统计项目数量和技术栈
   - 统计技能列表的广度和深度
3. **应用分配策略**：根据内容情况选择合适的题目配比
4. **生成具体题目**：
   - 提取关键信息（技术栈、成就、工具）
   - 结合 SRE 核心能力设计问题
   - 确保题目有深度和区分度
5. **格式化输出**：使用模板生成 Markdown 文件

---

## Embedded Configuration

### 评分权重和等级阈值

```yaml
dimensions:
  monitoring:
    weight: 0.20
    keywords: [Prometheus, Grafana, Exporter, metrics, SLI, SLO]
  alerting:
    weight: 0.15
    keywords: [Alertmanager, on-call, alert routing, runbook]
  automation:
    weight: 0.20
    keywords: [CI/CD, Jenkins, Terraform, Ansible, Python, Shell]
  containerization:
    weight: 0.15
    keywords: [Docker, Kubernetes, Helm, microservices, cloud]
  incident_handling:
    weight: 0.15
    keywords: [RCA, postmortem, troubleshooting, disaster recovery]
  resume_quality:
    weight: 0.15
    criteria: [STAR principle, quantification, clarity]

grade_thresholds:
  A+: { min: 9.5, max: 11.5 }
  A: { min: 8.5, max: 9.4 }
  B: { min: 7.0, max: 8.4 }
  C: { min: 5.5, max: 6.9 }
  D: { min: 4.0, max: 5.4 }
  F: { min: 0, max: 4.0 }
```

### AI 加分标准

| 加分 | 标准               | 要求                     |
| ---- | ------------------ | ------------------------ |
| +1.5 | 全面的 AI 技术应用 | 3+ 个不同类别,有量化成果 |
| +1.0 | 深度的 AI 技术应用 | 2 个类别,有量化成果      |
| +0.5 | 初步的 AI 技术应用 | 1 个类别,有一定深度      |
| +0.0 | 无 AI 应用         | 空洞表述或无关应用       |

**AI 应用类别**:

1. **LLM 应用**: 基于 LLM 开发运维工具 (智能助手、文档生成、代码生成)
2. **AI Agent**: 智能运维 Agent (自动巡检、故障自愈、对话式运维)
3. **AI IDE**: Cursor, GitHub Copilot 等,有量化效率提升
4. **ML Ops**: 异常检测、时序预测、智能告警
5. **AIOps**: 智能监控、预测性维护、自动化诊断

**不加分的情况**:

- 仅罗列 AI 工具无实际应用
- "了解机器学习" 等空洞表述
- AI 应用与 SRE 工作无关
- 无量化成果

---

## Output Templates

### score.json 结构

```json
{
  "resume_id": "string",
  "scoring": {
    "base_dimensions": {
      "monitoring": {
        "score": 8,
        "weight": 0.2,
        "weighted_score": 1.6,
        "evidence": ["配置 Prometheus 监控", "创建 Grafana 面板"],
        "grade": "B"
      }
    },
    "ai_bonus": {
      "score": 0.5,
      "categories": [
        {
          "category": "AI IDE",
          "applied": true,
          "evidence": "使用 Cursor 辅助开发",
          "quantified_results": "效率提升 30%"
        }
      ]
    },
    "base_score": 7.5,
    "total_score": 8.0,
    "overall_grade": "B"
  }
}
```

### analysis.json 结构

```json
{
  "resume_id": "string",
  "strengths": [
    {
      "dimension": "自动化能力",
      "description": "有 CI/CD 流水线搭建经验",
      "evidence": "使用 Jenkins 搭建自动化部署流程"
    }
  ],
  "weaknesses": [
    {
      "dimension": "告警设计",
      "description": "缺少告警降噪和分级经验",
      "suggestion": "补充 Alertmanager 配置经验"
    }
  ],
  "highlights": ["使用 Prometheus + Grafana 搭建完整监控体系"],
  "concerns": ["缺少生产环境故障处理经验"]
}
```

### suggestions.md 模板

**完整模板**: `templates/suggestions_template.md`

---

## References

详细参考文档位于 `.claude/skills/sre-resume-analyzer/`:

**数据源** (版本控制):
- `config/sre_keywords.yaml` - **唯一数据源** (300+ SRE 技术关键词、评分权重、等级阈值)
- `config/scoring_criteria.yaml` - 评分维度、权重、阈值配置
- `templates/suggestions_template.md` - 优化建议模板

**参考文档** (版本控制):
- `references/scoring_rubric.md` - 各维度详细评分标准 (1-10 分)
- `references/best_practices.md` - 简历最佳实践、STAR 原则、量化示例
- `references/star_method.md` - STAR 原则详细说明
- `references/ai_applications.md` - AI 技术在 SRE 中的应用示例

**生成文件** (本地查看, .gitignore 忽略):
- `references/sre_keywords.md` - 人类可读的完整关键词文档 (按需生成)
- `config/keywords_core.json` - 精简版核心关键词 (按需生成)

**维护文档**:
- `MAINTENANCE.md` - 关键词维护指南 (单文件方案说明)

**生成脚本**:
- `scripts/generate_keyword_docs.py` - 从 YAML 生成 Markdown 和 JSON

> **注意**: Skill 直接读取 `config/sre_keywords.yaml`，不需要其他文件即可正常工作。
> Markdown 和 JSON 文件仅供人类查看，可通过脚本按需生成。

---

## Notes

### 评分一致性

- 严格遵循评分标准,避免主观偏差
- 同质量简历应获得相近评分
- 每个维度至少 2 个证据项

### 学生背景考虑

- 理解学生经验有限 (实习、课程项目也有价值)
- 适当权重学习能力和成长潜力
- 不因缺少生产级系统经验而扣分
- 关注已展示的技术技能和理解深度

### PDF 提取注意事项

- 必须使用 pdfplumber 或 document-skills:pdf
- 不要使用 Read 工具直接读取 PDF
- 检查提取的联系方式、量化数据是否完整
- 多栏布局和表格需要特别处理

---

## Changelog

### v2.2.0 (2026-03-09)

- 新增面试题生成功能
- 新增 `interview_questions.md` 输出文件
- 添加面试题生成指南（题目类型、分配策略、质量标准）
- 更新工作流程为 6 步

### v2.1.0 (2026-03-05)

- 精简文档从 822 行到 350 行
- 更新 PDF 提取方式为 document-skills:pdf
- 将完整建议模板移到 `templates/suggestions_template.md`
- 保留核心评分逻辑和触发条件

### v2.0.0 (2026-03-05)

- 新增 "6+1" 评分体系
- 强化 AI 技术评估
- 新增 A+ 等级 (9.5-11.5 分)
