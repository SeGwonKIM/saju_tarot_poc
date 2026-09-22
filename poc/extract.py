"""② 상담 텍스트 → 구조화 입력 (PRD_PoC.md 3.2 · 4.3)

두 가지 방법을 나란히 둔다.

  RuleExtractor  정규식만 쓰는 기준선. 코드 몇십 줄, 공짜, 즉시.
  LlmExtractor   LLM 구조화 출력.

기준선을 같이 두는 이유는 하나다. LLM 점수가 20/25 라고 해도
규칙 기반이 19/25 라면 LLM 을 쓸 이유가 약하다. 옆에 놓아야 읽힌다.

쓰는 법:
    python -m poc.extract samples/상담_001.txt            # 기준선
    python -m poc.extract samples/상담_001.txt --llm      # LLM
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

_선언 = yaml.safe_load(
    (Path(__file__).resolve().parents[1] / "spec" / "fields.yaml").read_text(encoding="utf-8"))
필드 = tuple(s["id"] for s in _선언["slots"])
_슬롯 = {s["id"]: s for s in _선언["slots"]}


_범위 = _선언.get("service_range", {})


def 서비스범위(생년: int, 오늘연도: int | None = None) -> str | None:
    """상담 대상 연령을 벗어나면 이유를, 괜찮으면 None.

    라이브러리가 1880년을 받아 값을 내주지만 **그 값을 검증한 적이 없다**.
    표본도 없고 표준시 이력도 다르다. 계산해서 조용히 내보내는 대신 거부한다.
    """
    from datetime import date
    올해 = 오늘연도 or date.today().year
    아래 = _범위.get("min_birth_year", 1940)
    위 = _범위.get("max_birth_year") or 올해
    if 생년 < 아래:
        return (f"{생년}년생은 상담 대상이 아닙니다 "
                f"({아래}년 이후 출생자만 — {올해}년 기준 {올해 - 아래}세 이하)")
    if 생년 > 위:
        return f"{생년}년은 미래입니다 (오늘 {올해}년)"
    return None


def 정규화(값: dict) -> dict:
    """모델 출력에 **결정된 사실**을 코드가 채워 넣는다.

    양력에는 윤달이 없다. 이건 모델에게 물을 일이 아니라 정해진 사실이다.
    프롬프트로 부탁하면 모델이 잊는다 (실측: 양력 7건 중 7건을 null 로 둠).
    "계산은 코드가" 원칙을 여기에도 적용한다.
    """
    if 값.get("calendar_type") == "solar":
        값["is_leap"] = False
    return 값


def 빈칸판정(값: dict) -> list[str]:
    """무엇을 되물어야 하는지는 **코드가** 정한다 (검토의견 §7-2).

    F-16 — LLM 에게 missing 을 맡겼더니 이미 답한 항목을 "물어봐야 한다"고 적었다.
    대화 상태 판단은 규칙이 정해져 있으므로 코드가 한다. 그러면 이 오류는
    발생 자체가 불가능해진다.
    """
    빈칸 = []
    for f, 슬롯 in _슬롯.items():
        if 값.get(f) is not None:
            continue
        if 슬롯.get("required"):
            빈칸.append(f)
        elif 슬롯.get("required_when") == "calendar_type == lunar"                 and 값.get("calendar_type") == "lunar":
            빈칸.append(f)
    return 빈칸


@dataclass
class Intake:
    name: str | None = None
    gender: str | None = None            # male / female
    birth_date: str | None = None        # YYYY-MM-DD
    calendar_type: str | None = None     # solar / lunar
    is_leap: bool | None = None
    birth_time: str | None = None        # HH:MM
    birth_place: str | None = None
    question: str | None = None
    uncertain: list[str] | None = None   # 값은 넣었으나 확실하지 않은 필드
    missing: list[str] | None = None     # 물어봐야 하는 필드

    def to_dict(self) -> dict:
        return asdict(self)


# ══════════════════════════════════════════════════════════
# 기준선 — 정규식
# ══════════════════════════════════════════════════════════
_한글수 = {"영": 0, "공": 0, "일": 1, "이": 2, "삼": 3, "사": 4, "오": 5,
           "육": 6, "칠": 7, "팔": 8, "구": 9, "십": 10,
           "한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5, "여섯": 6,
           "일곱": 7, "여덟": 8, "아홉": 9, "열": 10,
           "스무": 20, "스물": 20, "서른": 30}

_도시 = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
         "수원", "성남", "고양", "용인", "청주", "전주", "포항", "창원",
         "제주", "춘천", "강릉", "목포", "여수"]


def _한글수읽기(t: str) -> int | None:
    """'스무' '여덟' '열둘' 같은 한글 수를 정수로. 못 읽으면 None."""
    t = t.strip()
    if t.isdigit():
        return int(t)
    if t in _한글수:
        return _한글수[t]
    m = re.fullmatch(r"(열|스물|스무|서른)([일이삼사오육칠팔구])?", t)
    if m:
        v = _한글수.get(m.group(1), 0)
        return v + (_한글수.get(m.group(2), 0) if m.group(2) else 0)
    # 한자어 수 — 이십, 삼십오, 십이 …
    m = re.fullmatch(r"([일이삼사오육칠팔구])?십([일이삼사오육칠팔구])?", t)
    if m:
        십 = _한글수.get(m.group(1), 1) if m.group(1) else 1
        return 십 * 10 + (_한글수.get(m.group(2), 0) if m.group(2) else 0)
    # '천구백칠십이' 같은 연도
    if all(c in "천구백십영일이삼사오육칠팔구" for c in t) and len(t) >= 3:
        값, 단 = 0, 0
        for c in t:
            if c == "천": 값 += max(단, 1) * 1000; 단 = 0
            elif c == "백": 값 += max(단, 1) * 100; 단 = 0
            elif c == "십": 값 += max(단, 1) * 10; 단 = 0
            else: 단 = _한글수.get(c, 0)
        return 값 + 단
    return None


class RuleExtractor:
    이름 = "규칙 기반 (기준선)"

    def extract(self, text: str) -> Intake:
        r = Intake(uncertain=[], missing=[])
        의뢰인 = "\n".join(l.split(":", 1)[1] for l in text.splitlines()
                          if l.startswith("의뢰인:"))

        # 이름 — 'XXX입니다/이에요/이요/이고요'
        m = re.search(r"([가-힣]{2,4})(?:입니다|이에요|예요|이요|이고요|이라고)", 의뢰인)
        if m: r.name = m.group(1)

        # 성별 — ① 의뢰인이 직접 말한 경우 ② 상담자가 묻고 의뢰인이 긍정한 경우
        if re.search(r"남자|남성", 의뢰인): r.gender = "male"
        elif re.search(r"여자|여성", 의뢰인): r.gender = "female"
        else:
            줄 = text.splitlines()
            for i, l in enumerate(줄[:-1]):
                if not l.startswith("상담자:"): continue
                다음 = 줄[i + 1]
                if not 다음.startswith("의뢰인:") or not re.search(r"네|예|맞", 다음):
                    continue
                if re.search(r"남자|남성", l): r.gender = "male"; break
                if re.search(r"여자|여성", l): r.gender = "female"; break

        # 음력/양력 — 상담자가 "양력이신가요 음력이신가요" 로 둘 다 말하므로
        #            의뢰인 발화를 먼저 본다
        바탕 = 의뢰인 if ("음력" in 의뢰인 or "양력" in 의뢰인) else text
        if "음력" in 바탕: r.calendar_type = "lunar"
        elif "양력" in 바탕: r.calendar_type = "solar"
        if r.calendar_type == "solar": r.is_leap = False
        elif "윤달" in text: r.is_leap = True

        # 생년월일 — 숫자형 먼저, 없으면 한글형
        # '1988년 음력 7월 20일' 처럼 년과 월 사이에 낱말이 끼는 일이 잦다
        m = re.search(r"(\d{4})\s*년\s*(?:음력|양력|윤달)?\s*"
                      r"(\d{1,2})\s*월\s*(\d{1,2})\s*일", text)
        if m:
            r.birth_date = f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        else:
            m = re.search(r"([가-힣]+)\s*년\s*([가-힣\d]+)\s*월\s*([가-힣\d]+)\s*일", 의뢰인)
            if m:
                y, mo, d = (_한글수읽기(g) for g in m.groups())
                if y and y < 100:  # '육십삼년' → 1963
                    y += 1900
                if y and mo and d:
                    r.birth_date = f"{y:04d}-{mo:02d}-{d:02d}"

        # 시간 — '모르겠' 이 있으면 미상
        if re.search(r"시간.{0,10}(모르|기억을 못)", text):
            r.birth_time = None
        else:
            # 한 사람이 시각을 여러 번 말한다 —
            # '새벽 한 시 좀 넘어서' 뒤에 '한 시 십 분쯤' 이 오는 식.
            # 분까지 말한 쪽이 더 자세하므로 그것을 고르고,
            # 오전/오후 표시는 다른 곳에서 말했어도 끌어온다.
            후보 = list(re.finditer(
                r"(오전|오후|아침|저녁|새벽|밤|낮)?\s*"
                r"([가-힣\d]+)\s*시\s*(?:([가-힣\d]+)\s*분)?", 의뢰인))
            m = next((c for c in 후보 if c.group(3)), 후보[0] if 후보 else None)
            if m:
                때, 시, 분 = m.group(1), _한글수읽기(m.group(2)), _한글수읽기(m.group(3) or "0")
                if 때 is None:   # 같은 시각을 가리키는 다른 발화에서 빌려온다
                    때 = next((c.group(1) for c in 후보
                               if c.group(1) and _한글수읽기(c.group(2)) == 시), None)
                if 시 is not None:
                    if 때 in ("오후", "저녁", "밤") and 시 < 12: 시 += 12
                    if 때 == "새벽" and 시 == 12: 시 = 0
                    r.birth_time = f"{시:02d}:{(분 or 0):02d}"
                    if re.search(r"쯤|정확하진|대략|정도", 의뢰인):
                        r.uncertain.append("birth_time")

        # 출생지
        for c in _도시:
            if c in 의뢰인: r.birth_place = c; break

        # 고민 — 마지막 의뢰인 발화 중 물음이 담긴 줄
        for l in reversed(의뢰인.splitlines()):
            if re.search(r"궁금|고민|문제|보고 싶|봐주|알고 싶", l):
                r.question = l.strip(); break

        정규화(r.__dict__)                     # 양력이면 is_leap=False (코드가 정한다)
        r.missing = 빈칸판정(r.to_dict())      # 코드가 판정한다 (F-16)
        return r


# ══════════════════════════════════════════════════════════
# LLM
# ══════════════════════════════════════════════════════════
_SYSTEM = """너는 사주 상담 접수를 정리하는 도우미다.
상담 녹취에서 아래 항목만 뽑아 JSON 으로 낸다.

