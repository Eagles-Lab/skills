# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此仓库工作时提供指导。

## 仓库用途

存储 Claude Code Agent Skills - 可复用的专业能力模块。每个技能独立存放在子目录中。

## 当前技能

### sre-resume-analyzer

SRE 简历自动化分析工具（v2.3.0），基于"6+1"评分体系。

**核心功能**：
- 完全自动化的评分系统（6 维度 + AI 加分）
- 个性化面试题生成
- 批量处理支持（并发）
- 生产级代码质量

**使用方式**：
```bash
# 单个简历
venv/bin/python3 sre-resume-analyzer/scripts/analyze_resume.py \
  --extracted resume_extracted.json

# 批量处理
venv/bin/python3 sre-resume-analyzer/scripts/batch_processor.py \
  --input-dir ./resumes --parallel 3
```

**详细文档**：`sre-resume-analyzer/README.md`

---

## 常用命令

### PDF 提取

**优先方式**（document-skills:pdf）：
```
Skill(skill="document-skills:pdf", args="extract text from {pdf_path}")
```

**备选方式**（Python 脚本）：
```bash
venv/bin/python3 sre-resume-analyzer/scripts/extract_pdf.py "{pdf_path}"
```

### 简历分析

```bash
# 完整分析流程（生成 5 个文件）
venv/bin/python3 sre-resume-analyzer/scripts/analyze_resume.py \
  --extracted resume_extracted.json \
  --output ./processing

# 批量处理
venv/bin/python3 sre-resume-analyzer/scripts/batch_processor.py \
  --input-dir ./resumes \
  --output-dir ./processing \
  --parallel 3
```

### 测试

```bash
venv/bin/python3 sre-resume-analyzer/tests/run_tests.py
```

### 从 YAML 生成文档

```bash
venv/bin/python3 sre-resume-analyzer/scripts/generate_keyword_docs.py
```

---

## Python 环境

**重要**：使用父目录共享虚拟环境 `../venv/`

所有 Python 命令必须使用 venv：
```bash
venv/bin/python3 script.py
venv/bin/pip install package_name
```

---

## 评分体系

### "6+1" 维度

**基础分**（1.0-10.0）：
- 监控经验 20% | 告警设计 15% | 自动化能力 20%
- 容器化 15% | 故障处理 15% | 简历质量 15%

**AI 加分**（+0 ~ +1.5）：
- +1.5：3+ 个 AI 类别深度应用 + 量化成果
- +1.0：2 个 AI 类别应用 + 量化成果
- +0.5：1 个 AI 类别实际应用

**等级阈值**：
- A+: 9.5-11.5 | A: 8.5-9.4 | B: 7.0-8.4
- C: 5.5-6.9 | D: 4.0-5.4 | F: <4.0

**详细说明**：`sre-resume-analyzer/docs/scoring_system.md`

---

## 架构要点

### 单一数据源

`config/sre_keywords.yaml` 是唯一数据源：
- 300+ SRE 技术关键词
- 关键词权重（高/中/低）

### 配置分离

- `sre_keywords.yaml`：关键词定义
- `scoring_weights.json`：维度权重和等级阈值
- `scoring_criteria.yaml`：详细评分标准

### 输出结构

每个简历生成独立目录：`processing/{resume_id}/`
```
processing/{resume_id}/
├── extracted.json         # 结构化数据
├── score.json             # 评分详情（含证据）
├── analysis.json          # 优劣分析
├── suggestions.md         # 优化建议
└── interview_questions.md # 面试题
```

---

## 工作要点

### 评分原则

- **证据驱动**：每个评分必须有具体证据
- **一致性**：同质量简历应得相近分数
- **学生友好**：实习、课程项目有价值
- **最少证据**：每个维度至少 2 个证据项

### PDF 处理

- 优先使用 `document-skills:pdf`
- 检查提取质量（多栏布局、表格）
- 验证联系方式和量化数据完整性

---

## 更新技能

### 添加关键词

1. 编辑 `config/sre_keywords.yaml`
2. 生成文档：`venv/bin/python3 scripts/generate_keyword_docs.py`
3. 测试简历分析

### 调整权重

1. 修改 `config/scoring_weights.json`
2. 用现有简历测试一致性

---

## v2.3.0 新特性

### 完全自动化

- ✅ 无需 Claude Agent 手动执行
- ✅ 独立的 Python 脚本
- ✅ 批量处理支持（并发）
- ✅ 完整错误处理和日志
- ✅ 测试覆盖（单元 + 集成）

### 新增文件

**核心脚本**：
- `scripts/scoring/` - 评分系统（keyword_matcher, score_calculator, ai_bonus_evaluator）
- `scripts/generators/` - 生成器（interview_generator, suggestions_generator）
- `scripts/analyze_resume.py` - 主流程入口
- `scripts/batch_processor.py` - 批量处理

**配置和测试**：
- `config/config_manager.py` - 统一配置管理
- `tests/` - 完整测试体系

**文档**：
- `docs/user_guide.md` - 用户指南
- `docs/scoring_system.md` - 评分体系详解
- `IMPLEMENTATION_REPORT.md` - 完整实施报告

### 完整实施报告

查看 `sre-resume-analyzer/IMPLEMENTATION_REPORT.md` 了解 v2.3.0 的详细优化内容。

