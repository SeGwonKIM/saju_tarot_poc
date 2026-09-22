"""README 에 넣을 시연 그림을 만든다.

과제요구사항 — "README (실행 방법과 **동작 결과 스크린샷·영상 등 시연 자료**)"

두 가지를 찍는다.
  ① 관리자 검수함 — 실제 HTML 을 헤드리스 브라우저로 그대로 캡처한다
  ② 터미널 출력  — out/*_결과.txt 의 **실제 출력**을 터미널 모양 페이지에 얹어 캡처한다

②도 지어낸 화면이 아니다. 파일에 남아 있는 **실행 원본**을 그대로 읽어 넣는다.
꾸민 것은 배경과 글꼴뿐이다.

쓰는 법:  python docs/make_shots.py
"""
from __future__ import annotations

import html
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

뿌리 = Path(__file__).resolve().parents[1]
그림방 = 뿌리 / "docs" / "img"

크롬후보 = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

# (나올 파일, 제목, 읽을 파일, 몇 줄까지)
터미널 = [
    ("s2.png", "python -m verify.s2_manseryeok", "out/s2_결과.txt", None),
    ("selftest.png", "python -m verify.selftest_negative", None, None),
    ("s1.png", "python -m verify.s1_extract --숨김2 --llm", "out/s1_숨김2_결과.txt", None),
    ("stt.png", "python -m verify.s1_stt", "out/s1_stt_결과.txt", None),
]


def 크롬() -> str:
    for c in 크롬후보:
        if Path(c).exists():
            return c
    raise SystemExit("크롬이나 엣지를 못 찾았습니다.")


def 터미널페이지(제목: str, 본문: str) -> str:
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
body{{margin:0;background:#1e1e1c;font-family:Consolas,'D2Coding','Malgun Gothic',monospace}}
.win{{margin:18px;border-radius:9px;overflow:hidden;box-shadow:0 6px 28px rgba(0,0,0,.4)}}
.bar{{background:#32312e;padding:9px 14px;display:flex;align-items:center;gap:7px}}
.dot{{width:11px;height:11px;border-radius:50%}}
.t{{color:#c9c7c1;font-size:12.5px;margin-left:9px}}
pre{{margin:0;padding:15px 18px;background:#1e1e1c;color:#e4e2dc;
font-size:12.5px;line-height:1.55;white-space:pre;overflow:hidden}}
.ok{{color:#7fd17f}} .no{{color:#e98383}} .hi{{color:#f0d070}}
</style></head><body><div class="win">
<div class="bar"><span class="dot" style="background:#ff5f57"></span>
<span class="dot" style="background:#febc2e"></span>
<span class="dot" style="background:#28c840"></span>
<span class="t">{html.escape(제목)}</span></div>
<pre>{본문}</pre></div></body></html>"""


def 물들이기(t: str) -> str:
    t = html.escape(t)
    for 낱말, 클래스 in (("PASS", "ok"), ("통과", "ok"), ("밟음", "ok"),
                        ("FAIL", "no"), ("미달", "no"), ("흔들림", "no"),
                        ("미검증", "no"), ("⚠", "hi")):
        t = t.replace(낱말, f'<span class="{클래스}">{낱말}</span>')
    return t


def 찍기(chrome: str, html_경로: Path, 나올것: Path, 폭: int, 높이: int,
        꼬리: str = "") -> None:
    with tempfile.TemporaryDirectory() as 임시:
        subprocess.run([
            chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
            f"--user-data-dir={임시}",
            f"--window-size={폭},{높이}",
            f"--screenshot={나올것}",
            html_경로.as_uri() + 꼬리,
        ], check=True, capture_output=True, timeout=120)


def main() -> int:
    chrome = 크롬()
    그림방.mkdir(parents=True, exist_ok=True)
    print(f"브라우저: {Path(chrome).name}")

    # ① 관리자 검수함 — 실물 HTML 그대로
    검수함 = 뿌리 / "out" / "검수함.html"
    if 검수함.exists():
        찍기(chrome, 검수함, 그림방 / "admin.png", 1400, 760)
        print("  admin.png      관리자 검수함 — 목록")
        찍기(chrome, 검수함, 그림방 / "admin_review.png", 1400, 1180, "#007")
        print("  admin_review.png  검수 화면 — 게이트가 오답을 잡은 장면")
    else:
        print("  ⚠ out/검수함.html 이 없습니다. python -m poc.admin 을 먼저 돌리세요.")

    # ② 터미널 출력 — 실행 원본을 그대로
    for 이름, 제목, 읽을것, 자르기 in 터미널:
        if 읽을것:
            p = 뿌리 / 읽을것
            if not p.exists():
                print(f"  ⚠ {읽을것} 없음 — 건너뜀")
                continue
            글 = p.read_text(encoding="utf-8")
        else:
            글 = subprocess.run(
                [sys.executable, "-m", "verify.selftest_negative"],
                cwd=뿌리, capture_output=True, text=True, encoding="utf-8",
                env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
            ).stdout
        줄 = [x for x in 글.splitlines() if not x.startswith("[")]
        if 자르기:
            줄 = 줄[:자르기]
        폭글자 = max((len(x) for x in 줄), default=80)
        높이 = min(1400, 60 + len(줄) * 20)
        너비 = min(1500, 90 + int(폭글자 * 7.3))

        임시 = 그림방 / "_tmp.html"
        임시.write_text(터미널페이지(제목, 물들이기("\n".join(줄))), encoding="utf-8")
        찍기(chrome, 임시, 그림방 / 이름, 너비, 높이)
        임시.unlink()
        print(f"  {이름:<15}{제목}  ({len(줄)}줄)")

    print(f"\n{그림방} 에 저장했습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