절대 규칙 — 어기면 뒤의 모든 계산이 틀어진다:
· 대화에 없는 값은 반드시 null 로 둔다. 추측하거나 지어내지 않는다.
· 이름으로 성별을 짐작하지 않는다. 성별이 말로 나오지 않았으면 null 이다.
· 음력인데 윤달 여부가 안 나왔으면 is_leap 은 null 이다. false 로 단정하지 않는다.
· '쯤', '정도', '대략' 처럼 불확실하게 말한 값은 값을 넣되 uncertain 목록에 필드명을 넣는다.
· missing 목록은 빈 배열로 두어라. 무엇을 되물을지는 프로그램이 정한다.

달력에 대해 — 지금까지 틀린 것이 전부 여기였다:
· **날짜에 산수를 하지 마라.** 들은 숫자를 그대로 옮겨 적는 일만 한다.
· 음력이라고 들었으면 **음력 월·일을 그대로** 적고 calendar_type 을 lunar 로 둔다.
  양력으로 바꾸지 마라. 변환은 프로그램이 한다.
· 윤달은 **is_leap: true 로만** 표시한다. 월 숫자를 1 올리지 마라.
  '윤2월'은 month=2, is_leap=true 이지 month=3 이 아니다.
· 말한 사람이 날짜를 고쳤으면("사월... 아니 오월") **마지막에 말한 값**을 쓴다.

