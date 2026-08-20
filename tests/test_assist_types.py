#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_assist_types — 助手诱导的类型文件查找链（规格面,零 LLM）。

契约:core.find_type_file 两条链,先显式后家族——
1) 弧声明「类型: T」→ 类根/T.md → 根/T.md（dict 弧）
2) 引擎 _type_file 同款家族链:类根/状态/<槽名>.md → 根/状态/…
   → 类根/消息/<槽名>.md → 根/消息/…（纯路径弧的知识住址）。
纯路径弧先前查不到任何类型文件(返回 None)是缺陷:树上明明有
类根/状态/需求.md 档案说明,助手却当没有,掉进常识模式。"""
import os

import pytest

import i3dna_core as core


def _mk(parent, rel, text=""):
    p = os.path.join(parent, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


@pytest.fixture
def tree(tmp_path):
    """最小树:研发类两条方法——纯路径弧(走家族链)+ dict 弧(走显式类型链)。"""
    r = str(tmp_path)
    _mk(r, "类/研发/方法/开发/任务.md", """---
i3dna: 微任务
输入:
  - "{实例}/需求/需求.md"
产物:
  - "{实例}/代码/核心.py"
---
开发。
""")
    _mk(r, "类/研发/方法/变更/任务.md", """---
i3dna: 微任务
输入:
  - 路径: "{实例}/需求/澄清单.md"
    类型: 需求澄清单
产物: []
---
变更。
""")

    _mk(r, "类/研发/状态/需求.md", "---\n定型: 实例化人\n---\n# 状态类型:需求\n档案说明。\n")
    _mk(r, "类/研发/消息/澄清单.md", "---\n键: [clarify_round]\n---\n# 消息类型:澄清单\n")
    _mk(r, "需求澄清单.md", "根级显式类型文件。")
    return r


@pytest.mark.unit
def test_family_chain_state(tree):
    """纯路径弧 → 类根/状态/<槽名去扩展>.md（引擎同款家族链）。"""
    tdir = os.path.join(tree, "类/研发/方法/开发")
    tf = core.find_type_file(tree, tdir, "需求.md")
    assert tf and tf.endswith(os.path.join("类", "研发", "状态", "需求.md"))


@pytest.mark.unit
def test_family_chain_message(tree):
    """纯路径弧 → 家族链依次查 状态 后查 消息。"""
    tdir = os.path.join(tree, "类/研发/方法/开发")
    tf = core.find_type_file(tree, tdir, "返工单.md")   # 无状态命中→消息也无→None
    assert tf is None
    _mk(tree, "类/研发/消息/返工单.md", "返工单说明")
    tf = core.find_type_file(tree, tdir, "返工单.md")
    assert tf and tf.endswith(os.path.join("消息", "返工单.md"))


@pytest.mark.unit
def test_explicit_type_arc_first(tree):
    """dict 弧声明的「类型:」优先于家族链（trade-v4 风格）。"""
    tdir = os.path.join(tree, "类/研发/方法/变更")
    tf = core.find_type_file(tree, tdir, "澄清单.md")
    assert tf and tf.endswith("需求澄清单.md"), "显式类型链应命中根级 需求澄清单.md"


@pytest.mark.unit
def test_no_knowledge_returns_none(tree):
    """树上无任何类型知识 → None（调用方落常识/自由编辑模式）。"""
    tdir = os.path.join(tree, "类/研发/方法/开发")
    assert core.find_type_file(tree, tdir, "不存在槽.md") is None


@pytest.mark.unit
def test_slot_json_maps_to_state_md(tree):
    """状态.json → 家族链查 状态/状态.md（引擎 _type_file 同名映射）。"""
    tdir = os.path.join(tree, "类/研发/方法/开发")
    _mk(tree, "类/研发/状态/状态.md", "---\n属主: {}\n---\n")
    tf = core.find_type_file(tree, tdir, "状态.json")
    assert tf and tf.endswith(os.path.join("状态", "状态.md"))


@pytest.mark.unit
def test_green_work_for(tmp_path):
    """绿任务单据 → 通用工单改道判据:实例文件+输入弧 case 代入+绿任务。
    澄清单喂绿任务「澄清需求」→改道;需求.md 喂蓝任务「开发」→不改道;
    非实例路径(类级文件)→不改道。"""
    r = str(tmp_path)
    _mk(r, "类/研发/方法/澄清需求/任务.md", """---
i3dna: 微任务
执行者: 人
输入:
  - "{实例}/需求/澄清单.md"
产物:
  - "{实例}/需求/需求.md"
  - 路径: "{实例}/需求/澄清单.md"
    可缺: 真
---
人工澄清。
""")
    _mk(r, "类/研发/方法/开发/任务.md", """---
i3dna: 微任务
输入:
  - "{实例}/需求/需求.md"
产物:
  - "{实例}/代码/核心.py"
---
开发。
""")
    _mk(r, "实例/研发/c1/需求/澄清单.md", "问: 目标?")
    _mk(r, "实例/研发/c1/需求/需求.md", "需求正文")
    tdir, case = core.green_work_for(
        r, os.path.join(r, "实例/研发/c1/需求/澄清单.md"))
    assert case == "c1" and tdir.endswith("澄清需求")
    assert core.green_work_for(
        r, os.path.join(r, "实例/研发/c1/需求/需求.md")) is None, \
        "蓝任务输入不改道"
    assert core.green_work_for(
        r, os.path.join(r, "类/研发/方法/开发/任务.md")) is None, \
        "非实例路径不改道"


# ── 助手静默防线（8-19 修订：基础给足 16K＋关思考兜底重试） ──────────

@pytest.mark.unit
def test_助手静默_关思考重试(monkeypatch):
    """首跑思考吃光预算（空文本+max_tokens）→ 重试级必须关思考
    （思考关了吃不掉预算，正文必然有字节）。零网络：urlopen 打桩。"""
    import json as _json
    import types as _types
    calls = []

    class _Resp:
        def __init__(self, obj):
            self._b = _json.dumps(obj).encode()

        def read(self):
            return self._b

        def __iter__(self):
            return iter([])

    def fake_urlopen(req, timeout=None):
        payload = _json.loads(req.data.decode())
        calls.append(payload)
        if len(calls) == 1:      # 病态沉思：只有 thinking 块，text 零字节
            return _Resp({"content": [{"type": "thinking",
                                       "thinking": "…想个没完"}],
                          "stop_reason": "max_tokens"})
        return _Resp({"content": [{"type": "text", "text": "【写好】Hello 类"}],
                      "stop_reason": "end_turn"})

    monkeypatch.setattr(core.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(
        "subprocess.run",
        lambda *a, **k: _types.SimpleNamespace(stdout="stub-key\n"))
    text = core.assist_llm("替申请起草类.md", on_delta=None)
    assert text.startswith("【写好】")
    assert len(calls) == 2
    assert calls[0]["max_tokens"] == 16000
    assert calls[0]["thinking"]["type"] == "enabled"
    assert calls[1]["thinking"]["type"] == "disabled", "重试级必须关思考"
