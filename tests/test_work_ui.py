#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_work_ui — 通用界面（聊天收参+编辑器+唯一确认按钮）规格面测试。

架构裁决:通用界面是人类和系统交互的通用通道,领域无关——澄清单/录入
产品/写审批意见同一条面。人自然语言说意图,agent 翻译成领域文件,人只按
一个确认按钮。HumanWorkForm 对话框已退役。
机械契约(零 LLM):
1) open_work_ui: 编辑器落首个必产(作业面),确认钮现身,工单绑定
   (销单靶=在场可缺消息产物,依据=实例侧在场输入弧全文)
2) confirm_work: 保存交付→销单→backfill 入账,事务后解绑
3) 换文件=脱离工位:解绑+隐藏确认钮
"""
import os

import pytest

import importlib

def _mk(parent, rel, text=""):
    p = os.path.join(parent, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


@pytest.fixture
def win(qapp, tmp_path):
    r = str(tmp_path)
    _mk(r, "类/研发/方法/澄清需求/任务.md", """---
i3dna: 微任务
执行者: 人
输入:
  - "{实例}/需求/澄清单.md"
  - 知识/执行契约.md
产物:
  - "{实例}/需求/需求.md"
  - 路径: "{实例}/需求/澄清单.md"
    描述: 澄清单（办结时人删单=已澄清收回）
    可缺: 真
---
人工澄清:读澄清单问题,答案写进需求。
""")
    _mk(r, "类/研发/消息/澄清单.md", "---\n键: [clarify_round]\n---\n")
    _mk(r, "知识/执行契约.md", "契约")
    _mk(r, "实例/研发/c1/需求/澄清单.md", "问: 目标?")
    _mk(r, "实例/研发/c1/需求/需求.md", "旧需求")
    import importlib
    ex = importlib.import_module("i3dna_explorer")
    w = ex.Explorer(r)
    w._assist_proc_run = lambda p: None      # 桩 LLM 车道
    w._engine_qproc = lambda args, msg, verb=None, hook=None: None   # 桩引擎
    yield w
    w.close()


@pytest.mark.unit
def test_open_binds_work(win, tmp_path):
    r = str(tmp_path)
    win.open_work_ui(r + "/类/研发/方法/澄清需求", "c1")
    assert win._edit_path == os.path.join(r, "实例/研发/c1/需求/需求.md"), \
        "作业面=首个必产"
    assert win.btn_confirm.isHidden() is False
    assert win._work["case"] == "c1"
    assert win._work["tickets"] == \
        [os.path.join(r, "实例/研发/c1/需求/澄清单.md")], "销单靶=在场单据"
    assert "澄清单.md" in win._work["inputs"], "依据=实例侧在场输入弧"
    assert "人工澄清" in win._work["instruction"]


@pytest.mark.unit
def test_confirm_saves_destroys_accounts(win, tmp_path):
    r = str(tmp_path)
    cap = {}
    win._engine_qproc = lambda args, msg, verb=None, hook=None: cap.update(args=args)
    win.open_work_ui(r + "/类/研发/方法/澄清需求", "c1")
    win.editor.setPlainText("# 需求\n答案:x+1\n")
    win.confirm_work()
    deliver = os.path.join(r, "实例/研发/c1/需求/需求.md")
    assert open(deliver, encoding="utf-8").read().startswith("# 需求\n答案"), \
        "确认即保存交付"
    assert not os.path.exists(
        os.path.join(r, "实例/研发/c1/需求/澄清单.md")), "确认=销单收回"
    assert "backfill" in cap["args"] and "c1" in cap["args"], "确认=入账"
    assert win._work is None and win.btn_confirm.isHidden()


@pytest.mark.unit
def test_switch_file_unbinds(win, tmp_path):
    r = str(tmp_path)
    win.open_work_ui(r + "/类/研发/方法/澄清需求", "c1")
    win._open_editor(os.path.join(r, "知识/执行契约.md"))
    assert win._work is None, "换文件=脱离工位"
    assert win.btn_confirm.isHidden()
