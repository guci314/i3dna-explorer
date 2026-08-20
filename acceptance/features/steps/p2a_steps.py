# -*- coding: utf-8 -*-
"""P2a step 定义——40 条清单的纯 UI 断言组(24 条),对象名驱动,零坐标零 OCR。

判据=断言(树/详情/工作流图/磁盘/状态栏),证据=widget.grab() 落盘 PNG。
复用 P1 步骤:打开目录/选中/编辑器改为/点击按钮/磁盘文件…包含/状态栏提示/
详情包含/编辑器包含/消费任务…已标过期/截图留证。
"""
import os
import time

from behave import given, when, then   # noqa: F401
from PyQt6.QtCore import QTimer, QUrl, Qt
from PyQt6.QtGui import QAction
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import (QApplication, QGraphicsLineItem,
                             QGraphicsPathItem, QGraphicsView, QInputDialog)

import i3dna_explorer as ex
from explorer_steps import _find_item, _pump, _win


def _app():
    return QApplication.instance()


def _scene_task_paths(win):
    return {str(i.data(0)) for i in win.wf_view.scene().items() if i.data(0)}


# ── 基础功能 ──────────────────────────────────────────────

@when("显示窗口")
def step_show(context):
    win = _win(context)
    win.resize(1280, 800)
    win.show()
    _pump(_app())


@then("窗口已显示")
def step_visible(context):
    assert _win(context).isVisible(), "窗口未显示"


@then("标题含包名 {name}")
def step_title(context, name):
    assert name in _win(context).windowTitle(),         f"标题「{_win(context).windowTitle()}」不含 {name}"


@then("蓝任务红任务与实体各有本色")
def step_colors(context):
    win = _win(context)
    found = {"蓝": False, "红": False, "实体": False}
    for it in win.items_by_path.values():
        fg = it.foreground().color()
        if fg == ex.C_TASK:
            found["蓝"] = True
        if fg == ex.C_SYM:
            found["红"] = True
        if "【实体】" in it.text() and fg == ex.C_ENTITY:
            found["实体"] = True
    assert all(found.values()), f"三色不齐: {found}"


@when("折叠节点 {rel}")
def step_collapse(context, rel):
    win = _win(context)
    win.tree.collapse(_find_item(win, rel).index())
    _pump(_app())


@when("展开节点 {rel}")
def step_expand(context, rel):
    win = _win(context)
    win.tree.expand(_find_item(win, rel).index())
    _pump(_app())


@then("节点已折叠 {rel}")
def step_is_collapsed(context, rel):
    win = _win(context)
    assert not win.tree.isExpanded(_find_item(win, rel).index()), f"{rel} 未折叠"


@then("节点已展开 {rel}")
def step_is_expanded(context, rel):
    win = _win(context)
    assert win.tree.isExpanded(_find_item(win, rel).index()), f"{rel} 未展开"


# ── 血缘与依赖 ────────────────────────────────────────────

@then("血缘高亮 输入与产物")
def step_hl(context):
    win = _win(context)
    assert win.hl_items, "选中任务后无血缘高亮"
    cols = [it.background().color() for it in win.hl_items]
    assert ex.BG_IN in cols, f"缺输入淡绿 {cols}"
    assert ex.BG_OUT in cols, f"缺产物淡橙 {cols}"


@when("磁盘文件 {rel} 追加 {text}")
def step_disk_append(context, rel, text):
    fp = os.path.join(context.tree_root, rel)
    with open(fp, "a", encoding="utf-8") as f:
        f.write("\n" + text + "\n")


@when("点击工具栏动作 {name}")
def step_tb_action(context, name):
    win = _win(context)
    act = win.findChild(QAction, "act" + name)
    assert act is not None, f"找不到工具栏动作 act{name}"
    act.trigger()
    _pump(_app())


# ── 工作流图 ──────────────────────────────────────────────

@when("切换到工作流页")
def step_wf_page(context):
    win = _win(context)
    win.tabs.setCurrentIndex(1)
    _pump(_app())


@then("工作流页有图")
def step_wf_scene(context):
    win = _win(context)
    assert win.tabs.currentIndex() == 1, "未切到工作流页"
    assert win.wf_view.scene() is not None \
        and len(win.wf_view.scene().items()) > 0, "工作流图为空"


@when("视图选择 {pkg}")
def step_wf_pkg(context, pkg):
    win = _win(context)
    labels = [win.cb_wfpkg.itemText(i) for i in range(win.cb_wfpkg.count())]
    assert pkg in labels, f"视图下拉无 {pkg}: {labels}"
    win.cb_wfpkg.setCurrentText(pkg)
    _pump(_app())


