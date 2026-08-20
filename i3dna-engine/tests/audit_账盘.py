#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""账-盘对账审计（一次性巡检脚本）：逐账把 输入清单/产物清单 的 sha256
对盘——验 ACID-C（每一笔承诺都要兑现）的系统性检查。
用法：python3 tests/audit_账盘.py <树根>…"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import i3dna_api as api   # noqa: E402

for target in sys.argv[1:]:
    root = os.path.abspath(target)
    import io
    import json
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            api.api_account(root, None, None)
        except SystemExit:
            pass
    d = json.loads(buf.getvalue())
    n_acc, n_entry, drift, missing = len(d["账"]), 0, [], []
    for a in d["账"]:
        rd = os.path.join(root, os.path.dirname(a["账目录"]))
        for kind in ("输入清单", "产物清单"):
            for it in a["记录"].get(kind) or []:
                if not isinstance(it, dict) or "sha256" not in it:
                    continue
                n_entry += 1
                p = os.path.join(root, it["名称"])
                if not os.path.isfile(p):
                    missing.append((a["账目录"], kind, it["名称"], "缺席"))
                    continue
                from i3dna_engine import sha256
                if api.eng.sha256(p) != it["sha256"]:
                    drift.append((a["账目录"], kind, it["名称"]))
    print(f"{target}: 账{n_acc} 条目{n_entry} 漂移{len(drift)} 缺席{len(missing)}")
    for x in drift[:6]:
        print(f"  漂移 {x[0]} · {x[1]} · {x[2]}")
    for x in missing[:6]:
        print(f"  缺席 {x[0]} · {x[1]} · {x[2]}")
