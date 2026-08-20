#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""i3dna_explorer — I3DNA 客户包的二部图浏览器（M2 工具链层，PyQt6）。

树上画的就是条件/事件网：**绿=实体节点（库所）、蓝=联结主义微任务（LLM 点火）、
红=符号主义微任务（执行程序/主程序 在场，点火跑确定性程序）**；
右键微任务 = 使能判定（preflight）＋点火（run）＋点火记录查看；
蓝任务可「检测可符号化／编译」，红任务可「回退联结主义」——渐进式符号化的操作面。
状态叠加：lint 悬空 ⛔、使能亮蓝/未使能灰蓝、输入过期 ⟳；
选中微任务时高亮其血缘（输入=淡绿背景、产物槽=淡橙背景）。

用法：python3 i3dna_explorer.py <包根目录>    （缺省弹目录选择框）
定位：图形 debug＝留痕投影（薄面板），不做图形建模；引擎/lint 逻辑全部 import 复用。
"""
import glob
import importlib.util
import json
import os
import sys
import tempfile
from datetime import datetime

from PyQt6.QtCore import (QObject, QPointF, QProcess, QSize, Qt, QTimer,
                          QThread)
from PyQt6.QtCore import pyqtSignal as _pyqtSignal
from PyQt6.QtGui import (QAction, QBrush, QColor, QFont, QIcon, QPainter, QPen,
                         QPixmap, QPolygonF, QStandardItem, QStandardItemModel)
from PyQt6.QtWidgets import (QGraphicsScene, QGraphicsView, QTabWidget)
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
                             QFileDialog, QFormLayout,
                             QHBoxLayout, QInputDialog, QLabel, QLineEdit,
                             QMainWindow, QMenu, QMessageBox, QPlainTextEdit,
                             QPushButton, QSplitter, QStackedWidget,
                             QTextBrowser, QToolBar, QTreeView, QVBoxLayout,
                             QWidget)
import html as _htm
import shlex

EDITABLE_EXT = {".txt", ".md", ".yaml", ".yml"}   # 真源类可编辑；.py/结果.json=产物禁手改

HERE = os.path.dirname(os.path.abspath(__file__))


if HERE not in sys.path:
    sys.path.insert(0, HERE)
import i3dna_core as core                        # 业务逻辑层(零 Qt)

eng, lint = core.eng, core.lint                  # 单一装载副本在 core
BASE = core.BASE                                 # 引擎家（explorer 迁出后跨仓寻引擎）

ROLE_PATH = Qt.ItemDataRole.UserRole + 1
ROLE_TYPE = Qt.ItemDataRole.UserRole + 2          # task / entity / dir / file

C_TASK = QColor("#1565c0")
C_SYM = QColor("#c62828")          # 符号主义微任务：执行程序/主程序 在场
C_HUM = QColor("#388e3c")          # 绿任务：执行者=人（人工工位）
C_TASK_OFF = QColor("#78909c")
C_ENTITY = QColor("#2e7d32")
C_FILE = QColor("#9e9e9e")
BG_IN = QColor(200, 230, 201, 120)                # 血缘：输入淡绿
BG_OUT = QColor(255, 224, 178, 150)               # 血缘：产物槽淡橙


def task_color(tdir):
    """三色谱→画笔。判定在 core.task_kind(业务),这里只配色(界面)。"""
    return {"红": C_SYM, "绿": C_HUM}.get(core.task_kind(tdir), C_TASK)


class WorkflowView(QGraphicsView):
    """工作流图视图：双击节点回目录页选中；滚轮缩放；拖拽平移。"""

    def __init__(self, on_jump, on_menu=None):
        super().__init__()
        self._on_jump = on_jump
        self._on_menu = on_menu
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    def contextMenuEvent(self, ev):
        """图上右键=树上右键同一张菜单——工位在哪里被看见,就在哪里能被办。"""
        it = self.itemAt(ev.pos())
        while it is not None and it.data(0) is None:
            it = it.parentItem()
        if it is not None and it.data(0) and self._on_menu:
            self._on_menu(str(it.data(0)), ev.globalPos())

    def wheelEvent(self, ev):
        f = 1.15 if ev.angleDelta().y() > 0 else 1 / 1.15
        self.scale(f, f)

    def zoom(self, f):
        self.scale(f, f)

    def fit_all(self, min_scale=0.8, max_scale=1.5):
        """全景适配，缩放钳在 [min,max]——字不缩没、图不胀爆，越界靠拖。"""
        if self.scene() is None:
            return
        rect = self.scene().itemsBoundingRect().adjusted(-40, -40, 40, 40)
        self.resetTransform()
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        m = self.transform().m11()
        if min_scale and m < min_scale:
            self.resetTransform()
            self.scale(min_scale, min_scale)
            self.centerOn(rect.topLeft() + QPointF(rect.width() / 4, 80))
        elif m > max_scale:
            self.resetTransform()
            self.scale(max_scale, max_scale)
            self.centerOn(rect.center())

    def mouseDoubleClickEvent(self, ev):
        it = self.itemAt(ev.position().toPoint())
        while it is not None and it.data(0) is None:
            it = it.parentItem()
        if it is not None and it.data(0):
            self._on_jump(it.data(0))
        super().mouseDoubleClickEvent(ev)


def dot(color):
    pm = QPixmap(12, 12)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QBrush(color))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(1, 1, 10, 10)
    p.end()
    return QIcon(pm)


def _ring(color):
    """空心环图标（未使能态）：范帱色前景保留,图标从实心点变空心环。"""
    pm = QPixmap(12, 12)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(color, 2))
    p.drawEllipse(2, 2, 8, 8)
    p.end()
    return QIcon(pm)



class _AssistThread(QThread):
    """直连车道工作线程:core.assist_llm 流式,delta/done 信号回 UI。"""
    delta = _pyqtSignal(str)
    done = _pyqtSignal(str)

    def __init__(self, prompt):
        super().__init__()
        self.prompt = prompt

    def run(self):
        try:
            full = core.assist_llm(self.prompt, on_delta=self.delta.emit)
            self.done.emit(full)
        except Exception as e:
            self.done.emit(f"（助手通道故障:{e}）")

class LoginDialog(QDialog):
    """树原生登录（ARCHITECTURE §5 主体）：凭证=人员档案的 pbkdf2 盐化
    哈希（/etc/shadow 同款——无明文、无 login.db）；验证在 core 纯函数，
    登录日志经引擎 login 子命令入账（不变式2：业务写经引擎）。"""

    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.setWindowTitle("登录（主体 = 人员档案）")
        self.root, self.principal = root, None
        self.ed_principal = QLineEdit()
        self.ed_principal.setObjectName("edPrincipal")
        self.ed_pass = QLineEdit()
        self.ed_pass.setObjectName("edPass")
        self.ed_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.lbl_msg = QLabel("员工编号或姓名 + 口令（凭证住 实例/人员/*/凭证.md）")
        btn = QPushButton("登录")
        btn.setObjectName("btnLogin")
        btn.clicked.connect(self._try)
        logout = QPushButton("注销")
        logout.setObjectName("btnLogout")
        logout.setToolTip("撤下当前会话主体（默认主体/切换前先撤）")
        logout.clicked.connect(self._logout)
        cancel = QPushButton("取消")
        cancel.setObjectName("btnCancel")
        cancel.clicked.connect(self.reject)
        lay = QFormLayout(self)
        lay.addRow("主体", self.ed_principal)
        lay.addRow("口令", self.ed_pass)
        row = QHBoxLayout()
        row.addWidget(btn)
        row.addWidget(logout)
        row.addWidget(cancel)
        lay.addRow(self.lbl_msg)
        lay.addRow(row)
        for w in (self.ed_principal, self.ed_pass):
            w.returnPressed.connect(self._try)

    def _logout(self):
        """注销：principal=None 收框（_set_principal 回未登录态）。"""
        self.principal = None
        self.accept()

    def _log(self, status):
        import subprocess
        subprocess.run(
            [sys.executable, "-u", os.path.join(
                BASE, "i3dna-engine", "i3dna_engine.py"),
             "login", self.principal["主体值"], "--root", self.root,
             "--status", status],
            capture_output=True, timeout=30)

    def _try(self):
        hit = core.find_principal(self.root, self.ed_principal.text().strip())
        if not hit:
            self.lbl_msg.setText("无此主体（人员档案未登记该编号/姓名）")
            return
        self.principal = hit
        if not core.verify_credential(hit["袋"], self.ed_pass.text()):
            self._log("密码错误")
            self.lbl_msg.setText("口令不符")
            return
        self._log("登录成功")
        self.accept()


CHAT_PROTO = """【右键对话协议】（101号·话语即签字；103号·起草车道=柜员的手）
你是案卷对话的编译器：对用户话语输出**三选一的 JSON**（只输出 JSON，别无他话），
或者对纯闲聊/澄清直接以普通文字回答（此时不要 JSON）。
查询（只需读树作答——状态/账/任务清单/悬账……）：
  {"模式": "查询", "读桥": [{"动词": "tree|tasks|task|account|lint|coverage",
                            "参数": {"任务": "…", "案卷号": "…"}}]}
签字（用户意图是执行变迁——点火/办结/推进/落位）：
  {"模式": "签字", "动词序列": [{"动词": "fire|settle|advance|draft",
                               "参数": {"任务": "…", "案卷号": "…"}}]}
起草（柜员的手——申请/产物不在场时替用户起草，**不念清单让人回家手写**）：
  {"模式": "起草", "任务": "<方法目录>", "案卷号": "…",
   "草稿": [{"路径": "<案卷内相对路径>", "内容": "<全文>"}]}
  起草 frontmatter 一律 `键: 值`（冒号后**有空格**）——无空格形读不出值。
规则：
- 签字动词仅限 fire/settle/advance/draft；「任务」＝**方法目录**路径——照抄闭包里
  「─── 域/…/方法/名 ───」行首标签（不带 /任务.md 后缀）；「案卷号」缺省=本案卷。
- **树面现状先查后断**：凡要断言「某域/类/文件/账在不在树、什么状态」，必须先出
  查询信封（读桥 tree/tasks/task/account）拿事实再答——案卷闭包只带类知识＋本案卷
  材料，树面全貌与 __账 都不在其中；**闭包里缺席≠树上没有**，草稿在场≠未办结
  （批准后底稿留在案卷）。无手艺卡不能查时，如实说「闭包看不到，无法断言」。
- 看方法的执行者声明：执行者=人 的绿站只能 settle（办结＝审批）——引擎拒代人
  点火；蓝站（执行者=agent，如 女娲·立域起草）由引擎点火起草。申请/产物不在场
  时**起草**：小材料（域意/要点）直接给「内容」；本类有蓝起草站且用户要办它
  管的活时，「任务」填蓝站并把它要的输入材料（如 域意.md：域名/域主/职责/说明）
  起草好——UI 自动点火蓝站产出正式草稿并回显给人过目。
- 用户过目后说「批准」→ 编译签字序列：先 draft 落位（参数含 草稿=[{"路径":
  "<树内产物槽全路径——照产物弧代入案卷键>", "源": "<案卷内草稿名>"}]），
  再 settle 绿站（意图=「批准」话语原文）。
- draft=柜员的手（落盘零入账）；fire/settle/advance=签字（入账）。一次编译
  可含多条动词；逐条执行逐条入账，意图字段将记话语原文。