@then("图上的任务节点与微任务一致")
def step_wf_nodes(context):
    win = _win(context)
    paths = _scene_task_paths(win) & {str(t) for t in win.task_rows}
    assert len(paths) == len(win.task_rows), \
        f"任务节点 {len(paths)} ≠ 微任务 {len(win.task_rows)}"


@then("图上有制品与连线")
def step_wf_bipartite(context):
    win = _win(context)
    if win.cb_flow.isChecked():
        win.cb_flow.setChecked(False)      # 二部图:微任务+材料两色节点+连线
        _pump(_app())
    scene = win.wf_view.scene()
    places = [i for i in scene.items()
              if i.data(0) and str(i.data(0)) not in win.task_rows]
    links = [i for i in scene.items()
             if isinstance(i, (QGraphicsLineItem, QGraphicsPathItem))]
    assert len(places) > 0, "二部图无制品节点"
    assert len(links) > 0, "二部图无连线"


@when("双击图上任务节点 {name}")
def step_wf_dclick(context, name):
    win = _win(context)
    win.resize(1280, 800)
    win.show()
    _pump(_app())
    target = None
    for i in win.wf_view.scene().items():
        p = i.data(0)
        if p and str(p) in win.task_rows and os.path.basename(str(p)) == name:
            target = i
            break
    assert target is not None, f"图上无任务节点 {name}"
    win.wf_view.centerOn(target.sceneBoundingRect().center())
    _pump(_app())
    pos = win.wf_view.mapFromScene(target.sceneBoundingRect().center())
    QTest.mouseDClick(win.wf_view.viewport(), Qt.MouseButton.LeftButton, pos=pos)
    _pump(_app())


@then("树页选中 {name}")
def step_tree_selected(context, name):
    win = _win(context)
    assert win.tabs.currentIndex() == 0, "未跳回目录页"
    idx = win.tree.currentIndex()
    assert idx.isValid(), "树上无选中"
    it = win.model.itemFromIndex(idx)
    assert os.path.basename(it.data(ex.ROLE_PATH) or "") == name, \
        f"选中「{it.text()}」≠ {name}"


@then("缩放改变视图比例")
def step_wf_zoom(context):
    v = _win(context).wf_view
    m0 = v.transform().m11()
    v.zoom(1.25)
    m1 = v.transform().m11()
    v.zoom(0.8)
    m2 = v.transform().m11()
    assert m1 > m0, "放大未生效"
    assert m2 < m1, "缩小未生效"


@then("拖拽平移已启用")
def step_wf_drag(context):
    assert _win(context).wf_view.dragMode() \
        == QGraphicsView.DragMode.ScrollHandDrag, "拖拽平移未启用"


@then("视图下拉按类切换")
def step_wf_pkg_switch(context):
    win = _win(context)
    labels = [win.cb_wfpkg.itemText(i) for i in range(win.cb_wfpkg.count())]
    assert len(labels) >= 2 and labels[-1] == "全部", f"下拉异常: {labels}"
    assert win.cb_wfpkg.currentText() == labels[0], "默认应为第一类"
    win.cb_wfpkg.setCurrentText("全部")
    _pump(_app())
    all_paths = _scene_task_paths(win) & {str(t) for t in win.task_rows}
    win.cb_wfpkg.setCurrentIndex(0)
    _pump(_app())
    one = _scene_task_paths(win) & {str(t) for t in win.task_rows}
    assert len(all_paths) == len(win.task_rows), "「全部」未画出全部微任务"
    assert len(one) < len(all_paths), "单类视图未收缩"


# ── 编辑与文件 ────────────────────────────────────────────

@then("编辑器已打开")
def step_editor_open(context):
    assert _win(context).stack.currentIndex() == 1, "未进入编辑页"


@then("编辑器非空")
def step_editor_nonempty(context):
    assert len(_win(context).editor.toPlainText()) > 0, "编辑器为空"


@when("右键运行文件 {rel}")
def step_run_file(context, rel):
    win = _win(context)
    item = _find_item(win, rel)
    menu = win.build_file_menu(item)
    run = next((a for a in menu.actions() if a.text().startswith("运行")), None)
    assert run is not None, "文件菜单无「运行…」动作"
    # 参数对话框自动确认(默认 1+2*3)——驱动协议里「回车确认」=accept
    def _confirm():
        dlg = QApplication.activeModalWidget()
        if isinstance(dlg, QInputDialog):
            dlg.accept()
    QTimer.singleShot(0, _confirm)
    run.trigger()
    t0 = time.time()
    while win._runs and time.time() - t0 < 20:
        _pump(_app(), 100)
    assert not win._runs, "运行 20 秒未结束"


