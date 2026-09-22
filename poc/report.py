"""⑥⑦ 리포트 초안 생성 (PRD_PoC.md 3.2)

PRD 3.3 은 "리포트 생성기가 이미 있으니 그대로 쓰면 된다"고 적었지만,
실제로 열어 보니 그대로는 안 됐다. 세 군데가 어긋난다.

  1. build_facts 가 **타로 3장을 필수로** 받는다. PoC 범위는 사주만이다.
  2. 주제 enum 이 재회운·상대방속마음·연애·재물·대인관계 다섯뿐이다.
     샘플의 고민은 이직·사업·건강·이사·취업 이라 하나도 안 맞는다.
  3. SYSTEM 프롬프트가 타로 카드를 전제로 쓰여 있다.

그래서 **사실 블록과 프롬프트만 사주 전용으로 새로 쓰고**, 나머지는 그대로 쓴다.

  그대로 쓰는 것   Report · BANNED · has_banned_word · 스키마로 주제를 못 박는 방식
  새로 쓰는 것     build_facts_saju · SYSTEM_SAJU · _user_prompt_saju

상용으로 갈 때 이 파일은 버리고 report_service 에 사주 전용 분기를 넣는 것이
맞다. PoC 에서 본 저장소를 건드리지 않으려고 따로 뺐을 뿐이다.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.report_service import Report  # noqa: E402
from poc import safety  # noqa: E402
from engine.saju_service import Chart, Period  # noqa: E402

# 샘플의 고민을 담을 수 있는 주제. enum 으로 못 박아 모델이 주제를 늘리지 못하게 한다.
주제목록 = ["이직", "사업", "재물", "건강", "이사", "취업", "연애", "대인관계", "종합"]

# 고민 문장에서 주제를 고르는 표 — 못 고르면 '종합'
_주제단서 = {
    "이직": ["이직", "옮길", "전직", "직장"],
    "취업": ["취업", "입사", "구직"],
    "사업": ["사업", "창업", "장사", "개업"],
    "재물": ["재물", "돈", "금전", "재정", "투자"],
    "건강": ["건강", "몸", "아프"],
    "이사": ["이사", "이전", "집을"],
    "연애": ["연애", "결혼", "애인", "배우자"],
    "대인관계": ["대인", "사람 관계", "인간관계"],
}


def 주제고르기(고민: str | None) -> list[str]:
    """고민 문장에서 주제를 2개까지 고른다. 못 고르면 '종합' 하나."""
    if not 고민:
        return ["종합"]
    골라낸 = [t for t, 단서 in _주제단서.items() if any(c in 고민 for c in 단서)]
    return 골라낸[:2] or ["종합"]


def build_facts_saju(chart: Chart, period: Period, basis: str,
                     보정메모: list[str]) -> str:
    """확정된 계산 결과를 사실 블록으로. 모델은 이 값을 바꿀 수 없다.

    타로가 없다는 것을 **명시**한다. 안 그러면 모델이 카드 이야기를 지어낸다.
    """
    def 표기(p, 이름):
        return None if p is None else f"{이름} {p.ko}({p.gan}{p.ji})"

    줄 = ["<계산결과>", f"이번 달(조회 시점): {period.label}"]
    기둥 = [표기(chart.year, "연주"), 표기(chart.month, "월주"),
            표기(chart.day, "일주"), 표기(chart.hour, "시주")]
    줄.append("원국: " + " / ".join(x for x in 기둥 if x))
    if chart.hour is None:
        줄.append("※ 출생시각 미상 — 시주를 제외한 3주 6글자 기준입니다. "
                  "시각에 따라 달라지는 이야기는 쓰지 마십시오.")
    줄.append("오행: " + ", ".join(f"{k} {v}" for k, v in chart.elements.counts.items())
              + f"  → 판정: {', '.join(chart.elements.verdict)}")
    if 보정메모:
        줄.append("시각 보정: " + " / ".join(보정메모))
    줄.append(f"기준시각: {basis}")
    줄.append(f"자시 규칙: {chart.midnight_rule}   엔진: {chart.engine_version}")
    줄.append("※ 이번 PoC 는 사주만 봅니다. 타로 카드는 뽑지 않았습니다. "
              "카드나 스프레드를 언급하지 마십시오.")
    줄.append("</계산결과>")
    return "\n".join(줄)


SYSTEM_SAJU = """당신은 사주 상담 리포트의 **초안**을 쓰는 보조자입니다.
계산은 이미 끝났습니다. <계산결과>는 확정된 사실이며, 절대 다시 계산하거나 바꾸지 마십시오.

[작성 규칙]
1. <계산결과>에 없는 사실을 만들어내지 마십시오. 특히 "이번 달"은 <계산결과>의
   세운·월운을 근거로 씁니다. 임의의 달을 가정하지 마십시오.
