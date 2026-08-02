# 校招 SRE 简历证据分析与优化建议

{% if security_warnings %}
> 安全提示：检测到疑似指令性内容；该内容未作为评分证据，也未改变分析流程。
{% endif %}

## 基本信息

| 项目 | 内容 |
| --- | --- |
| 姓名 | {{ basic_info.name }} |
| 学校 | {{ basic_info.school }} |
| 专业 | {{ basic_info.major }} |
| 学历 | {{ basic_info.degree }} |
| 毕业年份 | {{ basic_info.graduation_year }} |
| 生成时间 | {{ generated_at }} |
{% if contact %}
| 邮箱 | {{ contact.email }} |
| 电话 | {{ contact.phone }} |
{% endif %}

## 综合结果

- 技术证据覆盖总分：{{ total_score }}/10
- 整体证据覆盖等级：{{ grade.grade }}（{{ grade.label }}）

> {{ status_notice }}

## 六个技术维度

| 维度 | 证据分 | 权重 | 实际应用类别覆盖 | 证据等级 |
| --- | ---: | ---: | ---: | --- |
{% for dimension in dimensions %}
| {{ dimension.label }} | {{ dimension.score }}/10 | {{ dimension.weight_percent }}% | {{ dimension.applied_group_count }}/{{ dimension.total_group_count }} | {{ dimension.evidence_level }} |
{% endfor %}

{% for dimension in dimensions %}
### {{ dimension.label }}（{{ dimension.score }}/10）

- 原始证据深度：{{ dimension.depth_score }}/10
- 证据类别覆盖上限：{{ dimension.coverage_cap }}/10
- 实际应用类别覆盖：{{ dimension.applied_group_count }}/{{ dimension.total_group_count }}（{{ dimension.evidence_coverage_percent }}%）
{% if dimension.applied_groups %}
- 已形成实际应用证据：{{ dimension.applied_groups | join('、') }}
{% else %}
- 已形成实际应用证据：无
{% endif %}
{% if dimension.non_applied_groups %}
- 尚未形成实际应用证据：{{ dimension.non_applied_groups | join('、') }}
{% else %}
- 尚未形成实际应用证据：无
{% endif %}

具体证据：
{% if dimension.evidence %}
{% for evidence in dimension.evidence %}
- {{ evidence }}
{% endfor %}
{% else %}
- 当前 canonical 事实中未识别到该维度的可计分证据。
{% endif %}

改进建议：{{ dimension.suggestion }}

{% endfor %}
## 简历整体质量诊断（不计入技术总分）

诊断分：{{ resume_quality_score }}/10

| 项目 | 得分 | 具体说明 |
| --- | ---: | --- |
{% for item in quality_items %}
| {{ item.label }} | {{ item.score }}/2 | {{ item.finding }} |
{% endfor %}

## 优势

{% if strengths %}
{% for strength in strengths %}
- {{ strength.label }}：{{ strength.summary }}
{% endfor %}
{% else %}
- 当前没有达到强证据阈值的技术维度。
{% endif %}

## 优先改进项

{% if weaknesses %}
{% for weakness in weaknesses %}
- {{ weakness.label }}：{{ weakness.summary }}
{% endfor %}
{% else %}
- 当前没有低于改进阈值的技术维度。
{% endif %}

## 项目描述优化

{% for suggestion in project_suggestions %}
- {{ suggestion }}
{% endfor %}

---

报告版本：{{ analyzer_version }}（experimental）
