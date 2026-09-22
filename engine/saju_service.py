"""사주 원국·오행 계산 (PRD §8.2~§8.4).

계산은 `lunar-python` 이 하고, 이 모듈은 두 가지만 한다.
  ① 보정된 시각(§8.2.1)을 라이브러리에 **올바른 기준으로** 넣기
     — 연·월주는 절기 판정용 시각, 일·시주는 진태양시. 기준이 다르므로 두 번 호출한다.
  ② 오행 집계 정책 적용 (지장간 가중치는 우리 결정 — PRD §18.1 Q4)

LLM 은 이 결과를 문장으로 바꾸기만 한다. 계산은 절대 시키지 않는다 (PRD §11.1).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from lunar_python import Solar

ENGINE_VERSION = "saju-1.0.0-lunar-python-1.4.8"

# 야자시 유파 (PRD §18.1 Q6)
#   2 = 조자시 — 23:00~24:00 도 당일 일주 유지 (기본값)
#   1 = 야자시 — 익일 일간 기준
MidnightRule = Literal["조자시", "야자시"]
_SECT = {"조자시": 2, "야자시": 1}

# 천간·지지 → 오행 (PRD §8.4)
_GAN_ELEMENT = {
    "甲": "목", "乙": "목", "丙": "화", "丁": "화", "戊": "토",
    "己": "토", "庚": "금", "辛": "금", "壬": "수", "癸": "수",
}
_JI_ELEMENT = {
    "子": "수", "丑": "토", "寅": "목", "卯": "목", "辰": "토", "巳": "화",
    "午": "화", "未": "토", "申": "금", "酉": "금", "戌": "토", "亥": "수",
}

_GAN_KO = {
    "甲": "갑", "乙": "을", "丙": "병", "丁": "정", "戊": "무",
    "己": "기", "庚": "경", "辛": "신", "壬": "임", "癸": "계",
}
_JI_KO = {
    "子": "자", "丑": "축", "寅": "인", "卯": "묘", "辰": "진", "巳": "사",
    "午": "오", "未": "미", "申": "신", "酉": "유", "戌": "술", "亥": "해",
}

ELEMENTS = ("목", "화", "토", "금", "수")

# 지장간 가중치 — 본기 / 중기 / 여기 (PRD §18.1 Q4)
_HIDDEN_WEIGHTS = (1.0, 0.3, 0.2)


@dataclass(frozen=True)
class Pillar:
    gan: str
    ji: str
    ko: str


@dataclass(frozen=True)
class Elements:
    counts: dict[str, float]
    verdict: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Chart:
    year: Pillar
    month: Pillar
    day: Pillar
    hour: Pillar | None
    elements: Elements
    midnight_rule: MidnightRule
    engine_version: str = ENGINE_VERSION


def _pillar(ganzhi: str) -> Pillar:
    gan, ji = ganzhi[0], ganzhi[1]
    return Pillar(gan=gan, ji=ji, ko=f"{_GAN_KO[gan]}{_JI_KO[ji]}")


def _eight_char(moment: datetime, rule: MidnightRule):
    lunar = Solar.fromYmdHms(
        moment.year, moment.month, moment.day, moment.hour, moment.minute, moment.second
    ).getLunar()
    ec = lunar.getEightChar()
    ec.setSect(_SECT[rule])
    return ec


def _tally_elements(
    pillars: list[Pillar],
    hidden: list[list[str]],
    include_hidden: bool,
) -> Elements:
    counts = {e: 0.0 for e in ELEMENTS}

    for p in pillars:
        counts[_GAN_ELEMENT[p.gan]] += 1.0
        counts[_JI_ELEMENT[p.ji]] += 1.0

    if include_hidden:
        for stems in hidden:
            for stem, weight in zip(stems, _HIDDEN_WEIGHTS):
                counts[_GAN_ELEMENT[stem]] += weight

    total = sum(counts.values()) or 1.0
    verdict: list[str] = []
    for e in ELEMENTS:
        ratio = counts[e] / total
        if counts[e] == 0:
            verdict.append(f"{e} 없음")
        elif ratio >= 0.40:
            verdict.append(f"{e} 과다")
        elif ratio <= 0.05:
            verdict.append(f"{e} 부족")
    if not verdict:
        verdict.append("오행이 고르게 분포")

    return Elements(
        counts={e: round(counts[e], 2) for e in ELEMENTS},
        verdict=verdict,
    )


def build_chart(
    jieqi_reference: datetime,
    true_solar: datetime | None,
    *,
    midnight_rule: MidnightRule = "조자시",
    include_hidden_stems: bool = True,
) -> Chart:
    """원국 4주와 오행을 계산한다.

    두 시각을 받는 이유는 §8.2.1 그대로다.
      jieqi_reference — 절기 경계 판정용(베이징 기준). 연주·월주에 쓴다.
      true_solar      — 진태양시. 일주·시주에 쓴다. None 이면 시간 미상.

    시간 미상이면 시주를 빼고 3주로만 계산한다 (PRD §8.3).
    """
    ym = _eight_char(jieqi_reference, midnight_rule)
    year = _pillar(ym.getYear())
    month = _pillar(ym.getMonth())

    if true_solar is None:
        # 시각을 모르면 정오를 기준으로 일주만 잡는다. 시주는 만들지 않는다.
        noon = jieqi_reference.replace(hour=12, minute=0, second=0)
        dh = _eight_char(noon, midnight_rule)
        day = _pillar(dh.getDay())
        hour_pillar = None
        hidden = [ym.getYearHideGan(), ym.getMonthHideGan(), dh.getDayHideGan()]
        pillars = [year, month, day]
    else:
        dh = _eight_char(true_solar, midnight_rule)
        day = _pillar(dh.getDay())
        hour_pillar = _pillar(dh.getTime())
        hidden = [
            ym.getYearHideGan(),
            ym.getMonthHideGan(),
            dh.getDayHideGan(),
            dh.getTimeHideGan(),
        ]
        pillars = [year, month, day, hour_pillar]

    return Chart(
        year=year,
        month=month,
        day=day,
        hour=hour_pillar,
        elements=_tally_elements(pillars, hidden, include_hidden_stems),
        midnight_rule=midnight_rule,
    )


@dataclass(frozen=True)
class Period:
    """조회 시점의 기운 — 세운(그 해)과 월운(그 달) (PRD §8.5).

    원국은 평생 고정이고, 이 값이 달마다 바뀐다.
    "이번 달 흐름"이라는 리포트의 근거가 바로 이것이다.
    """

    year: Pillar
    month: Pillar
    label: str
    """사람이 읽는 표기 — 예: '2026년 9월 · 병오년 정유월'"""


def current_period(now: datetime, jieqi_reference: datetime) -> Period:
    """지금이 어느 세운·월운에 속하는지.

    월운은 **절기 기준**으로 바뀐다(달력 1일이 아니다). 그래서 원국과 같은
    라이브러리·같은 보정 규칙을 쓴다.
    """
    ec = _eight_char(jieqi_reference, "조자시")
    year = _pillar(ec.getYear())
    month = _pillar(ec.getMonth())
    return Period(
        year=year,
        month=month,
        label=f"{now.year}년 {now.month}월 · {year.ko}년 {month.ko}월",
    )


# 라이브러리 절기 테이블은 키가 두 가지로 섞여 나온다.
#   같은 절기가 앞뒤 해에 걸쳐 두 번 등장하는데, 두 번째는 로마자 키로 온다.
#   (예: '冬至' 2023-12-22 와 'DONG_ZHI' 2024-12-21)
# 또 간체자를 쓴다(惊蛰·谷雨·小满·芒种·处暑). 대조하려면 정규화해야 한다.
_ROMAN_TO_HANJA = {
    "LI_CHUN": "立春", "YU_SHUI": "雨水", "JING_ZHE": "惊蛰", "CHUN_FEN": "春分",
    "QING_MING": "清明", "GU_YU": "谷雨", "LI_XIA": "立夏", "XIAO_MAN": "小满",
    "MANG_ZHONG": "芒种", "XIA_ZHI": "夏至", "XIAO_SHU": "小暑", "DA_SHU": "大暑",
    "LI_QIU": "立秋", "CHU_SHU": "处暑", "BAI_LU": "白露", "QIU_FEN": "秋分",
    "HAN_LU": "寒露", "SHUANG_JIANG": "霜降", "LI_DONG": "立冬", "XIAO_XUE": "小雪",
    "DA_XUE": "大雪", "DONG_ZHI": "冬至", "XIAO_HAN": "小寒", "DA_HAN": "大寒",
}


def solar_term_table(year: int, *, year_only: bool = True) -> dict[str, str]:
    """그 해 24절기 시각 — **한국 기준**(라이브러리 값 + 1시간).

    KASI 대조(tools/verify_solar_terms.py)와 불변식 테스트가 이 값을 쓴다.
    year_only=True 면 그 달력 연도에 든 24개만 돌려준다.
    """
    from datetime import timedelta

    lunar = Solar.fromYmdHms(year, 6, 1, 12, 0, 0).getLunar()
    out: dict[str, str] = {}
    for name, solar in lunar.getJieQiTable().items():
        key = _ROMAN_TO_HANJA.get(name, name)
        beijing = datetime(
            solar.getYear(), solar.getMonth(), solar.getDay(),
            solar.getHour(), solar.getMinute(), solar.getSecond(),
        )
        korea = beijing + timedelta(hours=1)
        if year_only and korea.year != year:
            continue
        out[key] = korea.isoformat(sep=" ")
    return out
