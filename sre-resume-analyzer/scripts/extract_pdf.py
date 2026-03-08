#!/usr/bin/env python3
"""使用 pdfplumber 提取 PDF 简历文本"""

import sys
import json
import pdfplumber
from pathlib import Path

def extract_pdf(pdf_path):
    """提取 PDF 文本和表格"""
    result = {
        "file": str(pdf_path),
        "extraction_method": "pdfplumber",
        "pages": [],
        "full_text": "",
        "tables": []
    }

    with pdfplumber.open(pdf_path) as pdf:
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

    result["total_pages"] = len(result["pages"])
    result["total_char_count"] = len(result["full_text"])
    result["total_tables"] = len(result["tables"])

    return result

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 extract_pdf.py <pdf_path>")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])

    if not pdf_path.exists():
        print(f"Error: File not found: {pdf_path}")
        sys.exit(1)

    print(f"正在提取 PDF: {pdf_path.name}")
    print("-" * 60)

    result = extract_pdf(pdf_path)

    # 打印摘要
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

if __name__ == "__main__":
    main()
