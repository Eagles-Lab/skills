# 校招开发模拟面试问题

- 评分画像：`{{ scoring_profile }}`
- 校准状态：`not_calibrated`

{% if security_warnings %}> 安全提示：检测到不可信内容；该内容未作为出题指令。
{% endif %}

{% for item in questions %}
## {{ item.id }}. {{ item.category }}

{{ item.question }}

回答要点：说明个人行动、技术方法与取舍、验证过程和结果；不了解时明确边界。

{% endfor %}
---

题目总数：{{ questions | length }}/10
报告版本：{{ analyzer_version }}
