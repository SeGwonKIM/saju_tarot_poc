"""정답키를 엔진에 넣어, 샘플이 노린 경로를 실제로 밟는지 확인한다.

이건 S1(추출 정확도) 측정이 아니다. 샘플이 '어려운 입력'을 제대로
담고 있는지 보는 사전 점검이다.

쓰는 법:  python samples/check_samples.py
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import calendar_service, korea_time, saju_service

경도 = {"서울": 126.9780, "부산": 129.0756, "대구": 128.6014,
        "인천": 126.7052, "광주": 126.8526, "전주": 127.1480,
        "창원": 128.6811, None: 126.9780}   # 미언급이면 서울 기준

여기 = Path(__file__).resolve().parent
정답 = json.loads((여기 / "정답키.json").read_text(encoding="utf-8"))
숨김 = 여기 / "정답키_숨김.json"
if 숨김.exists():
    정답.update(json.loads(숨김.read_text(encoding="utf-8")))

def 간지(p): return "" if p is None else f"{p.gan}{p.ji}"

print("=" * 78)
print("샘플 사전 점검 — 어려운 경로를 실제로 밟는가")
print("=" * 78)

for 번호, a in 정답.items():
    print(f"\n[{번호}] {a['name']}  ·  {a['난이도']}")
    print(f"      노리는 것: {a['노리는 것']}")

    y, m, d = map(int, a["birth_date"].split("-"))

    # 음력이면 양력으로 변환. 윤달을 모르면 평달로 가정하고 표시한다.
    메모 = []
    if a["calendar_type"] == "lunar":
        윤달 = a["is_leap"]
        if 윤달 is None:
            있나 = calendar_service.has_leap_month(y, m)
            메모.append(f"윤달 미확인 — 그 해 {m}월에 윤달이 "
                        f"{'있음 ⚠ 반드시 물어야 함' if 있나 else '없음 (평달로 확정 가능)'}")
            윤달 = False
        conv = calendar_service.lunar_to_solar(y, m, d, 윤달)
        y, m, d = map(int, conv.solar_date.split("-"))
        메모.append(f"음력 → 양력 {y}-{m:02d}-{d:02d}")

    if a["birth_time"] is None:
        c = korea_time.correct(datetime(y, m, d, 12, 0), 경도[a["birth_place"]])
        chart = saju_service.build_chart(c.jieqi_reference, None)
        메모.append("시간 미상 → 3주 6글자")
    else:
        hh, mm = map(int, a["birth_time"].split(":"))
        c = korea_time.correct(datetime(y, m, d, hh, mm), 경도[a["birth_place"]])
        chart = saju_service.build_chart(c.jieqi_reference, c.true_solar)
        if c.dst_applied:
            메모.append("서머타임 적용 — 시계에서 1시간 뺌")
        메모.append(f"시계 {hh:02d}:{mm:02d} → 진태양시 "
                    f"{c.true_solar:%m-%d %H:%M} ({c.true_solar_correction_min:+d}분)")
        if c.true_solar.day != d:
            메모.append("⚠ 보정으로 날짜가 넘어감 — 일주가 바뀜")

    if a["birth_place"] is None:
        메모.append("출생지 미언급 — 서울 경도로 가정")

    for t in 메모:
        print(f"      · {t}")
    print(f"      원국: {간지(chart.year)} {간지(chart.month)} "
          f"{간지(chart.day)} {간지(chart.hour) or '(시주 없음)'}")
    print(f"      오행: {chart.elements.verdict}")

print("\n" + "=" * 78)
print("점검 끝 — 이 결과가 S1 채점의 '정답' 쪽이 된다")
print("=" * 78)
