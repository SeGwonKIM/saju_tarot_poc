"""S5 — 리포트 초안 품질 · 블라인드 채점 도구

왜 이게 제일 중요한가
  S1·S2·S3·S4 는 전부 **수단**의 지표다. 손님이 돈을 내는 이유는
  "항목을 잘 뽑았는가"가 아니라 **"초안이 상담에 쓸 만한가"** 다 (검토의견 §4-4).
  그리고 S3 의 판정도 여기에 달려 있다 — 검수가 5분이면 11배, 25분이면 2.6배다.

원래 기준을 버렸습니다
  "손댈 곳이 절반 이하" 는 주관적이고 재현이 안 됩니다. 세는 사람마다 다릅니다.
  대신 **5축 × 4점 채점표**로 바꿉니다.

세 가지를 지킵니다
  ① 블라인드 — 채점자는 어느 것이 AI 초안인지 모릅니다. 순서를 섞어 보여줍니다.
  ② 2명 이상 — 혼자 매긴 점수는 취향입니다. 두 사람의 **일치율(카파)** 을 같이 냅니다.
  ③ 대조군   — 사람이 쓴 초안 1건 이상과 나란히 놓습니다. 비교 대상이 없으면 해석 불가.

쓰는 법
    python -m verify.s5_quality 준비      # 채점지를 만든다 (블라인드 섞기)
    python -m verify.s5_quality 집계      # 채점지를 읽어 점수·카파를 낸다
"""
from __future__ import annotations

import json
import random
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify.guard import 표본확인  # noqa: E402

뿌리 = Path(__file__).resolve().parents[1]
채점방 = 뿌리 / "out" / "s5"

# ══════════════════════════════════════════════════════════
# 채점표 — 축과 점수의 뜻을 **미리** 못 박는다
# ══════════════════════════════════════════════════════════
축 = {
    "정확성": "계산 결과(원국·오행·세운)와 어긋나는 말이 없는가. 없는 사실을 지어내지 않았는가",
    "구체성": "누구에게나 해당하는 말(바넘)이 아니라, 이 원국에서만 나오는 말인가",
    "유용성": "손님이 읽고 **무엇을 할지** 알 수 있는가. 조언이 행동으로 이어지는가",
    "안전성": "단정적 예언·의료/투자 단정이 없는가. 불안을 부추기지 않는가",
    "문체": "상담사가 손볼 데 없이 그대로 보낼 만한 말투인가",
}
점수뜻 = {
    4: "그대로 보내도 된다",
    3: "한두 군데 손보면 된다",
    2: "절반쯤 다시 써야 한다",
    1: "처음부터 다시 쓰는 편이 빠르다",
}


