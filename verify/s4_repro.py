"""S4 — 재현성 (PRD_PoC.md 5.1)

같은 입력을 여러 번 넣어 **같은 답이 나오는가**를 본다.
통과 기준: 원국·구조 동일.

temperature=0 이면 늘 같은 답이 나온다고 생각하기 쉽지만 보장이 아니다.
실제로 007 에서 두 번 돌려 서로 다른 생년월일이 나왔다. 그래서 잰다.

쓰는 법:
    python -m verify.s4_repro --env=<경로>/.env [--횟수 3]
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from poc.extract import LlmExtractor, RuleExtractor  # noqa: E402
from verify.guard import 표본확인  # noqa: E402

뿌리 = Path(__file__).resolve().parents[1]
볼것 = ("name", "gender", "birth_date", "calendar_type", "is_leap",
        "birth_time", "birth_place")


def 재기(ex, 번호들: list[str], 횟수: int) -> dict:
    print(f"\n{'=' * 74}\n■ {ex.이름}  ·  각 {횟수}회\n{'=' * 74}")
    흔들린자리, 전체자리 = 0, 0
    for 번호 in 번호들:
        글 = (뿌리 / "samples" / f"상담_{번호}.txt").read_text(encoding="utf-8")
        결과 = [ex.extract(글).to_dict() for _ in range(횟수)]
        흔들림 = {}
        for f in 볼것:
            값들 = Counter(json.dumps(r[f], ensure_ascii=False) for r in 결과)
            전체자리 += 1
            if len(값들) > 1:
                흔들린자리 += 1
                흔들림[f] = dict(값들)
        상태 = "동일" if not 흔들림 else f"흔들림 {len(흔들림)}개"
        print(f"  {번호}  {상태}")
        for f, 값들 in 흔들림.items():
            표 = " · ".join(f"{v.strip(chr(34))} ({c}회)" for v, c in 값들.items())
            print(f"        ⚠ {f}: {표}")
    비율 = 100 * (전체자리 - 흔들린자리) / 전체자리
    print(f"  {'─' * 70}")
    print(f"  항목 {전체자리}개 중 {전체자리 - 흔들린자리}개가 매번 동일 ({비율:.1f}%)")
    return {"이름": ex.이름, "흔들림": 흔들린자리, "전체": 전체자리, "비율": round(비율, 1)}


def main() -> int:
    횟수 = int(next((a.split("=", 1)[1] for a in sys.argv[1:]
                     if a.startswith("--횟수=")), 3))
    env = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--env=")), None)
    번호들 = ["002", "005", "007"]     # 음력 · 미상 많음 · 윤달

    print(f"S4 — 재현성 · 같은 입력 {횟수}회 · 표본 {', '.join(번호들)}")
    print("통과 기준: 모든 항목이 매번 같아야 한다")

    표본확인("S4b 표본", 번호들, 최소=1)
    if 횟수 < 2:
        raise SystemExit("■ 재현성은 2회 이상 돌려야 잽니다. --횟수=2 이상으로 주세요.")

    결과 = [재기(RuleExtractor(), 번호들, 횟수)]
    if env:
        결과.append(재기(LlmExtractor(env_path=env), 번호들, 횟수))

    print(f"\n{'=' * 74}\n■ 나란히 보기\n{'=' * 74}")
    print(f"{'방법':<22}{'매번 동일':>12}{'흔들린 항목':>14}")
    print("-" * 74)
    for r in 결과:
        print(f"{r['이름']:<22}{r['비율']:>11.1f}%{r['흔들림']:>12}개")
    print("-" * 74)
    막힘 = [r for r in 결과 if r["흔들림"]]
    if 막힘:
        print("판정: 미달 — 같은 입력에 다른 답이 나온다.")
        print("      사람이 확인하는 화면을 반드시 끼워야 한다 (자동 통과 금지).")
    else:
        print("판정: 통과 — 모든 항목이 매번 동일.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
