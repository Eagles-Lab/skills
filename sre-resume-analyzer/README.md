# SRE Resume Analyzer

SRE (Site Reliability Engineer) 简历分析与评估工具，基于"6+1"评分体系。

## ✨ 核心功能

### 📊 简历评分
- **六维评分体系**：监控、告警、自动化、容器化、故障处理、简历质量
- **AI 技术加分**：评估 AI 技术在 SRE 场景的应用（最高 +1.5 分）
- **证据驱动**：每个评分都有简历中的具体证据支撑
- **等级划分**：A+ / A / B / C / D / F 六个等级

### 🎯 面试题生成
- **个性化定制**：根据简历内容（实习、项目、技能）动态生成面试题
- **智能分配**：根据简历内容密度自动调整题目数量（最多 10 题）
- **深度追问**：每题包含 3-4 个深度追问，考察技术理解
- **量化验证**：针对简历中的量化成果设计验证性问题

### 📄 多格式输出
- `extracted.json` - 结构化简历数据
- `score.json` - 详细评分（6+1 维度）
- `analysis.json` - 优势、劣势、亮点分析
- `suggestions.md` - 优化建议报告
- `interview_questions.md` - 个性化面试题

---

## 🚀 快速开始

### 前置要求

- Python 3.8+
- PDF 处理库：`pdfplumber` 或使用 `document-skills:pdf` skill
- 配置文件：`config/sre_keywords.yaml`

### 使用方法

```bash
# 分析单份简历
claude "分析这份 SRE 简历: path/to/resume.pdf"

# 批量分析
claude "批量处理 input/ 目录下的 SRE 简历"

# 生成面试题
claude "为这份简历生成面试题: path/to/resume.pdf"
```

---

## 📋 "6+1" 评分体系

### 基础评分（1.0-10.0）

| 维度          | 权重 | 核心关键词                             |
| ------------- | ---- | -------------------------------------- |
| 监控相关经验  | 20%  | Prometheus, Grafana, Exporter, SLI/SLO |
| 告警设计能力  | 15%  | Alertmanager, On-call, 告警降噪        |
| 自动化能力    | 20%  | CI/CD, Terraform, Ansible, 脚本        |
| 容器化/云原生 | 15%  | Docker, Kubernetes, Helm, 微服务       |
| 故障处理经验  | 15%  | RCA, Postmortem, 应急预案              |
| 简历整体质量  | 15%  | STAR 原则, 量化成果                    |

### AI 技术加分（+0 ~ +1.5）

| 加分 | 标准               | 要求                     |
| ---- | ------------------ | ------------------------ |
| +1.5 | 全面的 AI 技术应用 | 3+ 个不同类别,有量化成果 |
| +1.0 | 深度的 AI 技术应用 | 2 个类别,有量化成果      |
| +0.5 | 初步的 AI 技术应用 | 1 个类别,有一定深度      |

**AI 应用类别**：
- LLM 应用（智能助手、文档生成、代码生成）
- AI Agent（自动巡检、故障自愈、对话式运维）
- AI IDE（Cursor、GitHub Copilot）
- ML Ops（异常检测、时序预测、智能告警）
- AIOps（智能监控、预测性维护、自动化诊断）

### 等级阈值

| 等级 | 分数范围   | 建议                   |
| ---- | ---------- | ---------------------- |
| A+   | 9.5-11.5   | 直接投递,冲击顶级公司  |
| A    | 8.5-9.4    | 直接投递,保持优势      |
| B    | 7.0-8.4    | 针对性改进薄弱项       |
| C    | 5.5-6.9    | 重点关注高优先级改进项 |
| D    | 4.0-5.4    | 建议全面重构           |
| F    | <4.0       | 从零重新编写           |

---

## 🎯 面试题生成策略

### 动态题目分配

根据简历内容智能分配题目：

| 简历内容           | 实习题 | 项目题 | 技能题 | 总计 |
| ------------------ | ------ | ------ | ------ | ---- |
| 有实习+有项目+有技能 | 3 题   | 4 题   | 3 题   | 10 题 |
| 无实习+有项目+有技能 | -      | 6 题   | 4 题   | 10 题 |
| 无实习+无项目+有技能 | -      | -      | 10 题  | 10 题 |
| 有实习+无项目+有技能 | 5 题   | -      | 5 题   | 10 题 |

### 题目类型分布

**实习类题目**（针对 internships）：
- 30% 技术深度题（工具/平台的使用细节）
- 40% 问题解决题（遇到的挑战和解决方案）
- 30% 团队协作题（跨部门合作、沟通能力）

**项目类题目**（针对 projects）：
- 40% 架构设计题（技术选型、系统设计）
- 40% 实施细节题（具体实现、遇到的坑）
- 20% 优化改进题（性能优化、可扩展性）

