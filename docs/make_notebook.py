"""PoC 노트북을 만들고 **실제로 실행해서** 결과를 박아 넣는다.

왜 만드나
  과제는 형태가 자유지만(노트북·CLI·웹앱), 노트북은 **읽으면서 따라갈 수 있다**는
  장점이 있다. 심사자가 클론하지 않고 GitHub 에서 그냥 읽어도 결과가 보인다.

무엇을 담나
  ①~⑦ 각 단계를 셀 하나씩 나눠, 무엇이 들어가고 무엇이 나오는지 보여준다.
  LLM 호출은 **한 건만** 한다 — 나머지는 out/ 에 이미 있는 실행 결과를 읽는다.

  실행해서 출력을 박아 넣으므로 **지어낸 결과가 아니다.**

쓰는 법:
    python docs/make_notebook.py            # 만들고 실행까지
    python docs/make_notebook.py --안돌림    # 셀만 만들고 실행은 생략
"""
from __future__ import annotations

import sys
from pathlib import Path

import nbformat as nbf

뿌리 = Path(__file__).resolve().parents[1]
나올것 = 뿌리 / "PoC_둘러보기.ipynb"


def md(t: str):
    return nbf.v4.new_markdown_cell(t.strip("\n"))


def code(t: str):
    return nbf.v4.new_code_cell(t.strip("\n"))


