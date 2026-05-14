"""中文分词与 RNO 术语保护。模块导入即注册自定义词典 (一次)。"""
from __future__ import annotations

import jieba

RNO_TERMS: list[str] = [
    # 测量指标缩写
    "RSRP", "RSRQ", "SINR", "QoE",
    # 业务复合词
    "覆盖强度", "信号质量", "信噪比", "掉话率", "切换成功率", "吞吐量",
    "切换", "会话", "弱覆盖", "重选", "邻区",
    # 网元
    "基站", "小区", "用户", "终端", "扇区",
    # 数仓概念
    "宽表", "明细层", "汇总层", "评估",
]


def _register_terms() -> None:
    for w in RNO_TERMS:
        jieba.add_word(w, freq=100)


_register_terms()


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    words = jieba.lcut(text)
    return [w.strip().lower() for w in words if w.strip()]
