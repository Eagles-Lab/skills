# Agent Prompt 模板 - SRE 简历分析

## 📋 Prompt 模板

```text
请分析这份简历: {PDF_PATH}

**重要**: 必须严格遵循以下步骤:

### Step 1: PDF 提取 (强制使用 PDF skill)
**必须** 使用 `document-skills:pdf` skill 提取 PDF 内容:
```
Skill(skill="document-skills:pdf", args="extract text from {PDF_PATH}")
```

**禁止** 直接使用 Read 工具读取 PDF!

### Step 2: 信息提取
从 PDF skill 提取的完整内容中,提取:
- 基本信息(姓名、联系方式、学校、专业)
- 实习经历(公司、时间、职责、成果)
- 项目经历(技术栈、量化成果)
- 技能清单

### Step 3-5: 评分、建议、输出
按照 SRE Resume Analyzer Skill 标准执行。

参考配置:
- config/scoring_criteria.yaml
- config/sre_keywords.yaml
```

## 使用示例

```python
# Python 调用 Agent
prompt = f"""请分析这份简历: input/27届云计算/陈钰中.pdf

**关键要求**:
1. 必须先用 Skill(skill="document-skills:pdf", args="extract text from input/27届云计算/陈钰中.pdf") 提取 PDF
2. 禁止使用 Read 工具直接读取 PDF
3. 基于完整提取内容进行评分分析
4. 输出到 processing/ 目录

按照 SRE Resume Analyzer Skill 标准执行。
"""

agent = Agent(
    subagent_type="general-purpose",
    prompt=prompt,
    description="SRE 简历分析"
)
```
