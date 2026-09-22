"""내 상담 말투 샘플 로딩 (PRD §11.5 · Q7).

규칙만으로는 모델이 일반론을 쓴다. 실제 상담 문장을 few-shot 으로 넣어
어조·길이·어미를 따르게 한다.

파일: backend/data/tone_samples.md  (git 에 올라가지 않는다)
5건 미만이면 적용하지 않는다 — 표본이 적으면 문체가 잡히지 않고, 몇 문장을
그대로 베껴 쓰는 부작용이 생긴다.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

log = logging.getLogger("saju.tone")

SAMPLES_PATH = Path(__file__).resolve().parents[1] / "data" / "tone_samples.md"
MIN_SAMPLES = 5

# 실수로 개인정보가 들어왔을 때 걸러낸다 (PRD §12.9)
_BIRTH_LIKE = re.compile(r"\b(19|20)\d{2}[-. /]\d{1,2}[-. /]\d{1,2}")
_PHONE_LIKE = re.compile(r"01[016-9][-. ]?\d{3,4}[-. ]?\d{4}")


@dataclass(frozen=True)
class ToneSample:
    topic: str | None
    text: str


def parse(markdown: str) -> list[ToneSample]:
    samples: list[ToneSample] = []
    topic: str | None = None
    for line in markdown.splitlines():
        s = line.strip()
        if s.startswith("## "):
            topic = None
        elif s.startswith("주제:"):
            value = s[3:].strip()
            topic = value or None
        elif s.startswith("문장:"):
            text = s[3:].strip()
            if text:
                samples.append(ToneSample(topic=topic, text=text))
    return samples


def _scrub(samples: list[ToneSample]) -> list[ToneSample]:
    """개인정보로 보이는 문장은 버린다. 실수로 넣었어도 프롬프트로 나가지 않게."""
    kept: list[ToneSample] = []
    for s in samples:
        if _BIRTH_LIKE.search(s.text) or _PHONE_LIKE.search(s.text):
            log.warning("말투 샘플에 개인정보로 보이는 값이 있어 제외했습니다 (주제=%s)", s.topic)
            continue
        kept.append(s)
    return kept


@lru_cache
def load() -> list[ToneSample]:
    """파일이 없거나 5건 미만이면 빈 목록 — few-shot 없이 규칙만으로 생성한다."""
    if not SAMPLES_PATH.exists():
        return []
    try:
        # utf-8-sig: 메모장이 붙이는 BOM 을 함께 벗겨낸다.
        # 인코딩이 어긋나도(메모장에서 ANSI 로 저장 등) 예외가 리포트 생성을 막으면 안 된다.
        raw = SAMPLES_PATH.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        log.warning(
            "말투 샘플 파일의 인코딩이 UTF-8 이 아닙니다. "
            "메모장에서 [다른 이름으로 저장] → 인코딩 'UTF-8' 로 다시 저장하세요."
        )
        return []
    except OSError as e:
        log.warning("말투 샘플을 읽지 못했습니다: %s", type(e).__name__)
        return []

    samples = _scrub(parse(raw))
    if len(samples) < MIN_SAMPLES:
        log.info("말투 샘플 %d건 — %d건 이상이어야 적용됩니다", len(samples), MIN_SAMPLES)
        return []
    return samples


def as_prompt_block(topics: list[str]) -> str:
    """고른 주제에 해당하는 샘플을 앞에 놓고, 나머지도 함께 보여준다."""
    samples = load()
    if not samples:
        return ""

    ordered = [s for s in samples if s.topic in topics] + [
        s for s in samples if s.topic not in topics
    ]
    lines = [
        "[내 문체 예시]",
        "아래는 제가 실제로 손님에게 보낸 문장입니다.",
        "**어조·문장 길이·어미**를 이 문장들에 맞추십시오.",
        "내용은 참고하지 말고, <계산결과>에 있는 사실만 쓰십시오.",
    ]
    for s in ordered[:12]:
        label = f"({s.topic}) " if s.topic else ""
        lines.append(f"  - {label}{s.text}")
    return "\n".join(lines)


def is_active() -> bool:
    """리포트의 '문체 학습 전 초안' 배지를 뗄지 결정한다 (PRD §11.5)."""
    return bool(load())
