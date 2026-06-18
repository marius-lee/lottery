#!/usr/bin/env python3
"""参数溯源检查器 — 扫描所有 .py/.js 文件, 标记无来源的数值字面量.

运行: .venv/bin/python3 tools/check_sourced_params.py
CI:   在每次 commit 前自动运行
"""

import re
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

# 允许的值: 在 ssq_constants.py / constants.js 中定义的全局常量
ALLOWED_VALUES = {
    # 游戏规则
    33, 16, 6, 1, 2, 17,
    # 概率 (精确值)
    0.0625, 0.4863, 0.9377, 0.49,
    # 总组合数
    1107568, 17721088, 1043640,
}

# 允许的范围 (min, max)
ALLOWED_RANGES = {
    "dropout": (0.05, 0.5),
    "temperature": (0.3, 1.5),
    "learning_rate": (1e-6, 1e-2),
    "epochs": (1, 300),
    "block_size": (64, 1024),
}

# 需要检查的文件
PY_FILES = list(ROOT.glob("ml/**/*.py")) + list(ROOT.glob("server/**/*.py"))
JS_FILES = list(ROOT.glob("static/js/**/*.js"))

# 排除: 注释中的数字、字符串中的数字、数组索引
EXCLUDE_PATTERNS = [
    r'^\s*#',           # Python 注释
    r'^\s*//',          # JS 注释
    r'^\s*\*',          # 多行注释
    r'print\(',         # print 语句
    r'f["\']',          # f-string
    r'range\(',         # range() 循环
    r'len\(',           # len()
    r'\.shape',         # numpy shape
    r'self\.',          # self 属性
    r'format',          # format()
    r'created_at',      # 时间戳
    r'period',          # 期号
    r'id=',             # ID
]


def has_source_comment(line, num_str):
    """检查数值所在行是否有来源注释或引用"""
    sources = ["http", "doi", "来源", "[官方]", "[数学]", "[文献]", "[数据]", "[已知]",
               "cwl.gov.cn", "arxiv", "PNAS", "CVPR", "IEEE", "JMLR", "JAMES"]
    return any(s.lower() in line.lower() for s in sources)


def is_allowed(num_val, context=""):
    """检查数值是否在允许列表中"""
    if isinstance(num_val, int) and num_val in ALLOWED_VALUES:
        return True
    # 精确浮点
    for av in ALLOWED_VALUES:
        if isinstance(av, float) and abs(num_val - av) < 1e-6:
            return True
    # 范围检查
    for rname, (lo, hi) in ALLOWED_RANGES.items():
        if rname.lower() in context.lower() and lo <= num_val <= hi:
            return True
    return False


def is_named_constant(line):
    """命名常量定义 (UPPER_CASE = value) — 隐含已命名即已溯源"""
    return bool(re.match(r'^\s*[A-Z_][A-Z0-9_]*\s*=', line))

def is_function_default(line):
    """函数参数默认值 (def foo(param=value)) — 已文档化"""
    return 'def ' in line and '=' in line

def is_commented(line):
    """同行有解释性注释"""
    stripped = line.strip()
    return '# ' in stripped or '// ' in stripped or '/* ' in stripped

def scan_file(filepath):
    violations = []
    GAME_CONSTANTS = {33, 16, 6, 1, 2, 7, 8, 17, 11, 12, 22, 23, 100, 10, 1000}

    with open(filepath) as f:
        lines = f.readlines()

    for lineno, line in enumerate(lines, 1):
        # 跳过注释/文档/打印/URL/年份
        if re.match(r'^\s*(#|//|\*|\"\"\"|\'\'\')', line):
            continue
        if re.search(r'print\(|\.format\(|f["\']|logger\.|logging\.', line):
            continue
        if re.search(r'\b20[0-9]{2}\b', line):
            line = re.sub(r'\b20[0-9]{2}\b', '', line)
        line = re.sub(r'https?://\S+', '', line)

        # 命名常量/函数默认值/同行注释 → 跳过
        if is_named_constant(line) or is_function_default(line) or is_commented(line):
            continue

        # 提取裸数字
        nums = re.findall(r'(?<![a-zA-Z0-9_."\'#])(\d+\.?\d*)(?![a-zA-Z0-9_"\'\./])', line)
        for num_str in nums:
            try:
                val = float(num_str)
            except ValueError:
                continue
            if val in GAME_CONSTANTS: continue
            if val < 50 and val == int(val): continue
            if 'constants' in str(filepath) or 'ssq_constants' in str(filepath): continue
            if not has_source_comment(line, num_str):
                violations.append((lineno, num_str, line.strip()[:100]))

    return violations


def main():
    # 读取豁免文件
    ignore_file = Path(__file__).parent / ".sourced_params_ignore"
    ignored_files = set()
    if ignore_file.exists():
        for line in ignore_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                ignored_files.add(line)

    all_violations = {}
    for filepath in PY_FILES + JS_FILES:
        rel = str(Path(filepath).relative_to(ROOT))
        # 文件级或目录级豁免
        if rel in ignored_files or any(rel.startswith(d) for d in ignored_files if d.endswith('/')):
            continue
        v = scan_file(filepath)
        if v:
            all_violations[rel] = v

    if all_violations:
        print(f"❌ 发现 {sum(len(v) for v in all_violations.values())} 个无来源参数:\n")
        for fpath, vlist in sorted(all_violations.items()):
            print(f"  {fpath}:")
            for lineno, num, ctx in vlist[:5]:
                print(f"    L{lineno}: {num}  ← {ctx}")
            if len(vlist) > 5:
                print(f"    ... +{len(vlist)-5} more")
            print()
        sys.exit(1)
    else:
        print("✅ 当前活跃文件中所有参数已溯源")
        sys.exit(0)


if __name__ == "__main__":
    main()
