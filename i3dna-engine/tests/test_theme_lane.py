# -*- coding: utf-8 -*-
"""主题车道行为三件套（形状定律 8-21·工单2）：①命名: uuid 落位代起名
（write/stdout 两车道，agent 只交内容不交名，并发零碰撞）；②目录弧一火
一单消费（字典序最小、选单-删除-入账同提交点、账记消费清单——缺陷15
A 档引擎侧＋缺陷4 回执）；③悬账门主题目录推广（缺陷19 收窄 8-21：普通
站对非消费目录休眠，全夹盘点挂结账站）。零主题声明＝行为与现状同（m1
逐字节兼容另证）。判据=磁盘+账+退出码（97号：断言与账）。"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(os.path.dirname(HERE), "i3dna_engine.py")

TYPE_LAW = """---
i3dna: 消息
主题: "实例/审批/{案卷号}/审批单"
命名: uuid
键:
  - 申请人
---
审批单种（目录即类型，uuid 身份）。
"""

TYPE_PLAIN = """---
i3dna: 消息
---
审批单种（零声明——老行为对照）。
"""

OPEN_TASK = """---
i3dna: 微任务
输入:
  - "{实例}/申请.md"
产物:
  - "实例/审批/{案卷号}/审批单"
---
开一张审批单（产物弧＝目录弧）。
"""

EAT_TASK = """---
i3dna: 微任务
输入:
  - "实例/审批/{案卷号}/审批单"
产物:
  - "{实例}/回执.md"
---
办一张审批单（输入弧＝目录弧，一火一单）。
"""

OTHER_TASK = """---
i3dna: 微任务
输入:
  - "{实例}/申请.md"
产物:
  - "{实例}/他件.md"
