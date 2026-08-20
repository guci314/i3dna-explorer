#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_login — 树原生登录规格面测试（ARCHITECTURE §5 主体）。

裁决：登录主体=人员档案袋（员工编号.md + 凭证.md，pbkdf2 盐化哈希，
/etc/shadow 同款——树上无明文、无 login.db）；登录日志经引擎 login
子命令入账（不变式2：业务写经引擎）。
机械契约（零 LLM）：
1) core：set/verify 往返、错口令拒、无凭证袋拒；find_principal 编号/姓名双寻址
2) LoginDialog：对象名驱动填表，对则 accept 带回主体，错则留框
3) 会话主体贯穿：_executor_args 署名绿任务办结；助手 prompt 注入主体行
"""
import os

import pytest


def _mk(parent, rel, text=""):
    p = os.path.join(parent, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


@pytest.fixture
def tree(tmp_path):
    r = str(tmp_path)
    _mk(r, "实例/人员/刘亦菲/员工编号.md", "E0001")
    _mk(r, "实例/人员/刘亦菲/户口.md", "北京")
    _mk(r, "实例/人员/无凭证者/户口.md", "上海")
    import i3dna_core as core
    core.set_credential(os.path.join(r, "实例/人员/刘亦菲"), "demo1234")
    return r


@pytest.mark.unit
def test_credential_roundtrip(tree):
    import i3dna_core as core
    bag = os.path.join(tree, "实例/人员/刘亦菲")
    v = open(os.path.join(bag, "凭证.md"), encoding="utf-8").read()
    assert v.startswith("pbkdf2_sha256$") and "demo1234" not in v  # 无明文
    assert core.verify_credential(bag, "demo1234")
    assert not core.verify_credential(bag, "wrong")
    assert not core.verify_credential(
        os.path.join(tree, "实例/人员/无凭证者"), "x")


@pytest.mark.unit
def test_find_principal(tree):
    import i3dna_core as core
    by_id = core.find_principal(tree, "E0001")
    assert by_id and by_id["姓名"] == "刘亦菲"
    assert by_id["主体值"] == "实例/人员/刘亦菲"
    assert core.find_principal(tree, "刘亦菲")["编号"] == "E0001"
    assert core.find_principal(tree, "E9999") is None


@pytest.mark.unit
def test_login_dialog(tree, qapp):
    import importlib
    ex = importlib.import_module("i3dna_explorer")
    d = ex.LoginDialog(tree)
    d.ed_principal.setText("E0001")
    d.ed_pass.setText("demo1234")
    caps = []
    d._log = lambda status: caps.append(status)          # 桩引擎日志
    d._try()
    assert d.principal and d.principal["姓名"] == "刘亦菲"
    assert caps == ["登录成功"]
    d2 = ex.LoginDialog(tree)
    d2.ed_principal.setText("刘亦菲")
    d2.ed_pass.setText("bad")
    d2._log = lambda s: caps.append(s)
    d2._try()
    assert "口令不符" in d2.lbl_msg.text()
    assert caps[-1] == "密码错误"


@pytest.mark.unit
def test_principal_threads_executor_and_prompt(tree, qapp):
    import importlib
    ex = importlib.import_module("i3dna_explorer")
    w = ex.Explorer(tree)
    w._assist_proc_run = lambda p: None      # 桩 LLM 车道
    w._engine_qproc = lambda args, msg, verb=None: None   # 桩引擎
    # 本树有 刘亦菲 档案——启动默认已登录（8-20）；测「未登录不署名」先注销
    assert w._principal and w._principal["姓名"] == "刘亦菲", "默认主体"
    w._set_principal(None)
    assert w._executor_args() == []                      # 未登录不署名
    w._set_principal({"编号": "E0001", "姓名": "刘亦菲",
                      "袋": os.path.join(tree, "实例/人员/刘亦菲"),
                      "主体值": "实例/人员/刘亦菲"})
    assert w._executor_args() == ["--executor", "实例/人员/刘亦菲"]
    # 助手 prompt 注入主体行（实例化人不再问）
    got = {}
    w._assist_proc_run = lambda p: got.update(prompt=p)
    w._edit_path = os.path.join(tree, "实例/人员/刘亦菲/户口.md")
    w._assist_log = []
    w.assist_input.setText("你好")
    w.assist_talk()
    assert "[会话主体]" in got["prompt"]
    assert "实例/人员/刘亦菲" in got["prompt"]
    assert "不要再向用户询问" in got["prompt"]
    w.close()
