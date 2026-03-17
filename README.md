# Skills

Agent Skills - 可复用的专业能力模块

## 可用技能

### sre-resume-analyzer

SRE 简历自动化分析工具（v2.3.0）- 基于证据的 "6+1" 评分体系

**核心功能**：
- 📊 自动评分（6 维度 + AI 加分）
- 🎯 个性化面试题生成
- 📄 批量处理支持
- 🚀 完全自动化脚本

**快速使用**：
```bash
# 单个简历
venv/bin/python3 sre-resume-analyzer/scripts/analyze_resume.py \
  --extracted resume_extracted.json

# 批量处理
venv/bin/python3 sre-resume-analyzer/scripts/batch_processor.py \
  --input-dir ./resumes --parallel 3
```

**详细文档**: [sre-resume-analyzer/README.md](sre-resume-analyzer/README.md)
