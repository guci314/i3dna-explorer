# -*- coding: utf-8 -*-
"""step 定义——对象名驱动,零坐标零 OCR。

判据=断言(树/账/详情文本);证据=widget.grab() 落盘 PNG。
驱动协议:树节点走 items_by_path 寻址 + tree.setCurrentIndex(真实选中信号链),
按钮走 findChild(objectName).click()——与未来 AX 驱动共用同一张对象映射。
"""
import os
import re
import time

from behave import given, when, then   # noqa: F401
from PyQt6.QtWidgets import QWidget

import i3dna_explorer as ex
from environment import EVIDENCE


def _win(context):
    if getattr(context, "win", None) is None:
        context.win = ex.Explorer(context.tree_root)
    return context.win


def _pump(app, ms=300):
    """事件泵:让选中/保存的信号链与 refresh 走完。"""
    t0 = time.time()
    while time.time() - t0 < ms / 1000:
        app.processEvents()
        time.sleep(0.02)


def _find_item(win, rel):
    p = os.path.join(win.root, rel)
    item = win.items_by_path.get(p)
    assert item is not None, f"树上找不到节点: {rel}"
    return item


def _shot(context, tag):
    """证据链:场景名+步名+序号,唯一落盘。"""
    n = getattr(context, "_shot_n", 0) + 1
    context._shot_n = n
    fp = os.path.join(
        EVIDENCE,
        re.sub(r"[^\w一-龥]+", "_", context.scenario_name) + f"_{tag}_{n:02d}.png")
    _win(context).grab().save(fp)


# ── 给定 ────────────────────────────────────────────────

@given("打开目录 {name}")
def step_open(context, name):
    context.win = ex.Explorer(os.path.join(context.tmp, name))
    _pump(context.app if hasattr(context, "app") else _app_qapp())


def _app_qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance()


# ── 当 ──────────────────────────────────────────────────

@when("选中 {rel}")
def step_select(context, rel):
    win = _win(context)
    item = _find_item(win, rel)
    win.tree.setCurrentIndex(item.index())
    _pump(_app_qapp())


@when("编辑器改为 {text}")
def step_edit(context, text):
    win = _win(context)
    assert win.stack.currentIndex() == 1, "未进入编辑页（文件未打开为可编辑）"
    win.editor.setPlainText(text)
    _pump(_app_qapp())


@when("点击按钮 {name}")
def step_click(context, name):
    win = _win(context)
    from PyQt6.QtWidgets import QAbstractButton
    btn = win.findChild(QAbstractButton, name)
    assert btn is not None, f"找不到对象名 {name}"
    btn.click()


# ── 那么 ────────────────────────────────────────────────

@then("树上有 {n:d} 个微任务")
def step_taskcount(context, n):
    win = _win(context)
    assert len(win.tasks) == n, f"微任务 {len(win.tasks)} ≠ {n}"


@then("全部 {n:d} 个域可见")
def step_domaincount(context, n):
    win = _win(context)
    d = os.path.join(win.root, "域")
    doms = [x for x in os.listdir(d) if os.path.isdir(os.path.join(d, x))]
    item = _find_item(win, "域")
    assert len(doms) == n, f"域 {len(doms)} ≠ {n}"
    assert item.rowCount() >= n, "树上域节点未展开出子节点"


@then("案卷库有 {n:d} 个产品档案袋")
def step_pcount(context, n):
    win = _win(context)
    d = os.path.join(win.root, "实例", "产品")
    bags = [x for x in os.listdir(d)
            if not x.startswith((".", "__"))
            and os.path.isdir(os.path.join(d, x))]
    assert len(bags) == n, f"产品档案袋 {len(bags)} ≠ {n}"


@then("详情显示 {text}")
def step_detail_has(context, text):
    win = _win(context)
    assert text in win.detail.toPlainText(), f"详情不含「{text}」"


@then("详情包含 {text}")
def step_detail_contains(context, text):
    step_detail_has(context, text)


@then("编辑器包含 {text}")
def step_editor_has(context, text):
    win = _win(context)
    assert text in win.editor.toPlainText(), f"编辑器不含「{text}」"


@then("磁盘文件 {rel} 包含 {text}")
def step_disk_has(context, rel, text):
    fp = os.path.join(context.tree_root, rel)
    body = open(fp, encoding="utf-8").read()
    assert text in body, f"{rel} 不含「{text}」"


@then("状态栏提示 {text}")
def step_status_has(context, text):
    win = _win(context)
    sb = win.statusBar()
    assert sb is not None
    msg = sb.currentMessage()
    assert text in msg, f"状态栏「{msg}」不含「{text}」"


@then("消费任务 {task} 已标过期")
def step_stale(context, task):
    win = _win(context)
    tdir = None
    for t in win.tasks:
        if os.path.basename(t) == task:
            tdir = t
    assert tdir, f"无任务 {task}"
    item = win.items_by_path[tdir]
    assert "⟳" in item.text(), f"任务 {task} 未标过期: {item.text()}"
    assert win.stale_map.get(tdir), "stale_map 未置真"


@then("截图留证")
def step_shot(context):
    _shot(context, "step")
