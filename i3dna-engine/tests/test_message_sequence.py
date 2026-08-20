# -*- coding: utf-8 -*-
"""同键消息顺号（104号 工单·缺陷3 → 修订2/工单106）：顺号＝消息类型的
投递属性——类型文件（消息/<单名>.md）frontmatter 声明「顺号: 真」才启用
（默认关闭＝现状）。声明者同名顺号共存＋缺席免收回；未声明者（含跨主角
文件弧消费的单，如审查单）固定名翻页/收回不动。判据=磁盘与账 JSON
（97号）。主臂走 write 车道（生产默认），另钉 stdout 车道（顺号实名须
同步落位表——账记声明名即 lint 虚报漂移）。"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(os.path.dirname(HERE), "i3dna_engine.py")

DEV = """---
i3dna: 微任务
输入:
  - "{实例}/需求/需求.md"
产物:
  - "{实例}/代码/核心.py"
  - 路径: "实例/审查架/收件箱/请求审查单__{案卷号}.md"
    可缺: 真
---
开发：完工即开单投递审查信箱。
"""

TESTER = """---
i3dna: 微任务
输入:
  - 路径: "{实例}/测试/返工单.md"
    可缺: 真
  - "{实例}/需求/需求.md"
产物:
  - "{实例}/测试/测试.py"
  - 路径: "{实例}/测试/返工单.md"
    可缺: 真
---
测试：失败才开返工单（自开自销：同任务双声明）。
"""

REVIEW = """---
i3dna: 微任务
输入:
  - "实例/审查架/收件箱"
产物:
  - "审查记录.md"
---
审查：吃收件箱（目录弧→盘点单）。
"""

TICKET_LAW = """---
i3dna: 消息
键: [单号]
顺号: 真
路径: "实例/审查架/收件箱/请求审查单__{案卷号}.md"
发送方: 开发
接收方: 审查
完成: 审查消费即删
---
请求审查单类型件（声明顺号：目录弧收件箱消费，一请求一量子）。
"""

INSPECT = """---
i3dna: 微任务
产物:
  - 路径: "实例/产线/{案卷号}/测试/审查单.md"
    可缺: 真
---
质检：失败开出审查单（跨主角——落别家案卷，消费者按固定名读）。
"""

INSPECT_LAW = """---
i3dna: 消息
路径: "实例/产线/{案卷号}/测试/审查单.md"
---
审查单类型件（未声明顺号——文件弧消费，名字必须不变）。
"""

DEVFIX = """---
i3dna: 微任务
输入:
  - 路径: "{实例}/测试/审查单.md"
    可缺: 真
  - "{实例}/需求/需求.md"
产物:
  - "{实例}/代码/核心.py"
---
开发：按固定名读审查单修复（文件弧消费——名字变了就读不到新单）。
"""

STUB = """import os, re, sys
prompt = sys.stdin.read()
omit = os.environ.get("I3DNA_STUB_OMIT", "")
for p in re.findall(r"【产物→写到】(\\S+)", prompt):
    if omit and omit in p:
        continue
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(f"桩产物 {os.path.basename(p)}\\n")
print("完成")
"""

STUB_STDOUT = """import os, sys
for n in os.environ["I3DNA_STUB_PRODUCTS"].split(","):
    print(f"<<<I3DNA-产物:{n}>>>")
    print(f"桩正文 {n}")
