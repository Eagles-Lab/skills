#!/usr/bin/env python3
"""
SRE 简历分析主流程脚本
SRE Resume Analysis Main Script

整合 PDF 提取、结构化解析、评分、建议生成和面试题生成
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

# 添加父目录到系统路径，以便导入其他模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.scoring.score_calculator import ScoreCalculator
from scripts.generators.interview_generator import InterviewGenerator
from scripts.generators.suggestions_generator import SuggestionsGenerator
from scripts.logger import setup_logger, get_logger

# 初始化日志
logger = setup_logger("resume_analyzer")


class ResumeAnalyzerError(Exception):
    """简历分析错误"""
    pass


class ResumeAnalyzer:
    """简历分析器，整合完整的分析流程"""

    def __init__(self, config_dir: str = None, output_dir: str = None):
        """
        初始化简历分析器

        Args:
            config_dir: 配置文件目录
            output_dir: 输出目录
        """
        self.logger = get_logger("ResumeAnalyzer")

        try:
            self.config_dir = config_dir or str(Path(__file__).parent.parent / "config")
            self.output_dir = output_dir or str(Path(__file__).parent.parent / "processing")

            self.logger.info(f"初始化分析器 - 配置目录: {self.config_dir}, 输出目录: {self.output_dir}")

            # 初始化各模块
            self.score_calculator = ScoreCalculator(self.config_dir)
            self.interview_generator = InterviewGenerator(
                str(Path(__file__).parent.parent / "templates")
            )
            self.suggestions_generator = SuggestionsGenerator(
                str(Path(__file__).parent.parent / "templates")
            )

            self.logger.info("分析器初始化完成")

        except Exception as e:
            self.logger.error(f"分析器初始化失败: {e}", exc_info=True)
            raise ResumeAnalyzerError(f"分析器初始化失败: {e}")

    def analyze_resume(self, extracted_json_path: str, resume_text: str = None) -> Dict:
        """
        分析简历

        Args:
            extracted_json_path: extracted.json 文件路径
            resume_text: 简历原文文本（可选）

        Returns:
            分析结果，包含所有输出文件路径

        Raises:
            ResumeAnalyzerError: 分析失败
        """
        self.logger.info(f"开始分析简历: {extracted_json_path}")

        try:
            # 1. 读取结构化数据
            self.logger.info("步骤 1/6: 读取结构化数据")
            extracted_data = self._load_extracted_data(extracted_json_path)

            if not extracted_data:
                raise ResumeAnalyzerError(f"无法加载结构化数据: {extracted_json_path}")

            self.logger.info(f"✓ 数据加载成功")

            # 2. 生成简历 ID 和输出目录
            self.logger.info("步骤 2/6: 创建输出目录")
            resume_id = extracted_data.get("resume_id", self._generate_resume_id())
            output_dir = Path(self.output_dir) / resume_id
            output_dir.mkdir(parents=True, exist_ok=True)

            self.logger.info(f"✓ 输出目录: {output_dir}")

            # 3. 评分分析
            self.logger.info("步骤 3/6: 计算评分")
            score_data = self.score_calculator.calculate_scores(extracted_data, resume_text)
            score_data["resume_id"] = resume_id
            score_data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.logger.info(f"✓ 评分完成: 总分 {score_data['total_score']}/11.5")

            # 4. 分析优劣
            self.logger.info("步骤 4/6: 分析优势劣势")
            analysis_data = self._analyze_strengths_weaknesses(score_data, extracted_data)
            analysis_data["resume_id"] = resume_id
            analysis_data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.logger.info(f"✓ 分析完成: 优势 {len(analysis_data['strengths'])} 项, 劣势 {len(analysis_data['weaknesses'])} 项")

            # 5. 生成建议
            self.logger.info("步骤 5/6: 生成优化建议")
            suggestions = self.suggestions_generator.generate_suggestions(
                extracted_data, score_data, analysis_data
            )
            self.logger.info(f"✓ 建议生成完成")

            # 6. 生成面试题
            self.logger.info("步骤 6/6: 生成面试题")
            interview_questions = self.interview_generator.generate_interview_questions(
                extracted_data, score_data
            )
            self.logger.info(f"✓ 面试题生成完成")

            # 7. 保存所有输出文件
            self.logger.info("保存输出文件...")
            output_files = {
                "extracted": str(output_dir / "extracted.json"),
                "score": str(output_dir / "score.json"),
                "analysis": str(output_dir / "analysis.json"),
                "suggestions": str(output_dir / "suggestions.md"),
                "interview_questions": str(output_dir / "interview_questions.md")
            }

            # 保存 extracted.json（如果不存在）
            if not Path(output_files["extracted"]).exists():
                self._save_json(output_files["extracted"], extracted_data)

            # 保存 score.json
            self._save_json(output_files["score"], score_data)

            # 保存 analysis.json
            self._save_json(output_files["analysis"], analysis_data)

            # 保存 suggestions.md
            self._save_markdown(output_files["suggestions"], suggestions)

            # 保存 interview_questions.md
            self._save_markdown(output_files["interview_questions"], interview_questions)

            self.logger.info("✓ 所有文件保存完成")
            self.logger.info(f"✓ 分析完成！生成 5 个文件")

            return output_files

        except ResumeAnalyzerError:
            raise
        except Exception as e:
            self.logger.error(f"分析过程中发生未预期错误: {e}", exc_info=True)
            raise ResumeAnalyzerError(f"分析失败: {e}")

    def _load_extracted_data(self, json_path: str) -> Optional[Dict]:
        """
        加载结构化数据

        Args:
            json_path: JSON 文件路径

        Returns:
            结构化数据字典
        """
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.logger.debug(f"成功加载数据: {json_path}")
            return data
        except FileNotFoundError:
            self.logger.error(f"文件不存在: {json_path}")
            return None
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON 解析失败: {json_path}, 错误: {e}")
            return None

    def _analyze_strengths_weaknesses(self, score_data: Dict, extracted_data: Dict) -> Dict:
        """分析优势和劣势"""
        dimension_scores = score_data.get("dimension_scores", {})

        # 识别优势维度（得分 >= 8.0）
        strengths = []
        for dimension, info in dimension_scores.items():
            if info.get("score", 0) >= 8.0:
                strengths.append({
                    "dimension": dimension,
                    "score": info["score"],
                    "evidence_count": len(info.get("evidence", [])),
                    "top_keywords": [
                        e.get("keyword") for e in info.get("evidence", [])[:3]
                        if e.get("keyword")
                    ]
                })

        # 识别劣势维度（得分 < 7.0）
        weaknesses = []
        for dimension, info in dimension_scores.items():
            if info.get("score", 0) < 7.0:
                weaknesses.append({
                    "dimension": dimension,
                    "score": info["score"],
                    "gap": 7.0 - info["score"],
                    "suggestions": self._get_improvement_suggestions(dimension)
                })

        # AI 应用分析
        ai_bonus = score_data.get("ai_bonus", {})
        ai_analysis = {
            "has_ai_experience": ai_bonus.get("score", 0) > 0,
            "score": ai_bonus.get("score", 0),
            "categories": list(ai_bonus.get("applications", {}).keys()) if ai_bonus.get("applications") else []
        }

        return {
            "strengths": strengths,
            "weaknesses": weaknesses,
            "ai_analysis": ai_analysis,
            "overall_assessment": self._generate_overall_assessment(score_data)
        }

    def _get_improvement_suggestions(self, dimension: str) -> list:
        """获取改进建议"""
        suggestions_map = {
            "monitoring": [
                "学习 Prometheus + Grafana 监控体系",
                "了解 SLI/SLO 设计原则",
                "实践分布式追踪（Jaeger/Zipkin）"
            ],
            "alerting": [
                "学习 Alertmanager 配置",
                "设计告警分级和收敛策略",
                "编写 Runbook"
            ],
            "automation": [
                "深入实践 CI/CD 流水线",
                "学习 Terraform/Ansible",
                "提升脚本编程能力"
            ],
            "containerization": [
                "系统学习 Kubernetes",
                "实践微服务架构",
                "了解 Service Mesh"
            ],
            "incident_handling": [
                "参与故障排查实战",
                "学习 RCA 和 Postmortem",
                "了解高可用设计"
            ],
            "resume_quality": [
                "使用 STAR 原则优化项目描述",
                "量化项目成果",
                "改进简历结构和表达"
            ]
        }
        return suggestions_map.get(dimension, ["持续学习和实践"])

    def _generate_overall_assessment(self, score_data: Dict) -> str:
        """生成总体评估"""
        total_score = score_data.get("total_score", 0)
        grade = score_data.get("grade", {}).get("grade", "F")
        grade_label = score_data.get("grade", {}).get("label", "需改进")

        if total_score >= 9.5:
            return f"综合评分 {total_score}/11.5 ({grade} - {grade_label})，表现卓越，具备 AI 技术应用能力，可直接投递"
        elif total_score >= 8.5:
            return f"综合评分 {total_score}/11.5 ({grade} - {grade_label})，表现优秀，可直接投递"
        elif total_score >= 7.0:
            return f"综合评分 {total_score}/11.5 ({grade} - {grade_label})，表现良好，小幅优化后可投递"
        elif total_score >= 5.5:
            return f"综合评分 {total_score}/11.5 ({grade} - {grade_label})，需要针对性改进薄弱项"
        else:
            return f"综合评分 {total_score}/11.5 ({grade} - {grade_label})，需要大幅改进"

    def _generate_resume_id(self) -> str:
        """生成简历 ID"""
        return f"resume_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def _save_json(self, file_path: str, data: Dict):
        """保存 JSON 文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.logger.debug(f"JSON 文件已保存: {file_path}")
        except IOError as e:
            self.logger.error(f"保存 JSON 文件失败: {file_path}, 错误: {e}")
            raise

    def _save_markdown(self, file_path: str, content: str):
        """保存 Markdown 文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.logger.debug(f"Markdown 文件已保存: {file_path}")
        except IOError as e:
            self.logger.error(f"保存 Markdown 文件失败: {file_path}, 错误: {e}")
            raise


class ResumeAnalyzerError(Exception):
    """简历分析错误"""
    pass


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="SRE 简历分析工具")
    parser.add_argument(
        "--extracted",
        required=True,
        help="extracted.json 文件路径"
    )
    parser.add_argument(
        "--text",
        help="简历原文文本文件路径（可选）"
    )
    parser.add_argument(
        "--output",
        default="./processing",
        help="输出目录（默认: ./processing）"
    )
    parser.add_argument(
        "--config",
        help="配置文件目录（可选）"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别（默认: INFO）"
    )

    args = parser.parse_args()

    # 设置日志级别
    import logging
    logging.getLogger("sre_analyzer").setLevel(getattr(logging, args.log_level))

    # 获取日志记录器
    logger = get_logger("main")
    logger.info("=" * 60)
    logger.info("SRE 简历分析工具启动")
    logger.info("=" * 60)

    # 读取简历原文（如果提供）
    resume_text = None
    if args.text:
        try:
            with open(args.text, 'r', encoding='utf-8') as f:
                resume_text = f.read()
            logger.info(f"简历原文已加载: {args.text}")
        except FileNotFoundError:
            logger.warning(f"简历原文文件不存在: {args.text}")

    # 创建分析器并执行分析
    try:
        analyzer = ResumeAnalyzer(
            config_dir=args.config,
            output_dir=args.output
        )

        output_files = analyzer.analyze_resume(args.extracted, resume_text)

        logger.info("=" * 60)
        logger.info("✓ 分析成功完成！")
        logger.info("=" * 60)
        logger.info("生成的文件:")
        for file_type, file_path in output_files.items():
            logger.info(f"  - {file_type}: {file_path}")

        return 0

    except ResumeAnalyzerError as e:
        logger.error(f"分析失败: {e}")
        return 1
    except KeyboardInterrupt:
        logger.warning("用户中断执行")
        return 130
    except Exception as e:
        logger.error(f"未预期错误: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())