birth_date 는 YYYY-MM-DD, birth_time 은 24시간 HH:MM 으로 적는다.
gender 는 male 또는 female. calendar_type 은 solar 또는 lunar."""

_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": ["string", "null"]},
        "gender": {"type": ["string", "null"], "enum": ["male", "female", None]},
        "birth_date": {"type": ["string", "null"]},
        "calendar_type": {"type": ["string", "null"], "enum": ["solar", "lunar", None]},
        "is_leap": {"type": ["boolean", "null"]},
        "birth_time": {"type": ["string", "null"]},
        "birth_place": {"type": ["string", "null"]},
        "question": {"type": ["string", "null"]},
        "uncertain": {"type": "array", "items": {"type": "string"}},
        "missing": {"type": "array", "items": {"type": "string"}},
    },
    "required": list(필드) + ["uncertain", "missing"],
    "additionalProperties": False,
}


class LlmExtractor:
    이름 = "LLM"
    지문 = ""          # system_fingerprint — 모델 실체가 바뀌면 이 값이 달라진다
    사용량: dict = {}   # 토큰 — S6(원가) 의 재료

    def __init__(self, model: str = "gpt-4o-mini-2024-07-18",
                 env_path: str | None = None):
        self.model = model
        키 = os.environ.get("OPENAI_API_KEY")
        if not 키 and env_path:
            for line in Path(env_path).read_text(encoding="utf-8").splitlines():
                if line.startswith("OPENAI_API_KEY="):
                    키 = line.split("=", 1)[1].strip().strip('"').strip("'")
        if not 키:
            raise SystemExit("OPENAI_API_KEY 가 없습니다. 환경변수나 --env 로 주세요.")
        from openai import OpenAI
        self.client = OpenAI(api_key=키)

    def extract(self, text: str) -> Intake:
        res = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[{"role": "system", "content": _SYSTEM},
                      {"role": "user", "content": text}],
            seed=20260922,
            response_format={"type": "json_schema", "json_schema": {
                "name": "intake", "strict": True, "schema": _SCHEMA}},
        )
        self.지문 = getattr(res, "system_fingerprint", "") or ""
        u = getattr(res, "usage", None)
        if u:
            self.사용량 = {"in": u.prompt_tokens, "out": u.completion_tokens}
        d = 정규화(json.loads(res.choices[0].message.content))
        d["missing"] = 빈칸판정(d)             # 모델이 낸 목록은 버린다 (F-16)
        return Intake(**d)


# ══════════════════════════════════════════════════════════
def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit(__doc__)
    text = Path(args[0]).read_text(encoding="utf-8")
    env = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--env=")), None)
    ex = LlmExtractor(env_path=env) if "--llm" in sys.argv else RuleExtractor()
    print(f"# {ex.이름}")
    print(json.dumps(ex.extract(text).to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
