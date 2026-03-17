#!/usr/bin/env python3
"""
批量处理脚本
Batch Processor Script

支持并行处理多个简历，生成汇总报告
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.analyze_resume import ResumeAnalyzer
from scripts.logger import setup_logger, get_logger

# 初始化日志
logger = setup_logger("batch_processor")


class BatchProcessor:
    """批量处理器"""

    def __init__(self, config_dir: str = None, output_dir: str = None, max_workers: int = 3):
        """
        初始化批量处理器

        Args:
            config_dir: 配置文件目录
            output_dir: 输出目录
            max_workers: 最大并发数
        """
        self.config_dir = config_dir
        self.output_dir = output_dir
        self.max_workers = max_workers
        self.lock = threading.Lock()
        self.results = []
        self.logger = get_logger("BatchProcessor")

    def process_directory(self, input_dir: str, pattern: str = "*_extracted.json") -> Dict:
        """
        处理目录中的所有简历

        Args:
            input_dir: 输入目录
            pattern: 文件匹配模式

        Returns:
            处理结果汇总
        """
        input_path = Path(input_dir)

        if not input_path.exists():
            raise FileNotFoundError(f"输入目录不存在: {input_dir}")

        # 查找所有 extracted.json 文件
        extracted_files = list(input_path.glob(pattern))

        if not extracted_files:
            self.logger.warning(f"未找到匹配的文件: {input_dir}/{pattern}")
            return {
                "total": 0,
                "successful": 0,
                "failed": 0,
                "results": []
            }

        self.logger.info(f"找到 {len(extracted_files)} 个文件待处理")
        self.logger.info(f"并发数: {self.max_workers}")

        # 使用线程池并行处理
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._process_single_file, file_path): file_path
                for file_path in extracted_files
            }

            for future in as_completed(futures):
                file_path = futures[future]
                try:
                    result = future.result()
                    with self.lock:
                        self.results.append(result)
                    self.logger.info(f"✓ 完成: {file_path.name}")
                except Exception as e:
                    self.logger.error(f"✗ 失败: {file_path.name} - {e}")
                    with self.lock:
                        self.results.append({
                            "file": str(file_path),
                            "status": "failed",
                            "error": str(e)
                        })

        # 生成汇总报告
        summary = self._generate_summary()

        # 保存汇总报告
        summary_file = Path(self.output_dir) / "batch_summary.json"
        summary_file.parent.mkdir(parents=True, exist_ok=True)
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        self.logger.info(f"汇总报告已保存: {summary_file}")

        return summary

    def _process_single_file(self, file_path: Path) -> Dict:
        """
        处理单个文件

        Args:
            file_path: 文件路径

        Returns:
            处理结果
        """
        self.logger.debug(f"处理文件: {file_path}")

        analyzer = ResumeAnalyzer(
            config_dir=self.config_dir,
            output_dir=self.output_dir
        )

        try:
            output_files = analyzer.analyze_resume(str(file_path))

            # 读取评分结果
            score_file = output_files["score"]
            with open(score_file, 'r', encoding='utf-8') as f:
                score_data = json.load(f)

            return {
                "file": str(file_path),
                "status": "success",
                "resume_id": score_data.get("resume_id", "unknown"),
                "total_score": score_data.get("total_score", 0),
                "grade": score_data.get("grade", {}).get("grade", "F"),
                "output_files": output_files
            }

        except Exception as e:
            self.logger.error(f"处理失败: {file_path} - {e}")
            raise

    def _generate_summary(self) -> Dict:
        """
        生成汇总报告

        Returns:
            汇总报告
        """
        total = len(self.results)
        successful = sum(1 for r in self.results if r["status"] == "success")
        failed = total - successful

        # 统计各等级数量
        grade_distribution = {}
        score_distribution = []

        for result in self.results:
            if result["status"] == "success":
                grade = result["grade"]
                grade_distribution[grade] = grade_distribution.get(grade, 0) + 1
                score_distribution.append(result["total_score"])

        # 计算平均分
        average_score = sum(score_distribution) / len(score_distribution) if score_distribution else 0

        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total": total,
            "successful": successful,
            "failed": failed,
            "success_rate": f"{(successful / total * 100):.1f}%" if total > 0 else "0%",
            "average_score": round(average_score, 1),
            "grade_distribution": grade_distribution,
            "results": self.results
        }


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="SRE 简历批量处理工具")
    parser.add_argument(
        "--input-dir",
        required=True,
        help="输入目录（包含 extracted.json 文件）"
    )
    parser.add_argument(
        "--output-dir",
        default="./processing",
        help="输出目录（默认: ./processing）"
    )
    parser.add_argument(
        "--pattern",
        default="*_extracted.json",
        help="文件匹配模式（默认: *_extracted.json）"
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=3,
        help="并发数（默认: 3）"
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
    logging.getLogger("batch_processor").setLevel(getattr(logging, args.log_level))

    logger.info("=" * 60)
    logger.info("SRE 简历批量处理工具启动")
    logger.info("=" * 60)
    logger.info(f"输入目录: {args.input_dir}")
    logger.info(f"输出目录: {args.output_dir}")
    logger.info(f"并发数: {args.parallel}")

    # 创建批量处理器并执行
    processor = BatchProcessor(
        config_dir=args.config,
        output_dir=args.output_dir,
        max_workers=args.parallel
    )

    try:
        summary = processor.process_directory(args.input_dir, args.pattern)

        logger.info("=" * 60)
        logger.info("✓ 批量处理完成！")
        logger.info("=" * 60)
        logger.info(f"总数: {summary['total']}")
        logger.info(f"成功: {summary['successful']}")
        logger.info(f"失败: {summary['failed']}")
        logger.info(f"成功率: {summary['success_rate']}")
        logger.info(f"平均分: {summary['average_score']}")
        logger.info("等级分布:")
        for grade, count in summary.get("grade_distribution", {}).items():
            logger.info(f"  - {grade}: {count}")

        return 0

    except Exception as e:
        logger.error(f"批量处理失败: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
