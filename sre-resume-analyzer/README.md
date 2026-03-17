# SRE Resume Analyzer

SRE 简历自动化分析工具（v2.3.0）- 完全自动化的"6+1"评分体系

## ✨ 核心功能

### 📊 自动评分系统
- **六维评分**：监控、告警、自动化、容器化、故障处理、简历质量
- **AI 加分**：评估 AI 技术应用（+0 ~ +1.5 分）
- **证据驱动**：每个评分都有具体证据支撑
- **等级划分**：A+/A/B/C/D/F 六个等级

### 🎯 面试题生成
- 个性化定制（基于实习、项目、技能）
- 动态题目分配（10 题以内）
- 深度追问设计
- 量化成果验证

### 🚀 完全自动化
- 无需 Claude Agent 手动执行
- 支持批量处理（并发）
- 完整错误处理和日志
- 生产级代码质量

---

## 🚀 快速开始

### 安装依赖

```bash
cd /path/to/skills
venv/bin/pip install pdfplumber PyYAML jinja2
```

### 单个简历分析

```bash
# 方式 1：从 extracted.json 开始
venv/bin/python3 sre-resume-analyzer/scripts/analyze_resume.py \
  --extracted sre-resume-analyzer/tests/任海凌_extracted.json \
  --output ./processing

# 方式 2：从 PDF 开始（需要先提取）
venv/bin/python3 sre-resume-analyzer/scripts/extract_pdf.py resume.pdf
venv/bin/python3 sre-resume-analyzer/scripts/analyze_resume.py \
  --extracted resume_extracted.json
```

### 批量处理

```bash
venv/bin/python3 sre-resume-analyzer/scripts/batch_processor.py \
  --input-dir ./resumes \
  --output-dir ./processing \
  --parallel 3
```

### 输出文件

每个简历在 `processing/{resume_id}/` 生成 5 个文件：

- `extracted.json` - 结构化数据
- `score.json` - 评分详情（6+1 维度）
- `analysis.json` - 优劣分析
- `suggestions.md` - 优化建议
- `interview_questions.md` - 面试题

---

## 📋 评分体系

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

**详细说明**: [docs/scoring_system.md](docs/scoring_system.md)

---

## 📂 输出文件

```
processing/{resume_id}/
├── extracted.json         # 结构化数据
├── score.json             # 评分详情（含证据）
├── analysis.json          # 优劣分析
├── suggestions.md         # 优化建议
└── interview_questions.md # 面试题
```

---

## 📚 文档

- [用户指南](docs/user_guide.md) - 快速开始和常见问题
- [评分体系详解](docs/scoring_system.md) - 完整评分标准
- [API 参考](docs/api_reference.md) - 脚本 API 说明
- [完整实施报告](IMPLEMENTATION_REPORT.md) - v2.3.0 优化详情

---

## 🛠️ 开发

### 测试

```bash
venv/bin/python3 sre-resume-analyzer/tests/run_tests.py
```

### 更新关键词

```bash
# 编辑 config/sre_keywords.yaml
venv/bin/python3 sre-resume-analyzer/scripts/generate_keyword_docs.py
```

---

## 📊 示例

查看 `tests/` 目录：
- `任海凌_extracted.json` - 示例数据
- `任海凌_interview_questions.md` - 示例面试题

---

## 🔄 版本历史

- **v2.3.0** (2026-03-17) - 完全自动化，新增批量处理和测试
- **v2.2.0** (2026-03-09) - 新增面试题生成
- **v2.0.0** (2026-03-05) - "6+1" 评分体系

---

**Created**: 2026-03-05
**Version**: 2.3.0
**Status**: 生产就绪