- 主体={principal}：签字以该主体署名；蓝站点火以站声明的执行者署名。
"""


class _FnThread(QThread):
    """通用工作线程：fn() 同步执行，done(str) 回 UI（对话编译车道用）。"""
    done = _pyqtSignal(str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.done.emit(str(self.fn() or ""))
        except Exception as e:
            self.done.emit(f"（对话通道故障:{e}）")


class OmpRpcClient(QObject):
    """omp --mode rpc 持久流式车道（8-20 实测：text_delta 逐帧铺开，S5 实装）。
    spawn 一次多轮 prompt——进程开销只付一次，翻「omp 子进程已废」旧案；
    进程死＝下次 ask 自动重启；信号路由回 UI 线程（读写线程安全）。"""

    _d = _pyqtSignal(str)
    _ok = _pyqtSignal(str)
    _bad = _pyqtSignal(str)

    def __init__(self, parent):
        super().__init__(parent)
        self._p = None
        self._buf = []
        self._busy = False
        self._cb = None
        self._turn_done = False
        self._d.connect(self._ui_delta)
        self._ok.connect(self._ui_done)
        self._bad.connect(self._ui_fail)

    def _cmd(self):
        return shlex.split(os.environ.get(
            "I3DNA_OMP_RPC_CMD",
            "omp --mode rpc --no-session --no-tools"))

    def _ensure(self):
        if self._p and self._p.poll() is None:
            return True
        import subprocess as _sp
        import threading as _th
        try:
            self._p = _sp.Popen(
                self._cmd(), stdin=_sp.PIPE, stdout=_sp.PIPE,
                stderr=_sp.DEVNULL, text=True, encoding="utf-8",
                errors="replace", bufsize=1)
        except OSError as e:
            self._bad.emit(f"omp rpc 起不来：{e}")
            return False
        _th.Thread(target=self._read, daemon=True).start()
        return True

    def _read(self):
        """读线程：行分帧 JSON——assistant 消息起段清缓冲，text_delta 逐帧
        上抛；终帧＝agent_end（源码实证：prompt_result 只在 agentInvoked=
        false 的本地命令下发，agent 回合永不发——误等它＝永久占线）。"""
        p = self._p
        for line in p.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                m = json.loads(line)
            except ValueError:
                continue
            t = m.get("type")
            if t == "message_start" \
                    and m.get("message", {}).get("role") == "assistant":
                self._buf = []
            elif t == "message_update":
                ev = m.get("assistantMessageEvent") or {}
                if ev.get("type") == "text_delta" and ev.get("delta"):
                    self._buf.append(ev["delta"])
                    self._d.emit(ev["delta"])
            elif t in ("agent_end", "prompt_result") and self._busy \
                    and not self._turn_done:
                self._turn_done = True
                self._ok.emit("".join(self._buf).strip())
        if self._busy and not self._turn_done:
            self._bad.emit("omp rpc 进程退出（本轮未完）")

    def ask(self, prompt, on_delta, on_done):
        if self._busy:
            on_done("（omp 车道占线——上一轮未收尾）")
            return
        self._busy = True
        self._turn_done = False
        self._buf = []
        self._cb = (on_delta, on_done)
        if not self._ensure():
            self._busy = False
            return
        try:
            self._p.stdin.write(json.dumps(
                {"type": "prompt", "id": "i3dna", "message": prompt}) + "\n")
            self._p.stdin.flush()
        except (OSError, ValueError) as e:
            self._busy = False
            on_done(f"（omp 车道写失败：{e}）")

    def _ui_delta(self, d):
        if self._busy and self._cb and self._cb[0]:
            try:
                self._cb[0](d)
            except RuntimeError:
                pass                  # 对话窗已关

    def _ui_done(self, text):
        self._busy = False
        if self._cb and self._cb[1]:
            try:
                self._cb[1](text)
            except RuntimeError:
                pass
        self._cb = None

    def _ui_fail(self, msg):
        self._busy = False
        if self._cb and self._cb[1]:
            try:
                self._cb[1](f"（{msg}）")
            except RuntimeError:
                pass
        self._cb = None

    def reset(self):
        """车道重启（看门狗/进程死后）：杀进程，下次 ask 重 spawn。"""
        if self._p and self._p.poll() is None:
            try:
                self._p.terminate()
            except Exception:
                pass
        self._p = None
        self._busy = False
        self._cb = None


class ChatDialog(QDialog):
    """右键对话面板（101号）：话语即签字——复用聊天收发形，**无确认按钮**。
    零会话态：会话仅内存（_hist），关闭即散；签字闭包每条话语从树重组装。
    UI 只转发不解释：JSON 信封机械分派（查询→api_query 白名单代跑、
    签字→api_write 逐条执行入账），语义解释归模型，执行归引擎。"""

    ROUNDS = 5          # 查询环轮上限（继承老子手艺【查】环）

    def __init__(self, parent, root, croot, case, principal):
        super().__init__(parent)
        self.setObjectName("chatDialog")
        self.setWindowTitle(f"对话 · {os.path.basename(croot)}/{case}"
                            f" · {principal['姓名']}（话语即签字）")
        self.resize(680, 480)
        self.root, self.croot, self.case = root, croot, case
        self.principal = principal
        self._hist = []                 # (who, text)——内存瞬时，零落盘
        self._round = 0
        self._thread = None             # 在途编译线程（占线门——活的）
        self._signed = set()            # 本话语链已成功动词键（拒后重编不重复签）
        self._can_query = bool(self._skill_card())
        self._stream_open = False       # omp 流式回显段（打字机）
        self._pending = None            # 在途话语（看门狗防双触发）
        self._watch = None
        self._sign_plan = []            # 签字链待执行动词（后台逐条）
        self._sign_failed_list = []
        from PyQt6.QtWidgets import (QLineEdit, QTextBrowser, QVBoxLayout)
        lay = QVBoxLayout(self)
        self.log = QTextBrowser()
        self.log.setObjectName("chatLog")
        lay.addWidget(self.log)
        self.ed = QLineEdit()
        self.ed.setObjectName("chatInput")
        self.ed.setPlaceholderText("话语即签字（101号）——发送即执行，无确认")
        self.ed.returnPressed.connect(self.send)
        lay.addWidget(self.ed)
        self._say("对话", f"案卷闭包已载入（类子图＋全部方法声明＋案卷现状）；"
                         f"主体={principal['主体值']}。话语即签字："
                         f"发送即执行，执行后回显与账对照。会话仅内存，关闭即散。"
                         + ("" if self._can_query else
                            " 本树无《API手艺》卡——查询模式不可用（快照问答）。"))

    def _skill_card(self):
        """老子手艺门（101号 §3·presence-based）：API手艺.md 卡在=查询环
        可用（老师傅），无卡=快照问答——零第二登记。"""
        return self.parent()._laozi_skill()

    # ── 收发 ─────────────────────────────────────────────
    def _say(self, who, text):
        self._hist.append((who, text))
        import html as _h
        # QTextBrowser 按 HTML 渲染——裸 \n 被当空白折叠，多行回复挤成
        # 一段；转义后换行须显式成 <br>（8-20 用户实证「回复没有换行」）。
        self.log.append(f"<b>{who}：</b>"
                        + _h.escape(text).replace("\n", "<br>"))
        sb = self.log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _spawn(self, fn, on_done):
        """后台执行（_FnThread）——UI 线程零阻塞：api_write/api_query 的
        阻塞 subprocess 一律走此（真 fire 数分钟不冻窗——8-20 用户实证
        排队连接后主线程 subprocess 的冻窗面）。结果经闭包回传+done 信号
        回 UI 线程；异常时 on_done(None)。"""
        box = []

        def work():
            try:
                box.append(fn())
            except Exception:
                pass                     # _FnThread 兜底发故障串；box 空=失败
        th = _FnThread(work)
        th.done.connect(lambda _t: on_done(box[0] if box else None))
        ex = self.parent()
        if not hasattr(ex, "_chat_threads"):
            ex._chat_threads = []
        ex._chat_threads = [t for t in ex._chat_threads
                            if t.isRunning()] + [th]
        self._thread = th                # 占线门追在途
        th.start()

    def send(self):
        speech = self.ed.text().strip()
        if not speech:
            return
        if (self._thread and self._thread.isRunning()) \
                or self._pending is not None:
            self._say("对话", "（编译在途，请等上一句说完——串行即审计序）")
            return
        self._say("我", speech)
        self.ed.clear()
        self._round = 0
        self._signed = set()
        self._compile(speech)

    # ── 闭包与编译（每条话语从树重组装——定理 C 可重放）──
    def _closure(self):
        return chat_closure(self.root, self.croot, self.case)

    def _compile(self, speech):
        proto = CHAT_PROTO.replace("{principal}", self.principal["主体值"])
        if not self._can_query:
            proto += "\n- 本树无《API手艺》卡：查询模式不可用——以闭包作答或签变迁。"
        hist = "\n".join(
            f"[{w}] {t[:8000] if w == '查' else t[:1500]}"
            for w, t in self._hist[-12:])
        prompt = (proto + f"\n【案卷】{os.path.basename(self.croot)}/{self.case}"
                          f"（案卷号：{self.case}）\n【案卷闭包】\n"
                  + self._closure()
                  + f"\n\n【会话转录】\n{hist}\n\n【用户话语】{speech}")
        self._pending = speech
        self._stream_open = False
        self._watch = QTimer(self)
        self._watch.setSingleShot(True)
        self._watch.timeout.connect(lambda: self._watch_fire(speech))
        self._watch.start(600000)         # 流式车道卡死看门狗
        # 同步车道（桩/omp 占线分支）在调用内就完成整条链——_spawn 已把
        # _thread 设成链首线程，此处只在拿到真线程时才覆写（8-20 对抗
        # 验收：无条件覆写=占线门在 fire 链飞行中误开窗）。
        th = self.parent()._dialog_llm(
            prompt, self._on_model_done, speech,
            on_delta=self._stream_delta)
        if th is not None:
            self._thread = th

    def _on_model_done(self, speech, reply):
        if self._watch:
            self._watch.stop()
        streamed = self._stream_open
        self._pending = None
        self._on_model(speech, reply, streamed=streamed)

    def _watch_fire(self, speech):
        if self._pending is None:
            return                        # 已收尾（迟到的看门狗）
        self._pending = None
        if self._watch:
            self._watch.stop()
        self._stream_close()
        self.parent()._omp_rpc_reset()
        self._say("拒", "编译超时（600s）——omp 车道已重启，请重试（零副作用）")

    def _stream_delta(self, d):
        """omp rpc 流式回显：text_delta 逐帧打进日志（打字机）。"""
        import html as _h
        if not self._stream_open:
            self._stream_open = True
            self.log.append("<b>对话（流式）：</b>")
        from PyQt6.QtGui import QTextCursor
        self.log.moveCursor(QTextCursor.MoveOperation.End)
        self.log.insertHtml(_h.escape(d).replace("\n", "<br>"))

    def _stream_close(self):
        if self._stream_open:
            self._stream_open = False
            self.log.append("<br>")

    def _on_model(self, speech, reply, streamed=False):
        try:
            self._dispatch(speech, reply, streamed=streamed)
        except Exception as e:            # 槽内未捕获＝qFatal 整窗死——兜住
            self._say("拒", f"信封处理故障（零副作用未执行）：{e}")

    def _dispatch(self, speech, reply, streamed=False):
        env = _parse_envelope(reply)
        if env is None:                      # 非信封＝普通回答
            self._stream_close()
            if streamed:
                self._hist.append(("对话", (reply or "").strip()))  # 已流式显示
            else:
                self._say("对话", (reply or "").strip()[:4000])
            return
        if not isinstance(env, dict):
            self._say("拒", "信封不是对象——编译失败，请换个说法")
            return
        if env.get("模式") == "查询":
            reads = env.get("读桥")
            if not isinstance(reads, list):
                self._say("拒", "「读桥」不是数组——编译失败")
                return
            self._run_reads(speech, reads)
        elif env.get("模式") == "签字":
            verbs = env.get("动词序列")
            if not isinstance(verbs, list):
                self._say("拒", "「动词序列」不是数组——编译失败")
                return
            self._exec_sign(speech, verbs)
        elif env.get("模式") == "起草":
            if not isinstance(env.get("草稿"), list):
                self._say("拒", "「草稿」不是数组——编译失败")
                return
            self._exec_draft(speech, env)
        else:
            self._say("对话", "【拒】信封缺「模式」——编译失败，请换个说法")

    # ── 查询环（复用【查】工具环：api_query 白名单，≤5 轮；后台执行）──
    def _run_reads(self, speech, reads):
        if not self._can_query:
            self._say("拒", "本树无《API手艺》卡——查询模式不可用（快照问答）")
            return
        self._round += 1
        if self._round > self.ROUNDS:
            self._say("对话", "【拒】查询环到限（5 轮）——请换窄问题")
            return
        plan = []
        for r in (reads or [])[:3]:
            if not isinstance(r, dict):
                self._say("拒", f"读桥条目不是对象：{r!r}")
                continue
            参数 = r.get("参数")
            args = _flags_of(参数 if isinstance(参数, dict) else {})
            if args is None:
                self._say("拒", "参数值不干净（含 / 或以 . 开头）——防注入拒")
                continue
            plan.append((str(r.get("动词") or ""), args))

        def work():
            return [core.api_query(self.root, v, a) for v, a in plan]

        def done(res):
            self._reads_done(speech, plan, res)
        self._spawn(work, done)

    def _reads_done(self, speech, plan, res):
        if res is None:
            self._say("拒", "读桥执行故障（零副作用）")
            return
        for (verb, args), (ok, text) in zip(plan, res):
            self._say("查", f"{verb} {' '.join(args)} → "
                            f"{'✓' if ok else '✗'} {text[:8000]}")
        self._compile(speech)                # 结果喂回再编译（答复或签字）

    # ── 签字（逐条后台执行、逐条入账；失败零副作用喂回）────
    def _exec_sign(self, speech, verbs):
        plan, failed = [], []
        for v in verbs[:5]:
            if not isinstance(v, dict):
                self._say("拒", f"动词条目不是对象：{v!r}")
                failed.append(str(v))
                continue
            verb = str(v.get("动词") or "")
            参数 = v.get("参数")
            if not isinstance(参数, dict):
                参数 = {}
            if verb != "advance" and not 参数.get("案卷号"):
                参数 = dict(参数, 案卷号=self.case)   # 协议缺省的机械化
            key = (verb, 参数.get("任务", ""), 参数.get("案卷号", ""))
            if key in self._signed and verb != "draft":
                continue                    # 拒后重编不重复签已成功动词
                                                # （draft 除外：改稿重起草
                                                #  是合法循环，不去重）
            if verb not in core.API_WRITE_VERBS:
                self._say("拒", f"{verb} 不在签字面"
                                "（fire/settle/advance/draft）——未执行，账未动")
                failed.append(verb)
                continue
            args = _flags_of(参数)
            if args is None:
                self._say("拒", "参数值不干净（含 / 或以 . 开头）——防注入拒")
                failed.append(verb)
                continue
            payload = None
            if verb == "draft":             # 柜员的手：草稿经 stdin 载荷
                草稿 = [d for d in (参数.get("草稿") or [])
                        if isinstance(d, dict)]
                if not 草稿 or len(草稿) > 20:
                    self._say("拒", "draft 条目须带 1–20 条草稿——编译失败")
                    failed.append(verb)
                    continue
                payload = json.dumps(草稿, ensure_ascii=False)
            plan.append((verb, args, 参数, key, payload))
        if not plan:                         # 全非法：无需后台，直接收口
            self._sign_wrap(speech, failed)
            return
        self._sign_plan = plan               # 合法动词：后台链式逐条执行
        self._sign_failed_list = failed
        self._sign_step(speech)

    def _sign_step(self, speech):
        if not self._sign_plan:
            self._sign_wrap(speech, self._sign_failed_list)
            return
        verb, args, 参数, key, payload = self._sign_plan.pop(0)
        a = list(args)
        if verb != "draft":                 # 签字署登录主体＋记意图；draft
            a += ["--executor", self.principal["主体值"],   # 零入账无署名
                  "--intent", speech]

        def work():
            return core.api_write(self.root, verb, a, stdin_text=payload)
        self._spawn(work, lambda res: self._sign_done(
            speech, verb, 参数, key, res))

    def _sign_done(self, speech, verb, 参数, key, res):
        if res is None:
            self._say("拒", "写桥执行故障（本轮中断，请重试）")
            self._sign_failed_list.append(verb)
            self._sign_wrap(speech, self._sign_failed_list)
            return
        ok, text = res
        tail = ("✓ 已落盘（零入账）" if ok and verb == "draft" else
                "✓ 已入账" if ok else "✗ 被拒（零副作用）")
        self._say("签字" if ok else "拒",
                  f"说了「{speech}」→ {verb} {参数.get('任务', '')}"
                  f" 案卷={参数.get('案卷号', '（类级）')}"
                  f"：{tail}\n{text[:1200]}")
        if ok:
            self._signed.add(key)
        else:
            self._sign_failed_list.append(verb)
        self._sign_step(speech)

    def _sign_wrap(self, speech, failed):
        if not failed:
            return                            # 全签完：回显即对照，终态
        self._round += 1
        if self._round <= self.ROUNDS:
            self._compile(speech)             # 拒因喂回继续对话
        else:
            self._say("对话", "【拒】编译环到限（5 轮）仍有失败——请人过目")

    # ── 起草车道（103号 审批入图：柜员的手）────────────────
    # draft 落案卷（零入账）→ 蓝起草站自动点火（引擎产正式草稿，账记
    # 意图=话语/引擎=车道/执行者=站声明 agent）→ 读回案卷草稿回显 →
    # 等人批（绿审批站只 settle——顾客的签字）。绿站任务=只落草稿不点火。
    def _exec_draft(self, speech, env):
        任务 = str(env.get("任务") or "").strip()
        if 任务.endswith("/任务.md"):
            任务 = 任务[:-len("/任务.md")]
        if not 任务:
            self._say("拒", "起草信封缺「任务」（方法目录）——编译失败")
            return
        case = str(env.get("案卷号") or self.case)
        if "/" in case or case.startswith("."):
            self._say("拒", f"案卷号不干净：{case!r}——防注入拒")
            return
        tdir = os.path.join(self.root, 任务)
        if not os.path.isfile(os.path.join(tdir, "任务.md")):
            self._say("拒", f"不是可识别的方法目录：{任务}——起草未执行")
            return
        草稿 = [d for d in env.get("草稿") if isinstance(d, dict)][:20]
        if not 草稿:
            self._say("拒", "「草稿」无合法条目——编译失败")
            return
        payload = json.dumps(草稿, ensure_ascii=False)
        plan = [("draft", ["--task", 任务, "--case", case], payload)]
        if core.task_kind(tdir) != "绿":      # 蓝/红站：引擎自己点火起草
            plan.append(("fire",
                         ["--task", 任务, "--case", case,
                          "--engine", self.parent().cb_engine.currentData(),
                          "--intent", speech], None))
        self._draft_meta = (speech, 任务, case, tdir, len(plan) > 1, 草稿)
        self._draft_plan = plan
        self._draft_step()

    def _draft_step(self):
        if not getattr(self, "_draft_plan", None):
            self._draft_echo()
            return
        verb, args, payload = self._draft_plan.pop(0)

        def work():
            return core.api_write(self.root, verb, args, stdin_text=payload)
        self._spawn(work, lambda res: self._draft_done(verb, res))

    def _draft_done(self, verb, res):
        if res is None:
            self._say("拒", f"{verb} 执行故障（本轮中断，请重试）")
            self._draft_plan = []
            return
        ok, text = res
        self._say("起草" if ok and verb == "draft" else
                  ("点火" if ok else "拒"),
                  f"{verb}：{'✓' if ok else '✗（零副作用）'}\n{text[:1200]}")
        if not ok:
            self._draft_plan = []
            return
        self._draft_step()

    def _draft_echo(self):
        """回显案卷草稿给人过目（银行柜台：柜员写完递出来看）。"""
        _speech, _任务, case, tdir, fire_it, 草稿 = self._draft_meta
        shown, shown_n = set(), 0
        cdir = os.path.join(self.root, "实例",
                            os.path.basename(self.croot), case)
        if fire_it:                          # 蓝站产物（申请/域.md 草稿）
            try:
                task = core.eng.load_task(tdir, self.root, case=case)
            except SystemExit:
                task = None
            for r in (task or {}).get("rows", []):
                p = r.get("path")
                if r.get("kind") != "产物" or not p \
                        or not os.path.isfile(p) or not str(p).startswith(cdir):
                    continue
                body = open(p, encoding="utf-8", errors="replace").read()
                self._say("稿", f"《{os.path.basename(p)}》（案卷草稿）\n"
                                f"{body[:1200]}")
                shown.add(os.path.realpath(p))
                shown_n += 1
        # 案卷材料草稿同样递出来（8-20 用户实证三报「回复没有换行」的实体：
        # 绿站+材料起草零回显，人只能去流式 JSON 团里读 \n 字面量——过目
        # 诺言落空；产品槽落位形（树内全路径）从树根解析，与引擎落点同源）
        for d in 草稿[:5]:
            rel = str(d.get("路径") or "")
            if not rel or rel.startswith(("/", "\\")):
                continue
            for base in (cdir, self.root):
                p = os.path.join(base, *rel.replace("\\", "/").split("/"))
                rp = os.path.realpath(p)
                if rp in shown or not os.path.isfile(p):
                    continue
                shown.add(rp)
                body = open(p, encoding="utf-8", errors="replace").read()
                self._say("稿", f"《{os.path.basename(p)}》（案卷材料）\n"
                                f"{body[:1200]}")
                shown_n += 1
        if len(草稿) > 5:
            self._say("稿", f"（另有 {len(草稿) - 5} 份草稿已落案卷，此处略）")
            shown_n += len(草稿) - 5
        if not shown_n:
            self._say("对话", "草稿已落案卷（零入账）。")
        self._say("对话", "请过目：说「批准」即落位办结（意图=你的话语）；"
                         "要改就说改哪里。")


def _flags_of(参数):
    """参数对象→argv 旗标（任务/案卷号/状态三个已知键）。任务路径合法含 /
    （越界由 api _in_root 把关）；案卷号/状态须单段干净标量——含 / 或以 .
    开头一律整体拒（防路径注入写出树外），返回 None。"""
    args = []
    for key, flag in (("任务", "--task"), ("案卷号", "--case"),
                      ("状态", "--status")):
        v = 参数.get(key)
        if isinstance(v, str) and v.strip():
            v = v.strip()
            if key == "任务" and v.endswith("/任务.md"):
                v = v[:-len("/任务.md")]   # 容错归一：文件路径→方法目录
            if key != "任务" and ("/" in v or v.startswith(".")):
                return None
            args += [flag, v]
    return args


def _parse_envelope(text):
    """信封解析：剥代码围栏后取首尾花括号间尝试 json——失败=普通回答。
    信封外还有正文文字＝散文引用示例，不当信封（防「举例被执行」）。"""
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.strip("`").lstrip("json").strip()
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j <= i:
        return None
    if t[:i].strip() or t[j + 1:].strip():
        return None                       # 花括号外有话＝散文，不是信封
    try:
        import json as _json
        return _json.loads(t[i:j + 1])
    except ValueError:
        return None


def chat_closure(root, croot, case, cap=16384):
    """案卷闭包（101号 §4·stage1）：类子图（类.md/schema.md/知识/）＋
    全部方法 任务.md（含执行者/校验/弧声明——签字面的地形）＋案卷目录
    现状；文件截 16KB（引擎现常量精神），纯机械零 LLM。"""
    out = []
    case_dir = os.path.join(root, "实例", os.path.basename(croot), case)

    def rd(p, tag):
        try:
            t = open(p, encoding="utf-8", errors="replace").read(cap)
        except OSError:
            return
        out.append(f"─── {tag} ───\n{t}"
                   + ("…（截断）" if len(t) == cap else ""))

    for name in ("类.md", "schema.md"):
        p = os.path.join(croot, name)
        if os.path.isfile(p):
            rd(p, os.path.relpath(p, root))
    kdir = os.path.join(croot, "知识")
    if os.path.isdir(kdir):
        for f in sorted(os.listdir(kdir)):
            if f.endswith(".md"):
                rd(os.path.join(kdir, f), os.path.relpath(
                    os.path.join(kdir, f), root))
    mdir = os.path.join(croot, "方法")
    if os.path.isdir(mdir):
        for m in sorted(os.listdir(mdir)):
            p = os.path.join(mdir, m, "任务.md")
            if os.path.isfile(p):
                # 标签＝方法目录（写桥 --task 要的形状），不带 /任务.md
                # 后缀——模型照抄标签即合法，防「文件路径当任务目录」
                rd(p, os.path.relpath(os.path.dirname(p), root))
    if os.path.isdir(case_dir):
        for r, ds, fs in os.walk(case_dir):
            ds[:] = [d for d in ds if not d.startswith((".", "__"))]
            for f in sorted(fs):
                p = os.path.join(r, f)
                rd(p, os.path.relpath(p, root))
    return "\n\n".join(out)[:200000]


class Explorer(QMainWindow):
    def __init__(self, root):
        super().__init__()
        self.root = os.path.abspath(root)
        self.setWindowTitle(f"i3dna explorer — {os.path.basename(self.root)}")
        self.resize(1280, 800)
        self.items_by_path = {}
        self.hl_items = []
        self._runs = {}              # key -> ctx（多实例并行：一实例一进程一流）
        self._run_seq = 0
        self._guard_detail = False
        os.environ.pop("I3DNA_CASE", None)   # 实例视角已退役，不让残留 env 暗补
        self._principal = None            # 会话主体（登录后）：编号/姓名/袋/主体值
        # 启动默认主体（8-20 guci 偏好）：树里有 刘亦菲 档案即默认登录——
        # 免每次手输。登录=身份不是密码门，故免验凭证；也不记登录日志
        # （journal 记的是带凭证核验的认证事件，免得每次启动刷一笔）。
        # 无此档案的树（trade-v4 等）保持未登录，登录对话框照旧。

        tb = QToolBar()
        self.addToolBar(tb)
        tb.setIconSize(QSize(32, 32))
        _tb_font = QFont(); _tb_font.setPointSize(15); _tb_font.setBold(True)
        tb.setFont(_tb_font)
        _lbl = QLabel(f" 包根: {os.path.basename(self.root)}  ")
        _lbl.setFont(_tb_font)
        _lbl.setToolTip(self.root)
        tb.addWidget(_lbl)
        _lbl = QLabel(" 引擎:"); _lbl.setFont(_tb_font)
        tb.addWidget(_lbl)
        self.cb_engine = QComboBox()
        self.cb_engine.setObjectName("cbEngine")
        for label, cmd in (
                # 默认=ACP 款 + high 档（8-19 裁定）：死因可读（stopReason 进
                # 过程摘要），引擎在思考烧穿 128K 共池时自动降档重试
                # （THINKING_LADDER high→low）——CLI 款看不到 stopReason 只会
                # 盲重试再烧一遍（8-19 K1 复盘，max 档两跑皆烧穿）
                ("GLM 5.3（OMP·ACP）", "acp:omp --thinking high acp"),
                ("GLM 5.3（OMP）", "omp -p --no-session --thinking high @{prompt_file}"),
                ("DeepSeek V4 Flash",
                 "~/start-claude-deepseek.sh -p --model deepseek-v4-flash"),
                ("DeepSeek V4 Pro", "~/start-claude-deepseek.sh -p")):
            self.cb_engine.addItem(label, cmd)
        tb.addWidget(self.cb_engine)
        self.cb_sandbox = QCheckBox("沙盒")
        self.cb_sandbox.setFont(_tb_font)
        self.cb_sandbox.setChecked(False)
        self.cb_sandbox.setObjectName("cbSandbox")
        tb.addWidget(self.cb_sandbox)
        _lbl = QLabel(" 视角:"); _lbl.setFont(_tb_font)
        tb.addWidget(_lbl)
        self.cb_view = QComboBox()
        self.cb_view.setFont(_tb_font)
        self.cb_view.setObjectName("cbView")
        self.cb_view.addItem("目录", "目录")
        self.cb_view.addItem("场所", "场所")
        self.cb_view.currentIndexChanged.connect(self.refresh)
        tb.addWidget(self.cb_view)
        self.lbl_principal = QPushButton(" 主体: 未登录  ")
        self.lbl_principal.setObjectName("lblPrincipal")
        self.lbl_principal.setFlat(True)
        self.lbl_principal.setFont(_tb_font)
        self.lbl_principal.setToolTip("登录/切换主体（凭证=人员档案）")
        self.lbl_principal.clicked.connect(self.do_login)
        tb.addWidget(self.lbl_principal)
        hit = core.find_principal(self.root, "刘亦菲")
        if hit:
            self._set_principal(hit)       # 默认主体亮牌（工具栏即刻可见）
        # 动作按钮独立一行——单行放不下时「推进」会被藏进 >> 溢出菜单
        self.addToolBarBreak()
        tb2 = QToolBar()
        self.addToolBar(tb2)
        tb2.setFont(_tb_font)
        for label, slot in (("刷新", self.refresh),
                            ("全树对账", self.show_lint),
                            ("修复提案", self.show_fix_proposals),
                            ("覆盖报告", self.show_coverage),
                            ("登录", self.do_login),
                            ("推进", self.do_converge),
                            ("终止", self.do_stop)):
            act = QAction(label, self)
            act.setObjectName(f"act{label}")
            act.setFont(_tb_font)
            act.triggered.connect(slot)
            tb2.addAction(act)

        self.tree = QTreeView()
        self.tree.setObjectName("tree")
        self.tree.setHeaderHidden(True)
        _tree_font = QFont(); _tree_font.setPointSize(14); self.tree.setFont(_tree_font)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.on_menu)
        self.detail = QTextBrowser()
        self.detail.setObjectName("detail")
        self.detail.setOpenExternalLinks(False)
        self.detail.setOpenLinks(False)
        self.detail.anchorClicked.connect(self.on_anchor)
        # 编辑器页（真源文本：需求/诉求/DSL——改完保存立即体现在过期⟳与新一轮点火里）
        self.editor = QPlainTextEdit()
        self.editor.setObjectName("editor")
        self.ed_label = QLabel()
        self.ed_label.setObjectName("edLabel")
        btn_ghost = QPushButton("代笔")
        btn_ghost.setObjectName("btnGhost")
        btn_ghost.clicked.connect(self.ghostwrite)
        btn_save = QPushButton("保存")
        btn_save.setObjectName("btnSave")
        btn_save.clicked.connect(self._save_editor)
        # 通用界面唯一确认按钮:办理绿任务时现身——确认=保存交付+销单+入账。
        # 通用界面=聊天收参+编辑器,领域无关(澄清单/录入产品/写审批意见同一条面)。
        self.btn_confirm = QPushButton("✅ 办结入账")
        self.btn_confirm.setObjectName("btnConfirm")
        self.btn_confirm.setVisible(False)
        self.btn_confirm.clicked.connect(self.confirm_work)
        ed_bar = QHBoxLayout()
        ed_bar.addWidget(self.ed_label)
        ed_bar.addStretch()
        ed_bar.addWidget(btn_ghost)
        ed_bar.addWidget(self.btn_confirm)
        ed_bar.addWidget(btn_save)
        # 办单助手带（弧驱动：本槽 → 目标 schema 键覆盖一览,机械推导零 LLM）
        self.assist_label = QLabel("")
        self.assist_label.setObjectName("assistLabel")
        self.assist_label.setWordWrap(True)
        self.assist_label.setStyleSheet(
            "color:#546e7a; background:#eceff1; padding:4px; border-radius:3px;")
        # 办单对话区（agent 按 schema 聊天收参——红任务结构化 schema/
        # 蓝任务自然语言 schema 都走输入弧描述;写好按【写好】协议回填编辑器）
        self.assist_chat = QTextBrowser()
        self.assist_chat.setObjectName("assistChat")
        self.assist_chat.setMaximumHeight(150)
        self.assist_chat.setOpenExternalLinks(False)
        self.assist_input = QLineEdit()
        self.assist_input.setObjectName("assistInput")
        self.assist_input.setPlaceholderText(
            "跟办单助手聊:口语说意图,它按 schema 收参;齐了它写好申请给你过目")
        self.assist_input.returnPressed.connect(self.assist_talk)
        self.assist_proc = None
        self._assist_log = []
        ed_page = QWidget()
        ed_lay = QVBoxLayout(ed_page)
        ed_lay.addLayout(ed_bar)
        ed_lay.addWidget(self.assist_label)
        ed_lay.addWidget(self.editor)
        ed_lay.addWidget(self.assist_chat)
        ed_lay.addWidget(self.assist_input)
        # 详情区：QTabWidget（用户可见标签页）—— 内容 / 执行流
        # "内容"页内部仍是 QStackedWidget（浏览/编辑互斥切换）
        self.detail_tabs = QTabWidget()
        self.detail_tabs.setObjectName("detailTabs")
        self.stack = QStackedWidget()
        self.stack.setObjectName("stack")
        self.stack.addWidget(self.detail)      # 内容页内 0 = 浏览
        self.stack.addWidget(ed_page)          # 内容页内 1 = 编辑
        content_page = QWidget()
        content_lay = QVBoxLayout(content_page)
        content_lay.setContentsMargins(0, 0, 0, 0)
        content_lay.addWidget(self.stack)
        self.detail_tabs.addTab(content_page, "内容")
        # 执行流页（会话内存，不持久化）：一实例一页签，并行推进各看各的流
        self._stream_pages: dict = {}    # case(None=无实例包) -> {view, buf}
        self.stream_tabs = QTabWidget()
        self.stream_tabs.setObjectName("streamTabs")
        btn_clr = QPushButton("清空当前实例")
        btn_clr.clicked.connect(self._clear_stream)
        stream_bar = QHBoxLayout()
        stream_bar.addWidget(QLabel("执行流（一实例一页，点火/推进实时输出）"))
        stream_bar.addStretch()
        stream_bar.addWidget(btn_clr)
        stream_page = QWidget()
        stream_lay = QVBoxLayout(stream_page)
        stream_lay.setContentsMargins(0, 0, 0, 0)
        stream_lay.addLayout(stream_bar)
        stream_lay.addWidget(self.stream_tabs)
        self.detail_tabs.addTab(stream_page, "执行流")
        # 老子页（独立标签，不与内容/执行流争面板）
        self.chat_view = QTextBrowser()
        self.chat_view.setObjectName("laoziView")
        self.chat_view.setOpenExternalLinks(False)
        self.detail_tabs.addTab(self.chat_view, "老子")
        sp = QSplitter()
        sp.addWidget(self.tree)
        sp.addWidget(self.detail_tabs)
        sp.setSizes([560, 720])
        sp.setStretchFactor(0, 0)          # 树列:内容优先,不抢宽
        sp.setStretchFactor(1, 1)          # 内容列:吃剩余空间
        sp.setCollapsible(0, False)        # 树列不许拖没
        sp.setCollapsible(1, False)
        self.tree.setMinimumWidth(280)     # 但保证能拉宽(拖柄可用)
        # 工作流页：由参数表的输入/输出弧推导的二部图（transition=任务，place=制品）
        self.wf_view = WorkflowView(self._wf_jump, self._graph_menu)
        self.cb_ptr = QCheckBox("显示指针库所（索引文件）")
        self.cb_ptr.setChecked(False)
        self.cb_ptr.toggled.connect(lambda _: self._build_workflow())
        wf_bar = QHBoxLayout()
        wf_bar.addWidget(QLabel("视图:"))
        self.cb_wfpkg = QComboBox()
        # 不预置「全部」：让 _build_workflow 首次填表时默认落到第一个类，
        # 否则预置的「全部」会被当成"当前选择"保留，永远默认总览（多类堆叠）。
        self.cb_wfpkg.currentIndexChanged.connect(lambda _: self._build_workflow())
        wf_bar.addWidget(self.cb_wfpkg)
        self.cb_flow = QCheckBox("任务流程")
        self.cb_flow.setChecked(True)          # 默认折叠制品，直连微任务（更直观）
        self.cb_flow.setToolTip("勾选=只画微任务、箭头直连（材料名标在线上）；\n"
                                "取消=画完整的二部图（微任务+材料两色节点）")
        self.cb_flow.toggled.connect(lambda _: self._build_workflow())
        wf_bar.addWidget(self.cb_flow)
        for label, fn in (("＋", lambda: self.wf_view.zoom(1.25)),
                          ("－", lambda: self.wf_view.zoom(0.8)),
                          ("全景", lambda: self.wf_view.fit_all(0.0)),
                          ("1:1", lambda: (self.wf_view.resetTransform()))):
            b = QPushButton(label)
            b.setMaximumWidth(52)
            b.clicked.connect(lambda _, f=fn: f())
            wf_bar.addWidget(b)
        wf_bar.addWidget(self.cb_ptr)
        hint = QLabel("　滚轮=缩放 · 拖拽=平移 · 双击节点=跳到目录树")
        hint.setStyleSheet("color:#78909c")
        wf_bar.addWidget(hint)
        wf_bar.addStretch()
        wf_page = QWidget()
        wf_lay = QVBoxLayout(wf_page)
        wf_lay.setContentsMargins(0, 0, 0, 0)
        wf_lay.addLayout(wf_bar)
        wf_lay.addWidget(self.wf_view)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        self.tabs.addTab(sp, "目录")
        self.tabs.addTab(wf_page, "工作流")
        # 老子聊天条：结构化现状注入上下文，答案=三五行投影（核只读 summary）
        self.chat_input = QLineEdit()
        self.chat_input.setObjectName("laoziInput")
        self.chat_input.setPlaceholderText(
            "问老子：现在什么状态？上一炮测了什么？该干嘛？（回车发送）")
        self.chat_input.returnPressed.connect(self.ask_laozi)
        btn_ask = QPushButton("问老子")
        btn_ask.clicked.connect(self.ask_laozi)
        chat_row = QHBoxLayout()
        chat_row.addWidget(self.chat_input)
        chat_row.addWidget(btn_ask)
        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.tabs)
        lay.addLayout(chat_row)
        self.setCentralWidget(central)
        self.chat_proc = None
        self.ghost_proc = None
        self._chat_log = []
        self._laozi_rounds = 0
        self._hb = QTimer(self)
        self._hb.setInterval(5000)
        self._hb.timeout.connect(self._heartbeat)

        self.refresh()
        self._build_menu()
        core.recent_roots_save(self.root)     # 打开即入最近清单

    # ── 文件菜单：打开目录 / 打开最近的目录 ─────────────────
    def _build_menu(self):
        mb = self.menuBar()
        文件 = mb.addMenu("文件")
        act = QAction("打开目录…", self)
        act.triggered.connect(self._menu_open_dir)
        文件.addAction(act)
        self.recent_menu = 文件.addMenu("打开最近的目录")
        self.recent_menu.aboutToShow.connect(self._fill_recent_menu)
        文件.addSeparator()
        actq = QAction("退出", self)
        actq.triggered.connect(self.close)
        文件.addAction(actq)

    def _menu_open_dir(self):
        d = QFileDialog.getExistingDirectory(self, "打开目录", self.root)
        if d:
            self.open_root(d)

    def _fill_recent_menu(self):
        self.recent_menu.clear()
        roots = core.recent_roots_load()
        if not roots:
            a = QAction("（无最近目录）", self)
            a.setEnabled(False)
            self.recent_menu.addAction(a)
            return
        for r in roots:
            a = QAction(r, self)
            a.triggered.connect(lambda _=False, p=r: self.open_root(p))
            self.recent_menu.addAction(a)

    def open_root(self, path):
        """切换包根:换树、换标题、记最近、清旧状态(编辑/聊天/lint 缓存)。"""
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            return
        self.root = path
        self.setWindowTitle(f"i3dna explorer — {os.path.basename(path)}")
        self.lint_rep = None
        self._edit_path = None
        self._assist_log = []
        self._chat_log = []
        core.recent_roots_save(path)
        self.refresh()
        self.statusBar().showMessage(f"已打开 {path}")

    # ── 树构建与状态叠加 ────────────────────────────────────

    def refresh(self):
        self.items_by_path.clear()
        self.hl_items.clear()
        model = QStandardItemModel()
        self.model = model
        self.tasks = {os.path.abspath(d): k
                      for d, k in eng.find_tasks(self.root).items()}
        # 全实例并发代数：操作（推进/点火）扇出到每个实例，各自独立执行流页
        self.cases = self._all_cases()
        self._reconcile_stream_tabs()
        if self.cb_view.currentData() == "场所":
            root_item = self._build_place_tree()
        else:
            root_item = self._build_dir(self.root)
        model.appendRow(root_item)
        self.tree.setModel(model)
        self.tree.selectionModel().selectionChanged.connect(self.on_select)
        self.tree.expandToDepth(3)
        self.statusBar().showMessage(
            f"微任务 {len(self.tasks)} 个 · 刷新于 {datetime.now().strftime('%H:%M:%S')}")
        self._overlay_status()      # 在基础消息之后追加「对账:N 错 M 警」
        self._build_workflow()

    def _build_place_tree(self):
        """场所视角（运行时投影面，ARCHITECTURE §4）：企业（根场所）→
        部门场所（域）→ 实例架（域内类集）→ 实例。节点全带真路径
        （ROLE_PATH），选中/右键菜单/工位与目录视角同源；类定义面回
        目录视角看——场所只组织实例（Bean 平铺不搬目录的另一半）。"""
        top = QStandardItem("🏢 企业（根场所）")
        top.setEditable(False)
        top.setData(self.root, ROLE_PATH)
        top.setData("dir", ROLE_TYPE)
        self.items_by_path[self.root] = top
        库 = os.path.join(self.root, "实例")
        域内类 = set()
        for 名, 是根, 类名们, 种, 锚 in core.场所拓扑(self.root):
            if 是根:
                continue
            域内类 |= set(类名们)
            icon, tag = (("🧩", "装配场所") if 种 == "声明"
                         else ("🏭", "部门场所"))
            node = QStandardItem(f"{icon} {名}（{tag}）")
            node.setEditable(False)
            node.setData(锚, ROLE_PATH)
            node.setData("file" if os.path.isfile(锚) else "dir", ROLE_TYPE)
            self.items_by_path[锚] = node
            for cn in 类名们:
                架 = os.path.join(库, cn)
                if os.path.isdir(架):
                    node.appendRow(self._build_dir(架))
            top.appendRow(node)
        for e in (sorted(os.listdir(库)) if os.path.isdir(库) else []):
            p = os.path.join(库, e)
            if os.path.isdir(p) and e not in 域内类 \
                    and not e.startswith((".", "__")):
                top.appendRow(self._build_dir(p))       # 域外架（部门/游离类）
        for d in ("消息", "知识", "状态"):
            p = os.path.join(self.root, d)
            if os.path.isdir(p):
                top.appendRow(self._build_dir(p))       # 企业共享语义面
        return top

    def _build_dir(self, path):
        name = os.path.basename(path) or path
        if name == "实例":
            name = "案卷（实例库）"
        kind = eng.store.class_kind(path)          # 类.md 元声明：实体|过程
        if kind == "实体":
            name = "▣ " + name + "【实体】"      # 实体=填充方块（数据之家）
        elif kind == "过程":
            name = "▶ " + name + "【过程】"      # 过程=三角（动作/转换）
        if os.path.basename(path) == "档案袋":
            name = "▤ 档案袋（实体货架）"
        if os.path.basename(os.path.dirname(path)) == "档案袋":
            name = name + " ▤"
        item = QStandardItem(name)
        item.setEditable(False)
        item.setData(path, ROLE_PATH)
        if path in self.tasks:
            ntype = "task"
            c = task_color(path)
            item.setForeground(QBrush(c))
            item.setIcon(dot(c))
        elif any(f.endswith("索引文件.xlsx") and f.startswith("__")
                 for f in os.listdir(path)):
            ntype = "entity"
            item.setForeground(QBrush(C_ENTITY))
            item.setIcon(dot(C_ENTITY))
        else:
            ntype = "dir"
        if kind == "实体":
            item.setForeground(QBrush(C_ENTITY))
            if ntype == "dir":
                item.setIcon(dot(C_ENTITY))          # 实体类=绿点（数据之家）
        elif kind == "过程":
            if ntype == "dir":
                item.setIcon(dot(QColor("#ef6c00")))  # 过程类=橙点（动作）
        item.setData(ntype, ROLE_TYPE)
        self.items_by_path[path] = item
        try:
            entries = sorted(os.listdir(path))
        except OSError:
            entries = []
        for e in entries:
            if e.startswith(".") or e == "__pycache__":
                continue
            p = os.path.join(path, e)
            if os.path.isdir(p):
                item.appendRow(self._build_dir(p))
        for e in entries:
            p = os.path.join(path, e)
            if os.path.isfile(p) and not e.startswith("."):
                leaf = QStandardItem(e)
                leaf.setEditable(False)
                leaf.setForeground(QBrush(C_FILE))
                leaf.setData(p, ROLE_PATH)
                leaf.setData("file", ROLE_TYPE)
                self.items_by_path[p] = leaf
                item.appendRow(leaf)
        return item

    def _overlay_status(self):
        # 使能态 + 新鲜度（逐任务）；同时建 产物→生产任务 与 任务→输入 映射（拓扑序预警用）
        self.product_of, self.inputs_of, self.stale_map = {}, {}, {}
        self.task_rows, self.enabled_map = {}, {}
        for tdir in self.tasks:
            item = self.items_by_path.get(tdir)
            if item is None:
                continue
            sym = bool(eng.exec_entry(tdir))
            human = eng.get_value(os.path.join(tdir, "任务.md"), "执行者") == "人"
            tips = [f"微任务（{self.tasks[tdir]}族"
                    + ("·🧑 人工工位：引擎不自动点火，办结走 backfill" if human
                       else "·🔴 符号主义：点火跑执行程序" if sym
                       else "·🔵 联结主义：点火调 LLM")
                    + "）"]
            if human:
                item.setText(item.text().split(" 🧑")[0] + " 🧑")
            if sym:
                cstale = eng.compile_stale(tdir, self.root)
                if cstale:
                    item.setText(item.text() + " ⟳编译过期")
                    tips.append("⟳ 编译过期（依据在编译后变过）："
                                + "；".join(cstale) + "——现行程序照跑，重编译由人裁决")
            task = self._task_view(tdir)     # 受体视图：实例任务代入首个可解析实例
            if task is None:
                enabled, misses = False, ["无可解析受体（未实例化？）"]
            else:
                self.task_rows[tdir] = task["rows"]
                for r in task["rows"]:
                    if not r["path"]:
                        continue
                    if r["kind"] == "产物":
                        self.product_of[r["path"]] = tdir
                    else:
                        self.inputs_of.setdefault(tdir, []).append(r["path"])
                rows = eng.preflight_rows(task)
                enabled = rows[-1][4]
                self.enabled_map[tdir] = enabled
                misses = [f"{d} {n} {s}" for k, d, n, s, ok in rows[:-1]
                          if k == "输入" and not ok]
            if enabled:
                tips.append("✓ 使能")
            else:
                # 未使能=状态修饰,不盖范帱色:红/绿/蓝本色保留(图标演示不能骗人);
                # 图标换空心灰环,tooltip 说明缺什么
                item.setText(item.text().split(" ⚪")[0] + " ⚪未使能")
                item.setIcon(_ring(C_TASK_OFF))
                tips += ["✗ 未使能（范帱色保留,空心环=缺输入）"] + misses
            stale = self._stale_inputs(tdir)
            violated = self._violated_facts(tdir)
            self.stale_map[tdir] = bool(violated or stale)
            base = item.text().split(" ⟳")[0].split(" 🚫")[0]
            if violated:
                item.setText(base + " 🚫篡改")
                tips.append("🚫 事实件被篡改（审计红线，不重算，呈人裁决）："
                            + "；".join(violated))
            elif stale:
                item.setText(base + " ⟳")
                tips.append("⟳ 输入已变（相对上次点火记录）：" + "；".join(stale))
        # lint 悬空 ⛔
        rep = lint.lint_tree(self.root)
        self.lint_rep = rep
        self.statusBar().showMessage(
            self.statusBar().currentMessage()
            + f" · 对账: {len(rep.errors)} 错 {len(rep.warnings)} 警")
        by_item = {}
        for where, msg in rep.errors:
            fpart = where.split("#")[0].split("·")[0]
            p = os.path.join(self.root, fpart)
            it = self.items_by_path.get(p) or self.items_by_path.get(os.path.dirname(p))
            if it is not None:
                by_item.setdefault(id(it), (it, []))[1].append(f"{where}: {msg}")
        for it, msgs in by_item.values():
            if not it.text().endswith(" ⛔"):
                it.setText(it.text() + " ⛔")
            it.setToolTip((it.toolTip() + "\n" if it.toolTip() else "")
                          + "\n".join(msgs))

    def _violated_facts(self, tdir):
        return core.violated_facts(self.root, tdir)

    def _stale_inputs(self, tdir):
        return core.stale_inputs(self.root, tdir)

    # ── 选中：血缘高亮 + 详情 ───────────────────────────────

    def on_select(self, *_):
        if getattr(self, "_guard_detail", False):
            return
        for ctx in self._runs.values():       # 内容页在跑引擎子命令，用户想看别的
            if ctx["target"] == "detail":
                ctx["diverted"] = True
        for it in self.hl_items:
            it.setBackground(QBrush())
        self.hl_items.clear()
        item = self._current_item()
        if item is None:
            return
        path, ntype = item.data(ROLE_PATH), item.data(ROLE_TYPE)
        if ntype == "task":
            task = self._task_view(path)     # 血缘高亮走受体视图
            if task:
                for r in task["rows"]:
                    if not r["path"]:
                        continue
                    tgt = self.items_by_path.get(r["path"]) \
                        or self.items_by_path.get(os.path.dirname(r["path"]))
                    if tgt is not None:
                        tgt.setBackground(QBrush(
                            BG_OUT if r["kind"] == "产物" else BG_IN))
                        self.hl_items.append(tgt)
        self._render_node(item)

    def _current_item(self):
        idx = self.tree.currentIndex()
        return self.model.itemFromIndex(idx) if idx.isValid() else None

    def show_html(self, html):
        self.detail_tabs.setCurrentIndex(0)  # 外层切到"内容"标签
        self.stack.setCurrentIndex(0)        # 内容页内切到"浏览"
        self.detail.setHtml(html)

    def _open_editor(self, path):
        # 一文件一会话：换文件=新 session，对话记忆清零——助手无跨文件记忆，
        # context 全在目录树（弧/schema/类型文件），记忆是脏状态源。
        # 清完必须立即重渲染,否则旧 HTML 挂屏到下一条消息到达。
        # 换文件=脱离当前工位:解绑工单+隐藏确认按钮（通用界面归位普通编辑）。
        if getattr(self, "_edit_path", None) != path:
            self._assist_log = []
            self._render_assist_chat()
            self._work = None
            self.btn_confirm.setVisible(False)
        self.ed_label.setText(os.path.relpath(path, self.root))
        try:
            txt = open(path, encoding="utf-8", errors="replace").read()
        except FileNotFoundError:
            txt = ""        # 产物弧指向新文件（首办案卷）：开空稿，保存即落
        self.editor.setPlainText(txt)
        self._edit_path = path
        self.stack.setCurrentIndex(1)
        self.detail_tabs.setCurrentIndex(0)  # 确保外层在"内容"标签
        self._refresh_assist(path)
        if not getattr(self, "_ed_changed_bound", False):   # 只连一次:每次
            self._ed_changed_bound = True                   # 打开都 connect
            self.editor.textChanged.connect(               # 会累积重复回调
                lambda: self._refresh_assist(
                    getattr(self, "_edit_path", path)))
        # 空槽+有弧 → agent 自动开场亮牌（诱导式:不等用户先说）;
        # 工位开场由 open_work_ui 接管时压掉
        if not getattr(self, "_suppress_kick", False) \
                and not open(path, encoding="utf-8",
                             errors="replace").read().strip() \
                and core.slot_coverage(self.root, path):
            QTimer.singleShot(300, lambda: self.assist_kickoff(path))

    def _refresh_assist(self, path):
        """办单助手带（裁决:只有结构化 schema 才能机械化显示,自然语言 schema
        的唯一录入面是聊天 agent）。三层降格:
        - 无弧(非输入槽) → 自由编辑提示
        - 有弧但无 schema.md 键说明(自然语言 schema) → 让位聊天,不显示打勾
        - 有键说明(结构化 schema) → 键字面命中显示(非参数完整性判定:
          只对照文本是否出现键名,不猜语义;真判定在聊天 agent)。
        同义词等口语知识住 schema.md(领域自治),通用层零硬编码。"""
        cov = core.slot_coverage(self.root, path)
        if not cov:
            self.assist_label.setText(
                "办单助手：非任务输入槽，自由编辑。")
            return
        if not cov.get("schema_keys"):
            self.assist_label.setText(
                f"办单助手 ▸ 槽「{cov['input']}」喂给方法 "
                f"〔{os.path.basename(cov['task'])}〕——自然语言 schema,"
                "请在下方与助手对话收参（打勾不适用于非结构化）。")
            return
        text = self.editor.toPlainText()
        keys = cov["schema_keys"]
        defaults = cov.get("defaults") or {}
        hit, nohit = [], []
        for k in keys:
            (hit if k in text else nohit).append(k)
        for k in defaults:
            (hit if k in text else nohit).append(k + "（默认）")

        marks_h = " ".join(f"📄{k}" for k in hit) or "（无）"
        marks_n = " ".join(f"· {k}" for k in nohit)
        self.assist_label.setText(
            f"办单助手 ▸ 槽「{cov['input']}」→ 方法〔{os.path.basename(cov['task'])}〕"
            f" → 结构化 schema（{cov['target_class']}）\n"
            f"文本已出现：{marks_h}    未出现：{marks_n or '（全命中）'}"
            + ("    （键字面对照非完整性判定;未出现键播零值——知情不拦截）"
               if nohit else ""))
    def assist_kickoff(self, path):
        """诱导式开场：空槽时 agent 先亮牌（schema 键序/类型文件/常识要点）。"""
        self._assist_log = []
        self.assist_input.setText("（开场）亮牌：这份文档是什么、该收什么")
        self.assist_talk()
        self._assist_log[-1] = ("你", "〔开场:agent 主动亮牌〕")

    def assist_talk(self):
        """办单聊天：agent 读输入弧（自然语言 schema）+ 目标类 schema（结构化键）
        与用户口语收参;参数齐时按【写好】协议输出全文,程序截取回填编辑器。"""
        q = self.assist_input.text().strip()
        path = getattr(self, "_edit_path", None)
        if not q or not path:
            return
        _t = getattr(self, "_assist_thread", None)
        if _t is not None and _t.isRunning():
            self.statusBar().showMessage("助手在想上一条…")
            return
        self.assist_input.clear()
        self._assist_log.append(("你", q))
        self._render_assist_chat("…")
        cov = core.slot_coverage(self.root, path)
        # 双形态诱导引擎:结构化→schema诱导;无结构化→常识诱导(需求澄清单)
        if cov and cov.get("schema_keys"):
            guide = (
                f"[诱导模式·schema] 目标类「{cov['target_class']}」键："
                + "、".join(cov["schema_keys"])
                + (f"；默认：{cov['defaults']}" if cov.get("defaults") else "")
                + "。按键序诱导:逐键问缺的,枚举键给选项,有默认值的说明可跳过。")
        else:
            arc_desc = (cov or {}).get("input") or os.path.basename(path)
            # 无键说明 → 类型声明查找链(core.find_type_file:显式类型→引擎家族链)
            tfile = None
            if cov:
                tfile = core.find_type_file(self.root, cov["task"],
                                            os.path.basename(path))
            if tfile and os.path.isfile(tfile):
                ttxt = open(tfile, encoding="utf-8").read()[:800]
                guide = (
                    f"[诱导模式·类型文件] 输入槽「{arc_desc}」的类型文件"
                    f"「{os.path.basename(tfile)}」内容如下——这是树上的声明"
                    "知识（问序或档案说明）,优先于你的常识。据此决定这份"
                    "文档该收什么:有问序按问序问,是档案说明就按其性质"
                    "（该文档是什么、写给谁读）来诱导。文档为空时开场先亮牌:"
                    "用一两句告诉用户这份文档是什么,再主动问最核心的"
                    "一两个问题（不是要用户提交文件,而是替用户起草）:\n"
                    f"{ttxt}")
            elif cov:
                mname = os.path.basename(cov["task"])
                guide = (
                    f"[诱导模式·常识] 输入槽「{arc_desc}」喂给方法〔{mname}〕,"
                    "无结构化 schema、无类型文件。先依文件名和方法用途推断"
                    "这份文档该装什么,再依常识列要点(谁/什么/多少/何时/何地/"
                    "约束——按需取用,不适用的不问)亮牌给用户逐项确认;"
                    "用户说'不填'就记不填,不纠缠。不要臆断文档的领域类别。")
            else:
                guide = (
                    "[模式·自由编辑] 此文件非任务输入槽。按用户的问题正常协助"
                    "（起草/解释/修改均可）,不做收参诱导。")
        # 工位语境（通用界面办理绿任务时）:agent 知道在办哪张单、依据什么
        w = getattr(self, "_work", None)
        wctx = ""
        if w:
            wctx = (f"\n[工位·{os.path.basename(w['tdir'])}"
                    f"（实例 {w['case']}）·人工办理中]\n"
                    f"{w['instruction']}\n")
            for nm, txt in w["inputs"].items():
                wctx += f"[依据·{nm}]\n{txt[:600]}\n"
            wctx += ("你正陪人办这张单:先把单上的问题讲给人听,收集口语答案,"
                     "答案齐了替人起草上面的编辑器全文(【写好】协议)。\n")
        hist = "\n".join(f"{w}：{t}" for w, t in self._assist_log[-8:])
        pctx = (f"[会话主体] {self._principal['主体值']}"
                f"（{self._principal['姓名']}）——实例化人/经办人字段"
                "一律取此值自动署名，不要再向用户询问\n"
                if self._principal else "")
        prompt = (
            "你是 i3dna 办单助手（诱导式收参 agent）。\n"
            f"{guide}\n{wctx}{pctx}"
            "规则：\n"
            "1. 只收参数不裁决;枚举值逐字匹配,不匹配请用户重说\n"
            "2. 主动诱导:缺什么就问什么,一次最多两三个,别审讯;常识清单先亮牌;"
            "直接给内容,不复述用户原话\n"
            "3. 参数齐时输出以【写好】开头的完整文件全文"
            "（第一行就是文件第一行,无解释无围栏）,系统自动填入编辑器\n"
            "4. 无结构化 schema 且用户认可澄清单后,可在【写好】文末附一行"
            "'<!-- 建议键说明: k1,k2,... -->'供人决定是否沉淀为 schema.md\n"
            "5. 中文,两三行内\n\n"
            f"[输入槽] {os.path.basename(path)}\n"
            f"[当前文件内容]\n{self.editor.toPlainText()}\n\n"
            f"[对话]\n{hist}\n\n请回应「{q}」。")
        self._assist_proc_run(prompt)

    def _assist_proc_run(self, prompt):
        """直连车道（deepseek-v4-flash,thinking low,流式）:QThread 跑
        core.assist_llm,逐 delta 回 UI。旧 omp 子进程车道(6s进程+24s重模型)
        已废——交互场景必须轻通道。"""
        self._assist_thread = _AssistThread(prompt)
        self._assist_thread.delta.connect(self._on_assist_delta)
        self._assist_thread.done.connect(self._on_assist_done)
        self._assist_thread.start()

    def _on_assist_delta(self, text):
        """流式增量:更新末条助手消息,实时渲染。"""
        if self._assist_log and self._assist_log[-1][0] == "助手":
            self._assist_log[-1] = ("助手", self._assist_log[-1][1] + text)
        else:
            self._assist_log.append(("助手", text))
        self._render_assist_chat()
    def _on_assist_done(self, full):
        """收尾:全文到齐。若含【写好】→截取草稿回填编辑器(保存归人)。"""
        if not full.strip():
            if self._assist_log and self._assist_log[-1][0] == "助手":
                self._assist_log[-1] = ("助手", "（助手沉默了,再问一句）")
            else:
                self._assist_log.append(("助手", "（助手沉默了,再问一句）"))
        elif "【写好】" in full:
            draft = full.rsplit("【写好】", 1)[1].strip()
            # 申请全文回填编辑器（保存仍归人——过目后按保存）
            self.editor.setPlainText(draft)
            self._refresh_assist(getattr(self, "_edit_path", ""))
            if self._assist_log and self._assist_log[-1][0] == "助手":
                self._assist_log[-1] = ("助手", "已写好草稿填入上方编辑器——过目后按「保存」。")
            else:
                self._assist_log.append(("助手", "已写好草稿填入上方编辑器——过目后按「保存」。"))
        self._render_assist_chat()

    def _render_assist_chat(self, thinking=None):
        import html as _h2
        h = []
        for who, text in self._assist_log[-8:]:
            color = "#1565c0" if who == "你" else "#2e7d32"
            h.append(f"<p style='margin:2px'><b style='color:{color}'>{who}：</b>"
                     f"{_h2.escape(text).replace(chr(10), '<br>')}</p>")
        if thinking:
            h.append(f"<p style='margin:2px;color:#999'>助手思考中…</p>")
        self.assist_chat.setHtml("".join(h))
        sb = self.assist_chat.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _save_editor(self):
        p = getattr(self, "_edit_path", None)
        if not p:
            return
        tmp = p + ".tmp"
        os.makedirs(os.path.dirname(p), exist_ok=True)   # 新产物可先于目录
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(self.editor.toPlainText())
        os.replace(tmp, p)
        self.statusBar().showMessage(f"已保存 {os.path.relpath(p, self.root)}"
                                     "——受影响任务将标 ⟳ 过期")
        self.refresh()

    # ── 工作流页：弧表 → 二部图（transition/place 分层布局）──

    def _wf_jump(self, path):
        it = self.items_by_path.get(path)
        if it is not None:
            self.tabs.setCurrentIndex(0)
            self.tree.setCurrentIndex(it.index())
            self.tree.scrollTo(it.index())

    def _build_workflow(self):
        from PyQt6.QtGui import QFont, QPainterPath
        scene = QGraphicsScene()
        show_ptr = self.cb_ptr.isChecked()
        # 视图下拉：一类一工作流（包=类名，根级/旧式树退化为路径首段）。
        # 默认落到第一个类，避免多类堆叠成一张杂图；「全部」供总览，排在末尾。
        pkgs = sorted({core._pkg_of(self.root, t) for t in self.task_rows})
        want = pkgs + ["全部"]
        if [self.cb_wfpkg.itemText(i) for i in range(self.cb_wfpkg.count())] != want:
            cur = self.cb_wfpkg.currentText()
            self.cb_wfpkg.blockSignals(True)
            self.cb_wfpkg.clear()
            self.cb_wfpkg.addItems(want)
            if cur in want:
                self.cb_wfpkg.setCurrentText(cur)
            else:
                self.cb_wfpkg.setCurrentText(pkgs[0] if pkgs else "全部")
            self.cb_wfpkg.blockSignals(False)
        sel = self.cb_wfpkg.currentText()
        rows_f, arcs, places, opt_inputs = core.gather_arcs(
            self.root, self.task_rows, show_ptr, sel)
        COL, ROW, W, H, PW, PH = 210, 72, 190, 46, 160, 36
        vw = max(600, self.wf_view.viewport().width() - 60)

        def bezier(x1, y1, x2, y2, pen):
            path = QPainterPath(QPointF(x1, y1))
            dx = max(28.0, (x2 - x1) * 0.35)
            path.cubicTo(x1 + dx, y1, x2 - dx, y2, x2, y2)
            scene.addPath(path, pen)
            for dy in (-4, 4):
                scene.addLine(x2, y2, x2 - 9, y2 + dy, pen)

        def draw_task_node(t, x, y):
            stale = bool(self.stale_map.get(t))
            fill = (task_color(t) if self.enabled_map.get(t) else C_TASK_OFF)
            pen = QPen(QColor("#ef6c00"), 3) if stale \
                else QPen(fill.darker(130), 1.5)
            r = scene.addRect(x, y, W, H, pen, QBrush(fill))
            r.setData(0, t)
            r.setToolTip(os.path.relpath(t, self.root)
                         + ("\n⟳ 输入已变，建议重点火" if stale else "\n✓ 新鲜"))
            txt = scene.addSimpleText(
                os.path.basename(t) + (" ⟳" if stale else ""))
            fb = QFont(); fb.setPointSize(12); fb.setBold(True)
            txt.setFont(fb)
            txt.setBrush(QBrush(QColor("white")))
            txt.setPos(x + 10, y + 4)
            txt.setParentItem(r)
            sub = scene.addSimpleText(os.path.basename(os.path.dirname(t)))
            fs = QFont(); fs.setPointSize(9)
            sub.setFont(fs)
            sub.setBrush(QBrush(QColor(255, 255, 255, 170)))
            sub.setPos(x + 10, y + 27)
            sub.setParentItem(r)

        flow_mode = self.cb_flow.isChecked()
        flow_tarcs = core.task_flow_arcs(arcs, opt_inputs) if flow_mode else []
        y_base = 0
        for cnodes in core.components(rows_f, arcs, self.root):
            ctasks = [n for n in cnodes if n in rows_f]
            if not ctasks:
                continue
            cap = scene.addSimpleText(core._pkg_of(self.root, ctasks[0]))
            f = QFont(); f.setPointSize(13); f.setBold(True)
            cap.setFont(f)
            cap.setBrush(QBrush(QColor("#546e7a")))
            cap.setPos(0, y_base)

            if flow_mode:
                # ── 任务流程：折叠制品，只画任务 + 直连箭头（材料名标在线上）──
                tarcs = [(a, b, p, opt) for a, b, p, opt in flow_tarcs
                         if a in ctasks and b in ctasks]
                pos, comp_h = core.task_flow_layout(ctasks, tarcs, vw, y_base)
                pen_flow = QPen(QColor("#5c8bc4"), 1.8)
                pen_opt = QPen(QColor("#9e9e9e"), 1.2, Qt.PenStyle.DashLine)
                for a, b, p, opt in tarcs:
                    (x1, y1), (x2, y2) = pos[a], pos[b]
                    bezier(x1 + W, y1 + H / 2, x2, y2 + H / 2,
                           pen_opt if opt else pen_flow)
                    lbl = scene.addSimpleText(os.path.basename(p)[:12])
                    lf = QFont(); lf.setPointSize(9)
                    lbl.setFont(lf)
                    lbl.setBrush(QBrush(QColor("#1b5e20")))
                    lbl.setPos((x1 + W + x2) / 2 - 16, (y1 + y2) / 2 + H / 2 + 6)
                for t in ctasks:
                    x, y = pos[t]
                    draw_task_node(t, x, y)
                y_base += comp_h + 70
                continue

            # ── 二部图（微任务 + 材料两色节点）──
            pos, comp_h, carcs, cplaces = core.layout_component(
                cnodes, rows_f, places, arcs, opt_inputs, vw, y_base)
            if not carcs and not cplaces:
                continue
            pen_in = QPen(QColor("#90a4ae"), 1.3)
            pen_out = QPen(QColor("#5c8bc4"), 1.8)
            for t, p, k in carcs:
                if k == "输入":
                    (x1, y1), (x2, y2) = pos[p], pos[t]
                    bezier(x1 + PW, y1 + PH / 2, x2, y2 + H / 2, pen_in)
                else:
                    (x1, y1), (x2, y2) = pos[t], pos[p]
                    bezier(x1 + W, y1 + H / 2, x2, y2 + PH / 2, pen_out)
            for t in ctasks:
                x, y = pos[t]
                draw_task_node(t, x, y)
            for p in cplaces:
                x, y = pos[p]
                missing = not os.path.exists(p)
                is_ptr = "索引文件" in places[p]
                pen = QPen(QColor("#c62828"), 2, Qt.PenStyle.DashLine) if missing \
                    else QPen(QColor("#9e9e9e"), 1, Qt.PenStyle.DotLine) if is_ptr \
                    else QPen(QColor("#1b5e20"), 1.2)
                e = scene.addEllipse(x, y, PW, PH, pen,
                                     QBrush(QColor(232, 245, 233)))
                e.setData(0, p)
                e.setToolTip(os.path.relpath(p, self.root)
                             + ("\n✗ 不存在" if missing else ""))
                txt = scene.addSimpleText(places[p][:18])
                fp = QFont(); fp.setPointSize(11)
                txt.setFont(fp)
                txt.setBrush(QBrush(QColor("#1b5e20")))
                txt.setPos(x + 8, y + 2)
                txt.setParentItem(e)
                sub = scene.addSimpleText(
                    os.path.basename(os.path.dirname(p)))
                fs2 = QFont(); fs2.setPointSize(9)
                sub.setFont(fs2)
                sub.setBrush(QBrush(QColor("#78909c")))
                sub.setPos(x + 8, y + 22)
                sub.setParentItem(e)
            y_base += comp_h + 70
        self.wf_view.setScene(scene)
        self.wf_view.fit_all(1.0)     # 折行后图不再超宽：1:1 起步顶部对齐，滚轮下翻

    # ── 推进：一次决策收敛整网（使能∧(缺失∨过期) 自动点、新鲜跳）──

    def do_converge(self, target=None, case=None):
        """推进 = 消账实差到不动点。无实例视角：工具栏按钮扇出到全部实例并行
        （一实例一引擎进程一执行流页签）；右键实例节点仍是单实例推进。
        注：全部实例任务均有 {实例} 记号时并行安全；若存在无记号的类级任务，
        先到的实例推进会点它、后到的按新鲜跳过（并行窗口内理论可重入）。"""
        if case is not None and self._case_busy(case):
            QMessageBox.warning(self, "占线",
                                f"实例 {case} 已有推进/点火在飞，等它收尾。"
                                "（其他实例不受影响）")
            return
        self._divert_details()
        if not isinstance(target, str) or not target:
            target = self.root                 # 工具栏 QAction 会传 checked 布尔
        cases = [case] if case else (getattr(self, "cases", None) or [None])
        skip_busy = [c for c in cases if self._case_busy(c)]
        cases = [c for c in cases if c not in skip_busy]
        import subprocess as _sp
        eng_py = os.path.join(BASE, "i3dna-engine", "i3dna_engine.py")
        plans, total, ok_cases = [], 0, []
        for c in cases:
            cargs = ["--case", c] if c else []
            r = _sp.run([sys.executable, eng_py, "converge", target, "--plan"]
                        + cargs, capture_output=True, text=True)
            text = r.stdout + (("\n" + r.stderr) if r.returncode else "")
            n = text.count("▶")
            plans.append((c, text, r.returncode))
            if r.returncode == 0 and n > 0:    # 0 站实例不起进程（新鲜即静默）
                ok_cases.append(c)
                total += n
        tag = f"（实例 {case}）" if case else \
            (f"（{len(ok_cases)} 实例并行）" if len(ok_cases) > 1
             else (f"（实例 {ok_cases[0]}）" if ok_cases and ok_cases[0] else ""))
        h = [f"<h3>推进计划{tag}</h3>"]
        for c, text, _rc in plans:
            if len(plans) > 1:
                h.append(f"<h4>实例 {c}</h4>")
            h.append("<pre style='white-space:pre-wrap; word-wrap:break-word'>"
                     + _htm.escape(text) + "</pre>")
        if skip_busy:
            h.append(f"<p>↩ 实例 {'、'.join(map(str, skip_busy))}"
                     "已在推进/点火中，本次跳过（写集各归各，不冲突）。</p>")
        self.show_html("".join(h))
        if not ok_cases:
            self.statusBar().showMessage(
                "🟢 全网新鲜（含全部实例），无需推进"
                if all(rc == 0 for _c, _t, rc in plans)
                else "⛔ 推进计划失败（详情见右侧面板）")
            return
        if QMessageBox.question(
                self, "推进" + tag,
                f"计划点火 {total} 站（详情见右侧面板；上游重算后下游级联现算，"
                f"实际站数可能更多）。开始推进？") \
                != QMessageBox.StandardButton.Yes:
            return
        run_id = f"run-converge-{datetime.now().strftime('%H%M%S')}"
        first_page = None
        for c in ok_cases:
            cargs = ["--case", c] if c else []
            args = ["-u", eng_py, "converge", target, "--stream"] + cargs + [
                    "--engine", self.cb_engine.currentData(),
                    "--run-id", run_id]
            sandbox = None
            if self.cb_sandbox.isChecked():
                sandbox = tempfile.mkdtemp(
                    prefix=f"i3dna_converge_{c or 'nocase'}_sbx_")
                args += ["--sandbox", sandbox]
            page = self._stream_tab(c)
            if first_page is None:
                first_page = page
            page["buf"].append(f"$ python3 {' '.join(args[1:])}\n")
            self._start_run(args, target="stream", case=c, verb="推进中",
                            buf=page["buf"], log_verb="推进")
            self._render_stream_tab(c)
        self.detail_tabs.setCurrentIndex(1)    # 切到执行流标签页
        self.stream_tabs.setCurrentWidget(first_page["view"])

    # ── 老子：状态投影问答（核只读 summary）─────────────────

    def _status_context(self):
        return core.status_snapshot(
            self.root, self.tasks,
            {t: bool(s) for t, s in self.stale_map.items()},
            (len(self.lint_rep.errors), len(self.lint_rep.warnings)))

    def _laozi_skill(self):
        """手艺卡（知识住树·presence-based，8-19）：卡在=老师傅模式。
        泰勒主义（树上 SOP）干Routine；盘问诊断是老师傅的活——卡即技能，
        无卡则老子保持快照问答，零第二登记。"""
        for sub in (("域", "*", "类", "目录树元知识", "知识", "API手艺.md"),
                    ("类", "目录树元知识", "知识", "API手艺.md")):
            hit = sorted(glob.glob(os.path.join(self.root, *sub)))
            if hit:
                return open(hit[0], encoding="utf-8").read()
        return ""

    def ask_laozi(self):
        q = self.chat_input.text().strip()
        if not q:
            return
        if self.chat_proc is not None and \
                self.chat_proc.state() != QProcess.ProcessState.NotRunning:
            self.statusBar().showMessage("老子还在想上一条…")
            return
        self.chat_input.clear()
        self._chat_log.append(("你", q))
        self._laozi_rounds = 0
        self._laozi_call()

    def _laozi_call(self):
        """老子一轮：快照+手艺卡（若在）+会话转录 → 聊天进程；【查】工具环
        在 _on_chat_done 里接力（老师傅可反问树，写桥仍归人）。"""
        self._chat_partial = ""      # 流式累积：老子输出逐块拼到这里
        self._render_chat(thinking=True)
        self.detail_tabs.setCurrentIndex(2)   # 切到"老子"标签
        skill = self._laozi_skill()
        skill_block = ""
        if skill:
            skill_block = ("[手艺·读桥API] 树上有你的手艺卡，照办：\n"
                           + skill.strip()
                           + "\n要盘问就先查后答：单独一行输出【查】<读动词>"
                           " [旗标…]（如【查】tasks），系统跑 API 把 JSON 喂回"
                           "你再答；只许读动词，一次最多三查，查够了就【答】。\n")
        hist = "\n".join(f"[{w}] {t}" for w, t in self._chat_log[-10:])
        prompt = ("你是老子，勘察院 I3DNA 包看板的助手。只用中文，三到五行，"
                  "只说结论和该做的事，不复述快照。"
                  "最终答案必须以「【答】」开头（用于程序截取）。\n\n"
                  f"{skill_block}\n[当前包状态快照]\n"
                  + self._status_context() + f"\n\n[会话]\n{hist}")
        cmd = shlex.split(os.environ.get("I3DNA_CHAT_CMD", "hermes chat -Q -q"))
        self.chat_proc = QProcess(self)
        self.chat_proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.chat_proc.readyReadStandardOutput.connect(self._on_chat_output)
        self.chat_proc.finished.connect(self._on_chat_done)
        self.chat_proc.start(cmd[0], cmd[1:] + [prompt])

    def _on_chat_output(self):
        """流式：逐块拼到 _chat_partial，实时渲染。"""
        raw = bytes(self.chat_proc.readAllStandardOutput()).decode("utf-8", "replace")
        self._chat_partial += raw
        # 【答】前缀已出现 → 截取为正式回答；否则当思考过程原样显示
        if "【答】" in self._chat_partial:
            ans = self._chat_partial.rsplit("【答】", 1)[1].strip()
        elif self._chat_partial.strip():
            ans = self._chat_partial.strip()
        else:
            return                              # 还没输出，保持"思考中"
        # 更新末条而不是追加——每个流式增量都 append 会把思考流复读成
        # 一串越滚越长的假消息（与 _on_chat_done 的收尾模式保持同款）
        if self._chat_log and self._chat_log[-1][0] == "老子":
            self._chat_log[-1] = ("老子", ans)
        else:
            self._chat_log.append(("老子", ans))
        self._render_chat()

    def _on_chat_done(self, *_):
        """收尾：最终截取；【查】工具环——无【答】而有【查】行且轮数未到
        顶＝代跑读桥 API 喂回再问一轮（老师傅反问树，最多 5 轮）。"""
        raw = self._chat_partial + \
            bytes(self.chat_proc.readAllStandardOutput()).decode("utf-8", "replace")
        queries = [l.strip() for l in raw.splitlines()
                   if l.strip().startswith("【查】")]
        if "【答】" not in raw and queries and self._laozi_rounds < 5:
            self._chat_log.append(("老子", raw.strip()[:1200] or "（先查后答）"))
            results = []
            for ql in queries[:3]:
                toks = shlex.split(ql[len("【查】"):].strip())
                ok, text = core.api_query(self.root,
                                          toks[0] if toks else "", toks[1:])
                results.append(f"$ {ql}\n{text}")
            self._chat_log.append(("查", "\n".join(results)[:8000]))
            self._laozi_rounds += 1
            self._laozi_call()
            return
        if "【答】" in raw:
            ans = raw.rsplit("【答】", 1)[1].strip()
        else:
            ans = "\n".join(l for l in raw.splitlines()
                            if l.strip() and not l.startswith("session_id:")).strip()
        ans = ans or "（老子沉默——检查 hermes gateway 或设 I3DNA_CHAT_CMD 换通道）"
        # 替换流式期间追加的临时条目，只留最终答案
        if self._chat_log and self._chat_log[-1][0] == "老子":
            self._chat_log[-1] = ("老子", ans)
        else:
            self._chat_log.append(("老子", ans))
        self._chat_partial = ""
        self._render_chat()

    def _render_chat(self, thinking=False):
        h = ["<h3>老子</h3>"]
        for who, text in self._chat_log[-12:]:
            color = {"你": "#1565c0", "查": "#7b1fa2"}.get(who, "#2e7d32")
            h.append(f"<p><b style='color:{color}'>{who}：</b>"
                     f"{_htm.escape(text).replace(chr(10), '<br>')}</p>")
        if thinking:
            h.append("<p>…思考中…</p>")
        sb = self.chat_view.verticalScrollBar()
        follow = sb.value() >= sb.maximum() - 30   # 在底部→跟随；上翻了→别打扰
        keep = sb.value()
        self.chat_view.setHtml("".join(h))
        sb.setValue(sb.maximum() if follow else keep)

    # ── 代笔：口语意图 → 客户腔需求全文（变异归 agent，保存归人）──

    def ghostwrite(self):
        p = getattr(self, "_edit_path", None)
        if not p:
            return
        if self.ghost_proc is not None and \
                self.ghost_proc.state() != QProcess.ProcessState.NotRunning:
            self.statusBar().showMessage("代笔进行中…")
            return
        intent, ok = QInputDialog.getMultiLineText(
            self, "代笔", "口语说你要的改动（老子改写成客户腔需求全文，保存前给你看 diff）：")
        if not ok or not intent.strip():
            return
        cur = self.editor.toPlainText()
        prompt = ("下面是一份客户需求文档原文和用户的口语改动意图。把意图改写进文档："
                  "保持原有编号体例与客户口吻，输出完整的新版全文——"
                  "第一行就是文档第一行，不要解释、不要 markdown 围栏。\n\n"
                  f"[原文]\n{cur}\n\n[改动意图]\n{intent.strip()}")
        fd, pf = tempfile.mkstemp(suffix=".txt", prefix="i3dna_ghost_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(prompt)
        self.ed_label.setText(self.ed_label.text().split("  ")[0] + "  〔代笔中…〕")
        self.ghost_proc = QProcess(self)
        self.ghost_proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.ghost_proc.finished.connect(
            lambda *_: self._on_ghost_done(pf))
        self.ghost_proc.start("omp", ["-p", "--no-session", "--no-tools", "@" + pf])

    def _on_ghost_done(self, pf):
        os.unlink(pf)
        new = bytes(self.ghost_proc.readAllStandardOutput()) \
            .decode("utf-8", "replace").strip()
        self.ed_label.setText(self.ed_label.text().split("  ")[0])
        if not new:
            QMessageBox.warning(self, "代笔失败", "引擎空返，原文未动。")
            return
        old = self.editor.toPlainText()
        import difflib
        diff = "\n".join(difflib.unified_diff(
            old.splitlines(), new.splitlines(), "原文", "代笔稿", lineterm=""))
        box = QMessageBox(self)
        box.setWindowTitle("代笔稿 diff——保存归你")
        box.setText("左：-原文  右：+代笔稿（详情见下）")
        box.setDetailedText(diff or "（无差异）")
        box.setStandardButtons(QMessageBox.StandardButton.Save
                               | QMessageBox.StandardButton.Cancel)
        if box.exec() == QMessageBox.StandardButton.Save:
            self.editor.setPlainText(new)
            self._save_editor()

    def _lineage_html(self, path):
        """键级血缘面板(94号):__血缘.md 的只读出身史表(谁在何时改了哪个键)。"""
        import html as _h
        entries = core.lineage_entries(path)
        if not entries:
            return ""
        rows = []
        for e in entries:
            if e["键"] == "?":
                rows.append("<tr><td colspan=4><i>"
                            + _h.escape(e["原始"][:60]) + "</i></td></tr>")
            else:
                rows.append(f"<tr><td>{_h.escape(e['键'])}</td>"
                            f"<td>{_h.escape(e['哈希'])}</td>"
                            f"<td>{_h.escape(e['来源'])}</td>"
                            f"<td>{_h.escape(e['时间'])}</td></tr>")
        return ("<h4>🩸 键级血缘（谁在何时改了这个键）</h4>"
                "<table border=1 cellspacing=0 cellpadding=3>"
                "<tr><th>键</th><th>值哈希</th><th>来源(案卷/方法)</th>"
                "<th>时间</th></tr>" + "".join(rows) + "</table>")

    def _render_node(self, item):
        path, ntype = item.data(ROLE_PATH), item.data(ROLE_TYPE)
        tlabel = "🔵 微任务（变迁）"
        if ntype == "task" and eng.exec_entry(path):
            tlabel = "🔴 微任务（变迁·符号主义）"
        h = [f"<h3>{os.path.basename(path)}</h3>",
             f"<p>类型：{ {'task': tlabel, 'entity': '🟢 实体（库所）', 'dir': '目录', 'file': '文件'}[ntype] }"
             f"<br>路径：{os.path.relpath(path, self.root)}</p>"]
        if ntype == "task":
            entry = eng.exec_entry(path)
            if entry:
                cst = eng.compile_stale(path, self.root)
                h.append("<p>范式：<b style='color:#c62828'>符号主义</b>——点火跑 "
                         f"<code>{os.path.relpath(entry, path)}</code>（确定性程序，不调 LLM）"
                         + (("<br>⚠ <b>编译过期</b>：" + "；".join(cst)
                             + "——现行程序照跑，重编译与否由人裁决")
                            if cst else "") + "</p>")
            h.append(self._preflight_html(path))
            rp = os.path.join(path, "__结果.json")
            if os.path.isfile(rp):
                h.append(self._record_html(path))
        elif ntype == "file":
            base = os.path.basename(path)
            ext = os.path.splitext(base)[1].lower()
            if ext in EDITABLE_EXT and os.path.getsize(path) < 200000:
                # 待办单据（绿任务输入弧的 case 代入场）→ 通用界面办理:
                # 聊天收参+编辑器+唯一确认按钮,不落裸编辑器。
                gw = core.green_work_for(self.root, path)
                if gw:
                    self.open_work_ui(gw[0], gw[1])
                    return
                self._open_editor(path)            # 其余真源文本 → 可编辑
                return
            if base.endswith(".xlsx") and not base.startswith("~$"):
                h.append(self._xlsx_html(path))
            elif ext in (".docx", ".doc"):
                import subprocess as _sp
                import html as _h2
                r = _sp.run(["textutil", "-convert", "txt", "-stdout", path],
                            capture_output=True, text=True)
                h.append("<pre style='white-space:pre-wrap; word-wrap:break-word'>" + _h2.escape(r.stdout[:40000]) + "</pre>"
                         if r.returncode == 0 and r.stdout.strip()
                         else "<p>docx 转换失败（textutil）</p>")
            elif base == "__结果.json":
                h.append(self._record_html(os.path.dirname(path)))
            elif ext in eng.TEXT_EXT and os.path.getsize(path) < 40000:
                import html as _html
                h.append("<pre style='white-space:pre-wrap; word-wrap:break-word'>" + _html.escape(
                    open(path, encoding="utf-8", errors="replace").read())
                    + "</pre>")
        elif ntype == "entity":
            h.append(self._lineage_html(path))
            rows = []
            for f in os.listdir(path):
                if f.startswith("__") and f.endswith("索引文件.xlsx"):
                    for r in eng._index_rows_from_file(os.path.join(path, f)):
                        rows.append(f"<tr><td>{r['desc']}</td><td>{r['pname']}</td>"
                                    f"<td>{r['pdir']}</td></tr>")
            if rows:
                h.append("<h4>索引外联行</h4><table border=1 cellspacing=0 "
                         "cellpadding=3><tr><th>描述</th><th>名称</th><th>目录</th></tr>"
                         + "".join(rows) + "</table>")
        elif ntype == "dir":
            h.append(self._lineage_html(path))   # md 树档案是 dir 类型
        self.show_html("".join(h))

    # ── 右键：preflight / run / 点火记录 ────────────────────

    def on_menu(self, pos):
        item = self._current_item()
        if item is None:
            return
        t = item.data(ROLE_TYPE)
        if t == "task":
            menu = self.build_task_menu(item)
        elif t == "file" and str(item.data(ROLE_PATH)).endswith((".py", ".sh")):
            menu = self.build_file_menu(item)
        elif t == "dir":
            menu = self.build_dir_menu(item)
            if menu is None:
                return
        else:
            return
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    # ── 类与实例（OOP 面板：类=方法+知识，实例=实例）─────────

    def build_dir_menu(self, item):
        """普通目录的语义菜单：类根（含 方法/）→ 实例化；
        实例实例（父目录名=实例）→ 推进/绑定视角。其余目录无菜单。"""
        path = item.data(ROLE_PATH)
        menu = QMenu(self)
        if os.path.isdir(os.path.join(path, "方法")):
            act = QAction("实例化…", menu)
            act.triggered.connect(lambda _, p=path: self.do_instantiate(p))
            menu.addAction(act)
            act = QAction("实例结构（实例 schema）", menu)
            act.triggered.connect(lambda _, p=path: self.show_class_schema(p))
            menu.addAction(act)
            # 类→实例直通（8-19 连问两次的缺口）：Bean 平铺使类与实例分居
            # 两枝，从类上看不到实例——右键一键跳到本类实例架
            shelf = os.path.join(self.root, "实例", os.path.basename(path))
            ks = [k for k in sorted(os.listdir(shelf))
                  if os.path.isdir(os.path.join(shelf, k))
                  and not k.startswith(".")] if os.path.isdir(shelf) else []
            act = QAction(f"🥚 本类实例（{len(ks)}）→ 实例/{os.path.basename(path)}"
                          + ("" if ks else "（空——去「实例化…」或方法右键「新案卷」"),
                          menu)
            if ks:
                act.triggered.connect(
                    lambda _, s=shelf: self._nav_to(
                        s, msg=f"🥚 实例架：实例/{os.path.basename(shelf)}"
                        f"（{len(ks)} 案卷）"))
            else:
                act.setEnabled(False)
            menu.addAction(act)
            return menu
        par, gpar = os.path.dirname(path), os.path.dirname(os.path.dirname(path))
        case, croot = os.path.basename(path), None
        if os.path.basename(par) == "实例" \
                and os.path.isdir(os.path.join(gpar, "方法")):
            croot = gpar                       # 单类树退化布局:根/实例/<k>
        elif os.path.basename(gpar) == "实例":  # 实例库:实例/<类名>/<k>
            kname = os.path.basename(par)      # 类名→类根反查（v2.2 认域前缀）
            for cand in core.class_roots(os.path.dirname(gpar)):
                if os.path.basename(cand) == kname:
                    croot = cand
                    break
        if croot:
            if self._principal:               # 101号：未登录无入口（登录=身份，话语=签字的前提）
                act = QAction("💬 对话（话语即签字）", menu)
                act.setObjectName("act对话")
                act.triggered.connect(
                    lambda _, c=croot, k=case: self.open_chat(c, k))
                menu.addAction(act)
            act = QAction(f"推进本实例（{case}）…", menu)
            act.triggered.connect(
                lambda _, c=croot, k=case: self.do_converge(c, k))
            menu.addAction(act)
            missing_state = core.missing_state_slots(croot, path)
            if missing_state:                  # 裸建实例的显式修复门(人点才补)
                act = QAction(f"补播字段区（缺 {'、'.join(missing_state)}）", menu)
                act.triggered.connect(
                    lambda _, c=croot, p2=path: (
                        eng.seed_state_defaults(self.root, c, p2),
                        self.refresh(),
                        self.statusBar().showMessage("🌱 字段区已按默认补播")))
                menu.addAction(act)
            # 工位面板(调用约定统一论99号):实例=bean,一切调用 bean.method()。
            # 逐站状态+预绑 case 动词——待人办→办结(通用界面),need→点火,
            # 其余→站名+原因(只读)。替代旧 办结☐ 与方法菜单的选例点火。
            menu.addSeparator()
            head = QAction("— 工位（本实例 bean 的方法）—", menu)
            head.setEnabled(False)
            menu.addAction(head)
            for st in core.instance_stations(self.root, croot, case):
                icon = {"绿": "🧑", "红": "🔴", "蓝": "🔵"}.get(st["kind"], "·")
                label = f"{icon} {st['name']}：{st['reason'][:30]}"
                if st["human"] and st["reason"].startswith("待人办"):
                    act = QAction(f"办结 ☐ {label}", menu)
                    act.triggered.connect(
                        lambda _, t=st["task"], k=case:
                        self.open_work_ui(t, k))
                elif st["need"]:
                    act = QAction(f"点火 ▶ {label}", menu)
                    act.triggered.connect(
                        lambda _, t=st["task"], k=st["case"]:
                        self._fire_station(t, k))
                else:
                    act = QAction(label, menu)
                    act.setEnabled(False)
                menu.addAction(act)
            return menu
        return None

    # ── 右键对话（101号：话语即签字·零会话态）──────────────

    def open_chat(self, croot, case):
        """过程类实例右键「对话」：开面板（非模态；引用留 self._chat_dlg
        作测试锚——内存态，零落盘）。"""
        dlg = ChatDialog(self, self.root, croot, case, self._principal)
        self._chat_dlg = dlg
        dlg.show()

    def _omp_rpc_client(self):
        """omp rpc 持久车道（懒起，Explorer 生命周期共享一进程）。"""
        if getattr(self, "_omp_rpc", None) is None:
            self._omp_rpc = OmpRpcClient(self)
        return self._omp_rpc

    def _omp_rpc_reset(self):
        if getattr(self, "_omp_rpc", None) is not None:
            self._omp_rpc.reset()

    def _dialog_llm(self, prompt, on_done, speech, on_delta=None):
        """对话编译车道（S5 实装 8-20）：缺省=持久 omp --mode rpc 流式
        （text_delta 逐帧经 on_delta 打字机回显）；env I3DNA_DIALOG_CMD
        子进程＝验收桩/外接车道（整段返、无 delta）。返回线程或 None。"""
        cmd = os.environ.get("I3DNA_DIALOG_CMD")
        if not cmd:
            self._omp_rpc_client().ask(
                prompt, on_delta, lambda text: on_done(speech, text))
            return None
        else:
            def work():
                import subprocess as _sp
                r = _sp.run(shlex.split(cmd) + [prompt],
                            capture_output=True, text=True, timeout=600)
                return (r.stdout or r.stderr or "").strip()
        th = _FnThread(work)
        th.done.connect(lambda text: on_done(speech, text))
        if not hasattr(self, "_chat_threads"):
            self._chat_threads = []       # 存活引用（Qt 运行帧外防析构）
        self._chat_threads = [t for t in self._chat_threads
                              if t.isRunning()] + [th]
        th.start()
        return th

    def closeEvent(self, ev):
        """收尾：omp rpc 持久进程随窗退（不留孤儿）。"""
        if getattr(self, "_omp_rpc", None) is not None:
            self._omp_rpc.reset()
        super().closeEvent(ev)

    def _fire_station(self, tdir, case):
        """工位面板点火:预绑 case 直发(类方法 case=None),无选例对话框。"""
        if case is not None and self._case_busy(case):
            QMessageBox.warning(self, "占线",
                                f"实例 {case} 已有推进/点火在飞，等它收尾。")
            return
        self._divert_details()
        # 拓扑序预警:上游产物过期时提醒先点上游(消费旧基底会记旧 sha)
        ups = {self.product_of[p] for p in self.inputs_of.get(tdir, [])
               if p in self.product_of and self.product_of[p] != tdir}
        stale_ups = [u for u in ups if self.stale_map.get(u)]
        if stale_ups:
            names = "、".join(os.path.basename(u) for u in stale_ups)
            if QMessageBox.question(
                    self, "上游过期",
                    f"上游 ⟳ 过期：{names}。现在点火会消费旧基底"
                    "（出处记旧 sha）。仍要点火？") \
                    != QMessageBox.StandardButton.Yes:
                return
        # 执行者(部门):有部门档案才问;沙盒随工具栏
        executor = None
        depts = sorted(
            d for d in (os.listdir(os.path.join(self.root, "实例", "部门"))
                        if os.path.isdir(os.path.join(self.root, "实例", "部门"))
                        else [])
            if not d.startswith((".", "__")))
        if depts:
            items = [f"{d}（{self._dept_name(d)}）" for d in depts] \
                + ["不指定（用任务声明值）"]
            sel, ok = QInputDialog.getItem(
                self, "执行者", "哪个部执行（账记「执行者」）：", items, 0, False)
            if not ok:
                return
            if not sel.startswith("不指定"):
                executor = f"实例/部门/{sel.split('（')[0]}"
        run_id = f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        args = ["-u", os.path.join(BASE, "i3dna-engine", "i3dna_engine.py"),
                "run", tdir, "--stream",
                "--engine", self.cb_engine.currentData(),
                "--run-id", run_id]
        if executor:
            args += ["--executor", executor]
        if case:
            args += ["--case", case]
        if self.cb_sandbox.isChecked():
            sandbox = tempfile.mkdtemp(
                prefix=f"i3dna_explorer_{case or 'nocase'}_sbx_")
            args += ["--sandbox", sandbox]
        page = self._stream_tab(case)
        page["buf"].append(f"$ python3 {' '.join(args[1:])}\n")
        self._start_run(args, target="stream", case=case, verb="点火中",
                        buf=page["buf"], log_verb="点火", log_tdir=tdir)
        self._render_stream_tab(case)
        self.detail_tabs.setCurrentIndex(1)
        self.stream_tabs.setCurrentWidget(page["view"])

    def show_class_schema(self, croot):
        """实例结构(schema):推导在 core.class_schema,此处只渲染表格。"""
        import html as _h
        rows, undeclared = core.class_schema(croot)
        h = [f"<h3>实例结构：{_h.escape(os.path.basename(croot))} 的实例 schema</h3>",
             "<p>槽位从方法弧推导（路径真源在弧）；消息类型声明补键/开单收单。</p>",
             "<table border='1' cellspacing='0' cellpadding='4'>",
             "<tr><th>槽</th><th>生产</th><th>消费</th><th>性质</th>"
             "<th>使能条件</th><th>消息类型声明</th></tr>"]
        for d in rows:
            h.append("<tr><td>" + "</td><td>".join(
                _h.escape(str(d[k])) for k in
                ("槽", "生产", "消费", "性质", "使能", "类型")) + "</td></tr>")
        h.append("</table>")
        if undeclared:
            h.append("<p>⚠ 可缺消息未立类型声明（键 schema 无门）："
                     + "、".join(_h.escape(x) for x in undeclared) + "</p>")
        self.show_html("".join(h))

    def _pending_human(self, croot, case):
        return core.pending_human(self.root, croot, case)

    def _class_methods(self, croot):
        return core.class_methods(croot)

    def _ctor_params(self, croot):
        return core.ctor_params(self.root, croot)

    def do_instantiate(self, croot):
        """实例化＝造槽位：mkdir＋字段区播种。**零地址零内容**——
        构造参数的内容是之后的「请求」，人往法定地址写（账外直写），
        引擎的未使能守门天然等它。人在这里只输入一样东西：实例号。"""
        kname = os.path.basename(croot)
        case, ok = QInputDialog.getText(
            self, "实例化", f"类「{kname}」新实例号：")
        case = (case or "").strip()
        if not ok or not case:
            return
        if "/" in case or case.startswith("."):
            QMessageBox.warning(self, "非法实例号", "实例号不能含 / 或以 . 开头")
            return
        cdir = self._case_dir(croot, case)
        if os.path.isdir(cdir):
            QMessageBox.warning(self, "已实例化", f"实例 {case} 已存在")
            return
        os.makedirs(cdir, exist_ok=True)
        self._seed_defaults(croot, cdir)          # 字段区零值(Object 默认)
        slots = self._ctor_params(croot)
        for rel in slots:          # 造空槽文件:给人一个可点开编辑的落点。
            fp = os.path.join(cdir, rel)           # 空文件≠内容——引擎把
            if os.path.dirname(rel):               # 空的必需输入当 token 未到,
                os.makedirs(os.path.dirname(fp), exist_ok=True)
            if not os.path.isfile(fp):             # 不会拿空需求开跑
                open(fp, "w", encoding="utf-8").close()
        self.statusBar().showMessage(
            f"🟢 已实例化 {kname}/{case}（字段区已播种）。待写入内容："
            + "、".join(slots) + " ——写好后推进", 15000)
        self.refresh()

    # ── 实例代数：无视角，操作扇出到实例集合 ────────────────

    def _all_cases(self):
        return core.all_cases(self.root)

    def _case_dir(self, croot, case):
        return core.case_dir(self.root, croot, case)

    def _seed_defaults(self, croot, cdir):
        """字段区零值初始化——复用引擎的运行时职责实现（单一副本）。"""
        eng.seed_state_defaults(self.root, croot, cdir)

    def _task_marked(self, tdir):
        return core.task_marked(tdir)

    def _class_cases(self, tdir):
        return core.class_cases(self.root, tdir)

    def _task_accounts(self, tdir):
        return core.task_accounts(self.root, tdir)

    def _task_view(self, tdir):
        return core.task_view(self.root, tdir)

    def build_file_menu(self, item):
        menu = QMenu(self)
        act = QAction("运行…", menu)
        act.triggered.connect(lambda _, it=item: self.do_run_file(it))
        menu.addAction(act)
        return menu

    def do_run_file(self, item):
        if self._busy():
            QMessageBox.warning(self, "占线", "已有进程在执行，等它结束。")
            return
        path = item.data(ROLE_PATH)
        # 命令行参数输入（可直接回车=无参数运行，适合 GUI 程序）
        args_str, ok = QInputDialog.getText(
            self, "运行参数",
            f"python3 {os.path.relpath(path, self.root)}",
            text="1+2*3")
        if not ok:
            return
        cli_args = shlex.split(args_str) if args_str.strip() else []
        disp = os.path.relpath(path, self.root) + (
            " " + args_str if args_str.strip() else "")
        self.show_html("<h3>运行中…（GUI 程序会弹出真窗口）</h3><pre style='white-space:pre-wrap; word-wrap:break-word'>"
                       f"$ python3 {disp}</pre>")
        prog = "/bin/bash" if path.endswith(".sh") else sys.executable
        self._start_run([path] + cli_args if path.endswith(".sh")
                        else ["-u", path] + cli_args,
                        target="detail", case=None, verb="运行中", buf=None,
                        log_verb="运行文件", log_cmd=disp,
                        program=prog, workdir=os.path.dirname(path),
                        init_runlog=[f"$ python3 {disp}", ""])

    class _PathItem:
        """路径垫片:让 build_*_menu 同时服务树节点与图元(data(role)→path)。"""

        def __init__(self, p):
            self._p = p

        def data(self, _role):
            return self._p

        def text(self):
            return os.path.basename(self._p)

    def _graph_menu(self, path, gpos):
        shim = self._PathItem(path)
        if os.path.isfile(os.path.join(path, "任务.md")):
            self.build_task_menu(shim).exec(gpos)
        elif os.path.isdir(path):
            m = self.build_dir_menu(shim)
            if m is not None:
                m.exec(gpos)

    def _task_pending_cases(self, tdir, limit=8):
        return core.task_pending_cases(self.root, tdir, limit)

    def build_task_menu(self, item):
        menu = QMenu(self)
        tdir0 = item.data(ROLE_PATH)
        human = eng.get_value(os.path.join(tdir0, "任务.md"), "执行者") == "人"
        ncase = len(self._task_accounts(tdir0))   # 受体数：多点一实例数进执行流
        # 调用约定统一论(99号):一切点火/办结都是实例侧调用——方法节点
        # 只留定义级只读面(预检/记录);业务动词去实例右键「工位」。
        head = QAction("（定义级只读面·业务动词在 实例右键→工位）", menu)
        head.setEnabled(False)
        menu.addAction(head)
        if core.task_marked(tdir0):
            act = QAction("🆕 新案卷（立案开工位）…", menu)
            act.triggered.connect(lambda _, it=item: self.do_new_case(it))
            menu.addAction(act)
        menu.addSeparator()
        for label, fn in (("预检", self.do_preflight),
                          ("点火记录", self.do_record)):
            act = QAction(label, menu)
            act.triggered.connect(lambda _, f=fn, it=item: f(it))
            menu.addAction(act)
        menu.addSeparator()
        # 渐进式符号化操作面：蓝任务可检测/编译，红任务可回退
        tdir = item.data(ROLE_PATH)
        if human:
            act = QAction("检测可信息化（绿→蓝）", menu)
            act.triggered.connect(lambda _, it=item: self.do_inform(it))
            menu.addAction(act)
        elif eng.exec_entry(tdir):
            act = QAction("回退联结主义", menu)
            act.triggered.connect(lambda _, it=item: self.do_revert(it))
            menu.addAction(act)
        else:
            for label, fn in (("检测可符号化", self.do_detect),
                              ("编译（生成符号程序）", self.do_compile)):
                act = QAction(label, menu)
                act.triggered.connect(lambda _, f=fn, it=item: f(it))
                menu.addAction(act)
            if os.path.isfile(os.path.join(tdir, ".i3dna_compile",
                                           "执行程序", "主程序.py")):
                act = QAction("编译验收（暂存待裁决）", menu)
                act.triggered.connect(lambda _, td=tdir: self._compile_review(td))
                menu.addAction(act)
        menu.addSeparator()
        for label, kind in (("登记输入弧", "输入"), ("登记产物弧", "产物")):
            act = QAction(label, menu)
            act.triggered.connect(lambda _, k=kind, it=item: self.do_add_arc(it, k))
            menu.addAction(act)
        return menu

    # ── 渐进式符号化：检测 / 编译（验收归人）/ 回退 ──────────

    def _engine_qproc(self, args, header, verb="执行中", hook=None):
        """在内容页跑一条引擎子命令（QProcess，共用心跳/输出/收尾管线）。"""
        self.show_html(f"<h3>{header}</h3><pre style='white-space:pre-wrap; word-wrap:break-word'>$ python3 {' '.join(args[1:])}</pre>")
        self._start_run(args, target="detail", case=None, verb=verb,
                        buf=None, log_verb=verb, hook=hook,
                        init_runlog=[f"$ python3 {' '.join(args[1:])}", ""])


    def open_work_ui(self, tdir, case):
        """通用界面办理绿任务（人类和系统交互的通用通道,领域无关）:
        聊天收参 + 编辑器看稿 + 唯一「✅ 办结入账」确认按钮。
        人与 agent 自然语言协作——agent 把口语意图翻译成领域文件,
        人只确认。确认=保存交付+销单(收回=事已办妥)+backfill 入账。
        HumanWorkForm 对话框已退役。"""
        try:
            task = eng.load_task(tdir, self.root, case=case)
        except SystemExit as e:
            QMessageBox.warning(self, "无法办理", str(e))
            return
        deliver, tickets, inputs = None, [], {}
        for r in task["rows"]:
            if r["kind"] == "输入" and r["path"] \
                    and os.path.isfile(r["path"]) \
                    and os.path.relpath(r["path"], self.root).startswith(
                        ("实例/", "域/")):
                inputs[r["pname"]] = open(
                    r["path"], encoding="utf-8", errors="replace").read()
            if r["kind"] != "产物" or not r["path"]:
                continue
            if eng.is_message(task, r) and r.get("optional"):
                if os.path.isfile(r["path"]):
                    tickets.append(r["path"])     # 已在场单据:确认时销单
            elif deliver is None and not r.get("optional"):
                deliver = r["path"]               # 首个必产=作业面
        if deliver is None:
            prods = [r["path"] for r in task["rows"]
                     if r["kind"] == "产物" and r["path"]]
            if not prods:
                QMessageBox.warning(self, "无作业面", "该任务没有产物弧路径。")
                return
            deliver = prods[0]
        self._suppress_kick = True        # 压掉空槽自动开场,由工位语境开场
        self._open_editor(deliver)        # (换文件会清 _work,故先开后绑)
        self._suppress_kick = False
        self._work = {"tdir": tdir, "case": case, "tickets": tickets,
                      "instruction": (task.get("instruction") or "").strip(),
                      "inputs": inputs}
        self.btn_confirm.setVisible(True)
        # 工位开场:亮牌=要办什么+依据什么,引导人自然语言给答案
        self._assist_log = []
        self.assist_input.setText("（开场）亮牌：这个工位要办什么、依据什么、该收什么")
        self.assist_talk()
        self._assist_log[-1] = ("你", "〔工位开场:agent 主动亮牌〕")

    def do_new_case(self, item):
        """新案卷（8-19）：方法节点一键立案——建 实例/<类>/<案卷>/ 架并
        打开申请编辑（免手工 mkdir）。两段流是机制使然：申请（含内容记号
        要的键）填到合法，工位才能解析产物路径——先聊齐申请并保存，再
        右键案卷→工位→办结☐ 起草产物。"""
        tdir = item.data(ROLE_PATH)
        kr = eng.klass_rel(tdir, self.root)
        if not kr:
            QMessageBox.information(self, "新案卷", "该任务无类根，无法立案。")
            return
        case, ok = QInputDialog.getText(
            self, "新案卷",
            f"案卷号（将建 实例/{os.path.basename(kr)}/<案卷号>/）：")
        case = (case or "").strip()
        if not ok or not case:
            return
        if "/" in case or "\\" in case or case.startswith(".") \
                or case in (".", ".."):
            QMessageBox.warning(self, "新案卷", "案卷号不合法（含路径段或点开头）。")
            return
        cdir = os.path.join(self.root, "实例", os.path.basename(kr), case)
        if os.path.exists(cdir):
            QMessageBox.warning(self, "新案卷", f"案卷已存在：{case}")
            return
        os.makedirs(os.path.join(cdir))
        apply_path = os.path.join(cdir, "申请.md")
        if not os.path.exists(apply_path):
            with open(apply_path, "w", encoding="utf-8") as f:
                f.write("# 申请\n\n（和助手聊：frontmatter 键照《女娲格式》卡填，"
                        "保存后再开工位）\n")
        self.refresh()
        self._open_editor(apply_path)
        # 选中案卷目录（不选申请叶——叶选中会触发「点输入即开工位」
        # 自动跳转，把编辑器抢到产物上；新案卷要先聊申请）
        it = self.items_by_path.get(cdir)
        if it is not None:
            self.tree.setCurrentIndex(it.index())
        self.statusBar().showMessage(
            f"🆕 案卷已立：实例/{os.path.basename(kr)}/{case}"
            "——先把申请聊齐保存，再右键案卷 → 工位 → 办结☐ 起草产物")

    def do_login(self):
        """登录（97 号律二：对象名驱动）。异步模态——不阻塞事件循环，
        验收/单测可从 activeModalWidget 找到对话框填表（死路二：exec 卡线程）。"""
        dlg = LoginDialog(self.root, self)
        dlg.accepted.connect(lambda: self._set_principal(dlg.principal))
        dlg.open()

    def _set_principal(self, p):
        self._principal = p
        if p is None:                      # 注销：签字面随之撤下（话语=签字的前提）
            self.lbl_principal.setText(" 主体: 未登录  ")
            self.statusBar().showMessage("已注销——签字面关闭（登录=话语的前提）")
            return
        self.lbl_principal.setText(
            f" 主体: {p['姓名']}（{p['编号']}）  ")
        self.statusBar().showMessage(
            f"登录主体 {p['姓名']}（{p['主体值']}）——办单署名已挂会话")

    def _executor_args(self):
        """绿任务办结署名（§5 主体=点火三元组第三维）：登录时账记执行者。"""
        return (["--executor", self._principal["主体值"]]
                if self._principal else [])

    def _nav_to(self, path, msg=None):
        """办结即导航（8-19）：切目录视角→树上选中定位→状态栏报落点
        ——建完不用找，「在哪」由系统说话。msg 可换文案（类→实例直通用）。"""
        if not path:
            return
        if self.cb_view.currentText() != "目录":
            self.cb_view.setCurrentText("目录")
        self.refresh()
        it = self.items_by_path.get(path) \
            or self.items_by_path.get(os.path.dirname(path))
        if it is not None:
            self.tree.setCurrentIndex(it.index())
        self.statusBar().showMessage(msg or
                                     f"✅ 办结入账：产物 → {os.path.relpath(path, self.root)}")

    def _reenter_ok(self, tdir, case):
        """重办结防覆盖（8-19）：本案卷已有账且输入已变 → 明示将改写旧账
        （《女娲格式》第四条：一案卷一手术）。"""
        try:
            task = eng.load_task(tdir, self.root, case=case)
        except SystemExit:
            return True
        try:
            rec = eng.load_account(eng.rec_dir(task), self.root) or {}
        except (ValueError, OSError):
            return True
        for it in rec.get("输入清单") or []:
            n = it.get("名称")
            p = os.path.join(self.root, n) if n else None
            if p and os.path.isfile(p) and it.get("sha256") \
                    and eng.sha256(p) != it["sha256"]:
                return QMessageBox.question(
                    self, "重办结将改写账",
                    f"本案卷已有账，且输入已变（{os.path.basename(n)}）。\n"
                    "重办结会改写旧账——旧产物失去持证（lint 报无照），"
                    "旧账只在 git。\n按《女娲格式》第四条：一案卷一手术，"
                    "改立别类请开新案卷。\n\n仍要办结？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                ) == QMessageBox.StandardButton.Yes
        return True

    def confirm_work(self):
        """唯一确认按钮:保存交付→销单→backfill 入账,一次事务。
        办结即导航：完成后自动定位到产物落点。"""
        w = getattr(self, "_work", None)
        if not w:
            return
        if self._busy():
            QMessageBox.warning(self, "占线", "已有进程在执行，等它结束。")
            return
        if not self._reenter_ok(w["tdir"], w["case"]):
            return
        deliver = self._edit_path                 # 导航目标=本工位作业面
        self._save_editor()                       # 交付落盘(确认即保存)
        acts = []
        for t in w["tickets"]:                    # 销单=收回(事已办妥)
            try:
                os.remove(t)
                acts.append(f"销单 {os.path.basename(t)}")
            except FileNotFoundError:
                pass
        note = f"通用界面确认·{w['case']}"
        args = ["-u", os.path.join(BASE, "i3dna-engine", "i3dna_engine.py"),
                "backfill", w["tdir"], "--case", w["case"],
                "--note", note] + self._executor_args()
        self._engine_qproc(
            args, f"办结入账（实例 {w['case']}）："
            f"{os.path.relpath(w['tdir'], self.root)}"
            + ("　|　" + "、".join(acts) if acts else ""), verb="办结入账",
            hook=("nav", deliver) if deliver else None)
        self._work = None
        self.btn_confirm.setVisible(False)

    def do_backfill_human_tdir(self, tdir, case):
        """人工工位办结：人已在树上干完活（账外直写），此处补录台账。
        受体显式：实例写进对话框标题并作为 --case 明传（不靠环境暗补）。"""
        if self._busy():
            QMessageBox.warning(self, "占线", "已有进程在执行，等它结束。")
            return
        if case and not self._reenter_ok(tdir, case):
            return
        tag = f"（实例 {case}）" if case else ""
        note, ok = QInputDialog.getText(
            self, f"办结入账{tag}", "经办备注（例：人工澄清·张三）：",
            text="人工办结")
        if not ok:
            return
        args = ["-u", os.path.join(BASE, "i3dna-engine", "i3dna_engine.py"),
                "backfill", tdir] \
            + (["--case", case] if case else []) \
            + (["--note", note] if note.strip() else []) \
            + self._executor_args()
        self._engine_qproc(args,
                           f"办结入账{tag}：{os.path.relpath(tdir, self.root)}",
                           verb="办结入账")

    def _class_level_case(self, tdir):
        """类级判官(检测/编译/信息化)对 {实例} 任务取首个实例代入——
        判的是变换本身,受体取代表实例(参数路径由此可解析)。"""
        if not self._task_marked(tdir):
            return None
        cases = self._class_cases(tdir)
        return cases[0] if cases else None

    def do_detect(self, item):
        if self._busy():
            QMessageBox.warning(self, "占线", "已有进程在执行，等它结束。")
            return
        tdir = item.data(ROLE_PATH)
        args = ["-u", os.path.join(BASE, "i3dna-engine", "i3dna_engine.py"),
                "detect", tdir, "--stream",
                "--engine", self.cb_engine.currentData()]
        c = self._class_level_case(tdir)
        if c:
            args += ["--case", c]
        self._engine_qproc(args, "检测可符号化…（判官报告只投影不落树，"
                                 "拿拆分建议去重构微任务）", "检测中")

    def do_inform(self, item):
        if self._busy():
            QMessageBox.warning(self, "占线", "已有进程在执行，等它结束。")
            return
        tdir = item.data(ROLE_PATH)
        args = ["-u", os.path.join(BASE, "i3dna-engine", "i3dna_engine.py"),
                "inform", tdir, "--stream",
                "--engine", self.cb_engine.currentData()]
        c = self._class_level_case(tdir)
        if c:
            args += ["--case", c]
        self._engine_qproc(args, "检测可信息化（绿→蓝）…（判官报告只投影"
                                 "不落树，拿转蓝路径去改任务定义）", "检测中")

    def do_compile(self, item):
        if self._busy():
            QMessageBox.warning(self, "占线", "已有进程在执行，等它结束。")
            return
        tdir = item.data(ROLE_PATH)
        args = ["-u", os.path.join(BASE, "i3dna-engine", "i3dna_engine.py"),
                "compile", tdir, "--stream",
                "--engine", self.cb_engine.currentData()]
        c = self._class_level_case(tdir)
        if c:
            args += ["--case", c]
        self._engine_qproc(args, "编译中…（LLM 把变换写成确定性程序，"
                                 "进暂存隔离试跑；落位与否由你验收）", "编译中",
                           hook=("compile_review", tdir))

    def _compile_review(self, tdir):
        """编译验收视图：三件证据呈人，落位/放弃两个按钮。验收永远主观归人。"""
        stage = os.path.join(tdir, ".i3dna_compile")
        prog = os.path.join(stage, "执行程序", "主程序.py")
        if not os.path.isfile(prog):
            QMessageBox.warning(self, "编译验收", "暂存里没有主程序——编译未产出。")
            return

        def _read(name):
            p = os.path.join(stage, name)
            return open(p, encoding="utf-8", errors="replace").read() \
                if os.path.isfile(p) else "（无）"

        meta = {}
        try:
            meta = json.loads(_read("编译元.json"))
        except Exception:
            pass
        dlg = QDialog(self)
        dlg.setWindowTitle("编译验收——正确性在此层只能主观判断，落位与否归你")
        dlg.resize(980, 720)
        lay = QVBoxLayout(dlg)
        vsum = "；".join(f"{k}：{v}" for k, v in (meta.get("产物比对") or {}).items())
        lay.addWidget(QLabel(
            f"<b>{os.path.relpath(tdir, self.root)}</b> · 引擎 {meta.get('引擎','?')}"
            f" · 试跑退出码 {meta.get('试跑退出码','?')}"
            + (f"<br>产物比对：{vsum}" if vsum else "")
            + (f"<br>运行时输入（agent 自报）：{'、'.join(meta['运行时输入'])}"
               if meta.get("运行时输入") else "")))
        tabs = QTabWidget()
        for title, text in (("主程序（全文）", _read(os.path.join("执行程序", "主程序.py"))),
                            ("试跑输出", _read("试跑输出.txt")),
                            ("产物差异（vs 现物）", _read("试跑差异.txt"))):
            ed = QPlainTextEdit()
            ed.setPlainText(text)
            ed.setReadOnly(True)
            tabs.addTab(ed, title)
        lay.addWidget(tabs)
        bar = QHBoxLayout()
        bar.addStretch()
        for label, flag in (("落位转红", "--accept"), ("放弃（清暂存）", "--discard"),
                            ("稍后再定", None)):
            b = QPushButton(label)
            if flag is None:
                b.clicked.connect(dlg.reject)
            else:
                b.clicked.connect(lambda _, fl=flag: (dlg.accept(),
                                                      self._compile_finalize(tdir, fl)))
            bar.addWidget(b)
        lay.addLayout(bar)
        dlg.exec()

    def _compile_finalize(self, tdir, flag):
        import subprocess as _sp
        args = [sys.executable, os.path.join(BASE, "i3dna-engine", "i3dna_engine.py"),
                "compile", tdir, flag]
        r = _sp.run(args, capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
        self.show_html(f"<h3>编译{'落位' if flag == '--accept' else '放弃'}"
                       f"{'🔴' if flag == '--accept' and r.returncode == 0 else ''}</h3>"
                       "<pre style='white-space:pre-wrap; word-wrap:break-word'>$ python3 " + " ".join(args[1:]) + "\n"
                       + _htm.escape(r.stdout + r.stderr) + "</pre>")
        self.refresh()

    def do_revert(self, item):
        tdir = item.data(ROLE_PATH)
        if QMessageBox.question(
                self, "回退联结主义",
                f"删除 {os.path.basename(tdir)}/执行程序/ 退回蓝任务？\n"
                "journal 里有全档（编译落位那笔提交），可随时复辟。") \
                != QMessageBox.StandardButton.Yes:
            return
        import subprocess as _sp
        args = [sys.executable, os.path.join(BASE, "i3dna-engine", "i3dna_engine.py"),
                "revert", tdir]
        r = _sp.run(args, capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
        self.show_html("<h3>回退联结主义</h3><pre style='white-space:pre-wrap; word-wrap:break-word'>$ python3 "
                       + " ".join(args[1:]) + "\n"
                       + _htm.escape(r.stdout + r.stderr) + "</pre>")
        self.refresh()

    def _xlsx_html(self, path):
        try:
            wb = eng.openpyxl.load_workbook(path, read_only=True, data_only=True)
        except Exception as e:
            return f"<p>xlsx 打不开：{e}</p>"
        h = []
        for ws in wb.worksheets:
            rows = []
            for row in ws.iter_rows(values_only=True):
                cells = [eng.norm(c) for c in row]
                if any(cells):
                    rows.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells)
                                + "</tr>")
            h.append(f"<h4>[sheet] {ws.title}</h4><table border=1 cellspacing=0 "
                     f"cellpadding=3>" + "".join(rows) + "</table>")
        wb.close()
        return "".join(h)

    def do_add_arc(self, item, kind):
        """往微任务参数表追加一条弧（机器代笔）。类型默认带角色标记保证分类正确。"""
        import glob as _glob
        tdir = item.data(ROLE_PATH)
        recipes = _glob.glob(os.path.join(tdir, "__*大模型智能体*版本.xlsx"))
        if not recipes:
            QMessageBox.warning(self, "不支持", "任务定义/纯索引族暂不支持图形加弧。")
            return
        if kind == "输入":
            f, _ = QFileDialog.getOpenFileName(self, "选择输入文件", self.root)
            if not f:
                return
            f = os.path.abspath(f)
            if not f.startswith(self.root + os.sep):
                QMessageBox.warning(self, "越界", "输入必须在包根之内。")
                return
            tgt_dir, name = os.path.dirname(f), os.path.basename(f)
        else:
            d = QFileDialog.getExistingDirectory(self, "选择产物落点目录", self.root)
            if not d:
                return
            d = os.path.abspath(d)
            if not d.startswith(self.root + os.sep):
                QMessageBox.warning(self, "越界", "产物落点必须在包根之内。")
                return
            name, ok = QInputDialog.getText(self, "产物名称", "产物文件名：")
            if not ok or not name.strip():
                return
            tgt_dir, name = d, name.strip()
        desc, ok = QInputDialog.getText(self, "描述", "【描述】：")
        if not ok:
            return
        default_t = ("【补登记_输入参数文件】" if kind == "输入"
                     else "【补登记_成果模型文件】")
        ptype, ok = QInputDialog.getText(self, "参数文件类型",
                                         "【参数文件类型】（末段角色标记勿删）：",
                                         text=default_t)
        if not ok:
            return
        anchor = "\\...\\" + os.path.relpath(tgt_dir, self.root).replace("/", "\\")
        base = os.path.basename(tgt_dir)
        ver = base.lstrip("_") if len(base) > 4 and base.lstrip("_")[:3].isalpha() \
            and "-" in base else "*"
        wb = eng.openpyxl.load_workbook(recipes[0])
        ws = wb.active
        seqs = [int(c[0]) for c in eng.data_rows(ws)]
        ws.append([str(max(seqs) + 1 if seqs else 0), desc.strip() or "*",
                   ptype.strip(), anchor, ver, name])
        wb.save(recipes[0])
        wb.close()
        self.statusBar().showMessage(
            f"已加{kind}弧：{name} → {os.path.basename(recipes[0])}")
        self.refresh()

    def _preflight_html(self, tdir):
        """逐受体预检：{实例}任务每实例一行判词 + 首个实例的弧表（结构同构）。"""
        verdicts = core.preflight_verdicts(self.root, tdir)
        if not verdicts:
            return "<p>⚠ 无可预检受体（未实例化或任务不可解析）。</p>"
        task = self._task_view(tdir)
        if task is None:
            return "<p>⚠ 任务不可解析。</p>"
        rows = eng.preflight_rows(task)
        body = []
        for r, (k, d, n, s, ok) in zip(task["rows"], rows[:-1]):
            if r.get("path") and os.path.exists(r["path"]):
                rel = os.path.relpath(r["path"], self.root)
                n_html = f"<a href='i3dna:{rel}'>{n}</a>"
            else:
                n_html = n
            body.append(f"<tr><td>{'✓' if ok else '✗'}</td><td>{k}</td>"
                        f"<td>{d}</td><td>{n_html}</td><td>{s}</td></tr>")
        return ("<h4>预检（逐实例）</h4><p>"
                + "<br>".join(v for _c, v in verdicts) + "</p>"
                + "<table border=1 cellspacing=0 cellpadding=3><tr><th></th>"
                "<th>角色</th><th>描述</th><th>名称</th><th>状态</th></tr>"
                + "".join(body) + "</table>")

    def do_preflight(self, item):
        self.show_html(f"<h3>{item.text()}</h3>"
                            + self._preflight_html(item.data(ROLE_PATH)))

    def _record_html(self, tdir):
        accounts = [(c, rd) for c, rd in self._task_accounts(tdir)
                    if eng._account_exists(rd, self.root)]
        if not accounts:
            return "<p>暂无点火记录（账是 M0：实例模式在 实例/<类>/<k>/__账/）。</p>"
        return "".join(core.one_record_html(self.root, c, rd)
                       for c, rd in accounts)

    def do_record(self, item):
        self.show_html(f"<h3>{item.text()}</h3>"
                            + self._record_html(item.data(ROLE_PATH)))

    def on_anchor(self, url):
        s = url.toString()
        if s.startswith("i3dna-delrow:"):          # 修复提案：删除悬空登记行
            _, rel, seq = s.split(":", 2)
            self._fix_delete_row(rel, seq)
            return
        if url.scheme() != "i3dna":
            return
        p = os.path.join(self.root, url.path() or s[6:])
        it = self.items_by_path.get(p) or self.items_by_path.get(os.path.dirname(p))
        if it is not None:
            self.tree.setCurrentIndex(it.index())
            self.tree.scrollTo(it.index())

    # ── 修复提案：三桶分诊，选择归人 ────────────────────────

    def _triage(self):
        rep = getattr(self, "lint_rep", None) or lint.lint_tree(self.root)
        return core.triage_lint(rep.errors, rep.warnings)

    def show_coverage(self):
        """MBT 覆盖报告(P3):验收挂树上——变迁/边覆盖,缺口即推进清单。"""
        rep = core.coverage_report(self.root)
        nf, nt = rep["变迁覆盖"]
        kw, ke = rep["边覆盖"]
        full = nf == nt and kw == ke
        h = [f"<h3>覆盖报告（验收挂树上）</h3>"
             f"<p>变迁覆盖 {nf}/{nt} · 边覆盖 {kw}/{ke}　"
             + ("🟢 全覆盖" if full else "缺口即推进清单——右键实例「推进本实例」收敛")
             + "</p>"]
        if rep["未点火"]:
            h.append("<h4>◻ 未点火（变迁缺口）</h4>"
                     "<table border=1 cellspacing=0 cellpadding=3>"
                     + "".join(
                         f"<tr><td><a href='i3dna:{os.path.relpath(t, self.root)}'>"
                         f"{os.path.relpath(t, self.root)}</a></td></tr>"
                         for t in rep["未点火"]) + "</table>")
        missing = [e for e in rep["边"] if e not in rep["已走过"]]
        if missing:
            h.append("<h4>◻ 未走过（边缺口）</h4>"
                     "<table border=1 cellspacing=0 cellpadding=3>"
                     + "".join(
                         f"<tr><td>{os.path.basename(u)}→{os.path.basename(v)}</td>"
                         f"<td>{os.path.relpath(p, self.root)}</td></tr>"
                         for u, v, p in missing) + "</table>")
        self.show_html("".join(h))

    def show_lint(self):
        """全树 lint 聚合视图（Problems 面板）：逐条可点击跳转到树节点。"""
        rep = getattr(self, "lint_rep", None) or lint.lint_tree(self.root)
        h = [f"<h3>全树对账</h3><p>绑定边 {rep.edges} 条 · "
             f"错误 {len(rep.errors)} · 警告 {len(rep.warnings)}</p>"]
        for title, mark, items in (("错误", "✗", rep.errors),
                                   ("警告", "⚠", rep.warnings)):
            if not items:
                continue
            rows = []
            for where, msg in items:
                fpart = where.split("#")[0].split("·")[0]
                rows.append(
                    f"<tr><td>{mark}</td>"
                    f"<td><a href='i3dna:{fpart}'>{where}</a></td>"
                    f"<td>{msg}</td></tr>")
            h.append(f"<h4>{title}（{len(items)}）</h4>"
                     "<table border=1 cellspacing=0 cellpadding=3>"
                     + "".join(rows) + "</table>")
        if not rep.errors and not rep.warnings:
            h.append("<p>🟢 干净</p>")
        self.show_html("".join(h))

    def show_fix_proposals(self):
        b1, b2, b3 = self._triage()
        h = [f"<h3>修复提案（分诊）</h3>"
             f"<p>规范空白 {len(b1)} · 过期信号 {len(b2)} · 可修悬空 {len(b3)}</p>"]
        if b1:
            h.append(f"<h4>① 规范空白（{len(b1)}）——待对表，机器不修</h4>"
                     "<p>语义未决（行0 自声明 / 根变量），修法由博士定：确认惯例则教"
                     "对账器解读，确认真绑定则补目标。见 57 号六问、62 号语音单。</p>"
                     "<table border=1 cellspacing=0 cellpadding=3>"
                     + "".join(f"<tr><td>{w}</td><td>{r}</td></tr>"
                               for w, _, r in b1) + "</table>")
        if b2:
            h.append(f"<h4>② 过期信号（{len(b2)}）——修法=重新点火</h4>"
                     "<p>输入在记账后变了：这是漂移证据不是垃圾，改记录=伪造审计。"
                     "点任务重新点火即自愈。</p>"
                     "<table border=1 cellspacing=0 cellpadding=3>"
                     + "".join(f"<tr><td><a href='i3dna:{os.path.dirname(f)}'>"
                               f"{w}</a></td><td>{m[:80]}</td></tr>"
                               for w, m, f in b2) + "</table>")
        if b3:
            h.append(f"<h4>③ 真悬空（{len(b3)}）——逐条确认后删登记行</h4>"
                     "<table border=1 cellspacing=0 cellpadding=3>")
            for w, m, f in b3:
                seq = w.split("#行")[1].split("(")[0] if "#行" in w else ""
                act = (f"<a href='i3dna-delrow:{f}:{seq}'>删此行</a>"
                       if seq else "（无行号，手工处理）")
                h.append(f"<tr><td>{w}</td><td>{m[:80]}</td><td>{act}</td></tr>")
            h.append("</table>")
        if not (b1 or b2 or b3):
            h.append("<p>🟢 无账实不符</p>")
        self.show_html("".join(h))

    def _fix_delete_row(self, rel, seq):
        path = os.path.join(self.root, rel)
        if QMessageBox.question(
                self, "确认删行",
                f"删除 {rel} 的登记行 #{seq}？（原表先备份）") \
                != QMessageBox.StandardButton.Yes:
            return
        import shutil as _sh
        import tempfile as _tf
        _sh.copy2(path, os.path.join(_tf.gettempdir(),
                                     "i3dna_fixbak_" + os.path.basename(path)))
        wb = eng.openpyxl.load_workbook(path)
        ws = wb.active
        for i, row in enumerate(ws.iter_rows(), start=1):
            cells = [eng.norm(c.value) for c in row]
            if cells and cells[0] == seq and not eng.is_coord_row(cells):
                ws.delete_rows(i)
                break
        wb.save(path)
        wb.close()
        self.statusBar().showMessage(f"已删 {rel} 行#{seq}（备份在系统临时目录）")
        self.refresh()
        self.show_fix_proposals()

    def _dept_name(self, k):
        """部门号→名称（档案 部门.md 的 名称 键；读不到回退部门号）。"""
        v = eng.get_value(os.path.join(self.root, "实例", "部门", k,
                                       "部门.md"), "名称")
        return v or k


    def do_stop(self):
        """终止在飞的点火/推进：连锅端掉引擎及其子进程（启动脚本/claude/omp）。
        暂存-验收保证被掐的那炮零副作用。全部并行实例一起终止。"""
        if not self._runs:
            self.statusBar().showMessage("没有在飞的进程")
            return
        import subprocess as _sp
        for ctx in self._runs.values():
            proc = ctx["proc"]
            if proc.state() == QProcess.ProcessState.NotRunning:
                continue
            pid = proc.processId()
            kids = _sp.run(["pgrep", "-P", str(pid)], capture_output=True,
                           text=True).stdout.split()
            grandkids = []
            for k in kids:
                grandkids += _sp.run(["pgrep", "-P", k], capture_output=True,
                                     text=True).stdout.split()
            for p in grandkids + kids:
                _sp.run(["kill", "-TERM", p], capture_output=True)
            if ctx.get("log_fh") is not None:
                ctx["log_fh"].write("\n—— 用户终止 ——\n")
                ctx["log_fh"].close()
                ctx["log_fh"] = None
            proc.terminate()
        self.statusBar().showMessage("已终止（暂存隔离，真树零副作用）")

    # ── 并行运行管线：key→ctx，一实例一进程一流 ─────────────

    def _busy(self):
        """内容页类操作（编译/检测/办结/运行文件）的占线判据：
        它们共用内容页与 M1 任务目录暂存，任何在飞进程都不与之并行。"""
        return bool(self._runs)

    def _case_busy(self, case):
        """执行流类操作（点火/推进）的占线判据：按实例粒度。
        写集按构造不相交——K1 在推进不挡 K2；同实例重入才挡。"""
        return any(ctx["target"] == "stream" and ctx.get("case") == case
                   for ctx in self._runs.values())

    def _divert_details(self):
        """内容页在飞时用户看别处（推进计划/另一实例流）→ 停止覆盖内容页。"""
        for ctx in self._runs.values():
            if ctx["target"] == "detail":
                ctx["diverted"] = True

    def _start_run(self, args, *, target, case, verb, buf, log_verb,
                   log_tdir=None, log_cmd=None, program=None, workdir=None,
                   sandbox=None, hook=None, init_runlog=None):
        """统一点火口：创建 ctx 注册进 self._runs，接好信号即飞。
        target=stream → 输出进该实例执行流页签；target=detail → 内容页。"""
        import time as _t
        self._run_seq += 1
        key = self._run_seq
        disp = log_cmd if log_cmd is not None else ' '.join(args[1:])
        ctx = {"target": target, "case": case, "verb": verb, "buf": buf,
               "runlog": list(init_runlog or []), "sandbox": sandbox,
               "hook": hook, "diverted": False,
               "log_fh": None, "log_path": "",
               "t0": _t.time(), "last_out": _t.time()}
        proc = QProcess(self)
        if workdir:
            proc.setWorkingDirectory(workdir)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.readyReadStandardOutput.connect(lambda k=key: self._on_run_output(k))
        proc.finished.connect(
            lambda c, s, k=key: self._on_run_done(k, c, s))
        ctx["proc"] = proc
        self._runs[key] = ctx
        # 磁盘日志：点火日志落任务目录（带实例号），其余落 __日志/
        ts = datetime.now().strftime('%Y%m%d-%H%M%S')
        if log_tdir is not None:
            log_dir, name = log_tdir, f"__点火日志_{ts}_{case or 'nocase'}.txt"
        else:
            log_dir = os.path.join(self.root, "__日志")
            name = f"{log_verb}_{ts}_{case or 'nocase'}.log"
        os.makedirs(log_dir, exist_ok=True)
        ctx["log_path"] = os.path.join(log_dir, name)
        ctx["log_fh"] = open(ctx["log_path"], "w", encoding="utf-8")
        ctx["log_fh"].write(f"$ python3 {disp}\n\n")
        ctx["log_fh"].flush()
        self._hb.start()
        prog = program or sys.executable
        proc.start(prog, args)
        return ctx

    def _stream_tab(self, case):
        """取/建该实例的执行流页签（case=None → 无实例包的独页）。"""
        page = self._stream_pages.get(case)
        if page is None:
            view = QTextBrowser()
            view.setOpenExternalLinks(False)
            page = {"view": view, "buf": []}
            self._stream_pages[case] = page
            self.stream_tabs.addTab(view, str(case) if case else "执行流")
        return page

    def _reconcile_stream_tabs(self):
        """页签与实例库对账：新实例补页，消失实例收页（在飞的留）。"""
        want = list(getattr(self, "cases", None) or []) or [None]
        for c in want:
            if c not in self._stream_pages:
                self._stream_tab(c)
        for c in list(self._stream_pages):
            if c is not None and c not in want \
                    and not any(ctx.get("case") == c for ctx in self._runs.values()):
                page = self._stream_pages.pop(c)
                idx = self.stream_tabs.indexOf(page["view"])
                if idx >= 0:
                    self.stream_tabs.removeTab(idx)
                page["view"].deleteLater()

    def _run_header(self, ctx):
        import time as _t
        secs = int(_t.time() - ctx["t0"])
        silent = int(_t.time() - ctx["last_out"])
        note = ("（引擎工作中——所选车道长时间无中间输出属常态，非卡死）"
                if silent > 20 else "")
        return f"<h3>{ctx['verb']}…（已 {secs // 60}分{secs % 60:02d}秒）{note}</h3>"

    def _heartbeat(self):
        if not self._runs:
            self._hb.stop()
            return
        try:
            for ctx in self._runs.values():
                if ctx["target"] == "stream":
                    self._render_stream_tab(ctx["case"])
                elif not ctx["diverted"]:     # 用户去看别的了，不再覆盖
                    sb = self.detail.verticalScrollBar()
                    follow = sb.value() >= sb.maximum() - 30
                    keep = sb.value()
                    self.show_html(self._run_header(ctx) + "<pre style='white-space:pre-wrap; word-wrap:break-word'>" + "".join(ctx["runlog"])
                                   + "</pre>")
                    sb.setValue(sb.maximum() if follow else keep)
        except Exception as e:
            # 防止 slot 异常在 stderr 不可用时升级为 fatal/abort
            import logging
            logging.getLogger(__name__).exception("_heartbeat error: %s", e)

    def _on_run_output(self, key):
        import time as _t
        try:
            ctx = self._runs.get(key)
            if ctx is None:
                return
            ctx["last_out"] = _t.time()
            text = bytes(ctx["proc"].readAllStandardOutput()).decode("utf-8", "replace")
            if ctx["log_fh"] is not None:
                ctx["log_fh"].write(text)
                ctx["log_fh"].flush()
            if ctx["target"] == "stream":
                ctx["buf"].append(text)
                self._render_stream_tab(ctx["case"])
            else:
                ctx["runlog"].append(text)
                if not ctx["diverted"]:       # 用户去看别的了，只攒不刷屏
                    sb = self.detail.verticalScrollBar()
                    follow = sb.value() >= sb.maximum() - 30
                    keep = sb.value()
                    self.show_html(self._run_header(ctx) + "<pre style='white-space:pre-wrap; word-wrap:break-word'>" + "".join(ctx["runlog"])
                                   + "</pre>")
                    sb.setValue(sb.maximum() if follow else keep)
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception("_on_run_output error: %s", e)

    def _on_run_done(self, key, code, _status):
        try:
            ctx = self._runs.pop(key, None)
            if ctx is None:
                return
            tail = f"\n—— {'完成 🟢' if code == 0 else '失败 🔴'}，退出码 {code} ——"
            if ctx["log_fh"] is not None:
                ctx["log_fh"].write(tail + "\n")
                ctx["log_fh"].close()
                ctx["log_fh"] = None
                self.statusBar().showMessage(
                    f"日志已存 → {ctx['log_path']}", 8000)
            if ctx["target"] == "stream":
                if ctx.get("sandbox"):
                    tail += (f"\n⚠ 沙盒模式：产物与点火记录在 {ctx['sandbox']}，"
                             "正树未动——满意后去掉沙盒勾选重打才落正树。")
                ctx["buf"].append(tail)
                self._render_stream_tab(ctx["case"])
            else:
                note = (f"<p>⚠ <b>沙盒模式</b>：产物与点火记录在 {ctx['sandbox']}，"
                        "<b>正树未动</b>——满意后去掉沙盒勾选重打才落正树。</p>"
                        if ctx.get("sandbox") else "")
                ctx["runlog"].append(tail)
                self.show_html(f"<h3>{'完成 🟢' if code == 0 else '失败 🔴'}</h3>"
                               + note + "<pre style='white-space:pre-wrap; word-wrap:break-word'>" + "".join(ctx["runlog"]) + "</pre>")
                sb = self.detail.verticalScrollBar()
                sb.setValue(sb.maximum())
            if self._runs:                    # 还有在飞的（多实例并行），各自收尾
                hook = ctx.get("hook")
                if hook and hook[0] == "compile_review" and code == 0:
                    self._compile_review(hook[1])
                return
            self._hb.stop()
            if ctx["target"] == "detail":     # 完成信息压回 detail，refresh 后不丢
                done_html = self.detail.toHtml()
                self._guard_detail = True     # refresh 期间禁止 on_select 覆盖
                self.refresh()
                self._guard_detail = False
                self.show_html(done_html)
            else:
                self.refresh()
            hook = ctx.get("hook")
            if hook and hook[0] == "compile_review" and code == 0:
                self._compile_review(hook[1])
            if hook and hook[0] == "nav" and code == 0:
                self._nav_to(hook[1])          # 办结即导航：跳到产物落点
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception("_on_run_done error: %s", e)

    def _render_stream_tab(self, case):
        """渲染某实例的执行流页签（在飞则带头部计时；在底部→跟随上翻→别打扰）"""
        import html as _h
        page = self._stream_pages.get(case)
        if page is None:
            return
        view = page["view"]
        running = [ctx for ctx in self._runs.values()
                   if ctx["target"] == "stream" and ctx.get("case") == case]
        head = f"<h3>执行流：实例 {case}</h3>" if case else "<h3>执行流</h3>"
        for ctx in running:
            head += self._run_header(ctx)
        sb = view.verticalScrollBar()
        follow = sb.value() >= sb.maximum() - 30
        keep = sb.value()
        view.setHtml(
            head
            + "<pre style='font-size:12px; white-space:pre-wrap; word-wrap:break-word'>"
            f"{_h.escape(''.join(page['buf']))}</pre>")
        sb.setValue(sb.maximum() if follow else keep)

    def _clear_stream(self):
        """清空当前页签实例的执行流 buffer（磁盘日志全文保留）"""
        w = self.stream_tabs.currentWidget()
        for case, page in self._stream_pages.items():
            if page["view"] is w:
                page["buf"] = []
                self._render_stream_tab(case)
                return


def main():
    app = QApplication(sys.argv)
    root = sys.argv[1] if len(sys.argv) > 1 else \
        QFileDialog.getExistingDirectory(None, "选择 I3DNA 包根目录")
    if not root:
        return 1
    win = Explorer(root)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
