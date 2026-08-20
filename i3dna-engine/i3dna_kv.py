#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""i3dna_kv —— M2 取值运行时：结构化自然语言文档的键访问器。

一个访问器，多种底物，三种键位。调用方不必知道值住在文件的哪里：

  · frontmatter    ---↵key: value↵---      YAML 块
  · 行内字段        key:: value             **双冒号**（Dataview 式）——单冒号在
                                           散文里满地都是，双冒号才无歧义
  · 段落标题        ## key ＋其下 `- 条目`   wiki 式：标题即键，条目即列表值

值带类型：整数 / 小数 / 列表 / 字符串。**取不到一律 None，绝不返回空串冒充取到**
——静默失效是停机保证的头号杀手（判据取不到值时必须 fail-closed 且说得出原因）。
键名归一：大小写、空格/下划线/连字符互通，`retry_number` 与 `Retry Number` 同键。
围栏代码块内不扫字段（Dataview 同款）——测试输出里的 `::` 不该变成键。

M2 契约：任何 harness 要跑 i3dna 树，都得提供这个访问器。它是「key 是 schema、
是多方共识」这句话的**可执行形式**。引擎与树里的符号任务共用本模块，谁也别再
自己搓正则——读写同源，共识才不会因为两边各写各的而悄悄漂移。

（键名本身属 M1：本模块认识「文档有可寻址的键」，永远不认识任何具体的键。）
"""
import json
import os
import re

__all__ = ["get_value", "get_list", "set_value", "render", "norm_key"]

_FENCE = re.compile(r"^```.*?^```", re.M | re.S)
_INLINE = re.compile(r"^[ \t]*([^\s:#][^:\n]*?)[ \t]*::[ \t]*(.*?)[ \t]*$", re.M)
_HEADING = re.compile(r"^#{1,6}[ \t]+(.+?)[ \t]*$\n((?:(?!^#).*\n?)*)", re.M)
_ITEM = re.compile(r"^[ \t]*[-*][ \t]+(.+?)[ \t]*$", re.M)
_FM = re.compile(r"^---[ \t]*\n(.*?)\n---[ \t]*\n?", re.S)


def norm_key(k):
    """键名归一：小写、空格/连字符→下划线、去首尾。Dataview 的 canonical form。"""
    return re.sub(r"[\s\-]+", "_", str(k).strip()).lower()


def _coerce(v):
    """标量定型。列表原样传递；纯数字串变数字；其余保持字符串。
    刻意**不**按逗号切分——散文里的逗号切出来的是垃圾不是列表。"""
    if v is None or isinstance(v, (list, tuple, int, float, bool, dict)):
        return list(v) if isinstance(v, tuple) else v
    s = str(v).strip()
    if re.fullmatch(r"[+-]?\d+", s):
        return int(s)
    if re.fullmatch(r"[+-]?(\d+\.\d*|\.\d+)", s):
        return float(s)
    return s


def _put(fields, k, v):
    """同键重复出现即累积成列表（Dataview 的 inline field 语义）。"""
    k = norm_key(k)
    if k not in fields:
        fields[k] = _coerce(v)
        return
    cur = fields[k]
    fields[k] = (cur if isinstance(cur, list) else [cur]) + [_coerce(v)]


def _md_fields(text):
    fm, fields = {}, {}
    body, m = text, _FM.match(text)
    if m:
        body = text[m.end():]
        try:
            import yaml
            y = yaml.safe_load(m.group(1)) or {}
            if not isinstance(y, dict):
                raise ValueError("frontmatter 不是映射")
            for k, v in y.items():
                _put(fm, k, v)
        except Exception:
            # 宽容回退（8-20 真用例「加撤域」）：LLM 起草常见「键:值」无
            # 空格形——YAML 视整块为纯标量，frontmatter 静默蒸发（get_value
            # 全 None，拒因难解）。YAML 没读出映射时逐行按首冒号切兜底；
            # 合法 YAML 不走此路（含列表/嵌套形照旧归 YAML 管）。
            for ln in m.group(1).splitlines():
                if ":" not in ln or ln[0] in "#-*- \t":
                    continue
                k, _, v = ln.partition(":")
                v = v.strip()          # 与 YAML 读法对齐（工单108 F4）：
                if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                    v = v[1:-1]        # 剥前导空格与成对引号——两种读法
                if k.strip():          # 不得对同一文件读出不同值
                    _put(fm, k, v)
    # 行内字段扫描要避开围栏（测试输出里的 `::` 不该变成键）；
    # 段落标题扫描用原文——否则以代码块为值的键（如「测试输出」）会被掏空。
    for k, v in _INLINE.findall(_FENCE.sub("", body)):
        _put(fields, k, v)
    for head, block in _HEADING.findall(body):
        items = _ITEM.findall(block)
        if items:
            _put(fields, head, items)
        elif block.strip():
            _put(fields, head, block.strip())      # 无条目则整段散文即值
    # 机器面优先：同键在 frontmatter 与正文两面都出现时，frontmatter 赢——
    # 否则正文一个 `## 结论` 标题就把契约键污染成两项列表（拒单实测撞的车）。
    # 空键（`键:`→None,工单存根常态）不遮蔽——机器面没写值就让正文值
    # 透出（8-11 评审 #8）。正文内部的同键累积（Dataview 语义）保持不变。
    fields.update({k: v for k, v in fm.items() if v is not None})
    return fields


def _xlsx_fields(path):
    import openpyxl
    fields = {}
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        for ws in wb.worksheets:
            rows = ws.iter_rows(values_only=True)
            heads = next(rows, None)
            if not heads:
                continue
            first = next(rows, None)
            if not first:
                continue
            for h, c in zip(heads, first):
                if h is not None and c is not None:
                    _put(fields, h, c)
    finally:
        wb.close()
    return fields


def _fields(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return {norm_key(k): _coerce(v) for k, v in (data or {}).items()} \
            if isinstance(data, dict) else {}
    if ext == ".xlsx":
        return _xlsx_fields(path)
    with open(path, encoding="utf-8", errors="replace") as f:
        return _md_fields(f.read())


def get_value(path, key):
    """取值。键不存在 / 文件不存在 / 文件读不动 → None（绝不返回 ""）。"""
    if not path or not os.path.isfile(path):
        return None
    try:
        return _fields(path).get(norm_key(key))
    except Exception:
        return None


def get_list(path, key):
    """取列表值。标量自动裹成单元素列表；键不存在仍是 None（≠ 空列表）。"""
    v = get_value(path, key)
    if v is None:
        return None
    return v if isinstance(v, list) else [v]


def _yaml_scalar(v):
    """值 → 安全的单行 YAML 标量。数字/布尔原样；字符串遇 YAML 危险字符
    （冒号空格、#、引号、换行、首尾空白、流记号）转 JSON 字符串
    （JSON 是 YAML 合法子集）——裸写会把整块 frontmatter 写成非法 YAML，
    读侧 except:pass 让全部机器键静默蒸发（8-11 评审 #0）。"""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if s == "" or s != s.strip() \
            or any(c in s for c in "\n\"'#{}[]&*!|>%@`") \
            or ": " in s or s.endswith(":") or s.startswith(("- ", "? ")):
        return json.dumps(s, ensure_ascii=False)
    return s