2. 간지·오행을 스스로 다시 계산하지 마십시오. 주어진 글자만 씁니다.
3. 타로 카드를 언급하지 마십시오. 이번에는 뽑지 않았습니다.
4. 단정적 예언을 하지 마십시오. "~하게 됩니다"가 아니라 "~한 흐름이 보입니다"로 씁니다.
5. 질병·사망·임신·이혼·수익 보장에 해당하는 표현을 쓰지 마십시오.
   건강 주제라도 병명을 말하지 말고, 생활 습관 수준에서만 조언합니다.
6. 직업을 규정하지 마십시오. 특정 종목·코인·금액을 말하지 마십시오.
7. 이것은 **사람이 검수할 초안**입니다. 확신에 찬 문장보다 근거가 드러나는 문장을 씁니다."""


def _user_prompt_saju(facts: str, name: str, topics: list[str]) -> str:
    금지 = safety.프롬프트_금지목록()
    안내 = ""
    for t in topics:
        if t in safety.필수문구:
            안내 += ("\n※ " + t + " 주제에는 이 문장을 반드시 넣으십시오: "
                     + safety.필수문구[t][0])
    return f"""{facts}

{금지}{안내}

<사용자데이터>
이름: {name}
상담주제: {", ".join(topics)}
</사용자데이터>

다음 세 가지를 써 주십시오. 손님이 읽을 글이므로 충분히 풀어서 씁니다.

1. 사주 풀이 — **5개 항목**, 각 항목 **2~3문장(100~140자)**.
   원국이 어떤 사람인지를 다룹니다. 이번 달 이야기가 아니라 타고난 것입니다.
     ① 타고난 기질  ② 잘 드러나는 힘  ③ 약한 곳
     ④ 사람을 대할 때  ⑤ 일과 돈을 대할 때

2. 이번 달 흐름 — **3개 항목**, 각 항목 **2~3문장(100~140자)**.
   왜 그런 흐름인지 근거(세운·월운의 글자)를 함께 적습니다.

3. 주제별 조언 — 주제마다 **3~4문장(150~220자)**.
   지금 상황 → 무엇을 하면 좋은지 → 무엇을 조심할지 순으로 씁니다.