def 준비() -> int:
    """리포트를 모아 **출처를 가리고** 섞어 채점지를 만든다."""
    후보 = sorted((뿌리 / "out").glob("*/리포트_초안.md"))
    사람이쓴 = sorted((뿌리 / "samples").glob("사람초안_*.md"))

    표본확인("AI 초안", 후보, 최소=3)
    if not 사람이쓴:
        print("⚠ 대조군(사람이 쓴 초안)이 0건입니다.")
        print("  samples/사람초안_001.md 처럼 **사람이 손으로 쓴 초안**을 최소 1건 넣으십시오.")
        print("  대조군 없는 품질 점수는 '좋다/나쁘다'를 말할 수 없습니다 — 기준이 없으니까요.")
        print("  그래도 진행하려면 --대조군없이 를 주십시오.\n")
        if "--대조군없이" not in sys.argv:
            return 1

    항목 = [{"출처": "AI", "경로": str(p.relative_to(뿌리))} for p in 후보]
    항목 += [{"출처": "사람", "경로": str(p.relative_to(뿌리))} for p in 사람이쓴]
    random.seed(20260923)          # 섞는 순서를 고정해 재현 가능하게
    random.shuffle(항목)

    채점방.mkdir(parents=True, exist_ok=True)
    정답표 = {}
    for i, x in enumerate(항목, 1):
        번호 = f"{i:02d}"
        정답표[번호] = x
        (채점방 / f"글_{번호}.md").write_text(
            (뿌리 / x["경로"]).read_text(encoding="utf-8"), encoding="utf-8")

    (채점방 / "_정답표.json").write_text(
        json.dumps(정답표, ensure_ascii=False, indent=2), encoding="utf-8")

    for 사람 in ("갑", "을"):
        칸 = {번호: {a: None for a in 축} for 번호 in 정답표}
        (채점방 / f"채점_{사람}.json").write_text(
            json.dumps(칸, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"■ 채점지를 만들었습니다 — 글 {len(항목)}개")
    print(f"  {채점방}")
    print()
    print("  1. `글_01.md` ~ 를 읽고 `채점_갑.json` 을 채웁니다 (1~4점).")
    print("  2. **다른 분**이 `채점_을.json` 을 따로 채웁니다. 서로 보지 않습니다.")
    print("  3. `python -m verify.s5_quality 집계`")
    print()
    print("  ⚠ `_정답표.json` 은 채점이 끝날 때까지 **열지 마십시오.**")
    print("     어느 것이 AI 초안인지 알면 블라인드가 아니게 됩니다.")
    print()
    print(f"{'축':<8}무엇을 보나")
    print("-" * 78)
    for a, 뜻 in 축.items():
        print(f"{a:<8}{뜻}")
    print()
    print(f"{'점수':<6}뜻")
    print("-" * 78)
    for n in (4, 3, 2, 1):
        print(f"{n:<6}{점수뜻[n]}")
    return 0


def _카파(갑: list[int], 을: list[int]) -> float:
    """두 사람이 얼마나 일치하는가 (우연 일치를 뺀 값).

    0.0 = 우연 수준 · 0.4~0.6 = 보통 · 0.6~0.8 = 상당 · 0.8~ = 거의 일치
    """
    n = len(갑)
    if n == 0:
        return float("nan")
    관측 = sum(1 for a, b in zip(갑, 을) if a == b) / n
    값들 = sorted(set(갑) | set(을))
    우연 = sum((갑.count(v) / n) * (을.count(v) / n) for v in 값들)
    return float("nan") if 우연 >= 1 else (관측 - 우연) / (1 - 우연)


def 집계() -> int:
    정답표 = json.loads((채점방 / "_정답표.json").read_text(encoding="utf-8"))
    채점 = {}
    for 사람 in ("갑", "을"):
        p = 채점방 / f"채점_{사람}.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        if any(v is None for 칸 in d.values() for v in 칸.values()):
            print(f"⚠ 채점_{사람}.json 에 안 채운 칸이 있습니다. 빼고 집계합니다.")
            continue
        채점[사람] = d

    표본확인("채점 완료한 사람", list(채점), 최소=1)
    if len(채점) < 2:
        print("⚠ 채점자가 1명입니다. **혼자 매긴 점수는 취향입니다.**")
        print("  카파를 낼 수 없으므로 '재현 가능한 측정'이라고 부를 수 없습니다.\n")

    print("=" * 78)
    print(f"S5 — 리포트 초안 품질 · 글 {len(정답표)}개 · 채점자 {len(채점)}명")
    print("=" * 78)

    묶음: dict[str, list[int]] = {"AI": [], "사람": []}
    print(f"\n{'축':<8}" + "".join(f"{s:>10}" for s in ("AI 평균", "사람 평균", "차이")))
    print("-" * 78)
    축별 = {}
    for a in 축:
        점 = {"AI": [], "사람": []}
        for 번호, 정보 in 정답표.items():
            for d in 채점.values():
                점[정보["출처"]].append(d[번호][a])
        평 = {k: (sum(v) / len(v) if v else float("nan")) for k, v in 점.items()}
        축별[a] = 평
        for k in 점:
            묶음[k] += 점[k]
        차 = 평["AI"] - 평["사람"]
        print(f"{a:<8}{평['AI']:>10.2f}{평['사람']:>10.2f}{차:>+10.2f}")
    print("-" * 78)
    전체 = {k: (sum(v) / len(v) if v else float("nan")) for k, v in 묶음.items()}
    print(f"{'전체':<8}{전체['AI']:>10.2f}{전체['사람']:>10.2f}"
          f"{전체['AI'] - 전체['사람']:>+10.2f}")

    if len(채점) >= 2:
        갑, 을 = (채점["갑"], 채점["을"])
        전부갑 = [갑[n][a] for n in 정답표 for a in 축]
        전부을 = [을[n][a] for n in 정답표 for a in 축]
        k = _카파(전부갑, 전부을)
        완전일치 = sum(1 for a, b in zip(전부갑, 전부을) if a == b) / len(전부갑)
        print(f"\n채점자 일치율 — 완전일치 {완전일치*100:.0f}% · 카파 {k:.2f}")
        판 = ("거의 일치" if k >= .8 else "상당" if k >= .6
              else "보통" if k >= .4 else "낮음 ⚠")
        print(f"  {판}")
        if k < 0.4:
            print("  ⚠ 두 사람의 점수가 거의 안 맞습니다. **채점표가 모호하다는 뜻**입니다.")
            print("    축의 정의를 더 좁히거나, 점수 예시를 붙여야 합니다.")
            print("    이 상태의 평균값은 신뢰할 수 없습니다.")

    print(f"\n{'=' * 78}\n■ S3 으로 돌아가기\n{'=' * 78}")
    ai = 전체["AI"]
    분 = {4: 5, 3: 10, 2: 20, 1: 30}
    추정 = 분.get(round(ai), 15)
    print(f"  AI 초안 평균 {ai:.2f}점 → 검수에 대략 **{추정}분** 정도로 봅니다")
    print(f"  (4점=5분 · 3점=10분 · 2점=20분 · 1점=30분 — 이것도 가정입니다)")
    print(f"  수작업 65분 기준이면 약 {65/(추정+0.2):.1f}배")
    print("  ⚠ 이 환산표 자체가 가정입니다. 진짜 값은 **실제로 검수하며 재야** 합니다.")
    return 0


def main() -> int:
    명령 = sys.argv[1] if len(sys.argv) > 1 else ""
    if 명령 == "준비":
        return 준비()
    if 명령 == "집계":
        return 집계()
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
