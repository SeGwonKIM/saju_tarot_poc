"""잠금 시험셋 봉인 — "결과를 본 뒤에 고치지 않았다"를 증명한다

왜 필요한가
  지금 숫자는 전부 **검증셋 성적**이다 (F-23).

    학습셋(공개 5건)   규칙·프롬프트를 고치는 데 썼다 → 점수 무효
    검증셋1(3건)       고치는 방향을 정하는 데 썼다 → 소진
    검증셋2(3건)       고친 뒤 재측정했다 → 이미 한 번 봤다
    시험셋             **없다**

  마지막 주장("우리 추출기는 N% 다")의 근거가 되려면, **아무도 안 본 문제**를
  **채점기를 고정한 채 한 번만** 풀어야 한다.

이 파일이 하는 일
  봉인 — 개봉 **전에** 채점기·프롬프트·추출기의 해시를 찍어 둔다
  개봉 — 채점 직전에 해시를 다시 재서 **하나라도 다르면 거부**한다

  그러면 "문제를 보고 나서 프롬프트를 고쳤다"가 **불가능**해진다.
  고치면 해시가 달라지고, 달라지면 그 회차는 무효가 된다.

쓰는 법
    python -m verify.seal 봉인        # 시험셋을 만들기 전에 한 번
    python -m verify.seal 확인        # 채점 직전에
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

뿌리 = Path(__file__).resolve().parents[1]
봉인파일 = 뿌리 / "samples" / "시험셋_봉인.json"

# 이 파일들이 바뀌면 그 회차는 무효다.
대상 = [
    "poc/extract.py",          # 추출기 + 프롬프트
    "poc/confirm.py",          # 확인 게이트
    "poc/safety.py",           # 안전 계층
    "verify/s1_extract.py",    # 채점기
    "spec/fields.yaml",        # 채점 항목 선언
]


def 해시들() -> dict[str, str]:
    r = {}
    for 이름 in 대상:
        p = 뿌리 / 이름
        r[이름] = (hashlib.sha256(p.read_bytes()).hexdigest()[:16]
                   if p.exists() else "없음")
    return r


def _커밋() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=뿌리,
                              capture_output=True, text=True, check=True
                              ).stdout.strip()[:12]
    except Exception:                                  # noqa: BLE001
        return "git 없음"


def 봉인() -> int:
    if 봉인파일.exists():
        옛 = json.loads(봉인파일.read_text(encoding="utf-8"))
        print(f"■ 이미 봉인돼 있습니다 ({옛['봉인시각']}).")
        print("  다시 봉인하려면 기존 파일을 지우십시오 — 다만 그러면")
        print("  '결과를 본 뒤 고치지 않았다'는 증거가 사라집니다.")
        return 1
    기록 = {
        "봉인시각": datetime.now().isoformat(timespec="seconds"),
        "커밋": _커밋(),
        "해시": 해시들(),
        "약속": [
            "이 봉인 뒤에 만든 시험셋은 딱 한 번만 채점한다.",
            "채점 결과를 보고 위 파일을 고치면 그 회차는 무효다.",
            "고쳐야 한다면 새 시험셋을 다시 만들어야 한다.",
        ],
    }
    봉인파일.write_text(json.dumps(기록, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    print("■ 봉인했습니다.")
    for k, v in 기록["해시"].items():
        print(f"  {v}  {k}")
    print(f"\n  커밋 {기록['커밋']} · {봉인파일.name}")
    print("\n  이제 시험셋을 만드십시오. samples/시험셋_안내.md 를 보세요.")
    return 0


def 확인() -> int:
    if not 봉인파일.exists():
        print("■ 봉인 기록이 없습니다. `python -m verify.seal 봉인` 을 먼저 하십시오.")
        print("  봉인 없이 잰 점수는 '시험셋 성적'이 아니라 '검증셋 성적'입니다.")
        return 1
    옛 = json.loads(봉인파일.read_text(encoding="utf-8"))
    지금 = 해시들()
    바뀜 = [k for k in 대상 if 옛["해시"].get(k) != 지금.get(k)]

    print(f"봉인 시각 {옛['봉인시각']} · 커밋 {옛['커밋']}")
    for k in 대상:
        같음 = 옛["해시"].get(k) == 지금.get(k)
        print(f"  {'동일' if 같음 else '바뀜 ⚠'}  {k}"
              + ("" if 같음 else f"   {옛['해시'].get(k)} → {지금.get(k)}"))

    if 바뀜:
        print(f"\n■ {len(바뀜)}개 파일이 봉인 뒤에 바뀌었습니다.")
        print("  이 상태로 잰 점수는 **시험셋 성적이 아닙니다.**")
        print("  바꾼 것이 정당하다면(버그 수정 등) 새 시험셋을 다시 만들어야 합니다.")
        return 2

    print("\n■ 봉인 그대로입니다. 이 회차의 점수는 시험셋 성적으로 인정됩니다.")
    print("  ※ 채점은 **한 번만** 하십시오. 두 번째부터는 검증셋이 됩니다.")
    return 0


def main() -> int:
    명령 = sys.argv[1] if len(sys.argv) > 1 else ""
    if 명령 == "봉인":
        return 봉인()
    if 명령 == "확인":
        return 확인()
    print(__doc__)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
