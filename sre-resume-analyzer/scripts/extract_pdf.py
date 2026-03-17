#!/usr/bin/env python3
"""
PDF 提取脚本
PDF Extraction Script

使用 pdfplumber 提取 PDF 简历文本，支持错误处理和质量验证
"""

import sys
import json
import pdfplumber
from pathlib import Path
from typing import Dict, Optional
from logger import setup_logger

# 初始化日志
logger = setup_logger("extract_pdf")


class PDFExtractionError(Exception):
    """PDF 提取错误"""
    pass


class PDFValidationError(Exception):
    """PDF 验证错误"""
    pass


def validate_pdf(pdf_path: Path) -> None:
    """
    验证 PDF 文件

    Args:
        pdf_path: PDF 文件路径

    Raises:
        FileNotFoundError: 文件不存在
        PDFValidationError: 文件不是有效 PDF
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

    if not pdf_path.is_file():
        raise PDFValidationError(f"路径不是文件: {pdf_path}")

    if pdf_path.suffix.lower() != '.pdf':
        raise PDFValidationError(f"文件不是 PDF 格式: {pdf_path.suffix}")

    # 检查文件大小（最大 50MB）
    file_size = pdf_path.stat().st_size
    max_size = 50 * 1024 * 1024  # 50MB
    if file_size > max_size:
        raise PDFValidationError(
            f"PDF 文件过大 ({file_size / 1024 / 1024:.2f}MB)，最大支持 50MB"
        )


def validate_extraction_quality(result: Dict) -> None:
    """
    验证提取质量

    Args:
        result: 提取结果

    Raises:
        PDFExtractionError: 提取质量不达标
    """
    min_char_count = 100  # 最少字符数

    if result["total_char_count"] < min_char_count:
        raise PDFExtractionError(
            f"提取内容过少 ({result['total_char_count']} 字符)，"
            f"可能是扫描版 PDF 或提取失败"
        )


def extract_pdf(pdf_path: Path, strict: bool = True) -> Dict:
    """
    提取 PDF 文本和表格

    Args:
        pdf_path: PDF 文件路径
        strict: 是否严格验证提取质量

    Returns:
        提取结果字典

    Raises:
        FileNotFoundError: 文件不存在
        PDFValidationError: 文件验证失败
        PDFExtractionError: 提取失败
    """
    logger.info(f"开始提取 PDF: {pdf_path.name}")

    # 验证 PDF
    validate_pdf(pdf_path)

    result = {
        "file": str(pdf_path),
        "extraction_method": "pdfplumber",
        "pages": [],
        "full_text": "",
        "tables": []
    }

    try:
        with pdfplumber.open(pdf_path) as pdf:
            logger.info(f"PDF 总页数: {len(pdf.pages)}")

            for i, page in enumerate(pdf.pages):
                # 提取文本
                text = page.extract_text() or ""

                page_data = {
                    "page_number": i + 1,
                    "text": text,
                    "char_count": len(text)
                }
                result["pages"].append(page_data)
                result["full_text"] += text + "\n\n"

                # 提取表格
                tables = page.extract_tables()
                if tables:
                    for j, table in enumerate(tables):
                        if table:
                            result["tables"].append({
                                "page": i + 1,
                                "table_index": j,
                                "rows": len(table),
                                "data": table
                            })
                            logger.debug(f"第 {i+1} 页提取到表格 {j+1} ({len(table)} 行)")

            result["total_pages"] = len(result["pages"])
            result["total_char_count"] = len(result["full_text"])
            result["total_tables"] = len(result["tables"])

            logger.info(
                f"提取完成: {result['total_pages']} 页, "
                f"{result['total_char_count']} 字符, "
                f"{result['total_tables']} 个表格"
            )

            # 验证提取质量（严格模式）
            if strict:
                validate_extraction_quality(result)

            return result

    except pdfplumber.PdfError as e:
        logger.error(f"PDF 解析错误: {str(e)}")
        raise PDFExtractionError(f"PDF 解析错误: {str(e)}")
    except Exception as e:
        logger.error(f"提取过程中发生未预期错误: {str(e)}")
        raise PDFExtractionError(f"提取过程中发生未预期错误: {str(e)}")


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("Usage: python3 extract_pdf.py <pdf_path>")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])

    try:
        result = extract_pdf(pdf_path, strict=True)

        # 打印摘要
        print(f"\n✅ 提取成功")
        print(f"文件: {result['file']}")
        print(f"总页数: {result['total_pages']}")
        print(f"总字符数: {result['total_char_count']}")
        print(f"表格数量: {result['total_tables']}")
        print("-" * 60)
        print("\n完整文本内容:\n")
        print(result["full_text"])

        # 保存为 JSON
        output_json = pdf_path.parent / f"{pdf_path.stem}_extracted.json"
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print("\n" + "-" * 60)
        print(f"✅ 提取结果已保存到: {output_json}")

    except FileNotFoundError as e:
        logger.error(f"文件不存在: {e}")
        print(f"❌ 错误: {e}")
        sys.exit(1)
    except PDFValidationError as e:
        logger.error(f"PDF 验证失败: {e}")
        print(f"❌ 验证失败: {e}")
        sys.exit(1)
    except PDFExtractionError as e:
        logger.error(f"PDF 提取失败: {e}")
        print(f"❌ 提取失败: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"未预期错误: {e}", exc_info=True)
        print(f"❌ 未预期错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
