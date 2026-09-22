"""S2 — 만세력 엔진 검증 (PRD_PoC.md 5.1)

엔진은 lunar-python 이 계산한다. 같은 라이브러리로 대조하면 순환논리이므로,
라이브러리에 기대지 않는 네 가지로 검증한다.

  검증 1  실물 대조    — 실제 발행된 성명장의 사주와 맞는가
  검증 2  구조 불변식  — 60갑자 순환·년상기월법·일상기시법을 지키는가
  검증 3  경계         — 입춘·절기·자시 경계에서 기둥이 바뀌는가
  검증 4  한국 보정    — 진태양시·서머타임이 실제로 적용되는가

쓰는 법:  python -m verify.s2_manseryeok
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import calendar_service, korea_time, saju_service

SEOUL_LON = 126.9780  # 서울 경도 (기본 출생지)

GAN = "甲乙丙丁戊己庚辛壬癸"
JI = "子丑寅卯辰巳午未申酉戌亥"

결과: list[tuple[str, bool, str]] = []


def 확인(이름: str, 통과: bool, 메모: str = "") -> None:
    결과.append((이름, 통과, 메모))
    print(f"  {'PASS' if 통과 else 'FAIL'}  {이름}" + (f"   {메모}" if 메모 else ""))


def 사주(clock: datetime, lon: float = SEOUL_LON, *, 시간미상: bool = False):
    c = korea_time.correct(clock, lon)
    return saju_service.build_chart(
        c.jieqi_reference, None if 시간미상 else c.true_solar
    ), c


def 간지(p) -> str:
    return "" if p is None else f"{p.gan}{p.ji}"


# ══════════════════════════════════════════════════════════
def 검증1_실물대조() -> None:
    """실제 발행된 성명장(2026-08-10 未시생, 乾)의 사주와 대조한다.

    성명장 표기 (時日月年 순):  乙未 · 丙辰 · 丙申 · 丙午
    """
    print("\n[검증 1] 실물 성명장 대조")
    print("  자료: 하원명리역학연구소 발행 성명장 · 2026년 양력 8월 10일 未시생 (乾)")

    기대 = {"년": "丙午", "월": "丙申", "일": "丙辰"}
    # 시각이 '未시' 로만 적혀 있어 분 단위를 모른다. 未시 구간 전체를 훑는다.
    맞은시각 = []
    for hh in (13, 14):
        for mm in (0, 30):
            chart, _ = 사주(datetime(2026, 8, 10, hh, mm))
            if (간지(chart.year), 간지(chart.month), 간지(chart.day)) == \
               (기대["년"], 기대["월"], 기대["일"]):
                맞은시각.append((f"{hh:02d}:{mm:02d}", 간지(chart.hour)))

    확인("년·월·일주가 실물과 일치", len(맞은시각) == 4,
        f"未시 구간 4개 시각 모두 {기대['년']} {기대['월']} {기대['일']}")

    시주들 = {h for _, h in 맞은시각}
    확인("시주 후보에 실물의 乙未 가 포함", "乙未" in 시주들,
        f"진태양시 보정 후 시주: {', '.join(f'{t}→{h}' for t, h in 맞은시각)}")

    print("  참고: 성명장에 분 단위가 없어 시주는 단정할 수 없다. 이는 자료의 한계이지")
    print("        엔진의 오류가 아니다. 실패 사례 목록에 기록한다.")


# ══════════════════════════════════════════════════════════
def 검증2_구조불변식() -> None:
    """라이브러리와 무관하게 성립해야 하는 규칙들."""
    print("\n[검증 2] 구조 불변식")

    # ① 일주는 하루마다 60갑자를 정확히 한 칸씩 돈다
    기준 = datetime(2000, 1, 1, 12, 0)
    이전 = None
    어긋남 = []
    for i in range(400):
        chart, _ = 사주(기준 + timedelta(days=i))
        현재 = GAN.index(chart.day.gan) * 12 + JI.index(chart.day.ji)
        # 간지 인덱스를 60갑자 순번으로 환산
        순번 = next(n for n in range(60)
                    if n % 10 == GAN.index(chart.day.gan)
                    and n % 12 == JI.index(chart.day.ji))
        if 이전 is not None and (이전 + 1) % 60 != 순번:
            어긋남.append(i)
        이전 = 순번
    확인("일주 60갑자 연속성 (400일)", not 어긋남,
        "하루마다 정확히 한 칸씩 이동" if not 어긋남 else f"{len(어긋남)}곳 어긋남")

    # ② 년상기월법 — 연간에 따라 寅월의 월간이 정해진다
    #    甲己年→丙寅, 乙庚年→戊寅, 丙辛年→庚寅, 丁壬年→壬寅, 戊癸年→甲寅
    표 = {"甲": "丙", "己": "丙", "乙": "戊", "庚": "戊", "丙": "庚",
          "辛": "庚", "丁": "壬", "壬": "壬", "戊": "甲", "癸": "甲"}
    틀림 = []
    for y in range(1960, 2031):
        chart, _ = 사주(datetime(y, 2, 20, 12, 0))   # 입춘 지나 寅월 한가운데
        if chart.month.ji != "寅":
            continue
        if chart.month.gan != 표[chart.year.gan]:
            틀림.append((y, chart.year.gan, chart.month.gan, 표[chart.year.gan]))
    확인("년상기월법 (1960~2030 寅월)", not 틀림,
        f"연간→월간 규칙 일치" if not 틀림 else f"{len(틀림)}년 불일치 {틀림[:3]}")

    # ③ 일상기시법 — 일간에 따라 子시의 시간이 정해진다
    #    甲己日→甲子, 乙庚日→丙子, 丙辛日→戊子, 丁壬日→庚子, 戊癸日→壬子
    표2 = {"甲": "甲", "己": "甲", "乙": "丙", "庚": "丙", "丙": "戊",
           "辛": "戊", "丁": "庚", "壬": "庚", "戊": "壬", "癸": "壬"}
    틀림2 = []
    for i in range(120):
        d = datetime(2024, 1, 1, 12, 0) + timedelta(days=i)
        chart, _ = 사주(d)
        일간, 시지 = chart.day.gan, chart.hour.ji
        기대간 = GAN[(GAN.index(표2[일간]) + JI.index(시지)) % 10]
        if chart.hour.gan != 기대간:
            틀림2.append((d.date(), 일간, 시지, chart.hour.gan, 기대간))
    확인("일상기시법 (120일)", not 틀림2,
        "일간→시간 규칙 일치" if not 틀림2 else f"{len(틀림2)}건 불일치 {틀림2[:2]}")


# ══════════════════════════════════════════════════════════
def 검증3_경계() -> None:
    """절기·자시 경계에서 기둥이 실제로 바뀌는가."""
    print("\n[검증 3] 경계 처리")

    # ① 입춘 전후로 연주가 바뀐다 (양력 1월 1일은 아직 전년도 간지)
    바뀐해 = 0
    for y in (2000, 2010, 2020, 2026):
        정월, _ = 사주(datetime(y, 1, 15, 12, 0))
        삼월, _ = 사주(datetime(y, 3, 15, 12, 0))
        if 간지(정월.year) != 간지(삼월.year):
            바뀐해 += 1
    확인("입춘 기준 연주 전환", 바뀐해 == 4,
        f"1월과 3월의 연주가 다른 해 {바뀐해}/4 — 양력 1월 1일이 새 간지가 아님")

    # ② 절기 경계로 월주가 바뀐다 — 한 해에 월지가 12개 모두 나온다
    월지 = {간지(사주(datetime(2026, m, 20, 12, 0))[0].month)[1] for m in range(1, 13)}
    확인("한 해에 월지 12종이 모두 나옴", len(월지) == 12, f"{len(월지)}종")

    # ③ 자시 유파 — 진태양시가 子시(23시 이후)에 들어가야 갈린다.
    #    서울은 보정이 약 -32분이므로 시계로 23:45 여야 진태양시 23:12 가 된다.
    c = korea_time.correct(datetime(2026, 8, 10, 23, 45), SEOUL_LON)
    조 = saju_service.build_chart(c.jieqi_reference, c.true_solar, midnight_rule="조자시")
    야 = saju_service.build_chart(c.jieqi_reference, c.true_solar, midnight_rule="야자시")
    확인("조자시·야자시가 다른 결과를 냄", 간지(조.day) != 간지(야.day),
        f"진태양시 {c.true_solar:%H:%M} (子시) — 조자시 {간지(조.day)} / 야자시 {간지(야.day)}")

    # ④ 시간 미상이면 시주가 없다
    미상, _ = 사주(datetime(2026, 8, 10, 12, 0), 시간미상=True)
    확인("시간 미상 → 3주 6글자", 미상.hour is None, "시주 없음")


# ══════════════════════════════════════════════════════════
def 검증4_한국보정() -> None:
    """진태양시·서머타임 보정이 실제로 적용되는가."""
    print("\n[검증 4] 한국 시간 보정")

    c = korea_time.correct(datetime(2026, 8, 10, 13, 30), SEOUL_LON)
    확인("서울 진태양시 보정량이 약 -32분", -34 <= c.true_solar_correction_min <= -30,
        f"{c.true_solar_correction_min}분 (표준자오선 {c.standard_meridian}°)")

    확인("절기 기준과 진태양시가 다른 시각", c.jieqi_reference != c.true_solar,
        f"절기용 {c.jieqi_reference:%H:%M} / 진태양시 {c.true_solar:%H:%M}")

    # 서머타임 구간 (1987-05-10 ~ 1987-10-11)
    dst = korea_time.correct(datetime(1987, 7, 15, 13, 30), SEOUL_LON)
    확인("1987년 여름 서머타임 적용", dst.dst_applied, "-1시간 감산됨")
    non = korea_time.correct(datetime(1987, 12, 15, 13, 30), SEOUL_LON)
    확인("같은 해 겨울은 미적용", not non.dst_applied)

    # 표준자오선 시대 구분
    # 127.5° 시기는 1954-03-21 ~ 1961-08-09 뿐이다. 1950년은 135° 가 맞다.
    m1955 = korea_time.standard_meridian(datetime(1955, 6, 1).date())
    m2026 = korea_time.standard_meridian(datetime(2026, 1, 1).date())
    확인("표준자오선이 시대에 따라 다름", m1955 != m2026,
        f"1955년 {m1955}° (UTC+8:30 환원기) / 2026년 {m2026}°")
    확인("127.5° 시기 밖은 135°",
        korea_time.standard_meridian(datetime(1950, 1, 1).date()) == 135.0
        and korea_time.standard_meridian(datetime(1970, 1, 1).date()) == 135.0,
        "1950·1970년 모두 135° — 구간 경계가 정확")

    # 경도 보정 — 여기는 원래 확인(..., True, ...) 였다. 절대 실패할 수 없는
    # 시험을 통과로 세고 있었다 (자체 점검 2026-09-22 에서 발견). 진짜 검사로 바꾼다.
    #
    # 진태양시는 경도 1도당 4분이다. 서울(126.978°)과 울릉도(130.9057°)는
    # 3.9277° 차이이므로 보정량이 15.7분 달라야 한다.
    ㅅ = korea_time.correct(datetime(2026, 8, 10, 13, 5), 126.9780)
    ㅇ = korea_time.correct(datetime(2026, 8, 10, 13, 5), 130.9057)
    실제차 = ㅇ.true_solar_correction_min - ㅅ.true_solar_correction_min
    이론차 = (130.9057 - 126.9780) * 4
    확인("경도 1도 = 4분 규칙을 지킴", abs(실제차 - 이론차) <= 1,
        f"실제 {실제차}분 / 이론 {이론차:.1f}분")

    # 그리고 경계 시각에서는 실제로 시주가 갈려야 한다.
    # 서울 진태양시가 시주 경계 직전이 되도록 시각을 잡는다.
    갈린사례 = None
    for 시 in range(0, 24):
        for 분 in (0, 8, 16, 24, 32, 40, 48, 56):
            a, _ = 사주(datetime(2026, 8, 10, 시, 분), 126.9780)
            b, _ = 사주(datetime(2026, 8, 10, 시, 분), 130.9057)
            if 간지(a.hour) != 간지(b.hour):
                갈린사례 = (시, 분, 간지(a.hour), 간지(b.hour))
                break
        if 갈린사례:
            break
    확인("경도 차이로 시주가 실제로 갈리는 시각이 존재", 갈린사례 is not None,
        f"{갈린사례[0]:02d}:{갈린사례[1]:02d} — 서울 {갈린사례[2]} / 울릉도 {갈린사례[3]}"
        if 갈린사례 else "24시간 전 구간에서 한 번도 안 갈림 — 보정이 안 걸린 것")


# ══════════════════════════════════════════════════════════
def 경계커버리지() -> None:
    """검사 개수가 아니라 **어떤 경계를 밟았는가**를 센다 (검토의견 §4-2).

    "17/17 통과"는 17개 항목이 몇 개의 서로 다른 입력에서 나왔는지 말해주지 않는다.
    경계 입력이 표본에 없으면 그 경로는 검증된 적이 없는 것이다 (A9).
    """
    print()
    print("[경계 커버리지] 어떤 경계 입력을 실제로 밟았는가")
    표 = [
        ("윤달 출생", lambda: calendar_service.lunar_to_solar(1947, 2, 8, True).solar_date == "1947-03-30"),
        ("없는 윤달 거부", _없는윤달거부),
        ("자시 경계(23~01시)", lambda: 사주(datetime(2026, 8, 10, 23, 45))[0].hour is not None),
        ("입춘 전후(2월 초)", lambda: 간지(사주(datetime(2026, 2, 3, 12, 0))[0].year)
                                   != 간지(사주(datetime(2026, 2, 5, 12, 0))[0].year)),
        ("절기 당일", lambda: 사주(datetime(2026, 8, 7, 12, 0))[0].month is not None),
        ("서머타임 연도", lambda: korea_time.correct(datetime(1987, 7, 15, 13, 0), SEOUL_LON).dst_applied),
        ("127.5° 시기(1954~61)", lambda: korea_time.standard_meridian(datetime(1955, 6, 1).date()) == 127.5),
        ("경도 극단(울릉도)", lambda: korea_time.correct(datetime(2026, 8, 10, 13, 0), 130.9057)
                                    .true_solar_correction_min
                                    != korea_time.correct(datetime(2026, 8, 10, 13, 0), SEOUL_LON)
                                    .true_solar_correction_min),
        ("시간 미상(3주)", lambda: 사주(datetime(2026, 8, 10, 12, 0), 시간미상=True)[0].hour is None),
        ("서비스 범위 밖 거부(1940 이전)", _범위밖),
    ]
    밟음 = 0
    for 이름, 시험 in 표:
        try:
            ok = bool(시험())
        except Exception as e:                       # noqa: BLE001
            ok, 이름 = False, f"{이름}  ({type(e).__name__})"
        밟음 += ok
        print(f"  {'밟음' if ok else '미검증'}  {이름}")
    print(f"  경계 커버리지 {밟음}/{len(표)}")
    if 밟음 < len(표):
        print("  ⚠ 미검증 경계가 있으면 '표본 전부 일치'로 요약하면 안 됩니다.")


def _없는윤달거부() -> bool:
    try:
        calendar_service.lunar_to_solar(1947, 3, 8, True)
        return False
    except Exception:                                # noqa: BLE001
        return True


def _범위밖() -> bool:
    """1940년 이전 출생은 상담 대상이 아니다 (spec/fields.yaml service_range).

    엔진 자체는 1880년도 받아 값을 낸다. 그래서 **사업 규칙으로** 막는다.
    """
    from poc.extract import 서비스범위
    return (서비스범위(1939) is not None
            and 서비스범위(1940) is None
            and 서비스범위(2030) is not None)


# ══════════════════════════════════════════════════════════
def main() -> int:
    print("=" * 66)
    print("S2 — 만세력 엔진 검증")
    print(f"엔진: {saju_service.ENGINE_VERSION}")
    print("=" * 66)

    검증1_실물대조()
    검증2_구조불변식()
    검증3_경계()
    검증4_한국보정()
    경계커버리지()

    통과 = sum(1 for _, ok, _ in 결과 if ok)
    print("\n" + "=" * 66)
    print(f"통과 {통과}/{len(결과)}")
    실패 = [n for n, ok, _ in 결과 if not ok]
    if 실패:
        print("실패:", ", ".join(실패))
    print("판정:", "S2 통과 — 다음 단계로" if not 실패 else "S2 미통과 — 엔진부터 확인")
    print("=" * 66)
    return 0 if not 실패 else 1


if __name__ == "__main__":
    raise SystemExit(main())