**技能类题目**（针对 skills）：
- 50% 基础概念题（原理、机制）
- 30% 应用场景题（何时使用、最佳实践）
- 20% 对比分析题（工具选型、技术对比）

### 题目示例

**实习类**：
> 你在 XX 公司实习期间，提到使用了 Prometheus 监控系统。能详细说说：
> - 你们是如何设计告警规则的？
> - 遇到过哪些挑战？
> - 如何平衡告警的及时性和准确性？

**项目类**：
> 在你的容器化部署平台项目中，实现了零停机滚动更新。想了解：
> - 具体是如何实现零停机的？用了哪些 K8s 特性？
> - 如何处理滚动更新过程中的故障回滚？
> - 如何管理应用配置（ConfigMap/Secret）？

**技能类**：
> 你提到熟悉 Kubernetes，能说说：
> - Pod 的完整生命周期包括哪些状态和钩子？
> - Kubernetes 的调度器是如何工作的？
> - Service 和 Ingress 的区别是什么？

---

## 📂 输出文件说明

### 1. extracted.json
```json
{
  "resume_id": "张三_北京大学_计算机_27届云计算",
  "basic_info": {
    "name": "张三",
    "school": "北京大学",
    "major": "计算机科学与技术"
  },
  "internships": [...],
  "projects": [...],
  "skills": {...}
}
```

### 2. score.json
```json
{
  "resume_id": "张三_北京大学_计算机_27届云计算",
  "scoring": {
    "base_dimensions": {
      "monitoring": {
        "score": 8,
        "weight": 0.2,
        "weighted_score": 1.6,
        "evidence": ["配置 Prometheus 监控", "创建 Grafana 面板"]
      }
    },
    "ai_bonus": {
      "score": 0.5,
      "categories": [...]
    },
    "total_score": 8.0,
    "overall_grade": "B"
  }
}
```

### 3. analysis.json
```json
{
  "resume_id": "张三_北京大学_计算机_27届云计算",
  "strengths": [...],
  "weaknesses": [...],
  "highlights": [...],
  "concerns": [...]
}
```

### 4. suggestions.md
生成优化建议报告，包含：
- 基本信息和综合评分
- 六大维度得分和 AI 加分
- 优势亮点
- 待改进项（按优先级）
- 各维度详细分析和改进建议

### 5. interview_questions.md
生成个性化面试题，包含：
- 候选人信息
- 面试题列表（10 题以内）
- 面试建议（考察重点、预期回答）

---

## 🛠️ 配置文件

### config/sre_keywords.yaml
**唯一数据源**，包含：
- 300+ SRE 技术关键词
- 关键词权重（高/中/低）
- 技术栈映射

### config/scoring_weights.json
定义：
- 各维度评分权重
- 等级阈值（A+/A/B/C/D/F）

### config/scoring_criteria.yaml
详细评分标准：
- 各维度 1-10 分的评分细则
- AI 加分评估标准

### templates/
- `suggestions_template.md` - 优化建议模板
- `interview_questions_template.md` - 面试题模板

---

## 📚 参考文档

详细文档位于技能目录：
- `SKILL.md` - 完整技能文档
- `references/scoring_rubric.md` - 详细评分标准
- `references/best_practices.md` - 简历最佳实践
- `references/star_method.md` - STAR 原则说明
- `references/ai_applications.md` - AI 技术应用示例

---

## 🎯 适用场景

### ✅ 适合分析
- SRE (Site Reliability Engineer)
- DevOps 工程师
- 运维工程师
- AIOps 工程师
- 平台工程师

### ❌ 不适合
- 后端开发、前端开发
- 产品经理、UI/UX 设计师
- 数据分析师
- 学术研究型简历

---

## 📊 示例输出

查看 `tests/` 目录中的测试案例：
- `任海凌_extracted.json` - 示例简历数据
- `任海凌_interview_questions.md` - 示例面试题
- `测试报告.md` - 测试分析报告

---

## 🔄 更新日志

### v2.2.0 (2026-03-09)
- ✨ 新增面试题生成功能
- 📝 新增 `interview_questions.md` 输出文件
- 📚 添加面试题生成指南
- 🎯 支持基于简历内容的动态题目分配

### v2.1.0 (2026-03-05)
- 🎨 精简文档结构
- 📦 更新 PDF 提取方式

### v2.0.0 (2026-03-05)
- ✨ 新增 "6+1" 评分体系
- 🤖 强化 AI 技术评估
- 🏆 新增 A+ 等级

---

## 📝 许可证

本技能用于简历分析和面试准备，请遵守相关隐私保护法规。

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request 来改进关键词库、评分标准和面试题质量。

---

**Created**: 2026-03-05
**Last Updated**: 2026-03-09
**Version**: 2.2.0
**Author**: Claude Code Agent Skill
