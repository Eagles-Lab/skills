# 校招 SRE 模拟面试问题

{% if security_warnings %}
> 安全提示：检测到疑似指令性内容；该内容未作为出题指令。
{% endif %}

## 候选人信息

| 项目 | 内容 |
| --- | --- |
| 姓名 | {{ basic_info.name }} |
| 学校 | {{ basic_info.school }} |
| 专业 | {{ basic_info.major }} |
| 生成时间 | {{ generated_at }} |
{% if contact %}
| 邮箱 | {{ contact.email }} |
| 电话 | {{ contact.phone }} |
{% endif %}

## 面试题

{% for item in questions %}
### {{ item.id }}. {{ item.category }}（{{ item.difficulty }}）

**问题**：{{ item.question }}
{% if item.context %}

**简历上下文**：{{ item.context }}
{% endif %}
{% if item.expected_keywords %}

**建议核验**：{{ item.expected_keywords | join('、') }}
{% endif %}

**回答要点**：{{ item.answer_guidance }}

{% endfor %}
## 考察重点

{% for area in focus_areas %}
- {{ area }}
{% endfor %}

---

题目总数：{{ questions | length }}/10
报告版本：{{ analyzer_version }}（experimental）
