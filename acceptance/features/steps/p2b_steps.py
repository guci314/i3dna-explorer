# -*- coding: utf-8 -*-
"""P2b step 定义——副作用与外部调用组,对象名驱动+边界打桩。

判据=断言(树/账/磁盘/执行流/聊天),证据=widget.grab() 落盘 PNG。
外部调用(LLM)全部在边界替换为确定性桩:引擎→cb_engine 注入桩脚本,
聊天→I3DNA_CHAT_CMD 桩脚本,代笔→PATH 桩 omp——桩只替 LLM 一环,
引擎的暂存-验收-落位/账本/执行流管线全部真跑。
"""
import os
import sys
import time

from behave import given, when, then   # noqa: F401
from PyQt6.QtCore import QProcess, QTimer
from PyQt6.QtWidgets import (QAbstractButton, QApplication, QInputDialog,
                             QMessageBox)

import i3dna_core as core
import i3dna_explorer as ex
from environment import FAKES, REPO
from explorer_steps import _find_item, _pump, _win

eng = core.eng


def _app():
    return QApplication.instance()


def _task_dir(win, name):
    for t in win.tasks:
        if os.path.basename(t) == name:
            return t
    raise AssertionError(f"无任务 {name}")


def _click_modal(accept):
    """点掉当前模态:输入框 accept/reject;消息盒点 Yes/Save/No/Cancel。"""
    dlg = QApplication.activeModalWidget()
    if dlg is None:
        return
    if isinstance(dlg, QInputDialog):
        (dlg.accept() if accept else dlg.reject())
        return
    if isinstance(dlg, QMessageBox):
        if accept:
            b = dlg.button(QMessageBox.StandardButton.Yes) \
                or dlg.button(QMessageBox.StandardButton.Save) \
                or dlg.button(QMessageBox.StandardButton.Ok) \
                or dlg.defaultButton()
        else:
            b = dlg.button(QMessageBox.StandardButton.No) \
                or dlg.button(QMessageBox.StandardButton.Cancel)
        if b is None:
            dlg.accept()
            return
        b.click()


@when("自动应答弹窗 {mode}")
def step_auto_modals(context, mode):
    timer = QTimer()
    accept = mode == "接受"

    def _tick():
        _click_modal(accept)
    timer.timeout.connect(_tick)
    timer.start(50)
    context._modal_timer = timer
    QTimer.singleShot(30000, timer.stop)


def _stop_modals(context):
    t = getattr(context, "_modal_timer", None)
    if t is not None:
        t.stop()


# ── 任务操作 ──────────────────────────────────────────────
@then("蓝任务菜单无 {label}")
def step_blue_menu_not(context, label):
    win = _win(context)
    menu = win.build_task_menu(win.items_by_path[_task_dir(win, "上市")])
    labels = [x.text() for x in menu.actions()]
    assert not any(x == label or x.startswith(label + " ") for x in labels), \
        f"蓝菜单不应有 {label}(业务动词在实例工位): {labels}"


def _station(root, cname, case, sname):
    import i3dna_core as core
    cands = list(core.class_roots(os.path.join(root, "类"))) \
        + list(core.class_roots(root))
    for cand in cands:
        if os.path.basename(cand) == cname:
            for st in core.instance_stations(root, cand, case):
                if st["name"] == sname:
                    return st
    raise AssertionError(f"工位面板无 {cname}/{case}/{sname}")


@then("工位面板 {cname} 实例 {case} 含 {names}")
def step_station_panel(context, cname, case, names):
    import i3dna_core as core
    got = {s["name"] for s in core.instance_stations(
        context.tree_root, _station_root(context, cname), case)}
    for n in names.split(" "):
        assert n in got, f"{cname}/{case} 工位缺 {n}: {sorted(got)}"


def _station_root(context, cname):
    import i3dna_core as core
    cands = list(core.class_roots(os.path.join(context.tree_root, "类"))) \
        + list(core.class_roots(context.tree_root))
    for cand in cands:
        if os.path.basename(cand) == cname:
            return cand
    raise AssertionError(f"类根不存在: {cname}")


@when("触发工位点火 {cname} {case} {sname}")
def step_fire_station(context, cname, case, sname):
    win = _win(context)
    st = _station(context.tree_root, cname, case, sname)
    win._fire_station(st["task"], st["case"])
    _pump(_app(), 100)


@then("蓝任务菜单含 {a} {b} {c} {d}")
def step_blue_menu(context, a, b, c, d):
    win = _win(context)
    menu = win.build_task_menu(win.items_by_path[_task_dir(win, "上市")])
    labels = [x.text() for x in menu.actions()]
    for want in (a, b, c, d):
        assert any(x.startswith(want) for x in labels), \
            f"蓝菜单缺 {want}: {labels}"


@then("红任务菜单含 {label}")
def step_red_menu(context, label):
    win = _win(context)
    menu = win.build_task_menu(win.items_by_path[_task_dir(win, "出库")])
    labels = [x.text() for x in menu.actions()]
    assert any(x.startswith(label) for x in labels), \
        f"红菜单缺 {label}: {labels}"


@given("预置小额订单")
def step_small_order(context):
    fp = os.path.join(context.tree_root, "实例", "订单", "D001", "订单.md")
    body = open(fp, encoding="utf-8").read()
    open(fp, "w", encoding="utf-8").write(body.replace("数量: 100", "数量: 10"))


