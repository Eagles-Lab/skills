# 校招安全简历证据分析

{% if security_warnings %}
> 安全提示：检测到不可信指令或不安全攻防声明；相关内容未作为正向证据。
{% endif %}

## 分析契约

- 评分画像：`{{ scoring_profile }}`
- 分析器状态：`stable`
- 校准状态：`not_calibrated`
- 技术证据覆盖总分：{{ total_score }}/10（{{ grade.grade }}，{{ grade.label }}）

> 本报告衡量简历中可核验安全证据的覆盖度。评分尚未经过人工校准，不得用于候选人排名或招聘决策。

## 基本信息

| 项目 | 内容 |
| --- | --- |
{% if basic_info.name %}| 姓名 | {{ basic_info.name }} |
{% endif %}{% if basic_info.school %}| 学校 | {{ basic_info.school }} |
{% endif %}{% if basic_info.major %}| 专业 | {{ basic_info.major }} |
{% endif %}{% if basic_info.graduation_year %}| 毕业年份 | {{ basic_info.graduation_year }} |
{% endif %}{% if contact and contact.email %}| 邮箱 | {{ contact.email }} |
{% endif %}{% if contact and contact.phone %}| 电话 | {{ contact.phone }} |
{% endif %}

## 六维证据

| 维度 | 得分 | 权重 | 应用证据组 | 深度/覆盖上限 |
| --- | ---: | ---: | ---: | ---: |
{% for dimension in dimensions %}| {{ dimension.label }} | {{ dimension.score }}/10 | {{ dimension.weight_percent }}% | {{ dimension.applied_count }}/{{ dimension.group_count }} | {{ dimension.depth_score }}/{{ dimension.coverage_cap }} |
{% endfor %}

{% for dimension in dimensions %}
### {{ dimension.label }}

- 已形成应用证据：{{ dimension.applied_groups | join('、') if dimension.applied_groups else '无' }}
- 尚缺应用证据：{{ dimension.missing_groups | join('、') if dimension.missing_groups else '无' }}
- 改进建议：{{ dimension.suggestion }}

{% if dimension.evidence %}具体证据：
{% for evidence in dimension.evidence %}- {{ evidence }}
{% endfor %}{% else %}当前 canonical 事实中未识别到该维度的可计分证据。
{% endif %}
{% endfor %}

## 简历证据质量（不计入技术总分）

| 项目 | 得分 | 诊断 |
| --- | ---: | --- |
{% for item in quality_items %}| {{ item.label }} | {{ item.score }}/2 | {{ item.finding }} |
{% endfor %}

---

报告版本：{{ analyzer_version }}（stable；not calibrated）
