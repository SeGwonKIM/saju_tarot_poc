"""S1 — 항목 추출 정확도 (PRD_PoC.md 5.1)

5건 × 5항목 = 25개. 통과 기준 20개 이상.
규칙 기반(기준선)과 LLM 을 같은 자로 재서 나란히 놓는다.

쓰는 법:
    python -m verify.s1_extract                       # 기준선만
    python -m verify.s1_extract --llm --env=<경로>     # 둘 다
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from poc.extract import LlmExtractor, RuleExtractor
from verify.guard import 표본확인

뿌리 = Path(__file__).resolve().parents[1]
_숨김2 = "--숨김2" in sys.argv
_숨김 = "--숨김" in sys.argv or _숨김2
_키 = ("정답키_숨김2.json" if _숨김2
       else "정답키_숨김.json" if _숨김 else "정답키.json")
정답 = json.loads((뿌리 / "samples" / _키).read_text(encoding="utf-8"))

# 채점 항목을 손으로 적지 않는다 — spec/fields.yaml 의 scored: true 에서 뽑는다.
# 손으로 적던 시절에 is_leap·calendar_type 이 빠져 있었다 (F-17).
import yaml  # noqa: E402

_선언 = yaml.safe_load((뿌리 / "spec" / "fields.yaml").read_text(encoding="utf-8"))
채점필드 = tuple(s["id"] for s in _선언["slots"] if s.get("scored"))
서술형 = {s["id"] for s in _선언["slots"] if s.get("scoring") == "keywords"}
정답형 = tuple(f for f in 채점필드 if f not in 서술형)


def 맞았나(필드: str, 답, 정: dict) -> bool:
    """question 만 느슨하게 본다 — 표현이 달라도 뜻이 통하면 맞은 것으로."""
    기대 = 정[필드]
    if 필드 not in 서술형:
        return 답 == 기대
    if 기대 is None:
        return 답 is None
    if not 답:
        return False
    # 인정 낱말은 정답키에 미리 적어 두었다 (samples/make_samples.py)
    # 빈 문자열·한 글자는 무엇에나 걸리므로 버린다 — 채점을 무력화한다 (A6)
    낱말 = [w for w in (정.get("question_keywords") or [기대]) if len(str(w).strip()) >= 2]
    if not 낱말:
        return False        # 쓸 만한 낱말이 하나도 없으면 채점 불가 → 오답 처리
    return any(w in str(답) for w in 낱말)


def 재기(ex) -> dict:
    print(f"\n{'=' * 74}\n■ {ex.이름}\n{'=' * 74}")
    맞은수, 표 = 0, []
    걸린시간 = 0.0
    for 번호, 정 in 정답.items():
        text = (뿌리 / "samples" / f"상담_{번호}.txt").read_text(encoding="utf-8")
        t0 = time.perf_counter()
        r = ex.extract(text).to_dict()
        걸린시간 += time.perf_counter() - t0
        줄 = []
        for f in 채점필드:
            ok = 맞았나(f, r[f], 정)
            맞은수 += ok
            줄.append(ok)
        표.append((번호, 정, r, 줄))

    머리 = "".join(f"{f[:9]:<11}" for f in 채점필드)
    print(f"{'번호':<6}{머리} 점수")
    print("-" * (8 + 11 * len(채점필드)))
    for 번호, 정, r, 줄 in 표:
        표시 = "".join(f"{'O' if ok else 'X':<11}" for ok in 줄)
        print(f"{번호:<6}{표시} {sum(줄)}/{len(채점필드)}")
    print("-" * (8 + 11 * len(채점필드)))
    만점 = len(정답) * len(채점필드)
    기준 = round(만점 * 0.8)
    # 검토의견 M-2 — 표본 수와 항목 수는 다르다. 둘 다 적는다.
    정답형맞음 = sum(1 for _, 정, r, _ in 표 for f in 정답형 if 맞았나(f, r[f], 정))
    서술형맞음 = 맞은수 - 정답형맞음
    print(f"합계 {맞은수}/{만점}   ·   {'통과' if 맞은수 >= 기준 else '미달'} (기준 {기준})"
          f"   ·   {걸린시간:.2f}초")
    print(f"  표본 {len(정답)}건 · 항목 {만점}개   "
          f"(정답형 {정답형맞음}/{len(정답)*len(정답형)} · "
          f"서술형 {서술형맞음}/{len(정답)*len(서술형)})")
    완벽 = sum(1 for *_, 줄 in 표 if all(줄))
    print(f"  ⚠ 유효 표본은 {len(정답)}건이다. 한 건이 어긋나면 "
          f"{100/len(정답):.0f}%p 움직인다 — 항목 기준 {100/만점:.1f}%p 가 아니다.")
    print(f"  전 항목을 맞힌 표본 {완벽}/{len(정답)}건")

    # 틀린 자리만 자세히
    print("\n틀린 항목:")
    틀림 = 0
    for 번호, 정, r, 줄 in 표:
        for f, ok in zip(채점필드, 줄):
            if not ok:
                틀림 += 1
                print(f"  {번호} {f:<12} 정답 {정[f]!r}  →  나온 값 {r[f]!r}")
    if not 틀림:
        print("  없음")

    # 지어내지 않았는가 — null 이어야 할 자리에 값을 넣었는지
    print("\n지어냄 검사 (정답이 null 인 자리):")
    지어냄 = 0
    for 번호, 정, r, _ in 표:
        for f in ("gender", "birth_time", "birth_place", "is_leap"):
            if 정.get(f) is None and r.get(f) is not None:
                지어냄 += 1
                print(f"  ⚠ {번호} {f} — 대화에 없는데 {r[f]!r} 를 넣음")
    if not 지어냄:
        print("  없음 — 모르는 것을 null 로 둠")

    return {"이름": ex.이름, "점수": 맞은수, "초": round(걸린시간, 2),
            "지어냄": 지어냄, "만점": 만점, "표": [(n, s) for n, _, _, s in 표]}


def main() -> int:
    print(f"S1 — 항목 추출 정확도 · {'숨김 2차' if _숨김2 else '숨김 1차' if _숨김 else '공개 문제'} "
          f"{len(정답)}건 × {len(채점필드)}항목 = {len(정답)*len(채점필드)}개 · 통과 80%")
    if _숨김:
        print("※ 이 문제로는 규칙을 고치지 않는다. 고치면 숨김이 아니게 된다.")

    표본확인(f"S1 {_키}", 정답, 최소=1)
    for 번호 in 정답:
        표본확인(f"상담_{번호}.txt",
                (뿌리 / "samples" / f"상담_{번호}.txt").read_text(encoding="utf-8"),
                최소=50, 조용히=True)

    결과 = [재기(RuleExtractor())]

    if "--llm" in sys.argv:
        env = next((a.split("=", 1)[1] for a in sys.argv[1:]
                    if a.startswith("--env=")), None)
        결과.append(재기(LlmExtractor(env_path=env)))

    if len(결과) > 1:
        print(f"\n{'=' * 74}\n■ 나란히 보기\n{'=' * 74}")
        print(f"{'방법':<22}{'점수':>8}{'시간':>10}{'지어냄':>9}")
        print("-" * 74)
        for r in 결과:
            print(f"{r['이름']:<22}{r['점수']:>4}/{len(정답)*len(채점필드)}{r['초']:>9}초{r['지어냄']:>8}건")
        print("-" * 74)
        기준, 엘 = 결과[0], 결과[1]
        차 = 엘["점수"] - 기준["점수"]
        print(f"LLM 이 기준선보다 {차:+d}개")
        if 차 <= 0:
            print("→ 기준선을 못 이겼다. LLM 을 쓸 이유가 약하다.")
        elif 차 <= 2:
            print("→ 차이가 작다. 비용과 지연을 감안해 판단해야 한다.")
        else:
            print("→ 뚜렷하게 낫다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