@then("运行完成退出码 0")
def step_run_ok(context):
    txt = _win(context).detail.toPlainText()
    assert "完成 🟢" in txt and "退出码 0" in txt, f"运行未成功: {txt[-200:]}"


# ── Lint 与修复 ───────────────────────────────────────────

@when("点击首个错误锚点")
def step_first_error_jump(context):
    win = _win(context)
    rep = win.lint_rep
    assert rep is not None and rep.errors, "无 lint 错误可跳"
    where = rep.errors[0][0]
    fpart = where.split("#")[0].split("·")[0]
    context._err_fpart = fpart
    win.on_anchor(QUrl(f"i3dna:{fpart}"))
    _pump(_app())


@then("树上选中了错误节点")
def step_err_selected(context):
    win = _win(context)
    idx = win.tree.currentIndex()
    assert idx.isValid(), "点击错误后树上无选中"
    it = win.model.itemFromIndex(idx)
    assert context._err_fpart.split("/")[-1] in (it.data(ex.ROLE_PATH) or ""), \
        f"选中「{it.text()}」不匹配 {context._err_fpart}"


@then("三桶覆盖全部问题")
def step_triage_total(context):
    win = _win(context)
    rep = win.lint_rep
    b1, b2, b3 = win._triage()
    total = len(rep.errors) + len(rep.warnings)
    assert len(b1) + len(b2) + len(b3) == total, \
        f"三桶 {len(b1)}+{len(b2)}+{len(b3)} ≠ 共 {total}"


# ── 实例化 ────────────────────────────────────────────────

@given("预置演示程序 {rel}")
def step_seed_demo_py(context, rel):
    fp = os.path.join(context.tree_root, rel)
    with open(fp, "w", encoding="utf-8") as f:
        f.write("print(1 + 2 * 3)\n")


@given("预置字段区声明 {rel}")
def step_seed_law(context, rel):
    fp = os.path.join(context.tree_root, rel)
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, "w", encoding="utf-8") as f:
        f.write("---\n路径: 实例/{实例}/顾客档案.md\n默认:\n  可用量: 0\n---\n"
                "顾客档案字段区声明。\n")


@when("对 {rel} 触发菜单动作 {label}")
def step_menu_trigger(context, rel, label):
    win = _win(context)
    item = _find_item(win, rel)
    menu = win.build_dir_menu(item)
    assert menu is not None, f"{rel} 无目录菜单"
    act = next((a for a in menu.actions() if a.text().startswith(label)), None)
    assert act is not None, \
        f"菜单无动作 {label}: {[a.text() for a in menu.actions()]}"
    act.trigger()
    _pump(_app())


@then("实例菜单含 {label}")
def step_menu_has(context, label):
    win = _win(context)
    idx = win.tree.currentIndex()
    assert idx.isValid(), "树上无选中实例目录"
    it = win.model.itemFromIndex(idx)
    menu = win.build_dir_menu(it)
    assert menu is not None, "实例目录无菜单"
    assert any(a.text().startswith(label) for a in menu.actions()), \
        f"菜单缺 {label}: {[a.text() for a in menu.actions()]}"


@then("磁盘文件 {rel} 存在")
def step_disk_exists(context, rel):
    fp = os.path.join(context.tree_root, rel)
    assert os.path.isfile(fp), f"{rel} 不存在"


# ── 配置与状态 ────────────────────────────────────────────

@when("切换引擎到 {i:d}")
def step_engine_idx(context, i):
    win = _win(context)
    assert win.cb_engine.count() > i, "引擎下拉项不足"
    win.cb_engine.setCurrentIndex(i)
    _pump(_app())


@then("引擎配置正确 {label}")
def step_engine_ok(context, label):
    win = _win(context)
    assert win.cb_engine.count() >= 3 and not win.cb_engine.isEditable(), \
        "引擎下拉应为封闭多选"
    assert win.cb_engine.currentText() == label, \
        f"当前引擎「{win.cb_engine.currentText()}」≠ {label}"


@when("关闭窗口")
def step_close(context):
    _win(context).close()
    _pump(_app())


@then("窗口已关闭")
def step_closed(context):
    assert not _win(context).isVisible(), "窗口未关闭"