"""


def _mk(parent, rel, text=""):
    p = os.path.join(parent, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def _tree(tmp_path):
    r = str(tmp_path)
    _mk(r, "域/x域/域.md", "---\ni3dna: 域\n---\n")
    _mk(r, "域/x域/类/产线/类.md", "---\ni3dna: 类\n范畴: 过程\n---\n")
    _mk(r, "域/x域/类/产线/方法/开发/任务.md", DEV)
    _mk(r, "域/x域/类/产线/方法/测试岗/任务.md", TESTER)
    _mk(r, "域/x域/类/审查部/类.md", "---\ni3dna: 类\n范畴: 过程\n---\n")
    _mk(r, "域/x域/类/审查部/方法/审查/任务.md", REVIEW)
    _mk(r, "消息/请求审查单.md", TICKET_LAW)
    _mk(r, "消息/返工单.md", "---\ni3dna: 消息\n路径: \"{实例}/测试/返工单.md\"\n---\n返工单种。\n")
    _mk(r, "实例/产线/X/需求/需求.md", "需求。\n")
    os.makedirs(os.path.join(r, "实例/审查架/收件箱"))
    _mk(r, "桩.py", STUB)
    _mk(r, "桩stdout.py", STUB_STDOUT)
    return r


def _fire(r, task_rel, case, omit="", io="write", stub="桩.py"):
    env = dict(os.environ, I3DNA_STUB_OMIT=omit)
    cmd = [sys.executable, ENGINE, "run", os.path.join(r, task_rel),
           "--root", r, "--engine", f"{sys.executable} {os.path.join(r, stub)}",
           "--io", io]
    if case:
        cmd += ["--case", case]
    return subprocess.run(cmd, capture_output=True, text=True, env=env,
                          timeout=120)


def _acc(r, cls, case, method):
    return json.load(open(os.path.join(
        r, "实例", cls, case, "__账", method, "__结果.json"), encoding="utf-8"))


def test_臂1_跨主角连发两火_裸名与r2共存且账记实名(tmp_path):
    r = _tree(tmp_path)
    p1 = _fire(r, "域/x域/类/产线/方法/开发", "X")
    assert p1.returncode == 0, p1.stderr[-400:]
    p2 = _fire(r, "域/x域/类/产线/方法/开发", "X")
    assert p2.returncode == 0, p2.stderr[-400:]
    box = os.path.join(r, "实例/审查架/收件箱")
    names = sorted(os.listdir(box))
    assert names == ["请求审查单__X.md", "请求审查单__X__r2.md"], names
    assert _acc(r, "产线", "X", "开发")["产物清单"][-1]["名称"] \
        .endswith("请求审查单__X__r2.md"), "账记顺号实名（不记声明名）"


def test_臂2_第三火缺席_前单纹丝不动(tmp_path):
    r = _tree(tmp_path)
    for _ in range(2):
        assert _fire(r, "域/x域/类/产线/方法/开发", "X").returncode == 0
    p3 = _fire(r, "域/x域/类/产线/方法/开发", "X", omit="请求审查单")
    assert p3.returncode == 0, p3.stderr[-400:]
    box = os.path.join(r, "实例/审查架/收件箱")
    assert sorted(os.listdir(box)) == ["请求审查单__X.md",
                                       "请求审查单__X__r2.md"], "免收回"
    rec = _acc(r, "产线", "X", "开发")
    assert not any("请求审查单" in it["名称"] for it in rec["产物清单"]), \
        "本轮未开单不入产物清单"


def test_臂3_自开自销_翻页与收回不动(tmp_path):
    r = _tree(tmp_path)
    assert _fire(r, "域/x域/类/产线/方法/测试岗", "X").returncode == 0
    assert _fire(r, "域/x域/类/产线/方法/测试岗", "X").returncode == 0
    f = os.path.join(r, "实例/产线/X/测试/返工单.md")
    assert os.path.isfile(f), "在场→覆盖更新（自开自销翻页，不生 r2）"
    assert not os.path.exists(f.replace(".md", "__r2.md"))
    p3 = _fire(r, "域/x域/类/产线/方法/测试岗", "X", omit="返工单")
    assert p3.returncode == 0, p3.stderr[-400:]
    assert not os.path.exists(f), "缺席→收回（现状语义不动）"


def test_臂4_悬账门_r2在场结账被拒(tmp_path):
    r = _tree(tmp_path)
    for _ in range(2):
        assert _fire(r, "域/x域/类/产线/方法/开发", "X").returncode == 0
    p = subprocess.run(
        [sys.executable, ENGINE, "backfill",
         os.path.join(r, "域/x域/类/产线/方法/开发"),
         "--root", r, "--case", "X"],
        capture_output=True, text=True, timeout=60)
    assert p.returncode != 0
    assert "悬账" in (p.stdout + p.stderr), "顺号单也是案卷在途承诺"
    rec = _acc(r, "产线", "X", "开发")
    assert rec["状态"] == "执行", "拒=零副作用：火账原样，未被办结覆盖"


def test_臂5_盘点单_顺号名入册且新到催火(tmp_path):
    r = _tree(tmp_path)
    for _ in range(2):
        assert _fire(r, "域/x域/类/产线/方法/开发", "X").returncode == 0
    p = _fire(r, "域/x域/类/审查部/方法/审查", None)
    assert p.returncode == 0, p.stderr[-400:]
    rec = json.load(open(os.path.join(
        r, "域/x域/类/审查部/方法/审查/__结果.json"), encoding="utf-8"))
    dir_item = next(it for it in rec["输入清单"] if it.get("目录"))
    assert any("__r2" in n for n in dir_item["清单"]), "顺号名自动入盘点册"
    _mk(r, "实例/审查架/收件箱/请求审查单__X__r3.md", "新单\n")
    plan2 = subprocess.run(
        [sys.executable, ENGINE, "converge", r, "--plan", "--max-rounds", "1"],
        capture_output=True, text=True, timeout=120)
    assert "目录已变" in plan2.stdout, "新到单子→盘点差异→催火消费者"


def test_臂6_stdout车道_顺号且账记实名(tmp_path):
    """stdout 车道同钉（104号 diff 只写了 write 车道——两洞同在，账记
    实名须同步 dst_of 落位表，否则 lint 立刻虚报漂移）。"""
    r = _tree(tmp_path)
    assert _fire(r, "域/x域/类/产线/方法/开发", "X").returncode == 0
    env_extra = {"I3DNA_STUB_PRODUCTS": "核心.py,请求审查单__X.md"}
    os.environ.update(env_extra)
    try:
        p2 = _fire(r, "域/x域/类/产线/方法/开发", "X", io="stdout",
                   stub="桩stdout.py")
    finally:
        for k in env_extra:
            os.environ.pop(k, None)
    assert p2.returncode == 0, p2.stderr[-400:]
    box = os.path.join(r, "实例/审查架/收件箱")
    assert sorted(os.listdir(box)) == ["请求审查单__X.md",
                                       "请求审查单__X__r2.md"]
    rec = _acc(r, "产线", "X", "开发")
    assert any(it["名称"].endswith("__r2.md") for it in rec["产物清单"]), \
        "stdout 车道账也记顺号实名（落位表同步）"


def test_回归钉_未声明顺号的跨主角消息_两轮仍落固定名(tmp_path):
    """本单核心钉（工单106）：修订1 的 _cross_actor 启发式（非本任务输入
    即顺号）会把文件弧消费的单误编号——审查单第二轮落成 __r2，开发永远
    读不到新单、结账被悬账门拦死。类型未声明顺号 → 两轮都落固定名（现状
    行为，安全兜底）。"""
    r = _tree(tmp_path)
    _mk(r, "域/x域/类/审查部/方法/质检/任务.md", INSPECT)
    _mk(r, "消息/审查单.md", INSPECT_LAW)
    _mk(r, "域/x域/类/产线/方法/开发2/任务.md", DEVFIX)
    os.makedirs(os.path.join(r, "实例/审查部/X"))
    p1 = _fire(r, "域/x域/类/审查部/方法/质检", "X")
    assert p1.returncode == 0, p1.stderr[-400:]
    p2 = _fire(r, "域/x域/类/审查部/方法/质检", "X")
    assert p2.returncode == 0, p2.stderr[-400:]
    d = os.path.join(r, "实例/产线/X/测试")
    assert sorted(os.listdir(d)) == ["审查单.md"], \
        "固定名覆盖不编号（消费者按名可读——本单炸点场景不动）"
    rec = _acc(r, "审查部", "X", "质检")
    assert all("__r" not in it["名称"] for it in rec["产物清单"]), "账无顺号名"
