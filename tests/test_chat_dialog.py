#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_chat_dialog — 右键对话规格面测试（101号：话语即签字·零会话态）。

契约（docs/右键对话实现规格.md）：
1) 入口只挂过程类实例且须登录（实体实例/类根无口）；
2) 签字=api 写桥真跑，账记 执行者=登录主体＋意图=话语原文；
3) 查询=api_query 白名单代跑，零副作用不入账；
4) 非法动词拒且零副作用；零会话态=会话仅内存，树无新增文件。
机械判据=账 JSON/菜单动作/磁盘清单（97号），LLM 编译车道打桩。"""
import json
import os
import sys

import pytest


def _mk(parent, rel, text=""):
    p = os.path.join(parent, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


TASK = """---
i3dna: 微任务
执行者: 人
输入:
  - "{实例}/申请.md"
产物:
  - "{实例}/出.md"
---
干活。
"""


@pytest.fixture
def tree(tmp_path):
    r = str(tmp_path)
    _mk(r, "域/x域/域.md", "---\ni3dna: 域\n---\n")
    _mk(r, "域/x域/类/甲/类.md", "---\ni3dna: 类\n范畴: 过程\n---\n# 甲\n")
    _mk(r, "域/x域/类/甲/方法/办/任务.md", TASK)
    _mk(r, "域/x域/类/乙/类.md", "---\ni3dna: 类\n范畴: 实体\n---\n# 乙\n")
    _mk(r, "域/治理域/类/目录树元知识/知识/API手艺.md",
        "# API手艺\n读桥六动词用法。\n")     # 手艺门 presence-based
    _mk(r, "实例/甲/c1/申请.md", "---\n键: 值\n---\n申请。\n")
    _mk(r, "实例/乙/e1/乙.md", "实体档案\n")
    return r


def _login(win):
    win._principal = {"编号": "E1", "姓名": "刘亦菲", "袋": "刘亦菲",
                      "主体值": "实例/人员/刘亦菲"}


def _menu_texts(win, rel):
    it = win.items_by_path[os.path.join(win.root, rel)]
    win.tree.setCurrentIndex(it.index())
    m = win.build_dir_menu(it)
    return m, [a.text() for a in m.actions()] if m else []


@pytest.mark.unit
def test_菜单_过程实例登录门(tree, qapp):
    import i3dna_explorer as ex
    w = ex.Explorer(tree)
    w._assist_proc_run = lambda p: None
    _login(w)
    m, acts = _menu_texts(w, "实例/甲/c1")
    assert any(a.objectName() == "act对话" for a in m.actions()), acts
    w._principal = None                     # 未登录无入口（话语=签字的前提）
    m2, _ = _menu_texts(w, "实例/甲/c1")
    assert not any(a.objectName() == "act对话" for a in m2.actions())


@pytest.mark.unit
def test_菜单_实体实例与类根无对话口(tree, qapp):
    import i3dna_explorer as ex
    w = ex.Explorer(tree)
    _login(w)
    m, _ = _menu_texts(w, "实例/乙/e1")     # 实体实例：无菜单（无方法可签）
    assert m is None
    m, acts = _menu_texts(w, "域/x域/类/甲")  # 类根：菜单在但无对话口
    assert m is not None
    assert not any(a.objectName() == "act对话" for a in m.actions()), acts


def _wait_idle(d, qapp, timeout=15.0):
    """等对话链真静定（编译线程/签字链/查询环全收尾）再断言——
    连续 5 次不占线才算（防起步竞态与 done 信号尾投递）。"""
    import time
    t0, stable = time.time(), 0
    while time.time() - t0 < timeout:
        qapp.processEvents()
        th = getattr(d, "_thread", None)
        if th is None or not th.isRunning():
            stable += 1
            if stable >= 5:
                return True
        else:
            stable = 0
        time.sleep(0.02)
    return False


def _open(win, tree, fake_llm):
    win._dialog_llm = fake_llm
    win.open_chat(os.path.join(tree, "域/x域/类/甲"), "c1")
    return win._chat_dlg


@pytest.mark.unit
def test_签字_settle真跑入账(tree, qapp):
    import i3dna_explorer as ex
    w = ex.Explorer(tree)
    _login(w)
    _mk(tree, "实例/甲/c1/出.md", "产物\n")

    def fake(prompt, on_done, speech, on_delta=None):
        on_done(speech, json.dumps(
            {"模式": "签字", "动词序列": [
                {"动词": "settle", "参数": {
                    "任务": "域/x域/类/甲/方法/办", "案卷号": "c1"}}]},
            ensure_ascii=False))
    d = _open(w, tree, fake)
    d.ed.setText("办结这一单")
    d.send()
    assert _wait_idle(d, qapp)
    rec = json.load(open(os.path.join(
        tree, "实例/甲/c1/__账/办/__结果.json"), encoding="utf-8"))
    assert rec["状态"] == "事后追认"
    assert rec["执行者"] == "实例/人员/刘亦菲", "执行者=登录主体"
    assert rec["意图"] == "办结这一单", "意图=话语原文"
    assert "说了「办结这一单」→ settle" in d.log.toPlainText(), "执行后回显"


@pytest.mark.unit
def test_查询_读桥回显零副作用(tree, qapp):
    import i3dna_explorer as ex
    w = ex.Explorer(tree)
    _login(w)
    calls = []

    def fake(prompt, on_done, speech, on_delta=None):
        calls.append(prompt)
        if len(calls) == 1:                 # 首轮：查询 JSON；喂回后：普通回答
            on_done(speech, json.dumps(
                {"模式": "查询", "读桥": [{"动词": "tasks", "参数": {}}]},
                ensure_ascii=False))
        else:
            on_done(speech, "树上有任务，仅此而已。")
    d = _open(w, tree, fake)
    d.ed.setText("查一查树上有啥任务")
    d.send()
    assert _wait_idle(d, qapp)
    log = d.log.toPlainText()
    assert "查" in log and "tasks" in log, "查询结果须回显"
    assert "树上有任务" in log, "喂回后模型作答"
    assert not os.path.exists(os.path.join(tree, "实例/甲/c1/__账")), \
        "查询零副作用不入账"


@pytest.mark.unit
def test_非法动词_拒且零副作用(tree, qapp):
    import i3dna_explorer as ex
    w = ex.Explorer(tree)
    _login(w)

    def fake(prompt, on_done, speech, on_delta=None):
        on_done(speech, json.dumps(
            {"模式": "签字", "动词序列": [
                {"动词": "delete_tree", "参数": {"任务": "x"}}]},
            ensure_ascii=False))
    d = _open(w, tree, fake)
    d.ed.setText("非法动词测试")
    d.send()
    assert _wait_idle(d, qapp)
    assert "不在签字面" in d.log.toPlainText(), "非法动词须响亮拒"
    assert not os.path.exists(os.path.join(tree, "实例/甲/c1/__账")), \
        "拒=零副作用，账未动"


@pytest.mark.unit
def test_零会话态_树无新增文件(tree, qapp):
    import i3dna_explorer as ex
    w = ex.Explorer(tree)
    _login(w)
    _mk(tree, "实例/甲/c1/出.md", "产物\n")

    def fake(prompt, on_done, speech, on_delta=None):
        on_done(speech, "（不动手，只回答）")
    d = _open(w, tree, fake)
    before = {os.path.relpath(os.path.join(r, f), tree)
              for r, _, fs in os.walk(tree) for f in fs}
    d.ed.setText("第一句")
    d.send()
    d.ed.setText("第二句")
    d.send()
    after = {os.path.relpath(os.path.join(r, f), tree)
             for r, _, fs in os.walk(tree) for f in fs}
    assert before == after, "零会话态：纯对话不得落任何文件"


# ── 对抗验收修复钉（8-20 五镜头证伪后补）─────────────────

@pytest.mark.unit
def test_坏信封不崩_拒且零副作用(tree, qapp):
    """模型形状漂移（读桥=dict/顶层=数组）只许拒，不许 qFatal 整窗死。"""
    import i3dna_explorer as ex
    w = ex.Explorer(tree)
    _login(w)
    shapes = ['{"模式": "查询", "读桥": {"动词": "tasks"}}',
              '[{"模式": "签字"}]',
              '{"模式": "签字", "动词序列": {"动词": "fire"}}']
    replies = iter(shapes)

    def fake(prompt, on_done, speech, on_delta=None):
        on_done(speech, next(replies))
    d = _open(w, tree, fake)
    for s in ("第一问", "第二问", "第三问"):
        d.ed.setText(s)
        d.send()
        assert _wait_idle(d, qapp)
    log = d.log.toPlainText()
    assert log.count("编译失败") + log.count("不是数组") >= 2, log[-400:]
    assert not os.path.exists(os.path.join(tree, "实例/甲/c1/__账"))


@pytest.mark.unit
def test_散文引用信封不当真(tree, qapp):
    """『签字格式是 {…} 请照此』是散文不是信封——不得执行。"""
    import i3dna_explorer as ex
    w = ex.Explorer(tree)
    _login(w)

    def fake(prompt, on_done, speech, on_delta=None):
        on_done(speech, '签字格式是 {"模式": "签字", "动词序列": '
                        '[{"动词": "settle", "参数": {}}]} 请照此办理')
    d = _open(w, tree, fake)
    d.ed.setText("介绍一下签字格式")
    d.send()
    assert _wait_idle(d, qapp)
    assert "签字格式是" in d.log.toPlainText(), "散文应按普通回答展示"
    assert not os.path.exists(os.path.join(tree, "实例/甲/c1/__账"))


@pytest.mark.unit
def test_案卷号注入拒(tree, qapp):
    import i3dna_explorer as ex
    w = ex.Explorer(tree)
    _login(w)

    def fake(prompt, on_done, speech, on_delta=None):
        on_done(speech, json.dumps(
            {"模式": "签字", "动词序列": [
                {"动词": "settle", "参数": {
                    "任务": "域/x域/类/甲/方法/办",
                    "案卷号": "../../pwned_case"}}]},
            ensure_ascii=False))
    d = _open(w, tree, fake)
    d.ed.setText("帮我办结")
    d.send()
    assert _wait_idle(d, qapp)
    assert "不干净" in d.log.toPlainText(), "注入形案卷号须拒"
    assert not os.path.exists("/tmp/pwned_case"), "不得写出树外"


@pytest.mark.unit
def test_案卷号缺省机械注入本案卷(tree, qapp):
    """协议承诺「案卷号缺省=本案卷」——缺省须机械化，不得落类级账。"""
    import i3dna_explorer as ex
    w = ex.Explorer(tree)
    _login(w)
    _mk(tree, "实例/甲/c1/出.md", "产物\n")

    def fake(prompt, on_done, speech, on_delta=None):
        on_done(speech, json.dumps(
            {"模式": "签字", "动词序列": [
                {"动词": "settle", "参数": {
                    "任务": "域/x域/类/甲/方法/办"}}]},   # 无案卷号
            ensure_ascii=False))
    d = _open(w, tree, fake)
    d.ed.setText("办结这一单")
    d.send()
    assert _wait_idle(d, qapp)
    p = os.path.join(tree, "实例/甲/c1/__账/办/__结果.json")
    rec = json.load(open(p, encoding="utf-8"))
    assert rec["意图"] == "办结这一单" and rec["执行者"] == "实例/人员/刘亦菲"


@pytest.mark.unit
def test_任务路径带任务md后缀归一(tree, qapp):
    """真模型会照抄闭包文件路径（…/任务.md）当「任务」——归一为方法目录
    （真用例：用户在女娲 bean 说「请创建一个域」被拒的根因）。"""
    import i3dna_explorer as ex
    w = ex.Explorer(tree)
    _login(w)
    _mk(tree, "实例/甲/c1/出.md", "产物\n")

    def fake(prompt, on_done, speech, on_delta=None):
        on_done(speech, json.dumps(
            {"模式": "签字", "动词序列": [
                {"动词": "settle", "参数": {
                    "任务": "域/x域/类/甲/方法/办/任务.md",
                    "案卷号": "c1"}}]},
            ensure_ascii=False))
    d = _open(w, tree, fake)
    d.ed.setText("办结这一单")
    d.send()
    assert _wait_idle(d, qapp)
    p = os.path.join(tree, "实例/甲/c1/__账/办/__结果.json")
    rec = json.load(open(p, encoding="utf-8"))
    assert rec["任务"] == "域/x域/类/甲/方法/办"
    assert rec["意图"] == "办结这一单"
    # 闭包标签不再带 /任务.md 后缀（模型照抄即合法）
    assert "方法/办/任务.md ───" not in d._closure()
    assert "─── 域/x域/类/甲/方法/办 ───" in d._closure()


@pytest.mark.unit
def test_占线门_在途不发(tree, qapp):
    import i3dna_explorer as ex
    w = ex.Explorer(tree)
    _login(w)

    class _Busy:
        def isRunning(self):
            return True
    d = _open(w, tree, lambda p, o, s: None)
    d._thread = _Busy()
    d.ed.setText("第二句")
    d.send()
    assert "编译在途" in d.log.toPlainText(), "在途须挡并发"
    assert d.log.toPlainText().count("我：") == 0, "话语未吞"


@pytest.mark.unit
def test_无手艺卡查询拒(tree, qapp):
    """手艺门 presence-based：无 API手艺.md 卡=快照问答，查询模式拒。"""
    import i3dna_explorer as ex
    w = ex.Explorer(tree)
    _login(w)
    os.remove(os.path.join(tree, "域/治理域/类/目录树元知识",
                           "知识", "API手艺.md"))

    def fake(prompt, on_done, speech, on_delta=None):
        on_done(speech, json.dumps(
            {"模式": "查询", "读桥": [{"动词": "tasks", "参数": {}}]},
            ensure_ascii=False))
    d = _open(w, tree, fake)
    assert not d._can_query
    d.ed.setText("查一查")
    d.send()
    assert "查询模式不可用" in d.log.toPlainText()


# ── omp rpc 持久流式车道（S5 实装 8-20）──────────────────

def _wait_log(d, needle, qapp, timeout=15.0):
    import time
    t0 = time.time()
    while time.time() - t0 < timeout:
        qapp.processEvents()
        if needle in d.log.toPlainText():
            return True
        time.sleep(0.02)
    return False


@pytest.mark.unit
def test_omp_rpc_流式逐帧且持久单进程(tree, qapp, monkeypatch):
    """缺省车道=持久 omp --mode rpc：text_delta 逐帧回显（非整段），
    两轮话语共用同一进程（spawn 一次多轮——翻「omp 子进程已废」案）。"""
    import i3dna_explorer as ex
    fake = os.path.join(os.path.dirname(__file__), "fake_omp_rpc.py")
    monkeypatch.setenv("I3DNA_OMP_RPC_CMD", f"{sys.executable} {fake}")
    w = ex.Explorer(tree)
    _login(w)
    w.open_chat(os.path.join(tree, "域/x域/类/甲"), "c1")
    d = w._chat_dlg
    deltas = []
    _orig = d._stream_delta
    d._stream_delta = lambda t: (deltas.append(t), _orig(t))
    d.ed.setText("你好")
    d.send()
    assert _wait_log(d, "桩 omp", qapp), "流式回答须到达"
    import time as _t
    _t0 = _t.time()
    while d._pending is not None and _t.time() - _t0 < 10:
        qapp.processEvents()
        _t.sleep(0.02)
    assert d._pending is None, "本轮须收尾（prompt_result 终帧）"
    assert len(deltas) >= 5, f"text_delta 须逐帧（实测 {len(deltas)} 帧）"
    assert "流式）" in d.log.toPlainText(), "流式段有标头"
    pid1 = w._omp_rpc._p.pid
    d._stream_delta = lambda t: deltas.append(t)
    d.ed.setText("再来一句")
    d.send()
    assert _wait_log_for_hist(d, qapp), "第二轮须复用同一 omp 进程作答"
    assert w._omp_rpc._p.pid == pid1, "持久进程：两轮不得重 spawn"
    w.close()


def _wait_log_for_hist(d, qapp, timeout=10.0):
    import time
    t0 = time.time()
    while time.time() - t0 < timeout:
        qapp.processEvents()
        if len([h for h in d._hist if "桩 omp" in h[1]]) >= 2:
            return True
        time.sleep(0.02)
    return False


# ── 起草车道（103号 审批入图：柜员的手）──────────────────

BLUE = """---
i3dna: 微任务
执行者: agent
输入:
  - "{实例}/域意.md"
