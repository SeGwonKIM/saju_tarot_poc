"""S1(음성 입력 조건) — STT 를 거치면 얼마나 나빠지는가

왜 이걸 재나
  지금까지의 S1 성적은 전부 **깨끗한 텍스트**를 넣은 것이다 (검토의견 §3-1).
  파이프라인 그림에는 ① 받아쓰기가 있는데 **실행 0회**였다 — 유형 B 다.

  STT 오류는 항목 추출로 **전파**된다. 특히 이 도메인에서 깨지는 곳은 숫자다.
  "1995년 3월 12일" 이 "1995년 3월 십이일" 이 되거나 아예 안 들리면
  원국이 통째로 달라진다. 전체 WER 이 좋아도 숫자 하나면 끝이다.

⚠ 표본의 한계 — 반드시 같이 읽어야 한다
  여기 쓰는 음성은 **윈도우 TTS 가 또박또박 읽은 합성 음성**이다. 실제 녹취가 아니다.
  실제 통화에는 잡음·말 겹침·사투리·끊김·화자 혼선이 있고 **그건 여기서 못 잰다.**
  그러므로 이 점수는 **실제보다 좋게 나온 상한선**이다.

쓰는 법:
    powershell -ExecutionPolicy Bypass -File samples/make_audio.ps1 -번호 001
    python -m verify.s1_stt --env=<경로>/.env
"""
from __future__ import annotations

import difflib
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# 받아쓰기 도구 위치 — 남의 컴퓨터에서도 돌아가야 한다.
# 이 저장소는 whisper 도구를 품고 있지 않다 (별도 도구를 재사용한다).
sys.path.insert(0, os.environ.get("WHISPER_MCP", "C:/AI-Agent/whisper_mcp"))
from poc.extract import LlmExtractor, RuleExtractor  # noqa: E402
from verify.s1_extract import 맞았나, 채점필드  # noqa: E402

뿌리 = Path(__file__).resolve().parents[1]


def 받아쓰기(wav: Path, 모델: str = "turbo") -> tuple[str, dict]:
    """① 음성 → 텍스트. run() 은 **dict** 를 돌려준다 — 문자열이 아니다."""
    from transcribe import run                    # type: ignore[import-not-found]
    r = run(str(wav), language="ko", model=모델)
    글 = " ".join(r["구간_평문"]) if isinstance(r.get("구간_평문"), list) \
        else str(r.get("구간_평문", ""))
    return 글, r


def 숫자만(t: str) -> list[str]:
    return re.findall(r"\d+", t)


def main() -> int:
    env = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--env=")), None)
    정답 = {}
    for f in ("정답키.json", "정답키_숨김.json", "정답키_숨김2.json"):
        p = 뿌리 / "samples" / f
        if p.exists():
            정답.update(json.loads(p.read_text(encoding="utf-8")))

    wavs = sorted((뿌리 / "samples").glob("상담_*.wav"))
    from verify.guard import 표본확인
    표본확인("정답키", 정답, 최소=1)
    표본확인("음성 표본(wav)", wavs, 최소=1)

    print("=" * 78)
    print(f"S1(음성 입력 조건) — 표본 {len(wavs)}건")
    print("⚠ 합성 음성입니다. 실제 녹취가 아니므로 이 점수는 **상한선**입니다.")
    print("=" * 78)

    추출기 = LlmExtractor(env_path=env) if env else RuleExtractor()
    모음 = []
    for wav in wavs:
        번호 = wav.stem.replace("상담_", "")
        원문 = (뿌리 / "samples" / f"상담_{번호}.txt").read_text(encoding="utf-8")
        의뢰인말 = " ".join(l.split(":", 1)[1].strip() for l in 원문.splitlines()
                            if ":" in l)

        t0 = time.perf_counter()
        들은글, 정보 = 받아쓰기(wav)
        stt초 = time.perf_counter() - t0

        # 글자 단위 유사도 — WER 대신 (형태소 분석기 없이 WER 은 부정확하다)
        닮음 = difflib.SequenceMatcher(None, 의뢰인말.replace(" ", ""),
                                       들은글.replace(" ", "")).ratio()
        원숫자, 들은숫자 = 숫자만(원문), 숫자만(들은글)

        점수 = {}
        for 이름, 글 in (("텍스트", 원문), ("음성", 들은글)):
            r = 추출기.extract(글).to_dict()
            점수[이름] = (sum(맞았나(f, r[f], 정답[번호]) for f in 채점필드), r)

        모음.append((번호, 닮음, 원숫자, 들은숫자, 점수, stt초,
                     float(정보.get("영상길이_초", 0))))

        print(f"\n[{번호}] {정답[번호]['name']}  ·  받아쓰기 {stt초:.0f}초 "
              f"(음성 {정보.get('영상길이_초')}초, 배속 {정보.get('실시간대비배속')})")
        print(f"  글자 유사도 {닮음*100:.1f}%")
        print(f"  원문의 숫자 {원숫자}")
        print(f"  들은 숫자   {들은숫자}"
              + ("   ← 숫자가 사라짐 ⚠" if len(들은숫자) < len(원숫자) else ""))
        print(f"  추출 점수   텍스트 {점수['텍스트'][0]}/{len(채점필드)}  →  "
              f"음성 {점수['음성'][0]}/{len(채점필드)}")
        for f in 채점필드:
            ㄱ, ㄴ = 점수["텍스트"][1][f], 점수["음성"][1][f]
            if ㄱ != ㄴ:
                print(f"     {f:<14}{ㄱ!r}  →  {ㄴ!r}")

    print(f"\n{'=' * 78}\n■ 정리\n{'=' * 78}")
    만점 = len(모음) * len(채점필드)
    ㄱ합 = sum(x[4]["텍스트"][0] for x in 모음)
    ㄴ합 = sum(x[4]["음성"][0] for x in 모음)
    print(f"{'조건':<16}{'점수':>10}{'비율':>10}")
    print("-" * 78)
    print(f"{'텍스트 입력':<16}{ㄱ합:>6}/{만점}{100*ㄱ합/만점:>9.1f}%")
    print(f"{'음성 입력(STT)':<16}{ㄴ합:>6}/{만점}{100*ㄴ합/만점:>9.1f}%")
    print("-" * 78)
    print(f"낙폭 {100*(ㄱ합-ㄴ합)/만점:.1f}%p   ·   표본 {len(모음)}건 "
          f"(한 건이 {100/len(모음):.0f}%p)")

    총음성 = sum(x[6] for x in 모음)
    총stt = sum(x[5] for x in 모음)
    print(f"\n받아쓰기 시간: 음성 {총음성:.0f}초 → 처리 {총stt:.0f}초 "
          f"(실시간의 {총stt/총음성:.1f}배, CPU)")
    print("  ⚠ S3 에 이 시간이 **빠져 있었습니다.** 실제 상담은 10~30분이므로")
    print(f"    그 배속이면 받아쓰기만 {10*총stt/총음성:.0f}~{30*총stt/총음성:.0f}분이 걸립니다.")

    print(f"\n{'=' * 78}\n■ 이 측정이 답하지 못하는 것\n{'=' * 78}")
    for x in [
        "합성 음성입니다. 잡음·말 겹침·사투리·끊김이 없습니다 — 실제는 더 나쁩니다.",
        "화자 분리를 안 했습니다. 상담자 말이 의뢰인 정보로 섞일 위험이 큽니다.",
        f"표본 {len(모음)}건입니다.",
        "CPU 로 돌렸습니다. GPU 면 훨씬 빠릅니다.",
    ]:
        print(f"  · {x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
