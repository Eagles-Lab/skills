# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此仓库工作时提供指导。

## 仓库用途

存储 Claude Code Agent Skills - 可复用的专业能力模块。每个技能独立存放在子目录中。

## 当前技能

### sre-resume-analyzer

SRE 简历分析与评估工具，基于"6+1"评分体系（6个技术维度 + AI 加分）。

**核心功能**：
- PDF 简历结构化数据提取
- 六维评分：监控、告警、自动化、容器化、故障处理、简历质量
- AI 技术加分评估（最高 +1.5 分）
- 个性化面试题生成（10 题以内，基于简历内容）
- 生成 5 个文件：extracted.json、score.json、analysis.json、suggestions.md、interview_questions.md

**适用场景**：分析 SRE/DevOps/运维工程师简历，提供评分和优化建议

**详细文档**：`sre-resume-analyzer/SKILL.md`

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

### 从 YAML 生成文档

更新 `config/sre_keywords.yaml` 后，重新生成人类可读文档：
```bash
venv/bin/python3 sre-resume-analyzer/scripts/generate_keyword_docs.py
```

生成文件：
- `references/sre_keywords.md` - 关键词列表
- `config/keywords_core.json` - 核心关键词 JSON

## Python 环境

**重要**：使用父目录共享虚拟环境 `../venv/`

所有 Python 命令必须使用 venv：
- 执行脚本：`venv/bin/python3 script.py`
- 运行代码：`venv/bin/python3 << 'EOF' ... EOF`
- 安装包：`venv/bin/pip install package_name`

完整规范见 `../CLAUDE.md`

## 评分体系

### "6+1" 维度

**基础分**（1.0-10.0）：
- 监控经验 (20%) | 告警设计 (15%) | 自动化能力 (20%)
- 容器化 (15%) | 故障处理 (15%) | 简历质量 (15%)

**AI 加分**（+0 ~ +1.5）：
- +1.5：3+ 个 AI 类别的深度应用，有量化成果
- +1.0：2 个 AI 类别的应用，有量化成果
- +0.5：1 个 AI 类别的实际应用

**AI 类别**：LLM 应用、AI Agent、AI IDE (Cursor/Copilot)、ML Ops、AIOps

### 等级阈值

A+: 9.5-11.5 | A: 8.5-9.4 | B: 7.0-8.4 | C: 5.5-6.9 | D: 4.0-5.4 | F: <4.0

## 架构要点

### 单一数据源

`config/sre_keywords.yaml` 是唯一数据源：
- 300+ SRE 技术关键词
- 关键词权重（高/中/低）
- 技术栈映射

其他文件（MD/JSON）从 YAML 生成，仅供人类查看。

### 配置分离

- `sre_keywords.yaml`：关键词定义
- `scoring_weights.json`：维度权重和等级阈值
- `scoring_criteria.yaml`：详细评分标准

### 输出结构

每个简历生成独立目录：`processing/{resume_id}/`
- `extracted.json` - 结构化数据
- `score.json` - 评分详情（含证据）
- `analysis.json` - 优劣分析
- `suggestions.md` - 优化建议
- `interview_questions.md` - 个性化面试题（基于实习、项目、技能）

### 模板驱动

`suggestions.md` 基于 `templates/suggestions_template.md` 生成，使用占位符确保格式一致。

## 工作要点

### 技能触发

技能自动识别 SRE/DevOps/运维简历并执行：
1. PDF 文本提取
2. 结构化数据解析（基本信息、实习、项目、技能）
3. 六维评分（6+1 体系）
4. 生成分析和建议
5. **生成个性化面试题**（根据简历内容动态生成 10 题以内）

### 评分原则

- **证据驱动**：每个评分必须有简历中的具体证据
- **一致性**：同质量简历应得相近分数
- **学生友好**：考虑学生经验有限（实习、课程项目有价值）
- **最少证据**：每个维度至少 2 个证据项

### PDF 处理

- 必须使用 pdfplumber 或 document-skills:pdf（不要用 Read 工具直接读 PDF）
- 检查提取质量，特别是多栏布局和表格
- 验证联系方式和量化数据完整性

## 更新技能

### 添加关键词

1. 编辑 `config/sre_keywords.yaml`
2. 生成文档：`venv/bin/python3 scripts/generate_keyword_docs.py`
3. 测试简历分析
4. 只提交 YAML 文件（MD/JSON 已被 gitignore）

### 调整权重

1. 修改 `config/scoring_weights.json`（维度权重）
2. 修改 `config/scoring_criteria.yaml`（详细标准）
3. 用现有简历测试一致性
4. 在 SKILL.md 记录变更

### 更新模板

修改 `templates/suggestions_template.md` 改变输出格式，保持占位符与 JSON 结构一致。