---
同案卷别的事（不消费队列——悬账门对照）。
"""

STUB = """import os, re, sys
prompt = sys.stdin.read()
for p in re.findall(r"【产物→写到】(\\S+)", prompt):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(f"桩产物 {os.path.basename(p)}\\n")
print("完成")
"""

STUB_STDOUT = """print("<<<I3DNA-产物:审批单>>>")
print("桩正文 审批单")
"""


def _mk(parent, rel, text=""):
    p = os.path.join(parent, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def _tree(tmp_path, law=TYPE_LAW, with_producer=True, with_other=True):
    r = str(tmp_path)
    _mk(r, "域/x域/域.md", "---\ni3dna: 域\n---\n")
    _mk(r, "域/x域/类/甲/类.md", "---\ni3dna: 类\n范畴: 过程\n---\n# 甲\n")
    _mk(r, "域/x域/类/甲/消息/审批单.md", law)
    if with_producer:
        _mk(r, "域/x域/类/甲/方法/开单/任务.md", OPEN_TASK)
    _mk(r, "域/x域/类/甲/方法/办单/任务.md", EAT_TASK)
    if with_other:
        _mk(r, "域/x域/类/甲/方法/别的/任务.md", OTHER_TASK)
        _mk(r, "实例/甲/c1/他件.md", "他件在场（可办结）。\n")
    _mk(r, "实例/甲/c1/申请.md", "---\n申请人: 张三\n---\n申请。\n")
    _mk(r, "桩.py", STUB)
    _mk(r, "桩stdout.py", STUB_STDOUT)
    return r


BOX = os.path.join("实例", "审批", "c1", "审批单")     # 主题队列（相对树根）


def _seed(r, names):
    box = os.path.join(r, BOX)
    os.makedirs(box, exist_ok=True)
    for n in names:
        _mk(r, f"{BOX}/{n}", f"---\n申请人: 张三\n---\n{n} 的单。\n")


def _run(r, task_rel, case="c1", io="write", stub="桩.py"):
    cmd = [sys.executable, ENGINE, "run", os.path.join(r, task_rel),
           "--root", r, "--io", io,
           "--engine", f"{sys.executable} {os.path.join(r, stub)}"]
    if case:
        cmd += ["--case", case]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120)


def _backfill(r, task_rel, case="c1"):
    return subprocess.run(
        [sys.executable, ENGINE, "backfill", os.path.join(r, task_rel),
         "--root", r, "--case", case],
        capture_output=True, text=True, timeout=60)


def _acc(r, case, method):
    return json.load(open(os.path.join(
        r, "实例", "甲", case, "__账", method, "__结果.json"), encoding="utf-8"))


UUID_RE = re.compile(r"^审批单__[0-9a-f]{8}(?:-[0-9a-f]{4}){3}"
                     r"-[0-9a-f]{12}\.md$")


def test_uuid落位_write车道_引擎代起名(tmp_path):
    """验收①a：目录弧产物落 审批单__<uuid4>.md；agent 只交内容不交名；
    账记实名（产物清单 sha 对得上）。"""
    r = _tree(tmp_path)
    p = _run(r, "域/x域/类/甲/方法/开单")
    assert p.returncode == 0, p.stderr[-500:]
    box = os.path.join(r, BOX)
    names = os.listdir(box)
    assert len(names) == 1 and UUID_RE.match(names[0]), names
    acc = _acc(r, "c1", "开单")
    assert acc["产物清单"][0]["名称"] == f"{BOX}/{names[0]}"
    assert acc["产物清单"][0]["sha256"], "账记实名＋sha"


def test_uuid落位_stdout车道(tmp_path):
    """验收①b：stdout 车道同律——块键=种名（pname），落盘名引擎代起。"""
    r = _tree(tmp_path)
    p = _run(r, "域/x域/类/甲/方法/开单", io="stdout", stub="桩stdout.py")
    assert p.returncode == 0, p.stderr[-500:]
    names = os.listdir(os.path.join(r, BOX))
    assert len(names) == 1 and UUID_RE.match(names[0]), names
    body = open(os.path.join(r, BOX, names[0]), encoding="utf-8").read()
    assert "桩正文 审批单" in body


def test_uuid落位_并发双火不撞名(tmp_path):
    """验收①c：两火并发各起各的 uuid——缺陷1 抢名非原子/缺陷3 同名覆盖
    釜底抽薪。"""
    r = _tree(tmp_path)
    tdir = os.path.join(r, "域/x域/类/甲/方法/开单")
    cmd = [sys.executable, ENGINE, "run", tdir, "--root", r, "--case", "c1",
           "--engine", f"{sys.executable} {os.path.join(r, '桩.py')}"]
    ps = [subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True) for _ in range(2)]
    for x in ps:
        o, e = x.communicate(timeout=120)
        assert x.returncode == 0, e[-500:]
    names = sorted(os.listdir(os.path.join(r, BOX)))
    assert len(names) == 2 and len(set(names)) == 2 \
        and all(UUID_RE.match(n) for n in names), names


def test_一火一单_选单字典序最小(tmp_path):
    """验收③：选单规则=字典序最小（确定性可复算）——单火后恰吃最小名。"""
    r = _tree(tmp_path, with_producer=False, with_other=False)
    _seed(r, ["审批单__b.md", "审批单__a.md", "审批单__c.md"])
    p = _run(r, "域/x域/类/甲/方法/办单")
    assert p.returncode == 0, p.stderr[-500:]
    assert sorted(os.listdir(os.path.join(r, BOX))) \
        == ["审批单__b.md", "审批单__c.md"], "恰吃一张＝字典序最小"
    acc = _acc(r, "c1", "办单")
    assert len(acc["消费清单"]) == 1
    assert acc["消费清单"][0]["名称"] == f"{BOX}/审批单__a.md"
    assert acc["消费清单"][0]["消费"] is True
    # 盘点记点火时队列（3 张在场）——一账一单：账说得出本火吃了哪张
    inv = next(it for it in acc["输入清单"] if it.get("目录"))
    assert len(inv["清单"]) == 3, "盘点记消费前队列"


def test_一火一单_converge三轮吃空(tmp_path):
    """验收②：夹具 3 张单 → converge 三轮吃空，每轮恰一张（末账消费清单
    1 张；首轮账已被末火覆盖，火次看输出计数）。"""
    r = _tree(tmp_path, with_producer=False, with_other=False)
    _seed(r, ["审批单__1.md", "审批单__2.md", "审批单__3.md"])
    p = subprocess.run(
        [sys.executable, ENGINE, "converge", r, "--root", r, "--case", "c1",
         "--engine", f"{sys.executable} {os.path.join(r, '桩.py')}",
         "--max-rounds", "6"],
        capture_output=True, text=True, timeout=300)
    assert p.returncode == 0, (p.returncode, p.stdout[-500:], p.stderr[-500:])
    assert os.listdir(os.path.join(r, BOX)) == [], "三轮吃空"
    assert p.stdout.count("微任务：") == 3, \
        f"恰三火（一火一单），实点火次：{p.stdout.count('微任务：')}"
    acc = _acc(r, "c1", "办单")
    assert [it["名称"] for it in acc["消费清单"]] == [f"{BOX}/审批单__3.md"], \
        "末火恰吃最后一张（字典序收尾）"


def test_悬账门_普通站休眠_结账站拦_排干放行(tmp_path):
    """验收④（缺陷19 改钉 8-21）：普通办结对非消费主题目录休眠——队列
    非空不拦别家办结（审批夹/知会夹各一单两站互等＝环形等待，报销003
    实证）；全夹盘点挂结账站（结账: 真）——有单拒，排干放行。"""
    r = _tree(tmp_path)
    _seed(r, ["审批单__z.md"])
    p = _backfill(r, "域/x域/类/甲/方法/别的")
    assert p.returncode == 0, p.stderr[-400:]     # 普通站：他队列不拦
    assert os.listdir(os.path.join(r, BOX)) == ["审批单__z.md"], "零副作用"
    _mk(r, "域/x域/类/甲/方法/别的/任务.md",
        OTHER_TASK.replace("i3dna: 微任务\n", "i3dna: 微任务\n结账: 真\n"))
    p2 = _backfill(r, "域/x域/类/甲/方法/别的")
    assert p2.returncode != 0
    assert "结账门" in (p2.stdout + p2.stderr)
    os.remove(os.path.join(r, BOX, "审批单__z.md"))
    p3 = _backfill(r, "域/x域/类/甲/方法/别的")
    assert p3.returncode == 0, p3.stderr[-400:]   # 排干后放行


def test_悬账门_消费方办结豁免_办结即消费(tmp_path):
    """验收④补：办单自身的办结正是消费动作——豁免不拦，且办结吃一张。"""
    r = _tree(tmp_path, with_producer=False, with_other=False)
    _seed(r, ["审批单__m.md"])
    _mk(r, "实例/甲/c1/回执.md", "回执在场。\n")
    p = _backfill(r, "域/x域/类/甲/方法/办单")
    assert p.returncode == 0, p.stderr[-400:]
    assert os.listdir(os.path.join(r, BOX)) == [], "办结消费一张"
    assert _acc(r, "c1", "办单")["消费清单"][0]["名称"] \
        == f"{BOX}/审批单__m.md"


def test_零声明_无uuid命名时落固定名(tmp_path):
    """验收⑥：无 主题:/命名: 声明 → 目录弧产物按老行为落**固定名文件**
    （占弧路径本身——文件槽，零迁移；m1 全树逐字节兼容另证）。"""
    r = _tree(tmp_path, law=TYPE_PLAIN)
    p = _run(r, "域/x域/类/甲/方法/开单")
    assert p.returncode == 0, p.stderr[-500:]
    assert os.path.isfile(os.path.join(r, "实例/审批/c1/审批单")), \
        "固定名落位（老行为：弧路径即文件）"
