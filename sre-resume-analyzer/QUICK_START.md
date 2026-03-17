# 快速开始指南

## 5 分钟上手

### 1. 分析单个简历

```bash
# 从 PDF 开始（两步）
venv/bin/python3 sre-resume-analyzer/scripts/extract_pdf.py resume.pdf
venv/bin/python3 sre-resume-analyzer/scripts/analyze_resume.py \
  --extracted resume_extracted.json \
  --output ./processing

# 从 extracted.json 开始（一步）
venv/bin/python3 sre-resume-analyzer/scripts/analyze_resume.py \
  --extracted sre-resume-analyzer/tests/任海凌_extracted.json \
  --output ./processing
```

### 2. 查看结果

```bash
cd processing/任海凌_北京大学_计算机_27届云计算
ls -lh

# 输出：
# extracted.json         - 结构化数据
# score.json             - 评分详情
# analysis.json          - 优劣分析
# suggestions.md         - 优化建议
# interview_questions.md - 面试题
```

### 3. 批量处理

```bash
venv/bin/python3 sre-resume-analyzer/scripts/batch_processor.py \
  --input-dir ./resumes \
  --output-dir ./processing \
  --parallel 3
```

### 4. 运行测试

```bash
venv/bin/python3 sre-resume-analyzer/tests/run_tests.py
```

---

## 常见场景

### 场景 1：从 PDF 完整分析

```bash
# 步骤 1：提取 PDF
venv/bin/python3 sre-resume-analyzer/scripts/extract_pdf.py "张三_简历.pdf"

# 步骤 2：分析简历
venv/bin/python3 sre-resume-analyzer/scripts/analyze_resume.py \
  --extracted "张三_简历_extracted.json" \
  --output ./processing

# 步骤 3：查看建议
cat processing/张三_*/suggestions.md
```

### 场景 2：只生成面试题

```bash
# 需要先完成完整分析（生成 score.json）
venv/bin/python3 sre-resume-analyzer/scripts/analyze_resume.py \
  --extracted resume_extracted.json

# 面试题会自动生成在 processing/{resume_id}/interview_questions.md
```

### 场景 3：批量处理 + 汇总报告

```bash
# 批量处理会自动生成 batch_summary.json
venv/bin/python3 sre-resume-analyzer/scripts/batch_processor.py \
  --input-dir ./resumes \
  --output-dir ./processing \
  --parallel 5

# 查看汇总报告
cat processing/batch_summary.json | python3 -m json.tool
```

---

## 参数说明

### analyze_resume.py

| 参数           | 必需 | 说明                          |
| -------------- | ---- | ----------------------------- |
| `--extracted`  | 是   | extracted.json 文件路径       |
| `--output`     | 否   | 输出目录（默认：./processing）|
| `--log-level`  | 否   | 日志级别（DEBUG/INFO/WARNING/ERROR）|

### batch_processor.py

| 参数          | 必需 | 说明                              |
| ------------- | ---- | --------------------------------- |
| `--input-dir` | 是   | 输入目录（包含 extracted.json）   |
| `--output-dir`| 否   | 输出目录（默认：./processing）    |
| `--parallel`  | 否   | 并发数（默认：3）                 |
| `--pattern`   | 否   | 文件匹配模式（默认：*_extracted.json）|

---

## 故障排查

### 问题 1：PDF 提取失败

**症状**：`PDFValidationError: 文件不是 PDF 格式`

**解决**：
```bash
# 检查文件格式
file resume.pdf

# 使用备选提取方式
Skill(skill="document-skills:pdf", args="extract text from resume.pdf")
```

### 问题 2：评分异常低

**症状**：总分 < 3.0，所有维度得分都很低

**解决**：
```bash
# 检查 extracted.json 结构
cat extracted.json | python3 -m json.tool

# 确认有 internships/projects/skills 字段
```

### 问题 3：批量处理失败

**症状**：部分简历处理失败

**解决**：
```bash
# 查看错误日志
tail -f batch_processor.log

# 降低并发数
venv/bin/python3 scripts/batch_processor.py --parallel 1
```

---

## 性能优化

### 单个简历

- **处理时间**：< 5 秒
- **优化方式**：使用 `--log-level WARNING` 减少日志输出

### 批量处理

- **100 份简历**：< 5 分钟（并发 3）
- **优化方式**：增加并发数到 5-10（取决于 CPU）

---

## 下一步

- 📖 阅读 [用户指南](docs/user_guide.md)
- 📊 了解 [评分体系](docs/scoring_system.md)
- 📚 查看 [API 参考](docs/api_reference.md)
- 🎯 查看 [完整实施报告](IMPLEMENTATION_REPORT.md)
