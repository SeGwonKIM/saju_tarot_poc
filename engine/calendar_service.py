"""음↔양 변환 (PRD §8.1).

두 가지 함정을 피하도록 짜여 있다.

1. `setLunarDate(..., isIntercalation=True)` 는 **없는 윤달에도 True 를 반환한다.**
   그래서 모든 변환을 음→양→음으로 되돌려 같은 날이 나오는지 확인한다(왕복 검증).
2. `KoreanLunarCalendar` 는 내부에 상태를 들고 있다. FastAPI 가 동기 함수를
   스레드풀에서 돌리므로 인스턴스를 공유하면 응답이 섞인다. **호출마다 새로 만든다.**
"""

from dataclasses import dataclass
from datetime import date

from korean_lunar_calendar import KoreanLunarCalendar

MIN_YEAR = 1900
MAX_YEAR = date.today().year


class CalendarError(Exception):
    """도메인상 불가능한 날짜 — 422로 응답한다 (PRD §10.6)."""

    def __init__(self, code: str, message: str, field: str = "date") -> None:
        self.code = code
        self.message = message
        self.field = field
        super().__init__(message)


@dataclass(frozen=True)
class Converted:
    solar_date: str
    lunar_date: str
    is_leap_month: bool
    ganji: str


@dataclass(frozen=True)
class LunarMonth:
    month: int
    days: int
    has_leap: bool
    leap_days: int | None


def _check_year(year: int, *, lunar: bool = False) -> None:
    """서비스가 지원하는 연도 범위인지 본다.

    음력은 하한을 한 해 넓힌다. 양력 1900년 1월은 음력으로는 1899년 12월이라,
    1900년을 지원하려면 음력 1899년을 받아야 왕복 변환이 성립한다.
    """
    low = MIN_YEAR - 1 if lunar else MIN_YEAR
    if not low <= year <= MAX_YEAR:
        raise CalendarError(
            "YEAR_OUT_OF_RANGE",
            f"{MIN_YEAR}년부터 {MAX_YEAR}년까지만 지원합니다.",
        )


def _lunar_to_solar_checked(
    year: int, month: int, day: int, is_leap: bool
) -> tuple[str, str] | None:
    """왕복 검증을 통과하면 (양력 ISO, 간지)를 돌려주고, 아니면 None."""
    cal = KoreanLunarCalendar()
    if not cal.setLunarDate(year, month, day, is_leap):
        return None
    solar = cal.SolarIsoFormat()
    ganji = cal.getGapJaString()

    back = KoreanLunarCalendar()
    sy, sm, sd = (int(x) for x in solar.split("-"))
    if not back.setSolarDate(sy, sm, sd):
        return None
    same = (back.lunarYear, back.lunarMonth, back.lunarDay, bool(back.isIntercalation))
    if same != (year, month, day, is_leap):
        return None
    return solar, ganji


def lunar_to_solar(year: int, month: int, day: int, is_leap: bool) -> Converted:
    _check_year(year, lunar=True)
    result = _lunar_to_solar_checked(year, month, day, is_leap)
    if result is None:
        if is_leap and not has_leap_month(year, month):
            raise CalendarError(
                "LUNAR_DATE_NOT_FOUND", f"{year}년에는 윤{month}월이 없습니다."
            )
        raise CalendarError(
            "LUNAR_DATE_NOT_FOUND",
            f"음력 {year}년 {month}월 {day}일은 없는 날짜입니다.",
        )
    solar, ganji = result
    return Converted(
        solar_date=solar,
        lunar_date=f"{year:04d}-{month:02d}-{day:02d}",
        is_leap_month=is_leap,
        ganji=ganji,
    )


def solar_to_lunar(year: int, month: int, day: int) -> Converted:
    _check_year(year)
    try:
        date(year, month, day)  # 2월 30일 같은 입력 차단
    except ValueError as e:
        raise CalendarError("INVALID_SOLAR_DATE", "없는 날짜입니다.") from e

    cal = KoreanLunarCalendar()
    if not cal.setSolarDate(year, month, day):
        raise CalendarError("SOLAR_DATE_NOT_FOUND", "변환할 수 없는 날짜입니다.")

    return Converted(
        solar_date=f"{year:04d}-{month:02d}-{day:02d}",
        lunar_date=f"{cal.lunarYear:04d}-{cal.lunarMonth:02d}-{cal.lunarDay:02d}",
        is_leap_month=bool(cal.isIntercalation),
        ganji=cal.getGapJaString(),
    )


def _days_in_lunar_month(year: int, month: int, is_leap: bool) -> int | None:
    """음력 달은 29일(소월) 또는 30일(대월). 없는 달이면 None."""
    for day in (30, 29):
        if _lunar_to_solar_checked(year, month, day, is_leap) is not None:
            return day
    return None


def has_leap_month(year: int, month: int) -> bool:
    return _days_in_lunar_month(year, month, True) is not None


def lunar_year_info(year: int) -> list[LunarMonth]:
    """폼의 '일' 선택지와 윤달 체크박스 노출에 쓰인다 (PRD §6.1 필드 4·5)."""
    _check_year(year)
    months: list[LunarMonth] = []
    for month in range(1, 13):
        days = _days_in_lunar_month(year, month, False)
        leap_days = _days_in_lunar_month(year, month, True)
        months.append(
            LunarMonth(
                month=month,
                days=days or 29,
                has_leap=leap_days is not None,
                leap_days=leap_days,
            )
        )
    return months
