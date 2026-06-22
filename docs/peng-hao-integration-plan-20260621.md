# PDF阅读器工具 — 封装OCR流水线为可复用CLI

## Context
将彭浩PDF分析过程中的OCR流水线封装为可复用工具。放在独立 `pdfread/` 文件夹中，自包含，可独立复用。

## 方案：`pdfread/` 文件夹

```
pdfread/
  pdf_reader.py      # CLI工具 (~120行)
  SKILL.md           # Claude Code skill 定义 (~30行)
```

### 核心逻辑
1. 先 pdftotext 快速提取 → 有效文本直接输出
2. 扫描版PDF(无文本) → pdf2image + tesseract chi_sim 并行OCR
3. 输出到 `{pdf_basename}_ocr.txt` 或指定路径

### 调用方式
```bash
python3 pdfread/pdf_reader.py <pdf_path> [--pages 1-50] [--output out.txt] [--dpi 200]
```