def set_value(path, key, value):
    """定点更新一个键（getKey/setKey 原语对的写半边）。
    json：顶层键就地改，文件不存在则新建，**存在但坏/非字典＝响亮失败**
    （定点笔的承诺是只动一个键——静默重建等于碾掉全部他键，8-11 评审 #1）；
    md：frontmatter 键就地改（按 norm_key 等价匹配既有拼写变体、保留原行
    拼写——set/get 不对称会攒出同键列表，评审 #7；值经函数替换不当正则
    模板），无 frontmatter 则补一块，正文一字不动。与 get_value 互逆。"""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        data = {}
        if os.path.isfile(path) and os.path.getsize(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)          # 坏 json → 异常上抛，绝不静默重建
            if not isinstance(data, dict):
                raise ValueError(f"{path} 顶层不是字典，定点笔拒写（防碾他键）")
        hit = next((k for k in data if norm_key(k) == norm_key(key)), key)
        data[hit] = value
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        return
    text = open(path, encoding="utf-8", errors="replace").read() \
        if os.path.isfile(path) else ""
    val = _yaml_scalar(value)
    m = _FM.match(text)
    if m:
        fm, body = m.group(1), text[m.end():]
        lines, done = [], False
        for line in fm.split("\n"):
            lm = re.match(r"^(\S[^:]*?)[ \t]*:", line)
            if not done and lm and norm_key(lm.group(1)) == norm_key(key):
                lines.append(f"{lm.group(1)}: {val}")
                done = True
            else:
                lines.append(line)
        if not done:
            lines.append(f"{key}: {val}")
        text = "---\n" + "\n".join(lines).strip("\n") + "\n---\n" + body
    else:
        text = f"---\n{key}: {val}\n---\n" + text
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def render(fields, *blocks, intro=""):
    """渲染结构化自然语言文档，与 get_value **严格互逆**：
    fields → frontmatter（key 侧，机器读）；intro/blocks → 正文（value 侧，人与 agent 读）；
    列表值渲染成 `- 条目`，读回来还是列表。

    集合按序渲染——顺序不定会让同样的内容产出不同的 sha，
    在 sha 账驱动的图里等于凭空催火。
    """
    out = ["---"]
    for k, v in fields.items():
        out.append(f"{k}: {v}")
    out += ["---", ""]
    if intro:
        out += [intro.strip(), ""]
    for head, val in blocks:
        out.append(f"## {head}")
        out.append("")
        if isinstance(val, (set, frozenset)):
            out += [f"- {x}" for x in sorted(val)]
        elif isinstance(val, (list, tuple)):
            out += [f"- {x}" for x in val]
        else:
            out.append(str(val))
        out.append("")
    return "\n".join(out).rstrip() + "\n"


if __name__ == "__main__":                      # 命令行定点笔：蓝任务车道的
    import sys as _sys                          # function call——agent 用 shell
    _a = _sys.argv[1:]                          # 调它，只动一个键，不碰整文件
    if len(_a) >= 3 and _a[0] == "get":
        _v = get_value(_a[1], _a[2])
        print("" if _v is None else _v)
        _sys.exit(0 if _v is not None else 1)
    if len(_a) >= 4 and _a[0] == "set":
        if len(_a) > 4:
            _sys.exit("值被 shell 切成多段——含空格的值请加引号（拒绝静默截断）")
        set_value(_a[1], _a[2], _coerce(_a[3]))
        print(f"{_a[2]} = {_coerce(_a[3])!r}")
        _sys.exit(0)
    print("用法: i3dna_kv.py get <文件> <键> | set <文件> <键> <值>")
    _sys.exit(2)