产物:
  - "{实例}/申请.md"
  - "{实例}/域.md"
---
结构手术·起草站（柜员的手）。
"""

AUDIT = """---
i3dna: 微任务
执行者: 人
输入:
  - "{实例}/申请.md"
产物:
  - "域/{申请.域名}/域.md"
---
结构手术·审批站（顾客的签字）。
"""

STUB_ENGINE = """import os, re, sys
prompt = sys.stdin.read()
for p in re.findall(r"【产物→写到】(\\S+)", prompt):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write("---\\n域名: d9\\n域主: 张三\\n职责: 示范\\n---\\n桩起草\\n")
print("完成")
"""


def _stub_engine(tree, qapp, w):
    """写产物桩引擎上工具栏（UI 侧注入——LLM 侧 --engine 等于任意命令执行）。"""
    import sys as _s
    stub = os.path.join(tree, "桩引擎.py")
    open(stub, "w", encoding="utf-8").write(STUB_ENGINE)
    w.cb_engine.addItem("桩", f"{_s.executable} {stub}")
    w.cb_engine.setCurrentIndex(w.cb_engine.count() - 1)


@pytest.mark.unit
def test_起草_蓝站fire入账意图与执行者(tree, qapp):
    """两站前半：draft 落域意 → 蓝站 fire（引擎产申请+域.md 进案卷），
    账记 意图=话语/执行者=站声明 agent——银行模式的柜员的手。"""
    import i3dna_explorer as ex
    w = ex.Explorer(tree)
    _login(w)
    _mk(tree, "域/x域/类/甲/方法/起草/任务.md", BLUE)
    _stub_engine(tree, qapp, w)

    def fake(prompt, on_done, speech, on_delta=None):
        on_done(speech, json.dumps(
            {"模式": "起草", "任务": "域/x域/类/甲/方法/起草",
             "草稿": [{"路径": "域意.md", "内容": "域名: d9 域主: 张三"}]},
            ensure_ascii=False))
    d = _open(w, tree, fake)
    d.ed.setText("立个域 d9")
    d.send()
    assert _wait_idle(d, qapp)
    assert open(os.path.join(tree, "实例/甲/c1/域意.md"),
                encoding="utf-8").read().startswith("域名:"), "域意先落案卷"
    rec = json.load(open(os.path.join(
        tree, "实例/甲/c1/__账/起草/__结果.json"), encoding="utf-8"))
    assert rec["意图"] == "立个域 d9", "fire 账记意图=话语原文"
    assert rec["执行者"] == "agent", "蓝站以站声明执行者署名（本职不叫代）"
    assert "桩引擎" in rec["引擎"], "引擎=车道命令入账"
    assert os.path.isfile(os.path.join(tree, "实例/甲/c1/申请.md")), \
        "引擎产出正式草稿落案卷"
    log = d.log.toPlainText()
    assert "《申请.md》" in log and "请过目" in log, "草稿回显给人过目"


@pytest.mark.unit
def test_批准_draft落位加settle办结入账(tree, qapp):
    """两站后半：[draft 落位(源=案卷草稿), settle 绿站] ——落位零入账、
    办结账记 意图=批准话语/执行者=登录主体（顾客的签字）。"""
    import i3dna_explorer as ex
    w = ex.Explorer(tree)
    _login(w)
    _mk(tree, "域/x域/类/甲/方法/审/任务.md", AUDIT)
    _mk(tree, "实例/甲/c1/申请.md", "---\n域名: d9\n---\n申请。\n")
    _mk(tree, "实例/甲/c1/域.md", "---\n域主: 张三\n职责: 示范\n---\n域草稿\n")

    def fake(prompt, on_done, speech, on_delta=None):
        on_done(speech, json.dumps(
            {"模式": "签字", "动词序列": [
                {"动词": "draft", "参数": {
                    "任务": "域/x域/类/甲/方法/审", "案卷号": "c1",
                    "草稿": [{"路径": "域/d9/域.md", "源": "域.md"}]}},
                {"动词": "settle", "参数": {
                    "任务": "域/x域/类/甲/方法/审", "案卷号": "c1"}}]},
            ensure_ascii=False))
    d = _open(w, tree, fake)
    d.ed.setText("批准")
    d.send()
    assert _wait_idle(d, qapp)
    tp = os.path.join(tree, "域", "d9", "域.md")
    assert open(tp, encoding="utf-8").read().startswith("---\n域主:"), \
        "草稿落位到产物槽（抄录免模型重打全文）"
    rec = json.load(open(os.path.join(
        tree, "实例/甲/c1/__账/审/__结果.json"), encoding="utf-8"))
    assert rec["意图"] == "批准" and rec["执行者"] == "实例/人员/刘亦菲"
    log = d.log.toPlainText()
    assert "settle" in log and "✓" in log, "办结回显与账对照"


@pytest.mark.unit
def test_起草_绿站只落草稿不点火(tree, qapp):
    """绿审批站没资格被代点火：起草模式落草稿即止，等人说批准。"""
    import i3dna_explorer as ex
    w = ex.Explorer(tree)
    _login(w)

    def fake(prompt, on_done, speech, on_delta=None):
        on_done(speech, json.dumps(
            {"模式": "起草", "任务": "域/x域/类/甲/方法/办",
             "草稿": [{"路径": "要点.md", "内容": "要点"}]},
            ensure_ascii=False))
    d = _open(w, tree, fake)
    d.ed.setText("帮我准备材料")
    d.send()
    assert _wait_idle(d, qapp)
    assert os.path.isfile(os.path.join(tree, "实例/甲/c1/要点.md"))
    assert not os.path.exists(os.path.join(tree, "实例/甲/c1/__账")), \
        "绿站不得被点火（引擎守卫的通道面：起草模式干脆不发 fire）"
    assert "点火" not in d.log.toPlainText()


@pytest.mark.unit
def test_起草_案卷材料稿也回显_多行可读(tree, qapp):
    """8-20 用户三报「女娲的回复没有换行」的实体：绿站+案卷材料起草
    零回显——人只能去流式 JSON 团里读 \\n 字面量。材料草稿须照蓝站产物
    一样递出来看，多行正文在日志里逐行可读（toPlainText 有真换行）。"""
    import i3dna_explorer as ex
    w = ex.Explorer(tree)
    _login(w)
    body = "---\n域名: d9\n---\n#申请\n\n第一段。\n\n第二段。\n"

    def fake(prompt, on_done, speech, on_delta=None):
        on_done(speech, json.dumps(
            {"模式": "起草", "任务": "域/x域/类/甲/方法/办",
             "草稿": [{"路径": "申请.md", "内容": body},
                      {"路径": "任务.md", "内容": "任务稿\n"}]},
            ensure_ascii=False))
    d = _open(w, tree, fake)
    d.ed.setText("准备申请")
    d.send()
    assert _wait_idle(d, qapp)
    log = d.log.toPlainText()
    assert "《申请.md》（案卷材料）" in log and "《任务.md》（案卷材料）" in log, \
        "材料草稿照蓝站产物一样递出来"
    assert "第一段。" in log and "第二段。" in log
    assert "#申请\n" in log, "多行正文逐行可读（渲染含真换行，不是挤成一段）"
    assert "请过目" in log


@pytest.mark.unit
def test_起草_树路径非产物槽拒且零副作用(tree, qapp):
    import i3dna_explorer as ex
    w = ex.Explorer(tree)
    _login(w)

    def fake(prompt, on_done, speech, on_delta=None):
        on_done(speech, json.dumps(
            {"模式": "起草", "任务": "域/x域/类/甲/方法/办",
             "草稿": [{"路径": "域/别处/x.md", "内容": "偷写"}]},
            ensure_ascii=False))
    d = _open(w, tree, fake)
    d.ed.setText("往树里塞个文件")
    d.send()
    assert _wait_idle(d, qapp)
    assert not os.path.exists(os.path.join(tree, "域/别处")), "零副作用"
    assert "✗" in d.log.toPlainText(), "拒因须回显"


@pytest.mark.unit
def test_拒后重编_改稿draft不被去重吞(tree, qapp):
    """draft 不进成功去重键：拒后重编的**改稿**必须再落盘（8-20 对抗
    验收：按 (动词,任务,案卷) 去重会把改稿循环卡死在第一版）。"""
    import i3dna_explorer as ex
    w = ex.Explorer(tree)
    _login(w)
    rounds = iter(["第一版", "改好的第二版"])

    def fake(prompt, on_done, speech, on_delta=None):
        on_done(speech, json.dumps(
            {"模式": "签字", "动词序列": [
                {"动词": "draft", "参数": {
                    "任务": "域/x域/类/甲/方法/办", "案卷号": "c1",
                    "草稿": [{"路径": "要点.md",
                              "内容": next(rounds)}]}}]},
            ensure_ascii=False))
    d = _open(w, tree, fake)
    d.ed.setText("先起草")
    d.send()
    assert _wait_idle(d, qapp)
    d.ed.setText("改一下")
    d.send()
    assert _wait_idle(d, qapp)
    got = open(os.path.join(tree, "实例/甲/c1/要点.md"),
               encoding="utf-8").read()
    assert got == "改好的第二版", f"第二次 draft 须真落盘（实测 {got!r}）"
    assert d.log.toPlainText().count("draft") >= 2, "两次执行均须回显"
    assert "零入账" in d.log.toPlainText(), "draft 回显不得谎称已入账"


# ── 启动默认主体（8-20 guci 偏好）：刘亦菲档案在场即默认登录 ──

@pytest.mark.unit
def test_启动默认主体_刘亦菲(tree, qapp):
    import i3dna_explorer as ex
    _mk(tree, "实例/人员/刘亦菲/员工编号.md", "E0001\n")
    w = ex.Explorer(tree)
    assert w._principal and w._principal["姓名"] == "刘亦菲"
    assert w._principal["主体值"] == "实例/人员/刘亦菲"
    assert "刘亦菲" in w.lbl_principal.text(), "工具栏须亮默认主体牌"


@pytest.mark.unit
def test_无人员档案_保持未登录(tree, qapp):
    import i3dna_explorer as ex
    w = ex.Explorer(tree)
    assert w._principal is None, "无档案的树不默认登录（登录框照旧）"
    w.do_login()                     # 注销钮同链可撤下（_set_principal(None) 分支）
    w._set_principal(None)
    assert w._principal is None and "未登录" in w.lbl_principal.text()


# ── 回复换行（8-20 用户实证：QTextBrowser HTML 渲染吞 \n）──

@pytest.mark.unit
def test_回复换行_普通与流式都不折叠(tree, qapp):
    import i3dna_explorer as ex
    w = ex.Explorer(tree)
    _login(w)
    d = _open(w, tree, lambda p, o, s, on_delta=None: None)
    d._say("对话", "第一行\n\n第二行")
    assert "第一行\n\n第二行" in d.log.toPlainText(), \
        "多行回复须保留空行（<br> 不是空白折叠）"
    d._stream_open = False
    d._stream_delta("流式甲\n")
    d._stream_delta("流式乙")
    assert "流式甲\n流式乙" in d.log.toPlainText(), "流式帧内换行须成段"


@pytest.mark.unit
def test_协议含树面先查后断规则(tree):
    """真用例教训（8-20「删除域」）：模型凭闭包缺席断言「树上没有
    sample_domain」——实际已入树入账（闭包不含 域/树面与 __账）。
    协议须钉死：树面现状断言先读桥查询，缺席≠没有。"""
    import i3dna_explorer as ex
    proto = ex.CHAT_PROTO
    assert "树面现状先查后断" in proto, "硬规则在场"
    assert "缺席≠树上没有" in proto, "缺席推断禁令在场"
    assert "闭包看不到" in proto, "无手艺卡时的诚实降级话术在场"
