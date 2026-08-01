# SRE 简历证据分析与优化建议

{% if security_warnings %}
> 安全提示：{{ security_warnings | join('、') }}。可疑原文未进入评分证据或报告上下文。
{% endif %}

## 基本信息

| 项目 | 内容 |
| --- | --- |
| 姓名 | {{ basic_info.name }} |
| 学校 | {{ basic_info.school }} |
| 专业 | {{ basic_info.major }} |
| 学历 | {{ basic_info.degree }} |
| 毕业年份 | {{ basic_info.graduation_year }} |
| 简历 ID | {{ resume_id }} |
| 生成时间 | {{ generated_at }} |
{% if contact %}
| 邮箱 | {{ contact.email }} |
| 电话 | {{ contact.phone }} |
{% endif %}

## 综合结果

- 总分：{{ total_score }}/11.5
- 基础分：{{ base_score }}/10
- 等级：{{ grade.grade }}（{{ grade.label }}）
- AI 应用加分：{{ ai_bonus_score }}/1.5

{% if ai_applications %}
已识别的 AI 实际应用类别：{{ ai_applications | join('、') }}。
{% else %}
没有识别到满足证据要求的 AI 实际应用类别。
{% endif %}

> {{ status_notice }}

## 六个维度

| 维度 | 得分 | 权重 | 等级 |
| --- | ---: | ---: | --- |
{% for dimension in dimensions %}
| {{ dimension.label }} | {{ dimension.score }}/10 | {{ dimension.weight_percent }}% | {{ dimension.grade }} |
{% endfor %}

{% for dimension in dimensions %}
### {{ dimension.label }}（{{ dimension.score }}/10）

评分证据：
{% if dimension.evidence %}
{% for evidence in dimension.evidence %}
- {{ evidence }}
{% endfor %}
{% else %}
- 暂无满足规则的正向证据。
{% endif %}

改进建议：{{ dimension.suggestion }}

{% endfor %}
## 优势

{% if strengths %}
{% for strength in strengths %}
- {{ strength.label }}：{{ strength.summary }}
{% endfor %}
{% else %}
- 暂无得分达到优势阈值的维度。
{% endif %}

## 优先改进项

{% if weaknesses %}
{% for weakness in weaknesses %}
- {{ weakness.label }}：{{ weakness.summary }}
{% endfor %}
{% else %}
- 当前没有低于改进阈值的维度。
{% endif %}

## 项目描述优化

{% for suggestion in project_suggestions %}
- {{ suggestion }}
{% endfor %}

---

报告版本：{{ analyzer_version }}
