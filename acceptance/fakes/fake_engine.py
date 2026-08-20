#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验收桩引擎:stdin 收 prompt,确定性输出,零外部调用。

- write 车道:解析「【产物→写到】<绝对路径>」逐产物写桩内容,回复「完成」——
  引擎的暂存-验收-落位全链路被真实执行(桩只替代 LLM 那一环)。
- detect 车道:输出确定性判官报告。
"""
import os
import re
import sys

prompt = sys.stdin.read()
writes = re.findall(r"【产物→写到】(\S+)", prompt)
if writes:
    for p in writes:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(f"桩产物（P2b 验收桩引擎）\n落点 {p}\n")
    print("完成")
elif "可符号化" in prompt:
    print("判决：部分可符号化")
    print("理由：读订单与冲减库存是符号同一性；订单确认语义是语义指称。")
    print("拆分建议：出库单生成转符号程序，订单确认保留联结主义。")
else:
    print("桩引擎已收 prompt（未识别车道）")
