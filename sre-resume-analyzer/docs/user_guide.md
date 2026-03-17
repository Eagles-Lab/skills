# SRE 简历分析工具 - 用户指南

## 快速开始

### 1. 基本使用

#### 分析单个简历

```bash
# 方式 1：使用现有 extracted.json
venv/bin/python3 sre-resume-analyzer/scripts/analyze_resume.py \
  --extracted sre-resume-analyzer/tests/任海凌_extracted.json \
  --output ./processing

# 方式 2：从 PDF 开始（需要先提取）
venv/bin/python3 sre-resume-analyzer/scripts/extract_pdf.py resume.pdf
venv/bin/python3 sre-resume-analyzer/scripts/analyze_resume.py \
  --extracted resume_extracted.json \
  --output ./processing
```

#### 批量处理简历

```bash
venv/bin/python3 sre-resume-analyzer/scripts/batch_processor.py \
  --input-dir ./resumes \
  --output-dir ./processing \
  --parallel 3
```

### 2. 输出文件

分析完成后，会在 `processing/{resume_id}/` 目录下生成 5 个文件：

- **extracted.json** - 结构化数据（基本信息、实习、项目、技能）
- **score.json** - 评分详情（6 维度得分 + AI 加分 + 证据）
- **analysis.json** - 优劣分析（优势、劣势、改进建议）
- **suggestions.md** - 优化建议报告（人类可读）
- **interview_questions.md** - 个性化面试题（10 题以内）

### 3. 命令行参数

#### analyze_resume.py

| 参数 | 必需 | 说明 |
|------|------|------|
| `--extracted` | 是 | extracted.json 文件路径 |
| `--output` | 否 | 输出目录（默认：./processing） |
| `--text` | 否 | 简历原文文本文件（可选） |
| `--log-level` | 否 | 日志级别（DEBUG/INFO/WARNING/ERROR） |

#### batch_processor.py

| 参数 | 必需 | 说明 |
|------|------|------|
| `--input-dir` | 是 | 输入目录（包含 extracted.json 文件） |
| `--output-dir` | 否 | 输出目录（默认：./processing） |
| `--parallel` | 否 | 并发数（默认：3） |
| `--pattern` | 否 | 文件匹配模式（默认：*_extracted.json） |

## 常见问题

### Q: 如何提高评分准确性？

**A**: 确保简历文本提取质量，避免扫描版 PDF。使用 pdfplumber 或 document-skills:pdf 提取文本。

### Q: AI 加分如何计算？

**A**: 检测 5 个 AI 类别（LLM、AI Agents、AI IDE、ML Ops、AIOps），根据类别数量和量化成果加分：
- 3+ 类别 + 量化成果 → +1.5
- 2 类别 → +1.0
- 1 类别 → +0.5

### Q: 如何自定义关键词？

**A**: 编辑 `config/sre_keywords.yaml`，添加或修改关键词后运行：
```bash
venv/bin/python3 sre-resume-analyzer/scripts/generate_keyword_docs.py
```

### Q: 如何添加新的评分维度？

**A**:
1. 在 `config/sre_keywords.yaml` 添加关键词
2. 在 `config/scoring_weights.json` 添加维度权重
3. 在 `config/scoring_criteria.yaml` 添加评分标准
4. 更新 `scripts/scoring/score_calculator.py` 代码

## 最佳实践

1. **批量处理前先测试单份简历**，确保配置正确
2. **定期更新关键词库**，跟进新技术趋势
3. **保存原始简历文本**，方便重新分析
4. **检查日志输出**，发现异常情况

## 获取帮助

- 查看 `docs/scoring_system.md` 了解评分体系
- 查看 `docs/interview_guide.md` 了解面试题生成
- 查看 `docs/api_reference.md` 了解 API 详细说明