**길이를 채우려고 없는 사실을 지어내지 마십시오.** 근거는 <계산결과> 안에만 있습니다."""


def _schema(topics: list[str]) -> dict:
    return {
        "name": "saju_report", "strict": True,
        "schema": {
            "type": "object", "additionalProperties": False,
            "required": ["saju_reading", "monthly_flow", "advice", "keywords"],
            "properties": {
                "saju_reading": {"type": "array", "items": {"type": "string"},
                                 "minItems": 5, "maxItems": 5},
                "monthly_flow": {"type": "array", "items": {"type": "string"},
                                 "minItems": 3, "maxItems": 3},
                "advice": {
                    "type": "array", "minItems": len(topics), "maxItems": len(topics),
                    "items": {
                        "type": "object", "additionalProperties": False,
                        "required": ["topic", "text"],
                        "properties": {
                            "topic": {"type": "string", "enum": topics},
                            "text": {"type": "string"},
                        }},
                },
                "keywords": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
            },
        },
    }


def 금칙어검사(rep: Report) -> str | None:
    """걸린 이유를 문자열로, 깨끗하면 None. 규칙은 poc/safety.py 에 있다."""
    걸림 = safety.전체검사(rep.saju_reading + rep.monthly_flow + list(rep.advice.values()))
    return None if 걸림 is None else f"{걸림[0]} — {걸림[1]}"


def 필수문구_보강(rep: Report, topics: list[str]) -> list[str]:
    """3층 — 건강·재물 주제에 안내 문구가 빠졌으면 **코드가 붙인다.**

    모델에게 부탁하면 잊는다. 반드시 들어가야 하는 문장은 코드가 넣는다.
    """
    빠짐 = safety.빠진_필수문구(
        rep.saju_reading + rep.monthly_flow + list(rep.advice.values()), topics)
    for 문구 in 빠짐:
        for t in topics:
            if t in safety.필수문구 and safety.필수문구[t][0] == 문구:
                rep.advice[t] = (rep.advice.get(t, "") + " " + 문구).strip()
    return 빠짐


class SajuReportGenerator:
    """스키마로 주제를 못 박고, 금칙어가 나오면 한 번 다시 만든다."""

    사용량: dict = {}      # 누적 토큰. 재시도분도 더해야 F-8 의 비용이 보인다
    호출수 = 0

    def __init__(self, model: str = "gpt-4o-mini-2024-07-18",
                 env_path: str | None = None):
        self.model = model
        self.사용량 = {"in": 0, "out": 0}
        키 = os.environ.get("OPENAI_API_KEY")
        if not 키 and env_path:
            for line in Path(env_path).read_text(encoding="utf-8").splitlines():
                if line.startswith("OPENAI_API_KEY="):
                    키 = line.split("=", 1)[1].strip().strip('"').strip("'")
        if not 키:
            raise SystemExit("OPENAI_API_KEY 가 없습니다. --env 로 주세요.")
        from openai import OpenAI
        self.client = OpenAI(api_key=키)

    def generate(self, facts: str, name: str, topics: list[str]) -> tuple[Report | None, str]:
        """(리포트, 메모) 를 돌려준다. 실패해도 예외를 던지지 않는다 —
        계산 결과는 이미 유효하므로 문장만 비워 두는 편이 낫다."""
        메모 = []
        for 회차 in (1, 2):
            try:
                res = self.client.chat.completions.create(
                    model=self.model, temperature=0.4,
                    messages=[{"role": "system", "content": SYSTEM_SAJU},
                              {"role": "user", "content": _user_prompt_saju(facts, name, topics)}],
                    response_format={"type": "json_schema", "json_schema": _schema(topics)},
                )
                u = getattr(res, "usage", None)
                if u:
                    self.사용량["in"] += u.prompt_tokens
                    self.사용량["out"] += u.completion_tokens
                self.호출수 += 1
                d = json.loads(res.choices[0].message.content)
            except Exception as e:                      # noqa: BLE001
                메모.append(f"{회차}회차 실패: {type(e).__name__}")
                continue
            rep = Report(
                saju_reading=d["saju_reading"],
                monthly_flow=d["monthly_flow"],
                advice={a["topic"]: a["text"] for a in d["advice"]},
                keywords=d.get("keywords", []),
                model=self.model,
            )
            보강 = 필수문구_보강(rep, topics)
            if 보강:
                메모.append(f"필수 안내 {len(보강)}개를 코드가 덧붙임")
            걸린 = 금칙어검사(rep)
            if 걸린 is None:
                if 메모:
                    메모.append(f"{회차}회차에 통과")
                return rep, " / ".join(메모)
            메모.append(f"{회차}회차 금칙어 '{걸린}' — 다시 생성")
        return None, " / ".join(메모) + " / 초안 생성 실패 (계산 결과는 유효)"


def 마크다운(rep: Report | None, chart: Chart, period: Period,
            이름: str, topics: list[str], facts: str, 메모: str,
            확인=None) -> str:
    """사람이 읽는 초안 한 장. 계산 결과는 리포트가 없어도 반드시 남긴다."""
    def 표기(p):
        return "—" if p is None else f"{p.ko} ({p.gan}{p.ji})"

    줄 = [f"# {이름} 님 사주 리포트 **초안**", "",
          "> ⚠️ 이 문서는 **AI 가 만든 초안**입니다. 상담사가 검수한 뒤 전달합니다.", ""]
    if 확인 is not None and 확인.필요:
        줄 += ["> ## 🔴 보내기 전에 확인하십시오", ">"]
        for x in 확인.이유:
            줄.append(f"> - {x}")
        for x in 확인.경고:
            줄.append(f"> - ⚠ **{x}**")
        줄 += [">", f"> **읽어 드릴 문장** — \"{확인.대본}\"", ""]
    줄 += [
          "## 계산 결과 (확정)", "",
          "| | 연주 | 월주 | 일주 | 시주 |", "|---|---|---|---|---|",
          f"| 원국 | {표기(chart.year)} | {표기(chart.month)} | "
          f"{표기(chart.day)} | {표기(chart.hour)} |", ""]
    if chart.hour is None:
        줄 += ["출생시각 미상이라 **시주를 뺀 3주 6글자** 기준입니다.", ""]
    줄 += [f"- 오행: " + ", ".join(f"{k} {v}" for k, v in chart.elements.counts.items()),
           f"- 판정: {', '.join(chart.elements.verdict)}",
           f"- 이번 달: {period.label}",
           f"- 자시 규칙: {chart.midnight_rule} · 엔진: {chart.engine_version}", ""]

    if rep is None:
        줄 += ["## 초안", "", f"**생성 실패** — {메모}", "",
               "계산 결과는 위와 같이 유효하므로, 해석만 손으로 쓰시면 됩니다.", ""]
    else:
        줄 += ["## 사주 풀이", ""]
        줄 += [f"{i}. {t}" for i, t in enumerate(rep.saju_reading, 1)]
        줄 += ["", "## 이번 달 흐름", ""]
        줄 += [f"{i}. {t}" for i, t in enumerate(rep.monthly_flow, 1)]
        줄 += ["", "## 주제별 조언", ""]
        for t in topics:
            줄 += [f"### {t}", "", rep.advice.get(t, "—"), ""]
        if rep.keywords:
            줄 += [f"**키워드** — {' · '.join(rep.keywords)}", ""]
        줄 += [f"> {rep.disclaimer}", ""]
        if 메모:
            줄 += [f"*생성 메모: {메모}*", ""]

    줄 += ["---", "", "<details><summary>모델에 넘긴 사실 블록</summary>", "",
           "```", facts, "```", "", "</details>", ""]
    return "\n".join(줄)
