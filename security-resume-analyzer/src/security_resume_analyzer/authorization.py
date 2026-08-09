"""Negation-aware authorization predicates shared by audit, matching, and scoring."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

_EXPLICIT_UNAUTHORIZED = re.compile(
    r"(?:未授权|未经授权)(?:的)?(?:渗透|安全)?(?:测试|攻击|入侵|扫描|利用)|"
    r"(?:未授权|未经授权)(?:访问|攻击|入侵)(?:外部|他人|第三方)"
    r"(?:网站|系统|目标|网络|服务器)|"
    r"没有授权|无授权|不具备授权|越权攻击|入侵他人|非法攻击|黑产|"
    r"(?:尚未|还未|并未|从未|没有|未能|无法|未成功|未)"
    r"(?:获|获得|取得|得到)(?:了)?(?:书面|客户|正式)?授权|"
    r"(?:授权|许可)(?:申请)?(?:未通过|未获批|被拒绝|遭拒)|"
    r"(?:拒绝|取消|终止)(?:了)?(?:客户|书面|正式)?授权(?:的)?(?:渗透|安全)?测试|"
    r"\b(?:unauthori[sz]ed\s+(?:penetration\s+test(?:ing)?|pentest(?:ing)?|"
    r"security\s+(?:test(?:ing)?|assessment)|test(?:ing)?|attack|scan(?:ning)?|"
    r"exploit(?:ation)?|hacking|access\s+to\s+(?:an?\s+)?"
    r"(?:external|third[- ]party|client|target))|illegal hacking|permission denied|"
    r"(?:not|never)\s+(?:(?:an?|client)[- ]*)?authori[sz]ed|"
    r"non[- ]authori[sz]ed|"
    r"(?:without|no)\s+(?:(?:written|client)\s+)?(?:permission|authori[sz]ation)"
    r"(?:\s+for)?|"
    r"(?:did\s+not|never|not|failed\s+to)\s+(?:obtain|obtained|receive|received|"
    r"get|got)\s+(?:(?:written|client)\s+)?(?:permission|authori[sz]ation)|"
    r"(?:permission|authori[sz]ation)(?:\s+request)?\s+(?:was\s+|is\s+)?"
    r"(?:denied|rejected|not\s+granted))\b",
    re.I,
)
_UNAUTHORIZED_ACTIVITY_DISCLAIMER = re.compile(
    r"(?:未授权|未经授权)(?:的)?(?:渗透|安全)?(?:测试|攻击|入侵|扫描|利用)"
    r"(?:不作为|不是|不属于|不在|未纳入|不包含|不涉及)(?:本|该)?"
    r"(?:项目|经历|实践|工作)?(?:的)?内容|"
    r"(?:项目|经历|实践|工作)(?:内容)?(?:不包含|不涉及|未进行|未开展)"
    r"(?:未授权|未经授权)(?:的)?(?:渗透|安全)?(?:测试|攻击|入侵|扫描|利用)|"
    r"\bunauthori[sz]ed\s+(?:penetration\s+test(?:ing)?|pentest(?:ing)?|"
    r"security\s+test(?:ing)?|attack|scan(?:ning)?|exploit(?:ation)?|hacking)"
    r"\s+(?:was\s+|is\s+|were\s+|are\s+)?not\s+"
    r"(?:part\s+of|included\s+in|performed|conducted)\b",
    re.I,
)
_ABSENCE_OR_NEGATION = re.compile(
    r"未参与|未参加|未做|未进行|未开展|未实施|未完成|未接触|未在|不在|"
    r"不涉及|不属于|不是|并非|非(?=靶场|CTF)|"
    r"无关|暂无|尚无|无经验|没有经验|从未参加|从未参与|经验(?:为|是)?无|零经验|"
    r"范围(?:外|以外|之外)|未确认|不明|不确定|尚不清楚|"
    r"(?:没有|无|尚无)\s*(?:CTF|靶场|安全实验(?:室|环境)|漏洞赏金|授权测试)\s*"
    r"(?:经验|经历|实践)?|"
    r"(?:CTF|靶场|安全实验(?:室|环境)|漏洞赏金|授权测试)\s*(?:经验|经历)?\s*"
    r"(?:为|是|[:：])?\s*(?:无|暂无|否)|"
    r"(?:[:：]\s*)(?:无|否)(?:经验|经历)?(?:\s|$)|"
    r"\b(?:none|zero(?:\s+experience)?|never participated|never joined|no experience|"
    r"did not participate|didn't participate|not participating|not involved|not related|"
    r"unrelated|lack(?:s|ing)?|not\s+(?:in|within|a|part\s+of|eligible\s+for)|"
    r"outside(?:\s+the)?|out\s+of\s+scope|scope\s+unknown|no\s+\w+\s+access|"
    r"access\s+denied|participation\s*:\s*none)\b",
    re.I,
)
_PENDING_OR_HYPOTHETICAL = re.compile(
    r"讨论|询问|咨询|等待|待确认|需确认|需要确认|尚待确认|待批准|待授权|缺失|未定义|"
    r"是否(?:在)?授权|(?:如果|若|假设|假定|可能|也许|声称)[^。！？!?；;，,\n]{0,16}授权|"
    r"(?:计划|准备|希望|拟|将|想)[^。！？!?；;，,\n]{0,16}"
    r"(?:参加|参与|演练|测试|CTF|靶场|漏洞赏金|授权)|"
    r"可能(?:获得|取得)?授权|也许(?:获得|取得)?授权|计划(?:获得|申请)?授权|"
    r"(?:一旦|待|预计|预期|有望|假如|倘若)(?:获得|取得|得到)?授权|"
    r"申请授权|寻求授权|希望获得授权|"
    r"\b(?:discuss(?:ed|ing)?|ask(?:ed|ing)?|question(?:ed|ing)?|wait(?:ed|ing)?|"
    r"pending|to be confirmed|needs? confirmation|missing|undefined|may obtain|"
    r"might obtain|could obtain|plan(?:ned|ning)? to obtain|seek(?:ing)?|"
    r"request(?:ed|ing)? authorization|"
    r"(?:if|suppos(?:e|ed|ing)|assuming|allegedly|claimed)\b[^.;,!\n]{0,48}"
    r"\bauthori[sz]ed|"
    r"(?:plan(?:ned|ning)?|hope[sd]?|intend(?:ed|ing)?|will)\b[^.;,!\n]{0,48}"
    r"\b(?:participate|join|compete|ctf|bug bounty|security lab|lab exercise))\b",
    re.I,
)
_GLOBAL_AUTHORIZATION_DENIAL = re.compile(
    r"(?:攻击|测试|目标)?\s*范围(?:外|以外|之外)(?:目标)?|"
    r"(?:不在|未在|超出|超过|突破)(?:了)?(?:客户|书面|批准)?授权范围(?:内)?|"
    r"(?:许可|授权)(?:的)?(?:测试|目标)?范围"
    r"(?:尚未|还未|未|没有|不|尚不|待|尚待)(?:明确|确认|清楚|确定|定义)|"
    r"(?:许可|授权)(?:的)?(?:测试|目标)?范围(?:不明|未知|不确定)|"
    r"(?:该|此|这个|上述)?目标(?:并未|尚未|还未|未|没有|不曾)"
    r"(?:获准|获批|被授权|得到许可)(?:进行|开展)?(?:安全|渗透)?(?:测试|评估|扫描|攻击)?|"
    r"(?:并未|尚未|还未|未|没有|不曾)(?:获准|获批|被授权|得到许可)"
    r"(?:对)?(?:该|此|这个|上述)?目标(?:进行|开展)?(?:安全|渗透)?(?:测试|评估|扫描|攻击)|"
    r"(?:并未|尚未|还未|未|没有|不曾)(?:获准|获批|被授权|得到许可)"
    r"(?:进行|开展)?(?:安全|渗透)?(?:测试|评估|扫描|攻击)(?:该|此|这个|上述)?目标|"
    r"(?:许可|授权)(?:并未|尚未|还未|未|没有|不曾)(?:覆盖|包括)(?:该|此|这个|上述)?目标|"
    r"(?:许可|授权)(?:后来|随后|之后|此后|最终|现已|已经|已)?(?:又?被)?"
    r"(?:撤销|取消|终止|过期|到期|失效|作废|废止|无效|不再有效|不再生效|不再具有效力)|"
    r"(?:许可|授权)(?:后来|随后|之后|此后|最终|现已|已经|已|实际|其实)?(?:又?被)?"
    r"(?:确认|认定|证实|证明|发现)?(?:为|是|系|属于)?"
    r"(?:伪造|虚假|假的|无效|未生效)|"
    r"(?:后来|随后|之后|此后|最终)?(?:确认|认定|证实|证明|发现)"
    r"(?:该|此|其|上述)?(?:许可|授权)(?:为|是|系|属于)"
    r"(?:伪造|虚假|假的|无效|未生效)|"
    r"(?:该|此|其|上述|客户|书面|正式)?(?:许可|授权)"
    r"(?:并未|从未|未曾|尚未|还未|未|没有)(?:正式)?生效|"
    r"(?:该|此|其|上述|客户|书面|正式)?(?:许可|授权)(?:为|是|属于)?无效|"
    r"(?:获|获得|取得|得到|使用|提交|出示)(?:了)?"
    r"[^。！？!?；;，,\n]{0,12}(?:伪造|虚假|假的|无效|未生效|已撤销|已取消|已过期)"
    r"(?:的)?(?:书面|客户|正式)?(?:许可|授权)|"
    r"(?:伪造|虚假|假的|无效|未生效|已撤销|已取消|已过期)(?:的)?"
    r"(?:书面|客户|正式)?(?:许可|授权)(?=[^。！？!?；;，,\n]{0,12}"
    r"(?:后|进行|开展|测试|渗透|评估|扫描|利用|攻击)|[。！？!?；;，,\n]|$)|"
    r"授权期限(?:已)?结束|"
    r"\b(?:out\s+of\s+scope|outside\s+(?:the\s+)?scope|"
    r"(?:not|never)\s+(?:in|within)\s+(?:the\s+)?(?:authori[sz]ed|approved)\s+scope|"
    r"(?:beyond|exceeded?|breached)\s+(?:the\s+)?(?:authori[sz]ed|approved)\s+scope)"
    r"(?:\s+target)?\b|"
    r"\b(?:authorization|permission)\s+"
    r"(?:is\s+|was\s+|had\s+|has\s+been\s+|had\s+been\s+)?"
    r"(?:(?:later|subsequently|eventually|now)\s+)?"
    r"(?:(?:found|proven|determined|confirmed)\s+(?:to\s+be|as)\s+)?"
    r"(?:(?:turned\s+out|proved)(?:\s+to\s+be)?\s+)?"
    r"(?:forged|fake|fraudulent|fabricated|expired|revoked|withdrawn|cancelled|"
    r"canceled|terminated|rescinded|lapsed|invalid|void|"
    r"ineffective|not\s+(?:yet\s+)?effective|no\s+longer\s+(?:valid|effective|in\s+effect))\b|"
    r"\b(?:authorization|permission|approved)\s+scope\s+"
    r"(?:is\s+|was\s+|had\s+been\s+|remains?\s+)?(?:unclear|undefined|unknown|ambiguous|"
    r"not\s+(?:specified|defined|confirmed|clear))\b|"
    r"\b(?:authorization|permission)\s+(?:does\s+not|did\s+not|doesn't|didn't)\s+"
    r"(?:cover|include)\s+(?:this|that|the)\s+target\b|"
    r"\b(?:authorization|permission)\s+(?:(?:has|had)\s+not\s+(?:yet\s+)?"
    r"(?:become\s+effective|taken\s+effect)|never\s+(?:became\s+effective|took\s+effect)|"
    r"(?:has|had)\s+never\s+(?:become\s+effective|taken\s+effect)|"
    r"did\s+not\s+(?:become\s+effective|take\s+effect))\b|"
    r"\b(?:this|that|the)\s+target\s+(?:is\s+|was\s+|has\s+been\s+)?"
    r"not\s+(?:authori[sz]ed|approved|permitted)(?:\s+for\s+(?:security\s+|penetration\s+)?"
    r"(?:test(?:ing)?|assessment|scanning|attack))?\b|"
    r"\bnot\s+(?:authori[sz]ed|approved|permitted)\s+to\s+"
    r"(?:test|assess|scan|attack)\s+(?:this|that|the)\s+target\b|"
    r"\b(?:obtained|received|used|submitted|presented)\s+(?:an?\s+)?"
    r"(?:forged|fake|fraudulent|fabricated|invalid|ineffective|not[- ]yet[- ]effective)"
    r"\s+(?:(?:written|client)\s+)?(?:authorization|permission)\b|"
    r"\b(?:forged|fake|fraudulent|fabricated|invalid|ineffective|"
    r"not[- ]yet[- ]effective)\s+(?:(?:written|client)\s+)?"
    r"(?:authorization|permission)\b(?=[^.;,!\n]{0,32}"
    r"(?:test|assessment|scan|exploit|attack|after)|[.;,!\n]|$)|"
    r"\b(?:authorization|permission)\s+(?:period\s+)?(?:has\s+|is\s+)?ended\b",
    re.I,
)
_AUTHORIZATION_SCOPE_FINDING = re.compile(
    r"(?:复现|发现|修复|检测|识别|排查|验证|报告|披露|定位|解决|阻断|分析)"
    r"[^。！？!?；;，,\n]{0,32}(?:许可|授权)(?:的)?(?:测试|目标)?范围"
    r"(?:尚未|还未|未|没有|不|尚不|待|尚待)?"
    r"(?:明确|确认|清楚|确定|定义|不明|未知|不确定)"
    r"[^。！？!?；;，,\n]{0,16}(?:权限绕过|越权)?(?:漏洞|缺陷)|"
    r"\b(?:reproduc(?:ed|ing)?|found|fix(?:ed|ing)?|detect(?:ed|ing)?|"
    r"identif(?:ied|ying)|investigat(?:ed|ing)|report(?:ed|ing)?|disclos(?:ed|ing)|"
    r"remediat(?:ed|ing)?|analy[sz](?:ed|ing))\b"
    r"[^.;,!\n]{0,48}\b(?:authorization|permission|approved)\s+scope\s+"
    r"(?:is\s+|was\s+|had\s+been\s+)?"
    r"(?:unclear|undefined|unknown|ambiguous|not\s+(?:specified|defined|confirmed|clear))"
    r"[^.;,!\n]{0,24}\b(?:vulnerabilit(?:y|ies)|bugs?|flaws?|defects?|bypass)\b",
    re.I,
)
_AUTHORIZATION_LIFECYCLE_FINDING = re.compile(
    r"(?:复现|发现|修复|检测|识别|排查|验证|报告|披露|定位|解决|阻断|分析)"
    r"[^。！？!?；;，,\n]{0,32}(?:许可|授权)(?:的)?(?:并未|从未|未曾|尚未|还未|未|没有)"
    r"(?:正式)?生效[^。！？!?；;，,\n]{0,16}(?:权限绕过|越权)?(?:漏洞|缺陷)|"
    r"(?:复现|发现|修复|检测|识别|排查|验证|报告|披露|定位|解决|阻断|分析)"
    r"[^。！？!?；;，,\n]{0,32}(?:许可|授权)(?:的)?(?:现已|已经|已)?(?:又?被)?"
    r"(?:撤销|取消|终止|过期|到期|失效|作废|废止|无效|不再有效|不再生效)"
    r"[^。！？!?；;，,\n]{0,16}(?:权限绕过|越权)?(?:漏洞|缺陷)|"
    r"\b(?:reproduc(?:ed|ing)?|found|fix(?:ed|ing)?|detect(?:ed|ing)?|"
    r"identif(?:ied|ying)|investigat(?:ed|ing)|report(?:ed|ing)?|disclos(?:ed|ing)|"
    r"remediat(?:ed|ing)?|analy[sz](?:ed|ing))\b"
    r"[^.;,!\n]{0,48}\b(?:authorization|permission)\s+"
    r"(?:(?:is|was|has\s+been|had\s+been)\s+)?"
    r"(?:not\s+(?:yet\s+)?effective|revoked|expired|withdrawn|cancelled|canceled|"
    r"terminated|rescinded|lapsed|invalid|void|ineffective|no\s+longer\s+effective)"
    r"[^.;,!\n]{0,24}\b(?:vulnerabilit(?:y|ies)|bugs?|flaws?|defects?|bypass)\b",
    re.I,
)
_CONTINUED_AFTER_SCOPE_FINDING = re.compile(
    r"^\s*(?:[，,;；]\s*)?(?:(?:但|并|且|后|之后|随后)\s*)?"
    r"(?:仍|仍然|继续|依然|又)\s*[^。！？!?；;，,\n]{0,16}"
    r"(?:测试|扫描|攻击|利用|渗透|评估)|"
    r"^\s*(?:[,;]\s*)?(?:and\s+|but\s+|then\s+)?"
    r"(?:still\s+)?continued?\s+(?:to\s+)?"
    r"(?:test(?:ing)?|scan(?:ning)?|attack(?:ing)?|exploit(?:ing)?|assess(?:ing|ment)?)\b",
    re.I,
)
_MERE_MENTION = re.compile(
    r"了解|学习|阅读|浏览|介绍|概念|规则|仅知道|听说|熟悉|掌握|认知|"
    r"\b(?:learn(?:ed|ing)? about|read(?:ing)? about|overview|introduction|concept|"
    r"rules?|familiarity|familiar\s+with|knowledge\s+of)\b",
    re.I,
)
_NON_APPLIED_CONTEXT = re.compile(
    r"课程(?:作业|内容|学习|培训|教程|认证|考试|证书|项目|名称|介绍|中|[:：]|$)|"
    r"培训|教程|认证|证书|考试|学习材料|"
    r"\b(?:course|coursework|class|training|tutorial|certification|certificate|exam|"
    r"study material)s?\b",
    re.I,
)
_ACTIVE_PARTICIPATION = re.compile(
    r"参加|参与|完成|负责|进行|开展|实施|执行|复现|搭建|使用|"
    r"修复|检测|分析|验证|解决|加固|排查|"
    r"提交|入选|接受|获奖|夺得|"
    r"\b(?:participat(?:ed|ing)|competed|completed|practiced|exercised|tested|"
    r"used|built|submitted|accepted|joined|conducted|performed|worked|reported|won|"
    r"fix(?:ed|ing)|remediat(?:ed|ing)|resolv(?:ed|ing)|detect(?:ed|ing)|"
    r"analy[sz](?:ed|ing)|validat(?:ed|ing))\b",
    re.I,
)
_SECURITY_EXERCISE_ACTION = re.compile(
    r"测试|演练|攻防|渗透|复现|漏洞|代码审计|安全验证|CTF|竞赛|比赛|解题|夺旗|"
    r"提交\s*flag|"
    r"攻击|防御|应急|取证|检测|加固|排查|扫描|利用|回归|"
    r"\b(?:test(?:ed|ing)?|exercis(?:e|ed|ing)|challenge|exploit(?:ed|ing|ation)?|"
    r"assess(?:ed|ing|ment)?|pentest(?:ed|ing)?|penetration\s+test(?:ed|ing)?|"
    r"attack(?:ed|ing)?|defen(?:d|ded|ding|se)|incident|forensic|vulnerabilit|"
    r"bugs?|flaws?|defects?|"
    r"audit(?:ed|ing)?|reproduc(?:e|ed|ing)|scan(?:ned|ning)?|remediat|retest)\b",
    re.I,
)
_PARTICIPATION_ADMIN_ONLY = re.compile(
    r"(?:CTF|靶场|安全实验(?:室|环境)|漏洞赏金)[^。！？!?；;，,\n]{0,20}"
    r"(?:报名|注册|参观|观摩|设备|日常管理|会议室|盘点|预约|宣传|组织|协办|"
    r"裁判|摄影|拍摄|摄像|运营|会务|后勤|主持|志愿者|直播)|"
    r"(?:报名|注册|参观|观摩|设备|日常管理|会议室|盘点|预约|宣传|组织|协办|"
    r"裁判|摄影|拍摄|摄像|运营|会务|后勤|主持|志愿者|直播)"
    r"[^。！？!?；;，,\n]{0,20}(?:CTF|靶场|安全实验(?:室|环境)|漏洞赏金)|"
    r"\b(?:registration|registered|sign[- ]?up|tour|visited?|visitor|equipment|"
    r"room booking|inventory|administration|administrative|organized?|promoted?|"
    r"judge|judging|referee|photograph(?:y|er)?|camera|event operations?|event staff|"
    r"logistics|host|volunteer|livestream)"
    r"\b[^.;,!\n]{0,32}\b(?:ctf|security lab|cyber lab|bug bounty)\b|"
    r"\b(?:ctf|security lab|cyber lab|bug bounty)\b[^.;,!\n]{0,32}"
    r"\b(?:registration|sign[- ]?up|tour|equipment|room booking|inventory|"
    r"administration|administrative|organization|promotion|judge|judging|referee|"
    r"photograph(?:y|er)?|camera|event operations?|event staff|logistics|host|volunteer|"
    r"livestream)\b",
    re.I,
)
_EXPLICIT_AUTHORIZATION = re.compile(
    r"(?:已|正式|书面|客户)授权(?:的)?(?:渗透|安全)?测试|"
    r"(?:书面|客户|正式)?(?:授权|许可)(?:已|已经|当前)?生效(?:后)?|"
    r"(?:已(?:获得|取得)|已经(?:获得|取得)|获得|取得)"
    r"(?:了)?[^\u3002！？!?;\uff1b\n]{0,16}(?:书面|客户|正式)?授权(?:后|并|$)|"
    r"经(?:书面|客户|正式)?授权(?:后|范围内|进行|开展)|"
    r"(?:获得|取得)(?:书面|客户|正式)?授权(?:后|的)?(?:进行|开展)?(?:渗透|安全)?测试|"
    r"(?:在|于)?(?:明确|书面|客户|批准)?授权范围内|"
    r"在(?:明确|书面|客户|批准)?授权范围(?:内)?(?:负责|进行|开展)|"
    r"\b(?:client[- ]authori[sz]ed\s+(?:pentest|penetration test(?:ing)?|"
    r"security assessment|security test(?:ing)?)|"
    r"authori[sz]ed\s+(?:pentest|penetration test(?:ing)?|security assessment|"
    r"security test(?:ing)?)|"
    r"(?:written|client)\s+authorization\s+(?:for|to conduct)\s+(?:a\s+)?"
    r"(?:pentest|penetration test(?:ing)?|security assessment|security test(?:ing)?)|"
    r"(?:within|inside)\s+(?:the\s+)?(?:authori[sz]ed|approved)\s+scope)\b",
    re.I,
)
_LAB_CONTEXT = re.compile(
    r"安全(?:靶场|实验室|实验环境|演练环境)|网络安全(?:实验室|实验环境|演练)|"
    r"(?:靶场|安全实验环境)(?:演练|实践|测试|项目)?|"
    r"\b(?:(?:security|cyber(?:security)?|authori[sz]ed)\s+(?:lab|laboratory|exercise)|"
    r"lab\s+(?:environment|exercise))\b",
    re.I,
)
_NON_SECURITY_LAB = re.compile(
    r"\b(?:chemistry|chemical|biology|biological|physics|medical|clinical)\b|"
    r"化学|生物|物理|医学|临床|实验设备|\blab equipment\b",
    re.I,
)
_CTF_CONTEXT = re.compile(
    r"(?:参加|参与|完成|负责|进行|开展|执行|举办)?\s*CTF\s*"
    r"(?:竞赛|比赛|挑战|演练|解题|夺旗|题目|提交\s*flag)|"
    r"\bCTF\s+(?:competition|contest|challenge|exercise|problem solving|"
    r"flag capture|flag submission)\b",
    re.I,
)
_BUG_BOUNTY_CONTEXT = re.compile(
    r"(?:参加|参与|入选|接受|完成)(?:了|的)?(?:公开)?漏洞赏金(?:计划|项目)?|"
    r"(?:公开)?漏洞赏金(?:计划|项目)(?:中|内)|"
    r"在(?:公开)?漏洞赏金(?:计划|项目|范围)(?:中|内)?(?:负责|进行|开展)|"
    r"\b(?:accepted\s+(?:into\s+)?(?:a\s+)?bug bounty|"
    r"participated\s+in\s+(?:a\s+)?bug bounty)\b",
    re.I,
)
_CLAUSE_SPLIT = re.compile(r"[。！？!?；;，,\n]+|\b(?:but|however)\b|(?:但|不过|然而)", re.I)
_ALLOWED_ENVIRONMENTS = frozenset({"lab", "ctf", "bug_bounty", "authorized"})
_ENVIRONMENT_MARKERS: dict[str, re.Pattern[str]] = {
    "lab": re.compile(r"靶场|安全实验环境|安全实验室|\b(?:security|cyber)?\s*lab\b", re.I),
    "ctf": re.compile(r"(?<![A-Za-z0-9_])ctf(?![A-Za-z0-9_])|夺旗", re.I),
    "bug_bounty": re.compile(r"漏洞赏金|(?<![A-Za-z0-9_])bug bounty(?![A-Za-z0-9_])", re.I),
    "authorized": re.compile(r"授权|\b(?:authori[sz]ed|authorization|permission)\b", re.I),
}


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def _clauses(text: str) -> tuple[str, ...]:
    return tuple(
        clause.strip() for clause in _CLAUSE_SPLIT.split(_normalize(text)) if clause.strip()
    )


def _mask_authorization_state_findings(text: str) -> str:
    """Remove explicit tested-system authorization findings before permission checks."""

    def replacement(match: re.Match[str]) -> str:
        following = text[match.end() : match.end() + 64]
        if _CONTINUED_AFTER_SCOPE_FINDING.search(following):
            return match.group(0)
        return " "

    masked = _AUTHORIZATION_SCOPE_FINDING.sub(replacement, text)
    return _AUTHORIZATION_LIFECYCLE_FINDING.sub(replacement, masked)


def _clause_is_negated_or_unconfirmed(clause: str) -> bool:
    permission_text = _mask_authorization_state_findings(clause)
    return bool(
        _EXPLICIT_UNAUTHORIZED.search(permission_text)
        or _GLOBAL_AUTHORIZATION_DENIAL.search(permission_text)
        or _ABSENCE_OR_NEGATION.search(permission_text)
        or _PENDING_OR_HYPOTHETICAL.search(permission_text)
    )


def _clause_is_only_a_mention(clause: str) -> bool:
    return bool(_NON_APPLIED_CONTEXT.search(clause) or _MERE_MENTION.search(clause))


def _clause_has_explicit_unauthorized_activity(clause: str) -> bool:
    return bool(
        _EXPLICIT_UNAUTHORIZED.search(clause)
        and not _UNAUTHORIZED_ACTIVITY_DISCLAIMER.search(clause)
    )


def has_negative_authorization_signal(text: str) -> bool:
    """Return whether text denies, lacks, or leaves authorization unconfirmed."""

    return any(_clause_is_negated_or_unconfirmed(clause) for clause in _clauses(text))


def has_global_authorization_denial(text: str) -> bool:
    """Return whether scope, lifecycle, or explicit illegal activity denies authorization."""

    normalized = _mask_authorization_state_findings(_normalize(text))
    return bool(
        _GLOBAL_AUTHORIZATION_DENIAL.search(normalized)
        or any(
            _clause_has_explicit_unauthorized_activity(clause) for clause in _clauses(normalized)
        )
    )


def mask_negative_authorization_spans(text: str) -> str:
    """Remove denial, absence, and hypothetical phrases before positive matching."""

    normalized = _normalize(text)
    for pattern in (
        _EXPLICIT_UNAUTHORIZED,
        _GLOBAL_AUTHORIZATION_DENIAL,
        _ABSENCE_OR_NEGATION,
        _PENDING_OR_HYPOTHETICAL,
    ):
        normalized = pattern.sub(" ", normalized)
    return normalized


def _positive_clauses(text: str) -> tuple[str, ...]:
    if has_global_authorization_denial(text):
        return ()
    return tuple(
        clause
        for clause in _clauses(text)
        if not _clause_is_negated_or_unconfirmed(clause) and not _clause_is_only_a_mention(clause)
    )


def has_explicit_completed_authorization_signal(text: str) -> bool:
    """Require completed authorization, not merely another kind of safe environment."""

    return any(_EXPLICIT_AUTHORIZATION.search(clause) for clause in _positive_clauses(text))


def has_ctf_participation_signal(text: str) -> bool:
    """Require an affirmative CTF competition, challenge, or exercise context."""

    return any(
        _CTF_CONTEXT.search(clause)
        and _ACTIVE_PARTICIPATION.search(clause)
        and _SECURITY_EXERCISE_ACTION.search(clause)
        and not _PARTICIPATION_ADMIN_ONLY.search(clause)
        for clause in _positive_clauses(text)
    )


def has_lab_participation_signal(text: str) -> bool:
    """Require an affirmative security-lab or cyber-exercise context."""

    return any(
        _LAB_CONTEXT.search(clause)
        and _ACTIVE_PARTICIPATION.search(clause)
        and _SECURITY_EXERCISE_ACTION.search(clause)
        and not _NON_SECURITY_LAB.search(clause)
        and not _PARTICIPATION_ADMIN_ONLY.search(clause)
        for clause in _positive_clauses(text)
    )


def has_bug_bounty_participation_signal(text: str) -> bool:
    """Require accepted or actual participation in a bug-bounty program."""

    return any(
        _BUG_BOUNTY_CONTEXT.search(clause)
        and _ACTIVE_PARTICIPATION.search(clause)
        and not _PARTICIPATION_ADMIN_ONLY.search(clause)
        for clause in _positive_clauses(text)
    )


def has_positive_authorization_signal(text: str) -> bool:
    """Accept explicit authorization or a concrete safe security exercise context."""

    if has_global_authorization_denial(text):
        return False
    for clause in _clauses(text):
        if _clause_is_negated_or_unconfirmed(clause) or _clause_is_only_a_mention(clause):
            continue
        if _EXPLICIT_AUTHORIZATION.search(clause):
            return True
        if (
            _LAB_CONTEXT.search(clause)
            and _ACTIVE_PARTICIPATION.search(clause)
            and _SECURITY_EXERCISE_ACTION.search(clause)
            and not _NON_SECURITY_LAB.search(clause)
            and not _PARTICIPATION_ADMIN_ONLY.search(clause)
        ):
            return True
        if (
            _CTF_CONTEXT.search(clause)
            and _ACTIVE_PARTICIPATION.search(clause)
            and _SECURITY_EXERCISE_ACTION.search(clause)
            and not _PARTICIPATION_ADMIN_ONLY.search(clause)
        ):
            return True
        if (
            _BUG_BOUNTY_CONTEXT.search(clause)
            and _ACTIVE_PARTICIPATION.search(clause)
            and not _PARTICIPATION_ADMIN_ONLY.search(clause)
        ):
            return True
    return False


def infer_authorization_environment(text: str) -> str | None:
    """Classify an explicit positive context without trusting a supplied enum."""

    if has_explicit_completed_authorization_signal(text):
        return "authorized"
    if has_ctf_participation_signal(text):
        return "ctf"
    if has_lab_participation_signal(text):
        return "lab"
    if has_bug_bounty_participation_signal(text):
        return "bug_bounty"
    return None


def environment_is_authorized(environment: Any) -> bool:
    """Recognize only fixed structured environments as authorization evidence."""

    value = getattr(environment, "value", environment)
    return isinstance(value, str) and value in _ALLOWED_ENVIRONMENTS


def _environment_is_explicitly_denied(environment: Any, text: str) -> bool:
    value = getattr(environment, "value", environment)
    if not isinstance(value, str):
        return False
    marker = _ENVIRONMENT_MARKERS.get(value)
    if marker is None:
        return False
    return any(
        marker.search(clause)
        and _clause_is_negated_or_unconfirmed(clause)
        and not (value == "authorized" and _UNAUTHORIZED_ACTIVITY_DISCLAIMER.search(clause))
        for clause in _clauses(text)
    )


def source_is_authorized(
    environment: Any,
    text: str,
    *,
    require_explicit: bool = False,
) -> bool:
    """Apply the single authorization decision used by audit, matching, and scoring."""

    normalized = _normalize(text)
    if has_global_authorization_denial(text):
        return False
    if environment_is_authorized(environment) and any(
        _clause_has_explicit_unauthorized_activity(clause) for clause in _clauses(normalized)
    ):
        return False
    if _environment_is_explicitly_denied(environment, text):
        return False
    explicit = has_explicit_completed_authorization_signal(text)
    if require_explicit:
        return explicit
    if explicit:
        return True
    value = getattr(environment, "value", environment)
    if value == "ctf":
        return has_ctf_participation_signal(text)
    if value == "lab":
        return has_lab_participation_signal(text)
    if value == "bug_bounty":
        return has_bug_bounty_participation_signal(text)
    if value == "authorized":
        return False
    return has_positive_authorization_signal(text)


__all__ = [
    "environment_is_authorized",
    "has_bug_bounty_participation_signal",
    "has_ctf_participation_signal",
    "has_explicit_completed_authorization_signal",
    "has_global_authorization_denial",
    "has_lab_participation_signal",
    "has_negative_authorization_signal",
    "has_positive_authorization_signal",
    "infer_authorization_environment",
    "mask_negative_authorization_spans",
    "source_is_authorized",
]
