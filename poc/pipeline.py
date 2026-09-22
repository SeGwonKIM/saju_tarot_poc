"""①~⑦ 전체를 잇는 진입점 (PRD_PoC.md 3.2 · 4.1)

    python -m poc.pipeline --text samples/상담_001.txt --env <경로>/.env
    python -m poc.pipeline --audio samples/상담_001.m4a --env <경로>/.env

단계마다 걸린 시간을 재서 run.json 에 남긴다. S3 의 분자가 이 값이다.
중간 산출을 전부 파일로 남기는 이유는 **어느 단계에서 틀렸는지 알기 위해서**다.

    out/001/transcript.txt   ② 텍스트
    out/001/input.json       ③ 구조화 입력
    out/001/chart.json       ⑤ 원국·오행·세운
    out/001/facts.txt        ⑥ 모델에 넘긴 사실 블록
    out/001/리포트_초안.md    ⑦ 결과
    out/001/run.json         단계별 소요 시간·모델·버전
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import calendar_service, korea_time, saju_service  # noqa: E402
from poc import confirm as C  # noqa: E402
from poc import mask as M  # noqa: E402
from poc import report as R  # noqa: E402
from poc.extract import LlmExtractor, RuleExtractor, 서비스범위  # noqa: E402

import yaml  # noqa: E402

_선언버전 = yaml.safe_load(
    (Path(__file__).resolve().parents[1] / "spec" / "fields.yaml")
    .read_text(encoding="utf-8"))["version"]

# 출생지 경도. 모르면 서울로 두고 그 사실을 반드시 표시한다.
경도표 = {"서울": 126.9780, "부산": 129.0756, "대구": 128.6014, "인천": 126.7052,
          "광주": 126.8526, "대전": 127.3845, "울산": 129.3114, "전주": 127.1480,
          "창원": 128.6811, "제주": 126.5312, "춘천": 127.7298, "포항": 129.3435}
서울 = 126.9780


class 시계:
    """단계별 소요 시간을 잰다. S3 의 분자."""

    def __init__(self):
        self.기록: dict[str, float] = {}

    def 재기(self, 이름: str):
        시계자신 = self

        class _재기:
            def __enter__(self):
                self.t = time.perf_counter()
                return self

            def __exit__(self, *a):
                시계자신.기록[이름] = round(time.perf_counter() - self.t, 3)
                return False
        return _재기()

    @property
    def 합계(self) -> float:
        return round(sum(self.기록.values()), 3)


def _whisper경로() -> str:
    """받아쓰기 도구의 위치. 남의 컴퓨터에서도 돌아가야 한다.

    이 저장소는 whisper 도구를 품고 있지 않다 (별도 도구를 재사용한다).
    환경변수 WHISPER_MCP 로 위치를 줄 수 있고, 없으면 기본 경로를 본다.
    """
    import os
    return os.environ.get("WHISPER_MCP", "C:/AI-Agent/whisper_mcp")


def 받아쓰기(audio: Path, t: 시계) -> tuple[str, dict]:
    """① 음성 → 텍스트. 이미 있는 도구를 쓴다 (새로 짜지 않는다).

    ⚠ 이 함수는 **한 번도 실행된 적이 없어서 깨져 있었다** (F-24).
      run() 은 dict 를 돌려주는데 문자열로 받고 있었다.
      "코드가 있다"와 "돌아간다"는 다르다 — 돌려 보기 전에는 모른다.
    """
    sys.path.insert(0, _whisper경로())
    with t.재기("① 받아쓰기"):
        from transcribe import run          # type: ignore[import-not-found]
        r = run(str(audio), language="ko")
    구간 = r.get("구간_평문")
    글 = " ".join(구간) if isinstance(구간, list) else str(구간 or "")
    return 글, r


def 사주계산(입력: dict, t: 시계) -> tuple[saju_service.Chart, saju_service.Period, list[str], str]:
    """③→⑤ 음양력 변환 · 진태양시 보정 · 원국 산출. 전부 결정론적 코드다."""
    메모: list[str] = []
    y, m, d = map(int, 입력["birth_date"].split("-"))

    with t.재기("③ 음양력 변환"):
        if 입력.get("calendar_type") == "lunar":
            윤달 = 입력.get("is_leap")
            if 윤달 is None:
                있나 = calendar_service.has_leap_month(y, m)
                if 있나:
                    raise SystemExit(
                        f"윤달 여부를 확인해야 합니다 — {y}년 {m}월에는 윤달이 있습니다. "
                        "평달인지 윤달인지 손님에게 되물어 주세요.")
                메모.append(f"음력 {m}월에 윤달 없음 → 평달로 확정")
                윤달 = False
            conv = calendar_service.lunar_to_solar(y, m, d, 윤달)
            y, m, d = map(int, conv.solar_date.split("-"))
            메모.append(f"음력{'(윤달)' if 윤달 else ''} → 양력 {y}-{m:02d}-{d:02d}")

    경도 = 경도표.get(입력.get("birth_place") or "", 서울)
    if 입력.get("birth_place") not in 경도표:
        메모.append(f"출생지 미상/미등록 — 서울 경도({서울})로 가정")

    with t.재기("④ 진태양시·서머타임 보정"):
        시각 = 입력.get("birth_time")
        if 시각:
            hh, mm = map(int, 시각.split(":"))
            c = korea_time.correct(datetime(y, m, d, hh, mm), 경도)
            if c.dst_applied:
                메모.append("서머타임 적용 — 시계에서 1시간 뺌")
            메모.append(f"시계 {hh:02d}:{mm:02d} → 진태양시 "
                        f"{c.true_solar:%Y-%m-%d %H:%M} ({c.true_solar_correction_min:+d}분)")
            if c.true_solar.day != d:
                메모.append("⚠ 보정으로 날짜가 넘어감 — 일주가 바뀜")
            진태양 = c.true_solar
        else:
            c = korea_time.correct(datetime(y, m, d, 12, 0), 경도)
            메모.append("출생시각 미상 — 시주 제외 (3주 6글자)")
            진태양 = None

    with t.재기("⑤ 원국·세운 산출"):
        chart = saju_service.build_chart(c.jieqi_reference, 진태양)
        period = saju_service.current_period(datetime.now(), c.jieqi_reference)

    기준 = (진태양 or c.jieqi_reference).strftime("%Y-%m-%d %H:%M")
    return chart, period, 메모, 기준


def main() -> int:
    ap = argparse.ArgumentParser(description="사주 리포트 초안 파이프라인")
    입력군 = ap.add_mutually_exclusive_group(required=True)
    입력군.add_argument("--audio", type=Path, help="상담 녹취 (.m4a/.wav)")
    입력군.add_argument("--text", type=Path, help="상담 텍스트 (.txt)")
    ap.add_argument("--env", type=str, help="OPENAI_API_KEY 가 든 .env 경로")
    ap.add_argument("--out", type=Path, default=Path("out"))
    ap.add_argument("--규칙", action="store_true", help="LLM 대신 규칙 기반으로 추출")
    ap.add_argument("--초안없이", action="store_true", help="⑦ 리포트 생성을 건너뜀")
    ap.add_argument("--마스킹없이", action="store_true",
                    help="개인정보 마스킹을 끄고 원문 그대로 보냄 (권장하지 않음)")
    ap.add_argument("--확인엄격", action="store_true",
                    help="확인이 필요하면 초안을 만들지 않고 멈춤 (상용에서 쓸 기본값)")
    a = ap.parse_args()

    원본 = a.audio or a.text
    방 = a.out / 원본.stem.replace("상담_", "")
    방.mkdir(parents=True, exist_ok=True)
    t = 시계()

    print(f"■ 입력: {원본}\n■ 출력: {방}\n")

    # ①② 텍스트 확보
    stt정보 = {}
    if a.audio:
        글, stt정보 = 받아쓰기(a.audio, t)
        print(f"① 받아쓰기 — {stt정보.get('모델')} · 음성 "
              f"{stt정보.get('영상길이_초')}초 → {t.기록['① 받아쓰기']:.0f}초 "
              f"(실시간의 {t.기록['① 받아쓰기']/float(stt정보.get('영상길이_초', 1)):.1f}배)")
    else:
        글 = a.text.read_text(encoding="utf-8")
        print("① 받아쓰기 — 건너뜀 (텍스트 입력)")
    (방 / "transcript.txt").write_text(글, encoding="utf-8")

    # 개인정보 마스킹 — 사주 계산에 필요 없는 값은 보내지 않는다
    가림 = M.가리기(글)
    보낼글 = 글 if a.마스킹없이 else 가림.글
    if a.마스킹없이:
        print("⚠ 마스킹 끔 — 원문이 그대로 나갑니다")
    elif 가림.지운것:
        print("   개인정보 가림: "
              + ", ".join(f"{k} {v}건" for k, v in 가림.지운것))

    # ② 항목 추출
    추출기 = RuleExtractor() if a.규칙 else LlmExtractor(env_path=a.env)
    with t.재기("② 항목 추출"):
        입력 = 추출기.extract(보낼글).to_dict()
    (방 / "input.json").write_text(
        json.dumps(입력, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"② 항목 추출 ({추출기.이름}) — {입력['name']} / {입력['birth_date']} / "
          f"{입력.get('birth_time') or '시각 미상'}")
    if 입력.get("missing"):
        print(f"   ⚠ 되물어야 할 항목: {', '.join(입력['missing'])}")

    if not 입력.get("birth_date"):
        print("\n생년월일이 없어 계산할 수 없습니다. 되물어 주세요.")
        return 1

    # 서비스 범위 (spec/fields.yaml service_range)
    # 1940년 이전 출생자는 상담 대상이 아니다. 엔진은 1880년도 값을 내주지만
    # 그 값을 검증한 적이 없으므로, 조용히 내보내는 대신 여기서 막는다.
    벗어남 = 서비스범위(int(입력["birth_date"][:4]))
    if 벗어남:
        print(f"\n■ 서비스 범위 밖 — {벗어남}")
        print("  계산하지 않습니다. 잘못 들은 것인지 먼저 확인해 주세요.")
        return 2

    # 확인 게이트 — 틀릴 수 있는 자리는 사람에게 넘긴다
    확인 = C.판정(입력, 글)      # 대조는 원문으로 한다 (가린 글은 숫자가 빠질 수 있음)
    print()
    print(확인.출력())
    if 확인.필요 and a.확인엄격:
        print()
        print("■ --확인엄격 이므로 여기서 멈춥니다. 손님께 확인한 뒤 다시 돌려 주세요.")
        return 3
    print()

    # ③~⑤ 계산
    chart, period, 메모, 기준 = 사주계산(입력, t)
    (방 / "chart.json").write_text(json.dumps({
        "pillars": {k: (None if v is None else asdict(v)) for k, v in
                    (("year", chart.year), ("month", chart.month),
                     ("day", chart.day), ("hour", chart.hour))},
        "elements": chart.elements.counts, "verdict": chart.elements.verdict,
        "period": period.label, "midnight_rule": chart.midnight_rule,
        "engine": chart.engine_version, "basis": 기준, "notes": 메모,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    for x in 메모:
        print(f"   · {x}")
    간지 = lambda p: "—" if p is None else f"{p.gan}{p.ji}"   # noqa: E731
    print(f"⑤ 원국 — {간지(chart.year)} {간지(chart.month)} "
          f"{간지(chart.day)} {간지(chart.hour)}   ({period.label})")

    # ⑥ 사실 블록
    topics = R.주제고르기(입력.get("question"))
    with t.재기("⑥ 사실 블록"):
        facts = R.build_facts_saju(chart, period, 기준, 메모)
    (방 / "facts.txt").write_text(facts, encoding="utf-8")
    print(f"⑥ 주제 — {', '.join(topics)}")

    # ⑦ 초안
    rep, 생성메모, gen = None, "건너뜀 (--초안없이)", None
    if not a.초안없이:
        gen = R.SajuReportGenerator(env_path=a.env)
        보낼이름, 이름표 = (입력["name"] or "손님", {}) if a.마스킹없이             else M.이름가리기(입력.get("name"))
        with t.재기("⑦ 초안 생성"):
            rep, 생성메모 = gen.generate(facts, 보낼이름, topics)
        if rep is not None and 이름표:                 # 받아온 문장에서 실명을 되돌린다
            rep.saju_reading[:] = [M.되돌리기(x, 이름표) for x in rep.saju_reading]
            rep.monthly_flow[:] = [M.되돌리기(x, 이름표) for x in rep.monthly_flow]
            for k in list(rep.advice):
                rep.advice[k] = M.되돌리기(rep.advice[k], 이름표)
        print(f"⑦ 초안 — {'생성됨' if rep else '실패'}"
              + (f" ({생성메모})" if 생성메모 else ""))

    (방 / "리포트_초안.md").write_text(
        R.마크다운(rep, chart, period, 입력["name"] or "손님", topics, facts,
                  생성메모, 확인),
        encoding="utf-8")

    # 검토의견 M-4 — 조건(모델·seed·프롬프트 해시)이 없으면 나중에 비교가 불가능하다.
    import hashlib
    from poc import extract as EX
    프롬프트해시 = {
        "추출": hashlib.sha256(EX._SYSTEM.encode()).hexdigest()[:12],
        "리포트": hashlib.sha256(R.SYSTEM_SAJU.encode()).hexdigest()[:12],
    }
    사용량 = {"in": 0, "out": 0}
    for 것 in (추출기, gen if not a.초안없이 else None):
        for k in ("in", "out"):
            사용량[k] += (getattr(것, "사용량", None) or {}).get(k, 0)

    (방 / "run.json").write_text(json.dumps({
        "입력": str(원본), "추출기": 추출기.이름,
        "단계별_초": t.기록, "합계_초": t.합계,
        "초안": bool(rep), "생성메모": 생성메모,
        "엔진": chart.engine_version,
        "조건": {
            "모델": getattr(추출기, "model", "규칙 기반"),
            "temperature": 0 if not a.규칙 else None,
            "seed": 20260922 if not a.규칙 else None,
            "system_fingerprint": getattr(추출기, "지문", ""),
            "프롬프트해시": 프롬프트해시,
            "선언버전": _선언버전,
        },
        "토큰": 사용량,
        "재생성": getattr(gen, "호출수", 0) - 1 if not a.초안없이 else 0,
        "확인필요": 확인.필요, "확인이유": 확인.이유, "확인경고": 확인.경고,
        "마스킹": {"적용": not a.마스킹없이, "지운것": dict(가림.지운것),
                   "이름가림": not a.마스킹없이},
        "stt_실행": bool(a.audio),
        "stt": {k: stt정보.get(k) for k in
                ("모델", "영상길이_초", "걸린시간_초", "실시간대비배속",
                 "연산장치", "감지언어")} if stt정보 else None,
        "실행시각": datetime.now().isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'─' * 54}")
    for 이름, 초 in t.기록.items():
        print(f"  {이름:<22}{초:>8.2f}초")
    print(f"{'─' * 54}\n  {'합계':<22}{t.합계:>8.2f}초\n")
    print(f"리포트: {방 / '리포트_초안.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