@when("注入桩引擎")
def step_stub_engine(context):
    win = _win(context)
    fake = os.path.join(FAKES, "fake_engine.py")
    labels = [win.cb_engine.itemText(i) for i in range(win.cb_engine.count())]
    if "桩引擎（验收）" not in labels:
        win.cb_engine.insertItem(0, "桩引擎（验收）", f"{sys.executable} -u {fake}")
    win.cb_engine.setCurrentIndex(0)
    _pump(_app())


@when("触发任务菜单动作 {task} {label}")
def step_task_menu_trigger(context, task, label):
    win = _win(context)
    menu = win.build_task_menu(win.items_by_path[_task_dir(win, task)])
    act = next((x for x in menu.actions() if x.text().startswith(label)), None)
    assert act is not None, f"菜单无 {label}: {[x.text() for x in menu.actions()]}"
    act.trigger()
    _pump(_app(), 100)


@when("等待点火收尾")
def step_wait_runs(context):
    win = _win(context)
    t0 = time.time()
    while win._runs and time.time() - t0 < 90:
        _pump(_app(), 150)
    assert not win._runs, "点火 90 秒未收尾"
    _pump(_app(), 300)
    _stop_modals(context)


@then("执行流显示 {text}")
def step_stream_has(context, text):
    win = _win(context)
    texts = "\n".join(p["view"].toPlainText() or ""
                      for p in win._stream_pages.values())
    assert text in texts, f"执行流不含 {text}: {texts[-300:]}"


@then("账记录 {task} 状态 {status}")
def step_account(context, task, status):
    win = _win(context)
    tdir = _task_dir(win, task)
    for _c, rd in core.task_accounts(win.root, tdir):
        try:
            d = eng.load_account(rd, win.root)
        except (ValueError, OSError):
            continue
        if d and d.get("状态") == status:
            return
    raise AssertionError(f"{task} 无状态「{status}」的账")


@then("执行程序已删 {task}")
def step_reverted(context, task):
    win = _win(context)
    tdir = _task_dir(win, task)
    assert not os.path.isdir(os.path.join(tdir, "执行程序")), "执行程序仍在"
    assert core.task_kind(tdir) != "红", "任务未回蓝"


# ── 推进 ──────────────────────────────────────────────────

@when("右键实例推进 {rel}")
def step_inst_converge(context, rel):
    win = _win(context)
    item = _find_item(win, rel)
    menu = win.build_dir_menu(item)
    act = next((x for x in menu.actions() if x.text().startswith("推进本实例")),
               None)
    assert act is not None, f"实例菜单无推进: {[x.text() for x in menu.actions()]}"
    act.trigger()
    _pump(_app(), 100)


# ── AI 辅助 ───────────────────────────────────────────────

@when("问老子 {q}")
def step_ask_laozi(context, q):
    win = _win(context)
    win.chat_input.setText(q)
    win.ask_laozi()
    _pump(_app(), 100)


@then("老子回答包含 {text}")
def step_laozi_ans(context, text):
    win = _win(context)
    t0 = time.time()
    while time.time() - t0 < 15:
        _pump(_app(), 100)
        if win.chat_proc is not None \
                and win.chat_proc.state() != QProcess.ProcessState.NotRunning:
            continue
        _pump(_app(), 200)
        if text in win.chat_view.toPlainText():
            return
    raise AssertionError(
        f"老子未回答 {text}: {win.chat_view.toPlainText()[-200:]}")


@then("老子思考过程可见")
def step_laozi_thinking(context):
    win = _win(context)
    t0 = time.time()
    while time.time() - t0 < 3:
        _pump(_app(), 60)
        if "💭" in win.chat_view.toPlainText():
            return
    raise AssertionError("思考过程未显示")


@when("代笔意图 {intent}")
def step_ghost(context, intent):
    win = _win(context)

    def _fill():
        dlg = QApplication.activeModalWidget()
        if isinstance(dlg, QInputDialog):
            dlg.setTextValue(intent)
            dlg.accept()
    QTimer.singleShot(0, _fill)
    timer = QTimer()
    timer.timeout.connect(lambda: _click_modal(True))
    timer.start(50)
    context._modal_timer = timer
    QTimer.singleShot(30000, timer.stop)
    btn = win.findChild(QAbstractButton, "btnGhost")
    assert btn is not None, "找不到代笔按钮"
    btn.click()
    _pump(_app(), 100)


@when("等待代笔收尾")
def step_wait_ghost(context):
    win = _win(context)
    t0 = time.time()
    while win.ghost_proc is not None \
            and win.ghost_proc.state() != QProcess.ProcessState.NotRunning \
            and time.time() - t0 < 20:
        _pump(_app(), 100)
    _pump(_app(), 300)
    _stop_modals(context)


# ── 性能 ──────────────────────────────────────────────────

@when("加载大包 {name} 并计时")
def step_big_load(context, name):
    import time as _t
    big = os.path.join(REPO, name)
    assert os.path.isdir(big), f"大包不存在: {big}"
    t0 = _t.time()
    w = ex.Explorer(big)
    context._big_dt = _t.time() - t0
    context._big_tasks = len(w.tasks)
    w.close()


@then("大包耗时小于 {secs:g} 秒")
def step_big_fast(context, secs):
    assert context._big_tasks >= 20, f"大包任务太少: {context._big_tasks}"
    assert context._big_dt < secs, \
        f"大包加载 {context._big_dt:.2f}s ≥ {secs}s"
