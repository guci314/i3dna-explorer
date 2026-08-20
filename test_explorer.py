#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_explorer — explorer 的 offscreen 冒烟（规格面纪律：动态发现，不钉内部名）。

用法：python3 test_explorer.py [包根]   （默认 ../8.5）
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import importlib.util
import inspect
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1
                       else os.path.join(HERE, "..", "8.5"))

spec = importlib.util.spec_from_file_location(
    "i3dna_explorer", os.path.join(HERE, "i3dna_explorer.py"))
ex = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ex)

from PyQt6.QtWidgets import QApplication, QMainWindow

results = []


def report(tag, ok, msg=""):
    results.append(ok)
    print(f"  {'✓' if ok else '✗'} {tag} {msg}")


def walk(item):
    yield item
    for i in range(item.rowCount()):
        yield from walk(item.child(i))


def main():
    print(f"═ explorer 冒烟（包根 {os.path.basename(ROOT)}）═")
    wcls = next((o for _, o in inspect.getmembers(ex, inspect.isclass)
                 if issubclass(o, QMainWindow) and o is not QMainWindow), None)
    report("T1 模块含 QMainWindow 子类", wcls is not None,
           wcls.__name__ if wcls else "")
    if not wcls:
        return 1

    app = QApplication.instance() or QApplication(sys.argv)
    win = wcls(ROOT)
    report("T2 对包根构造窗口", True)

    items = list(walk(win.model.item(0)))
    tasks = [i for i in items if i.data(ex.ROLE_TYPE) == "task"]
    entities = [i for i in items if i.data(ex.ROLE_TYPE) == "entity"]
    n_expect = len(ex.eng.find_tasks(ROOT))
    report("T3 微任务节点数=find_tasks", len(tasks) == n_expect,
           f"{len(tasks)} vs {n_expect}")

    ct = {i.foreground().color().name() for i in tasks}
    ce = {i.foreground().color().name() for i in entities}
    report("T4 蓝绿双色区分", bool(ct) and bool(ce) and not (ct & ce),
           f"task={sorted(ct)} entity={sorted(ce)[:2]}")

    menu = win.build_task_menu(tasks[0])
    labels = {a.text() for a in menu.actions() if a.text()}
    need = {"预检", "点火", "点火记录"}
    report("T5 右键动作集", need <= labels, f"{sorted(labels)}")
    report("T8 右键含登记弧动作", {"登记输入弧", "登记产物弧"} <= labels)

    m1 = next((i for i in tasks if i.data(ex.ROLE_PATH).endswith("_通用程序")), None)
    report("T6a 找到 _通用程序 任务节点", m1 is not None)
    if m1 is not None:
        win.tree.setCurrentIndex(m1.index())
        app.processEvents()
        hl = {i.data(ex.ROLE_PATH) for i in win.hl_items}
        has_spec = any(p and "上下文合成文本" in p and p.endswith("开发文本.md")
                       for p in hl)
        has_prod = any(p and p.rstrip("/").endswith(
            ("_数据库输入", "__数据库输入_代码.py")) for p in hl)
        report("T6b 血缘高亮含规格输入", has_spec, f"高亮 {len(hl)} 节点")
        report("T6c 血缘高亮含产物槽", has_prod)

    idx_leaf = next((i for i in items if i.data(ex.ROLE_TYPE) == "file"
                     and str(i.data(ex.ROLE_PATH)).endswith("索引文件.xlsx")), None)
    report("T7a 找到索引文件叶节点", idx_leaf is not None)
    if idx_leaf is not None:
        win.tree.setCurrentIndex(idx_leaf.index())
        app.processEvents()
        html = win.detail.toHtml()
        report("T7b 右侧渲染索引内容", "目录-文件名称" in html)

    report("T18 引擎为封闭下拉", hasattr(win, "cb_engine")
           and win.cb_engine.count() >= 3 and not win.cb_engine.isEditable(),
           f"{[win.cb_engine.itemText(i) for i in range(win.cb_engine.count())]}")
    report("T10 平台钉已除（概念拆除）", not hasattr(win, "cb_platform"),
           "工具栏不得再有平台下拉")

    win.show_lint()
    html = win.detail.toHtml()
    n_err = len(win.lint_rep.errors)
    report("T9a 全树对账视图", "全树对账" in html and f"错误 {n_err}" in html,
           f"{n_err} 错 {len(win.lint_rep.warnings)} 警")
    if win.lint_rep.errors:
        from PyQt6.QtCore import QUrl
        fpart = win.lint_rep.errors[0][0].split("#")[0].split("·")[0]
        win.on_anchor(QUrl(f"i3dna:{fpart}"))
        cur = win.model.itemFromIndex(win.tree.currentIndex())
        report("T9b 点错误跳转到节点", cur is not None and
               fpart.split("/")[-1] in (cur.data(ex.ROLE_PATH) or ""),
               cur.text() if cur else "")

    b1, b2, b3 = win._triage()
    win.show_fix_proposals()
    html = win.detail.toHtml()
    total = len(win.lint_rep.errors) + len(win.lint_rep.warnings)
    report("T11 修复提案三桶分诊全覆盖", len(b1) + len(b2) + len(b3) == total
           and "规范空白" in html,
           f"规范空白{len(b1)} 过期{len(b2)} 可修{len(b3)} / 共{total}")

    txt = next((i for i in items if i.data(ex.ROLE_TYPE) == "file"
                and str(i.data(ex.ROLE_PATH)).endswith("__说明.txt")), None)
    if txt is not None:
        win.tree.setCurrentIndex(txt.index())
        app.processEvents()
        report("T12 真源文本进编辑器", win.stack.currentIndex() == 1
               and len(win.editor.toPlainText()) > 10,
               f"{len(win.editor.toPlainText())} 字符")
    py = next((i for i in items if i.data(ex.ROLE_TYPE) == "file"
               and str(i.data(ex.ROLE_PATH)).endswith(".py")), None)
    if py is not None:
        labels = {a.text() for a in win.build_file_menu(py).actions()}
        report("T13 py 文件右键含运行", "运行" in labels, f"{sorted(labels)}")

    from PyQt6.QtWidgets import QLineEdit, QPushButton
    report("T14 老子聊天条", isinstance(getattr(win, "chat_input", None), QLineEdit)
           and callable(getattr(win, "ask_laozi", None))
           and len(win._status_context()) > 50,
           f"状态快照 {len(win._status_context())} 字符")
    btns = {b.text() for b in win.stack.widget(1).findChildren(QPushButton)}
    report("T15 编辑器含代笔/保存", {"代笔", "保存"} <= btns, f"{sorted(btns)}")

    tb_acts = {a.text() for a in win.findChildren(__import__('PyQt6.QtGui',
               fromlist=['QAction']).QAction)}
    report("T17 工具栏含推进", "推进" in tb_acts, f"{sorted(tb_acts)[:8]}")
    report("T16a 工作流标签页", win.tabs.count() == 2
           and win.tabs.tabText(1) == "工作流")
    # 一类一工作流：下拉按类切（默认单类），「全部」拼总览且排末尾
    pkg_labels = [win.cb_wfpkg.itemText(i)
                  for i in range(win.cb_wfpkg.count())]
    report("T16c 工作流下拉按类切且默认单类", len(pkg_labels) >= 1
           and pkg_labels[-1] == "全部"
           and win.cb_wfpkg.currentText() == pkg_labels[0],
           f"{pkg_labels} 默认={win.cb_wfpkg.currentText()}")
    win.cb_wfpkg.setCurrentText("全部")
    app.processEvents()
    scene = win.wf_view.scene()
    node_paths = {i.data(0) for i in scene.items() if i.data(0)}
    task_nodes = node_paths & set(win.task_rows)
    place_nodes = node_paths - task_nodes
    report("T16b 图含全部微任务", len(task_nodes) == len(win.task_rows),
           f"{len(task_nodes)} 任务 / {len(place_nodes)} 制品 / "
           f"{len(scene.items())} 图元")

    # T19 渐进式符号化：瞬态造红（建执行程序→验色与菜单→还原现场）
    import shutil
    labels_blue = {a.text() for a in win.build_task_menu(tasks[0]).actions()
                   if a.text()}
    report("T19a 蓝任务菜单含检测/编译",
           {"检测可符号化", "编译（生成符号程序）"} <= labels_blue
           and "回退联结主义" not in labels_blue)
    t_dir = next((t for t, on in win.enabled_map.items() if on), None)
    report("T19b 存在使能任务可造红", t_dir is not None)
    if t_dir is not None:
        ed_dir = os.path.join(t_dir, "执行程序")
        os.makedirs(ed_dir, exist_ok=True)
        with open(os.path.join(ed_dir, "主程序.py"), "w") as f:
            f.write("print('t19')\n")
        try:
            win.refresh()
            items2 = list(walk(win.model.item(0)))
            red_item = next(i for i in items2 if i.data(ex.ROLE_PATH) == t_dir)
            c_red = red_item.foreground().color().name()
            others = {i.foreground().color().name() for i in items2
                      if i.data(ex.ROLE_TYPE) == "entity"
                      or (i.data(ex.ROLE_TYPE) == "task"
                          and not ex.eng.exec_entry(i.data(ex.ROLE_PATH)))}
            report("T19c 符号任务红色且异于蓝绿", c_red == "#c62828"
                   and c_red not in others, f"红={c_red}")
            labels_red = {a.text() for a in
                          win.build_task_menu(red_item).actions() if a.text()}
            report("T19d 红任务菜单含回退、不含编译",
                   "回退联结主义" in labels_red
                   and "编译（生成符号程序）" not in labels_red)
        finally:
            shutil.rmtree(ed_dir, ignore_errors=True)
            win.refresh()

    txt2 = next((i for i in walk(win.model.item(0))
                 if i.data(ex.ROLE_TYPE) == "file"
                 and str(i.data(ex.ROLE_PATH)).endswith("__说明.txt")), None)
    if txt2 is not None:
        p = txt2.data(ex.ROLE_PATH)
        orig = open(p, "rb").read()
        win.tree.setCurrentIndex(txt2.index())
        app.processEvents()
        win.editor.setPlainText(win.editor.toPlainText() + "\n■T12b■")
        save_btn = next(b for b in win.stack.widget(1).findChildren(QPushButton)
                        if b.text() == "保存")
        save_btn.click()
        app.processEvents()
        on_disk = open(p, encoding="utf-8").read()
        report("T12b 编辑→保存落盘", on_disk.rstrip().endswith("■T12b■"))
        with open(p, "wb") as f:          # 还原现场：真源按原字节写回
            f.write(orig)

    win.close()
    n_fail = results.count(False)
    print(f"通过 {results.count(True)} / 失败 {n_fail}")
    print("🟢 PASS" if n_fail == 0 else "🔴 FAIL")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
