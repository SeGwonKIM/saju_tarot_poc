"""되묻기 확인 게이트 — 위험한 입력은 사람에게 넘긴다

왜 필요한가
  LLM 추출의 남은 오답이 **전부 음력 날짜**다 (F-22).

    002  음력 7월 20일          → 1988-08-20   (정답 07-20)
    007  음력 윤2월 초여드레     → 1947-02-18   (정답 02-08)
    010  음력 윤유월 초닷새      → 1960-07-05   (정답 06-05)

  그리고 같은 입력에서 값이 갈리기도 한다 (S4b 미달). 프롬프트로 좋아졌지만
  없어지지 않았고, **없어질 것 같지도 않다.**

  그래서 모델을 더 조이는 대신 **틀릴 수 있는 자리를 골라 사람에게 되묻는다.**
  오프라인 상담에서 이미 하는 일이다 — "생년월일 다시 한번 불러 드릴게요".

두 가지를 한다
  ① 위험 등급 판정 — 음력·윤달·자시 경계·서머타임·미상 값은 무조건 확인
  ② 숫자 대조 (회귀 가드) — 낸 월·일이 **원문에 실제로 나온 수**인가

  ②는 **정확도 증거가 아니다.** 이미 알고 있는 오답 3건을 보고 만든 검사라
  과거 실패를 덮는 안전망일 뿐이다 (검토의견 §5-2). 그래서 이름도 '회귀 가드'다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ── 숫자 읽기 ────────────────────────────────────────────
_수 = {"일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8,
       "구": 9, "십": 10, "열": 10, "스무": 20, "스물": 20, "서른": 30}
_날말 = {"하루": 1, "이틀": 2, "사흘": 3, "나흘": 4, "닷새": 5, "엿새": 6,
         "이레": 7, "여드레": 8, "아흐레": 9, "열흘": 10, "보름": 15, "스무날": 20}


def _읽기(t: str) -> int | None:
    t = t.strip()
    if t.isdigit():
        return int(t)
    if t in _수:
        return _수[t]
    if (m := re.fullmatch(r"([일이삼사오육칠팔구])?십([일이삼사오육칠팔구])?", t)):
        return (_수.get(m.group(1), 1) if m.group(1) else 1) * 10 \
            + (_수.get(m.group(2), 0) if m.group(2) else 0)
    if (m := re.fullmatch(r"(열|스물|스무)([일이삼사오육칠팔구])?", t)):
        return _수[m.group(1)] + (_수.get(m.group(2), 0) if m.group(2) else 0)
    return None


def 원문의수(글: str) -> dict[str, set[int]]:
    """원문에 **날짜로** 등장한 수를 역할별로 모은다.

    그냥 모으면 '팔팔년생' 의 8 이 월로 오인된다. 그래서 역할을 본다.
    """
    r: dict[str, set[int]] = {"월": set(), "일": set()}
    for 기호 in ("월", "일"):
        for m in re.finditer(rf"([가-힣\d]{{1,4}})\s*{기호}", 글):
            if (v := _읽기(m.group(1))) is not None:
                r[기호].add(v)
    for 말, 값 in _날말.items():          # 초여드레 · 스무날
        if 말 in 글:
            r["일"].add(값)
    return r


# ── 확인 결과 ────────────────────────────────────────────
@dataclass
class 확인요청:
    필요: bool = False
    이유: list[str] = field(default_factory=list)
    경고: list[str] = field(default_factory=list)      # 숫자 대조가 걸린 것
    대본: str = ""                                     # 상담사가 읽을 문장

    def 출력(self) -> str:
        if not self.필요:
            return "확인 게이트 — 통과 (위험 요소 없음)"
        줄 = ["확인 게이트 — 사람 확인이 필요합니다", ""]
        for x in self.이유:
            줄.append(f"  · {x}")
        for x in self.경고:
            줄.append(f"  ⚠ {x}")
        줄 += ["", "  [상담사가 읽을 문장]", f"  \"{self.대본}\""]
        return "\n".join(줄)


_서머타임 = ((1948, 1951), (1987, 1988))
_변칙표준시 = (1954, 1961)


def 판정(입력: dict, 원문: str) -> 확인요청:
    """무엇을 되물어야 하는지 정한다. 규칙은 전부 여기 한 곳에 있다."""
    r = 확인요청()
    y = int(입력["birth_date"][:4]) if 입력.get("birth_date") else None

    # ① 음력 — 남은 오답이 전부 여기다
    if 입력.get("calendar_type") == "lunar":
        r.이유.append("음력으로 말씀하셨습니다 — 추출 오답이 가장 많이 나오는 자리입니다")
        if 입력.get("is_leap"):
            r.이유.append("윤달입니다 — 윤달을 한 달 밀어 적는 실수가 실제로 있었습니다")
        elif 입력.get("is_leap") is None:
            r.이유.append("윤달 여부를 듣지 못했습니다")

    # ② 자시 경계 — 일주가 통째로 바뀐다
    if (시각 := 입력.get("birth_time")):
        hh = int(시각[:2])
        if hh >= 23 or hh < 1:
            r.이유.append(f"출생 시각이 자시 경계({시각})입니다 — 보정 결과에 따라 일주가 바뀝니다")
    else:
        r.이유.append("출생 시각을 모르십니다 — 시주를 뺀 3주 6글자로 봅니다")

    # ③ 시대 보정 구간
    if y:
        for 시작, 끝 in _서머타임:
            if 시작 <= y <= 끝:
                r.이유.append(f"{y}년은 서머타임 시행 구간입니다 — 시계에서 1시간을 뺍니다")
                break
        if _변칙표준시[0] <= y <= _변칙표준시[1]:
            r.이유.append(f"{y}년은 표준시가 127.5°이던 시기입니다")

    # ④ 빠진 값
    if not 입력.get("birth_place"):
        r.이유.append("출생지를 듣지 못했습니다 — 서울 기준으로 계산합니다")
    for f in (입력.get("missing") or []):
        r.이유.append(f"필수 항목이 비어 있습니다: {f}")
    for f in (입력.get("uncertain") or []):
        r.이유.append(f"불확실하게 말씀하신 값입니다: {f}")

    # ⑤ 숫자 대조 (회귀 가드)
    if 입력.get("birth_date"):
        수 = 원문의수(원문)
        _, m, d = (int(x) for x in 입력["birth_date"].split("-"))
        if 수["월"] and m not in 수["월"]:
            r.경고.append(f"뽑아낸 '{m}월' 이 대화에 안 나옵니다 "
                          f"(대화에 나온 월: {sorted(수['월'])})")
        if 수["일"] and d not in 수["일"]:
            r.경고.append(f"뽑아낸 '{d}일' 이 대화에 안 나옵니다 "
                          f"(대화에 나온 일: {sorted(수['일'])})")

    r.필요 = bool(r.이유 or r.경고)
    r.대본 = 대본만들기(입력)
    return r


def 대본만들기(입력: dict) -> str:
    """상담사가 손님에게 그대로 읽어 줄 문장."""
    조각 = []
    if 입력.get("name"):
        조각.append(f"{입력['name']} 님")
    if 입력.get("birth_date"):
        y, m, d = 입력["birth_date"].split("-")
        달력 = "음력" if 입력.get("calendar_type") == "lunar" else "양력"
        윤 = " 윤달" if 입력.get("is_leap") else ""
        조각.append(f"{달력}{윤} {y}년 {int(m)}월 {int(d)}일")
    if 입력.get("birth_time"):
        hh, mm = (int(x) for x in 입력["birth_time"].split(":"))
        때 = "오전" if hh < 12 else "오후"
        조각.append(f"{때} {hh if hh <= 12 else hh - 12}시 {mm}분" if mm
                    else f"{때} {hh if hh <= 12 else hh - 12}시")
    else:
        조각.append("태어난 시각은 모름")
    if 입력.get("birth_place"):
        조각.append(f"{입력['birth_place']} 출생")
    if 입력.get("gender"):
        조각.append("남성" if 입력["gender"] == "male" else "여성")
    return ", ".join(조각) + " — 맞으실까요?"