def 셀들():
    c = []
    a = c.append

    a(md("""
# 사주 상담 접수·리포트 초안 자동화 — PoC 둘러보기

> **Main Quest 2** 「내 도메인에서 AI로 개선 지점 찾아서 PoC 만들기」
> 저장소 https://github.com/SeGwonKIM/saju_tarot_poc

이 노트북은 **파이프라인을 한 단계씩 뜯어 보는 용도**입니다.
실제 실행은 명령 한 줄이면 됩니다.

```bash
python -m poc.pipeline --text samples/상담_007.txt --env 경로/.env
```

## 설계 원칙 한 줄

> **계산은 코드가, 문장은 AI가.**

| 단계 | 누가 | 왜 |
|---|---|---|
| ① 받아쓰기 | **AI** (Whisper) | 말소리 → 글자는 규칙으로 못 함 |
| ② 항목 추출 | **AI** (LLM) | 사람 말투가 무한히 다양함 |
| ③④⑤⑥ 음양력·보정·원국·사실블록 | **코드** | **답이 정해져 있음.** AI 에 맡기면 지어냄 |
| ⑦ 리포트 문장 | **AI** (LLM) | 정답이 없는 글쓰기 |

③~⑥을 AI 에 안 맡긴 것이 가장 중요한 선택이었고, **실측으로 옳았음이 확인됐습니다** —
아래 5장에서 보여드립니다.
"""))

    a(md("""
---
## 0. 준비
"""))
    a(code("""
import json, sys
from pathlib import Path

# 노트북을 어디서 열든 저장소 뿌리를 찾는다 — poc/ 와 samples/ 가 같이 있는 곳.
def 저장소뿌리():
    후보 = [Path.cwd(), *Path.cwd().parents]
    for p in 후보:
        if (p/"poc").is_dir() and (p/"samples").is_dir():
            return p
        if (p/"saju_tarot_poc"/"poc").is_dir():
            return p/"saju_tarot_poc"
    raise SystemExit("저장소를 못 찾았습니다. saju_tarot_poc 안에서 열어 주세요.")

뿌리 = 저장소뿌리()
sys.path.insert(0, str(뿌리))

print("저장소 :", 뿌리)
print("파이썬 :", sys.version.split()[0])
"""))

    a(md("""
---
## 1. 입력 — 상담 녹취

가장 어려운 표본을 고릅니다. **음력 · 윤달 · 날짜를 한글로** 말하는 건입니다.
"""))
    a(code("""
원문 = (뿌리 / "samples" / "상담_007.txt").read_text(encoding="utf-8")
print(원문)
"""))

    a(md("""
정답은 이렇습니다. `초여드레` = **8일**, 윤달이므로 `is_leap = True`.
"""))
    a(code("""
정답 = json.loads((뿌리/"samples"/"정답키_숨김.json").read_text(encoding="utf-8"))["007"]
for k in ("name","gender","birth_date","calendar_type","is_leap","birth_time","birth_place"):
    print(f"  {k:<15}{정답[k]!r}")
print(f"\\n  난이도: {정답['난이도']}")
"""))

    a(md("""
---
## 2. 개인정보 마스킹 — 보내기 전에 지운다

사주 계산에 **필요 없는 값**은 LLM 으로 보내지 않습니다.
생년월일·시각은 **건드리면 안 되므로** 무늬를 좁게 잡았습니다.
"""))
    a(code("""
from poc import mask as M

시험 = '''의뢰인: 010-1234-5678이요. 이메일은 hong@example.com 입니다.
의뢰인: 주민번호는 901231-1234567이에요. 테헤란로 152, 301호 삽니다.
의뢰인: 음력 이월 초여드레인데요, 윤달이라고 하셨어요. 1947년이요.'''

r = M.가리기(시험)
print(r.글)
print("\\n지운 것:", r.지운것)
print("\\n생년월일 표현이 살아 있나:", "음력 이월 초여드레" in r.글, "/", "1947년" in r.글)
"""))

    a(md("""
넓게 잡으면 큰일 납니다. 처음 쓴 계좌번호 무늬 `\\d{2,6}-\\d{2,6}-\\d{2,7}` 는
**`1990-12-31` 같은 날짜도 삼킵니다.** 그래서 계좌번호는 '계좌·통장' 이라는 말이
앞에 있을 때만 지웁니다.
"""))
    a(code("""
for 글 in ["1990-12-31 이요", "계좌는 110-234-567890 입니다", "밤 열한시 사십분"]:
    r = M.가리기(글)
    print(f"  {'그대로' if r.글==글 else '가림  '}  {글}  →  {r.글}")
"""))

    a(md("""
---
## 3. ② 항목 추출 — 기준선을 옆에 둔다

LLM 만 재면 "좋다/나쁘다"를 말할 수 없습니다.
**정규식만 쓰는 기준선**을 같은 자로 잽니다.
"""))
    a(code("""
from poc.extract import RuleExtractor

규칙 = RuleExtractor().extract(원문).to_dict()
for k in ("name","gender","birth_date","calendar_type","is_leap","birth_time","birth_place"):
    맞음 = "O" if 규칙[k] == 정답[k] else "X"
    print(f"  {맞음}  {k:<15}{규칙[k]!r}")
print(f"\\n  되물어야 할 항목: {규칙['missing']}")
"""))

    a(md("""
**이름을 `윤달` 로 잡았습니다.** `윤달이라고 하셨어요` 의 `~이라고` 가 이름 무늬에 걸린 것입니다.
날짜는 아예 못 읽었습니다 — 연도와 월일을 **다른 문장에서** 말했기 때문입니다.

정규식의 한계가 그대로 드러납니다. 이제 LLM 결과를 보겠습니다.
이미 돌려 둔 것을 읽습니다 (매번 호출하면 돈이 듭니다).
"""))
    a(code("""
llm = json.loads((뿌리/"out"/"007"/"input.json").read_text(encoding="utf-8"))
print(f"{'항목':<16}{'규칙 기반':<14}{'LLM':<14}정답")
print("-"*62)
for k in ("name","gender","birth_date","calendar_type","is_leap","birth_time","birth_place"):
    print(f"{k:<16}{str(규칙[k]):<14}{str(llm[k]):<14}{정답[k]}")
"""))

    a(md("""
LLM 이 대부분 맞혔습니다. **딱 한 자리, 날짜를 틀렸습니다** — `초여드레`(8일)를 18일로.

이 오답이 지금까지 **세 번** 나왔고 **전부 음력 날짜**였습니다.
프롬프트에 "달력 변환을 하지 마라"를 넣어 좋아졌지만 **없어지지 않았습니다.**
"""))

    a(md("""
---
## 4. 확인 게이트 — 틀릴 수 있는 자리를 사람에게

모델을 더 조여도 안 없어지므로, **틀릴 수 있는 자리를 골라 되묻습니다.**
오프라인 상담에서 이미 하는 일입니다.
"""))
    a(code("""
from poc import confirm as C

확인 = C.판정(llm, 원문)
print(확인.출력())
"""))

    a(md("""
**숫자 대조가 오답을 잡았습니다.** 손님이 말한 날짜는 `8` 인데 LLM 이 `18` 을 냈습니다.

⚠ 다만 이건 **정확도가 좋아진 게 아닙니다.** 모델은 여전히 18일이라고 합니다.
틀린 것을 **틀렸다고 알려 주게** 됐을 뿐입니다. 그래서 이름도 `회귀 가드` 입니다.
"""))
    a(code("""
# 표본 11건 전수 — 정답을 넣으면 조용하고, 하루 어긋나면 잡는가
정답전체 = {}
for f in ("정답키.json","정답키_숨김.json","정답키_숨김2.json"):
    정답전체.update(json.loads((뿌리/"samples"/f).read_text(encoding="utf-8")))

오검 = 탐지 = 0
for 번호, a_ in 정답전체.items():
    글 = (뿌리/"samples"/f"상담_{번호}.txt").read_text(encoding="utf-8")
    좋은 = {**a_, "missing": [], "uncertain": []}
    y, m, d = a_["birth_date"].split("-")
    나쁜 = {**좋은, "birth_date": f"{y}-{m}-{int(d)%28+1:02d}"}
    오검 += bool(C.판정(좋은, 글).경고)
    탐지 += bool(C.판정(나쁜, 글).경고)
print(f"정답에 잘못 경고한 건수  {오검}/11")
print(f"틀린 값을 잡은 건수      {탐지}/11")
"""))

    a(md("""
---
## 5. ③④⑤ 계산 — **AI 에 맡기지 않는 구간**

여기가 이 PoC 의 핵심 주장입니다.
"""))
    a(code("""
from engine import calendar_service, korea_time, saju_service
from datetime import datetime

# 음력 윤2월 8일 → 양력
conv = calendar_service.lunar_to_solar(1947, 2, 8, True)
print("음력 윤2월 8일 (1947) → 양력", conv.solar_date)

y, m, d = map(int, conv.solar_date.split("-"))
c = korea_time.correct(datetime(y, m, d, 10, 0), 127.1480)   # 전주
print(f"시계 10:00 → 진태양시 {c.true_solar:%Y-%m-%d %H:%M} ({c.true_solar_correction_min:+d}분)")

chart = saju_service.build_chart(c.jieqi_reference, c.true_solar)
간지 = lambda p: "—" if p is None else f"{p.ko}({p.gan}{p.ji})"
print(f"\\n원국  {간지(chart.year)} {간지(chart.month)} {간지(chart.day)} {간지(chart.hour)}")
print(f"오행  {chart.elements.counts}  →  {chart.elements.verdict}")
"""))

    a(md("""
### LLM 은 이 계산을 **세 번 다 틀렸습니다**

| 표본 | 말한 것 | LLM | 정답 |
|---|---|---|---|
| 002 | 음력 **7월** 20일 | `1988-08-20` | `1988-07-20` |
| 007 | 음력 **윤2월 초여드레** | `1947-02-18` | `1947-02-08` |
| 010 | 음력 **윤유월 초닷새** | `1960-07-05` | `1960-06-05` |

002 의 `08-20` 은 **말한 날짜도 아니고 올바른 변환값(`08-31`)도 아닙니다.**
007 은 `is_leap: true` 를 맞게 넣고도 월을 한 칸 올렸습니다 — **윤달을 두 번 센 것**입니다.

반면 코드 구간은 **8표본 × 20회 전부 같은 값**을 냈습니다.
"""))
    a(code("""
# 엔진은 없는 윤달을 거부한다 — 틀린 원국이 조용히 나가지 않는다
for 월 in (2, 3):
    try:
        print(f"음력 윤{월}월 8일 (1947) → {calendar_service.lunar_to_solar(1947, 월, 8, True).solar_date}")
    except Exception as e:
        print(f"음력 윤{월}월 8일 (1947) → 거부됨: {e}")
"""))

    a(md("""
---
## 6. ⑦ 리포트 초안 — 그리고 안전 계층

문장은 AI 가 씁니다. 다만 **그대로 내보내지 않습니다.**
"""))
    a(code("""
from poc import safety

시험문장 = [
    ("암시하는 흐름입니다", "통과해야"),
    ("위암이 걱정됩니다", "막아야"),
    ("당신은 40세에 큰 병이 옵니다", "막아야"),
    ("몸이 무거워지기 쉬우니 휴식을 챙기세요", "통과해야"),
    ("이혼하게 됩니다", "막아야"),
    ("이혼을 생각하시는 분이 많은 시기입니다", "통과해야"),
    ("반드시 성공하게 됩니다", "막아야"),
    ("성과가 나기 좋은 흐름입니다", "통과해야"),
]
for 글, 기대 in 시험문장:
    r = safety.문장검사(글)
    print(f"  {'차단 '+r[0] if r else '통과':<26}{글}")
"""))

    a(md("""
`암시` 는 통과하고 `위암이` 는 막힙니다 — 한 음절 낱말은 **조사 경계**를 봅니다.

`당신은 40세에 큰 병이 옵니다` 에는 **금칙어가 하나도 없습니다.**
위험한 것은 낱말이 아니라 **문장의 말투**라서, 2층에서 문장 구조를 봅니다.
"""))
    a(code("""
보고 = json.loads((뿌리/"out"/"007"/"report.json").read_text(encoding="utf-8"))
print(f"■ {보고['이름']} 님 · 주제 {보고['주제']}\\n")
print("[사주 풀이]")
for i, t in enumerate(보고["사주풀이"][:2], 1):
    print(f"  {i}. {t}")
print("\\n[조언]")
for k, v in 보고["조언"].items():
    print(f"  {k}: {v[:110]}…")
"""))

    a(md("""
건강 주제에 **의료기관 안내가 코드로 붙습니다.** 모델에게 부탁하면 잊기 때문입니다.
"""))

    a(md("""
---
## 7. 검증 — 검사가 실패할 수 있는지 검사

이 PoC 에서 가장 많이 배운 부분입니다.

**"성립하지 않는 시험"을 두 번 발견했습니다.**

| | 무엇 |
|---|---|
| F-14 | 지어냄 검사의 대상이 **0개**였는데 "위반 0건 → 통과" 로 셌다 |
| F-15 | 검사 조건이 리터럴 `True` 여서 **절대 실패할 수 없었다** |

둘 다 "검사를 돌렸더니 통과했다"는 모습을 완벽히 갖춥니다. **눈으로는 안 잡힙니다.**
그래서 일부러 틀린 입력을 넣어 **실패하는지** 봅니다.
"""))
    a(code("""
import subprocess, os
r = subprocess.run([sys.executable, "-m", "verify.selftest_negative"],
                   cwd=뿌리, capture_output=True, text=True, encoding="utf-8",
                   env={**os.environ, "PYTHONIOENCODING": "utf-8"})
print("\\n".join(r.stdout.splitlines()[-10:]))
"""))

    a(code("""
r = subprocess.run([sys.executable, "-m", "verify.s2_manseryeok"],
                   cwd=뿌리, capture_output=True, text=True, encoding="utf-8",
                   env={**os.environ, "PYTHONIOENCODING": "utf-8"})
print("\\n".join(r.stdout.splitlines()[-16:]))
"""))

    a(md("""
---
## 8. 지금 성적표

| 기준 | 상태 | 값 |
|---|---|---|
| **S1** 항목 추출 (텍스트) | 측정·달성 | 검증셋2 LLM **20/21** · 기준선 16/21 |
| **S1** 항목 추출 (음성) | 측정·달성 | 13/14 (⚠ 합성 음성) |
| **S2** 만세력 | 측정·달성 | **17/17** · 경계 커버리지 10/10 |
| **S3** 처리 시간 | **미측정** | 분모(수작업)가 가정값 |
| **S4a** 코드 결정성 | 측정·달성 | **100%** |
| **S4b** 추출 재현성 | **측정·미달** | 95.2% — 사람 확인 화면이 필요한 근거 |
| **S5** 초안 품질 | **미측정** | 평가자 2명 필요 |
| **S6** 원가 | 측정·참고 | 건당 약 0.9~1.1원 (⚠ 단가 미확인) |

### 정직하게 남겨 둔 것

- 표본 **11건이 전부 가상 대화**입니다. 실제 녹취는 **0건**입니다.
- `20/21` 은 **표본 3건 × 7항목**입니다. 한 건이 어긋나면 **33%p** 움직입니다.
- 아직 **아무도 안 본 잠금 시험셋이 없어서**, 이 숫자는 전부 "검증셋 성적"입니다.

한때 **"100%"** 라고 발표했다가, 채점 항목이 좁아서 나온 값임이 외부 검토로 드러나
**95% 로 정정**했습니다. 그 경위는 `개선효과검증결과.md` 의 「기준 변경 대장」에 있습니다.

---

## 더 볼 것

| 문서 | 무엇 |
|---|---|
| `문제정의서.md` | 왜 만드는가 |
| `모델선정근거.md` | **왜 이 모델을 골랐는가** · 안 쓴 모델과 이유 |
| `개선효과검증결과.md` | 측정값 · **실패 사례 27건** · 기준 변경 대장 |
| `docs/상용전환_설계.md` | PoC 다음에 무엇이 필요한가 |
| `out/검수함.html` | 관리자 검수 화면 (파일 하나, 서버 없음) |
"""))
    return c


def main() -> int:
    nb = nbf.v4.new_notebook(cells=셀들())
    nb.metadata = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": sys.version.split()[0]},
    }

    if "--안돌림" not in sys.argv:
        import os

        from nbclient import NotebookClient
        print("노트북을 실행합니다 — 출력이 박힙니다 …")
        os.chdir(뿌리)          # 커널이 이 폴더를 물려받는다
        NotebookClient(nb, timeout=600, kernel_name="python3",
                       resources={"metadata": {"path": str(뿌리)}}).execute()
        print("실행 끝")

    nbf.write(nb, 나올것)
    코드셀 = sum(1 for c in nb.cells if c.cell_type == "code")
    찬셀 = sum(1 for c in nb.cells if c.cell_type == "code" and c.get("outputs"))
    print(f"\n{나올것.name} — 셀 {len(nb.cells)}개 (코드 {코드셀}, 출력이 박힌 것 {찬셀})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
