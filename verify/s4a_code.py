"""S4a — 코드 구간 결정성 (검토의견 §4-3)

S4 를 셋으로 나눈 것 중 첫째다.

  S4a  ③④⑤⑥ 음양력·보정·원국·사실블록  = **코드**   → 목표 100%
  S4b  ② 항목 추출                      = LLM     → 측정 완료, 미달
  S4c  ⑦ 리포트 문장                     = LLM     → 목표 없음

**여기서 1%라도 흔들리면 그건 "LLM 특성"이 아니라 버그다.**
같은 생년월일시를 넣었는데 원국이 달라지면 서비스가 성립하지 않는다.

쓰는 법:  python -m verify.s4a_code [--횟수 20]
"""
from __future__ import annotations

import hashlib
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import calendar_service, korea_time, saju_service  # noqa: E402
from poc import report as R  # noqa: E402

뿌리 = Path(__file__).resolve().parents[1]

# 어려운 것만 골랐다. 쉬운 입력이 안 흔들리는 건 당연하다.
표본 = [
    ("양력 기본", 1995, 3, 12, 15, 20, "solar", False, 126.9780),
    ("음력 평달", 1988, 7, 20, 19, 0, "lunar", False, 128.6014),
    ("음력 윤달", 1947, 2, 8, 10, 0, "lunar", True, 127.1480),
    ("서머타임 + 자시", 1987, 7, 22, 1, 10, "solar", False, 126.7052),
    ("127.5° 시기", 1955, 6, 1, 12, 0, "solar", False, 126.9780),
    ("자시 경계", 2003, 10, 29, 23, 50, "solar", False, 128.6811),
    ("시간 미상", 1963, 9, 5, None, None, "solar", False, 126.9780),
    ("경도 극단", 1990, 5, 5, 13, 5, "solar", False, 130.9057),
]


def 한번(이름, y, m, d, hh, mm, 달력, 윤, 경도, 지금: datetime) -> str:
    """③④⑤⑥ 을 한 번 돌리고 결과 전체를 문자열로. 이걸 해시해서 비교한다."""
    if 달력 == "lunar":
        conv = calendar_service.lunar_to_solar(y, m, d, 윤)
        y, m, d = map(int, conv.solar_date.split("-"))
    if hh is None:
        c = korea_time.correct(datetime(y, m, d, 12, 0), 경도)
        chart = saju_service.build_chart(c.jieqi_reference, None)
        진태양 = None
    else:
        c = korea_time.correct(datetime(y, m, d, hh, mm), 경도)
        chart = saju_service.build_chart(c.jieqi_reference, c.true_solar)
        진태양 = c.true_solar
    period = saju_service.current_period(지금, c.jieqi_reference)
    기준 = (진태양 or c.jieqi_reference).strftime("%Y-%m-%d %H:%M")
    return R.build_facts_saju(chart, period, 기준, [f"경도 {경도}"])


def 해시(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()[:12]


def main() -> int:
    횟수 = int(next((a.split("=", 1)[1] for a in sys.argv[1:]
                     if a.startswith("--횟수=")), 20))
    from verify.guard import 표본확인
    표본확인("S4a 표본", 표본, 최소=3)
    if 횟수 < 2:
        raise SystemExit("■ 결정성은 2회 이상 돌려야 잽니다.")

    print("=" * 78)
    print(f"S4a — 코드 구간(③④⑤⑥) 결정성 · 표본 {len(표본)}종 × {횟수}회")
    print("목표 100% — 여기서 흔들리면 LLM 특성이 아니라 버그다")
    print("=" * 78)

    # ① '지금'을 고정하고 돌린다. 이게 진짜 S4a 다.
    고정 = datetime(2026, 9, 23, 12, 0, 0)
    print(f"\n[1] 조회 시각을 고정 ({고정:%Y-%m-%d %H:%M}) — 순수 입력→출력")
    흔들림 = 0
    for 이름, *인자 in 표본:
        결과 = Counter(해시(한번(이름, *인자, 고정)) for _ in range(횟수))
        ok = len(결과) == 1
        흔들림 += not ok
        print(f"  {'동일' if ok else '흔들림 ⚠'}  {이름:<16} {list(결과)[0]}"
              + ("" if ok else f"  {dict(결과)}"))
    print(f"  {'─' * 70}")
    비율 = 100 * (len(표본) - 흔들림) / len(표본)
    print(f"  {len(표본) - 흔들림}/{len(표본)} 동일 ({비율:.1f}%)")

    # ② '지금'을 고정하지 않으면? — 설계상 달라진다. 그걸 확인해 둔다.
    print("\n[2] 조회 시각을 고정하지 않으면 — 사실 블록이 '이번 달'을 담는다")
    a = 한번(*표본[0], datetime(2026, 9, 23, 12, 0))
    b = 한번(*표본[0], datetime(2026, 10, 23, 12, 0))
    다름 = 해시(a) != 해시(b)
    print(f"  9월 조회 {해시(a)}  /  10월 조회 {해시(b)}  → "
          f"{'다름 (설계대로)' if 다름 else '같음 ⚠ 세운·월운이 안 들어간 것'}")
    print("  ※ 이건 버그가 아니다. '이번 달 흐름'을 쓰려면 조회 시점이 들어가야 한다.")
    print("    다만 **S4a 를 잴 때는 반드시 시각을 고정해야** 한다. 안 그러면")
    print("    달이 바뀔 때마다 '재현 안 됨'이 되어 진짜 버그를 놓친다.")

    # ③ 원국만 따로 — 이건 조회 시각과 무관하게 평생 고정이어야 한다
    print("\n[3] 원국 8글자만 — 조회 시각과 무관해야 한다")
    막힘 = 0
    for 이름, *인자 in 표본:
        전체 = [한번(이름, *인자, datetime(2026, 월, 15, 12, 0)) for 월 in (1, 5, 9, 12)]
        원국들 = {t.split("원국: ")[1].split("\n")[0] for t in 전체}
        ok = len(원국들) == 1
        막힘 += not ok
        print(f"  {'고정' if ok else '변함 ⚠'}  {이름:<16} {list(원국들)[0][:44]}")
    print(f"  {'─' * 70}")
    print(f"  {len(표본) - 막힘}/{len(표본)} 고정")

    print(f"\n{'=' * 78}")
    통과 = (흔들림 == 0 and 막힘 == 0 and 다름)
    print(f"판정: S4a {'통과' if 통과 else '미달'} (목표 100%)")
    if 통과:
        print("  코드 구간은 같은 입력에 항상 같은 답을 낸다.")
        print("  → 재현성 문제는 전부 LLM 구간(S4b) 에 있다.")
    print("=" * 78)
    return 0 if 통과 else 1


if __name__ == "__main__":
    raise SystemExit(main())
