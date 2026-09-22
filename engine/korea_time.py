"""한국 시간대 보정 레이어 (PRD §8.2.1).

만세력 라이브러리는 절기를 **베이징 기준(UTC+8, 동경 120°)** 으로 계산한다.
한국 출생자를 그냥 넣으면 절기 경계 근처에서 연주·월주가 틀린다.
이 모듈이 그 간격을 메운다. 라이브러리가 절대 해주지 않는 부분이다.

보정 순서
  ① 서머타임 제거      — 시행 구간 출생이면 시계 시각에서 1시간 뺀다
  ② 그 시기 표준시로 UTC 환산 — 표준자오선이 135° ↔ 127.5° 로 바뀌었다
  ③ 절기 판정용 시각    = UTC + 8h   → 연주·월주에 쓴다
  ④ 진태양시           = UTC + 경도 × 4분 → 일주·시주에 쓴다

③과 ④를 나누는 이유
  절기 경계는 양쪽을 같은 기준으로 비교하므로 경도 보정이 상쇄된다(UTC 비교로 충분).
  반면 시주(자시 23~01시)는 **태양 기준 시각**으로 정하므로 경도가 결과를 바꾼다.

⚠️ 아래 표준시·서머타임 표는 **잠정값**이다 (PRD §18.1 Q3).
   릴리스 전 KASI·법령으로 1회 검증해야 한다. 날짜 경계가 하루라도 틀리면
   그 날 태어난 사람의 시주가 전부 틀린다.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

# ── 표준자오선 변천 (잠정, KASI 검증 대상) ────────────────────
# (시작일, 표준자오선 경도). 마지막 구간은 현재까지.
_MERIDIAN_ERAS: list[tuple[date, float]] = [
    (date(1900, 1, 1), 127.5),   # 대한제국 시기 — 동경 127.5° (UTC+8:30)
    (date(1912, 1, 1), 135.0),   # UTC+9
    (date(1954, 3, 21), 127.5),  # UTC+8:30 으로 환원
    (date(1961, 8, 10), 135.0),  # UTC+9 — 현재까지
]

# ── 서머타임 시행 구간 (잠정, KASI 검증 대상) ─────────────────
# 구간 안이면 시계가 1시간 앞당겨져 있었다 → 시계 시각에서 1시간 뺀다.
_DST_PERIODS: list[tuple[date, date]] = [
    (date(1948, 6, 1), date(1948, 9, 12)),
    (date(1949, 4, 3), date(1949, 9, 10)),
    (date(1950, 4, 1), date(1950, 9, 9)),
    (date(1951, 5, 6), date(1951, 9, 8)),
    (date(1955, 5, 5), date(1955, 9, 8)),
    (date(1956, 5, 20), date(1956, 9, 29)),
    (date(1957, 5, 5), date(1957, 9, 21)),
    (date(1958, 5, 4), date(1958, 9, 20)),
    (date(1959, 5, 3), date(1959, 9, 19)),
    (date(1960, 5, 1), date(1960, 9, 17)),
    (date(1987, 5, 10), date(1987, 10, 11)),
    (date(1988, 5, 8), date(1988, 10, 8)),
]

BEIJING_MERIDIAN = 120.0
MINUTES_PER_DEGREE = 4  # 지구가 1시간에 15° 돌므로 1° = 4분


@dataclass(frozen=True)
class CorrectedTime:
    """보정 결과. 리포트의 '계산 기준' 블록에 그대로 노출한다 (PRD §6.3 ⑦)."""

    clock: datetime
    """입력된 시계 시각 (출생 당시 그 지역 시계가 가리킨 값)"""
    utc: datetime
    dst_applied: bool
    standard_meridian: float
    """그 시기 한국 표준자오선 (135.0 또는 127.5)"""
    longitude: float
    """출생지 경도"""
    jieqi_reference: datetime
    """절기 판정용 = UTC + 8h. 연주·월주 계산에 쓴다"""
    true_solar: datetime
    """진태양시 = UTC + 경도×4분. 일주·시주 계산에 쓴다"""
    true_solar_correction_min: int
    """시계 시각 대비 진태양시 차이(분). 서울·135° 기준이면 약 -32"""


def is_dst(d: date) -> bool:
    return any(start <= d <= end for start, end in _DST_PERIODS)


def standard_meridian(d: date) -> float:
    result = _MERIDIAN_ERAS[0][1]
    for start, meridian in _MERIDIAN_ERAS:
        if d >= start:
            result = meridian
        else:
            break
    return result


def correct(clock: datetime, longitude: float) -> CorrectedTime:
    """시계 시각 + 출생지 경도 → 절기용·진태양시용 두 기준 시각."""
    dst = is_dst(clock.date())
    meridian = standard_meridian(clock.date())

    # ① 서머타임 제거 → ② 그 시기 표준시로 UTC 환산
    standard = clock - timedelta(hours=1) if dst else clock
    utc = standard - timedelta(minutes=meridian * MINUTES_PER_DEGREE)

    # ③ 절기 판정용 (베이징 기준)
    jieqi_reference = utc + timedelta(minutes=BEIJING_MERIDIAN * MINUTES_PER_DEGREE)

    # ④ 진태양시
    true_solar = utc + timedelta(minutes=longitude * MINUTES_PER_DEGREE)

    correction = round((true_solar - clock).total_seconds() / 60)

    return CorrectedTime(
        clock=clock,
        utc=utc,
        dst_applied=dst,
        standard_meridian=meridian,
        longitude=longitude,
        jieqi_reference=jieqi_reference,
        true_solar=true_solar,
        true_solar_correction_min=correction,
    )
