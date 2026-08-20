# -*- coding: utf-8 -*-
"""frontmatter 宽容回退（8-20 真用例「加撤域」）：LLM 起草常见「键:值」
无空格形——YAML 视整块为纯标量，frontmatter 静默蒸发（取值全 None）。
回退只兜 YAML 读不出映射的场；合法 YAML（含列表/嵌套）原路不动。"""
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "kv_t", os.path.join(os.path.dirname(_HERE), "i3dna_kv.py"))
kv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kv)


def _mk(tmp_path, text):
    p = tmp_path / "a.md"
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_无空格冒号形_回退可读(tmp_path):
    p = _mk(tmp_path, "---\n域:治理域\n类名:女娲\n---\n正文。\n")
    assert kv.get_value(p, "域") == "治理域"
    assert kv.get_value(p, "类名") == "女娲"


def test_合法YAML_不走回退且列表形不坏(tmp_path):
    p = _mk(tmp_path, "---\n键: 值\n列表:\n  - a\n  - b\n---\n正文。\n")
    assert kv.get_value(p, "键") == "值"
    assert kv.get_value(p, "列表") == ["a", "b"]


def test_纯正文无frontmatter_仍无键(tmp_path):
    p = _mk(tmp_path, "# 标题\n\n散文正文。\n")
    assert kv.get_value(p, "域") is None


def test_混合形_回退值与YAML读法同值(tmp_path):
    """F4（工单108）：一行有空格一行无的混合形把 YAML 炸掉→走回退；回退
    须剥前导空格与成对引号——两种读法不得对同一文件读出不同值。"""
    p = _mk(tmp_path, "---\n域: 治理域\n类名:女娲\n名字: \"刘亦菲\"\n---\n正文。\n")
    assert kv.get_value(p, "域") == "治理域"    # 有空格行
    assert kv.get_value(p, "类名") == "女娲"    # 无空格行（剥前导空格后同值）
    assert kv.get_value(p, "名字") == "刘亦菲"  # 带引号行（剥成对引号后同值）
