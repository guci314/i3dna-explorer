# -*- coding: utf-8 -*-
"""behave 环境——ATDD 验收层（P1 重建:对象名驱动+断言为判据+截图为证据）。

设计律（对齐调研结论）:
- 验收判据=断言与树/账（地面真值）,截图(widget.grab)只做证据链,不做判据;
- 驱动=对象名(findChild/objectName)+树模型寻址,零坐标零OCR;
- 每场景独立树副本(trade-v4 → tmp),场景间零泄漏;
- offscreen 平台,CI 可跑;演示时同一步骤定义换 onscreen 即录屏。
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
EXPLORER_DIR = os.path.dirname(os.path.dirname(HERE))     # explorer/（已迁出独立安家）
REPO = os.environ.get("I3DNA_HOME") or os.path.expanduser(
    os.path.join("~", "work", "report_generate"))          # 树与引擎所在仓
EVIDENCE = os.path.join(EXPLORER_DIR, "acceptance", "evidence")
FAKES = os.path.join(EXPLORER_DIR, "acceptance", "fakes")
BASELINES = os.path.join(EXPLORER_DIR, "acceptance", "baselines")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, EXPLORER_DIR)
_BASE_PATH = os.environ.get("PATH", "")

from PyQt6.QtWidgets import QApplication          # noqa: E402

_app = None


def before_all(context):
    global _app
    os.makedirs(EVIDENCE, exist_ok=True)
    for f in os.listdir(EVIDENCE):      # 证据=当次运行的链,旧链清场防混杂
        if f.endswith(".png"):
            os.remove(os.path.join(EVIDENCE, f))
    _app = QApplication.instance() or QApplication([])


def before_scenario(context, scenario):
    import i3dna_core as core                     # 窗口构造会写 recent,先隔离
    context.tmp = tempfile.mkdtemp(prefix="i3dna_accept_")
    core.RECENT_FILE = os.path.join(context.tmp, "recent.json")
    # 树选择:场景/功能标签 @tree:<名> 指定验收树(默认 trade-v4)。
    # 每场景独立副本,场景间零泄漏。
    tags = list(getattr(scenario, "tags", [])) \
        + list(getattr(scenario.feature, "tags", []))
    tree = next((t.split(":", 1)[1] for t in tags if t.startswith("tree:")),
                "trade-v4")
    context.tree_root = os.path.join(context.tmp, tree)
    shutil.copytree(os.path.join(REPO, tree), context.tree_root)
    context.scenario_name = scenario.name.replace("/", "_")
    # P2b 外部调用打桩(边界测试替身,工业方法论):聊天走桩脚本;
    # 代笔的 omp 子进程用桩可执行文件顶 PATH 首位(只影响本场景进程)。
    os.environ["PATH"] = _BASE_PATH
    context.fake_bin = os.path.join(context.tmp, "bin")
    os.makedirs(context.fake_bin, exist_ok=True)
    shutil.copy(os.path.join(FAKES, "omp"), os.path.join(context.fake_bin, "omp"))
    os.chmod(os.path.join(context.fake_bin, "omp"), 0o755)
    os.environ["PATH"] = context.fake_bin + os.pathsep + os.environ["PATH"]
    os.environ["I3DNA_CHAT_CMD"] = \
        f"{sys.executable} -u {os.path.join(FAKES, 'fake_chat.py')}"
    # 右键对话（101号）：编译车道打桩——桩只答【右键对话协议】prompt，
    # 按话语标记返回固定 查询/签字 JSON；真车道（omp flash 直连）S5 接入。
    os.environ["I3DNA_DIALOG_CMD"] = \
        f"{sys.executable} -u {os.path.join(FAKES, 'fake_dialog.py')}"


def after_scenario(context, scenario):
    win = getattr(context, "win", None)
    if win is not None:
        win.close()
        context.win = None
    shutil.rmtree(context.tmp, ignore_errors=True)
