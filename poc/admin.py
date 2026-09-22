"""관리자 검수함을 단일 파일 HTML 로 굽는다 (상용전환_설계.md 2장)

왜 만드나
  설계 문서에 "30분 뒤 자동 발송, 위험한 건만 사람에게" 라고 적어 두었지만
  **실물이 없으면 그게 어떻게 보이는지 아무도 모른다.**

  그리고 이 화면이 S5(초안 품질)를 재는 도구이기도 하다.
  관리자가 **무엇을 고쳤는지**가 곧 초안의 약한 곳이다.

무엇을 하나
  out/*/ 의 산출물을 읽어 데이터를 HTML 안에 구워 넣는다.
  서버가 없다. 파일 하나를 열면 바로 돈다.

  · 검수함 — 남은 시간 순. 보류된 건은 위로
  · 검수 화면 — 게이트 이유가 맨 위. 계산 결과는 잠금. 초안만 수정 가능
  · 30분 타이머 — 실제로 센다. 0이 되면 '발송됨'으로 바뀐다
  · 검수 시간 자동 측정 — 연 순간부터 잰다. S3 의 빠진 분모다
  · 고친 내용 내보내기 — JSON 으로 저장해 s5 채점에 쓴다

쓰는 법:  python -m poc.admin  →  out/검수함.html
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from verify.guard import 표본확인  # noqa: E402

뿌리 = Path(__file__).resolve().parents[1]
타이머분 = 30


def 모으기() -> list[dict]:
    주문 = []
    for 방 in sorted((뿌리 / "out").glob("*/report.json")):
        d = json.loads(방.read_text(encoding="utf-8"))
        번호 = 방.parent.name
        입력 = json.loads((방.parent / "input.json").read_text(encoding="utf-8"))
        run = json.loads((방.parent / "run.json").read_text(encoding="utf-8"))
        글 = (방.parent / "transcript.txt").read_text(encoding="utf-8")
        주문.append({
            "번호": 번호, "보고": d, "입력": 입력,
            "실행": {"합계_초": run.get("합계_초"), "생성메모": run.get("생성메모"),
                     "모델": (run.get("조건") or {}).get("모델"),
                     "토큰": run.get("토큰"), "재생성": run.get("재생성"),
                     "마스킹": run.get("마스킹")},
            "원문": 글,
        })
    return 주문


HTML = """<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>검수함</title>
<style>
:root{--bg:#f6f5f2;--card:#fff;--line:#e3e1db;--ink:#1a1a18;--dim:#6b6a65;
--red:#c0392b;--redbg:#fdecea;--amber:#9a6b00;--amberbg:#fdf3dd;
--green:#1d6f4a;--greenbg:#e6f4ec;--lock:#f0efeb}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.7 system-ui,'Malgun Gothic',sans-serif}
header{background:var(--card);border-bottom:1px solid var(--line);
padding:14px 20px;display:flex;align-items:center;gap:16px;flex-wrap:wrap}
h1{font-size:17px;margin:0;font-weight:600}
.sub{color:var(--dim);font-size:13px}
.wrap{display:grid;grid-template-columns:330px 1fr;gap:0;min-height:calc(100vh - 56px)}
.list{border-right:1px solid var(--line);background:var(--card);overflow:auto}
.row{padding:12px 16px;border-bottom:1px solid var(--line);cursor:pointer}
.row:hover{background:#faf9f7}
.row.on{background:#eef3fb;box-shadow:inset 3px 0 0 #2a6fd6}
.row .nm{font-weight:600}
.row .mt{font-size:12.5px;color:var(--dim);margin-top:2px}
.pill{display:inline-block;font-size:11.5px;padding:1px 7px;border-radius:9px;
font-weight:600;vertical-align:1px}
.p-hold{background:var(--redbg);color:var(--red)}
.p-wait{background:var(--amberbg);color:var(--amber)}
.p-sent{background:var(--greenbg);color:var(--green)}
main{padding:20px 24px;overflow:auto}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:16px 18px;margin-bottom:14px}
.why{border-left:4px solid var(--red);background:var(--redbg);border-radius:0 8px 8px 0}
.why h3{margin:0 0 8px;font-size:14px;color:var(--red)}
.why li{margin:3px 0}
.why .warn{font-weight:700}
h2{font-size:15px;margin:0 0 10px}
.lock{background:var(--lock);border-radius:8px;padding:12px 14px;font-size:14px}
.lockmsg{font-size:12.5px;color:var(--dim);margin-top:8px}
table{border-collapse:collapse;width:100%;font-size:14px}
td,th{border:1px solid var(--line);padding:6px 9px;text-align:left}
th{background:#faf9f7;font-weight:600;width:88px}
textarea{width:100%;font:14px/1.7 inherit;border:1px solid var(--line);
border-radius:7px;padding:9px 11px;resize:vertical;background:#fffef9}
textarea:focus{outline:2px solid #2a6fd6;outline-offset:-1px;background:#fff}
textarea.dirty{border-color:#d08700;background:#fffaf0}
.fld{margin-bottom:10px}
.fld label{display:block;font-size:12.5px;color:var(--dim);margin-bottom:3px}
.bar{position:sticky;bottom:0;background:var(--card);border-top:1px solid var(--line);
padding:12px 0 2px;display:flex;gap:9px;align-items:center;flex-wrap:wrap}
button{font:14px inherit;padding:8px 15px;border-radius:7px;border:1px solid var(--line);
background:#fff;cursor:pointer}
button:hover{background:#f3f2ef}
button.go{background:#1d6f4a;color:#fff;border-color:#1d6f4a;font-weight:600}
button.hold{background:#fff;color:var(--red);border-color:#e0b4ae}
.timer{font-variant-numeric:tabular-nums;font-weight:700}
.timer.urgent{color:var(--red)}
.meta{font-size:12.5px;color:var(--dim)}
.empty{padding:60px 20px;text-align:center;color:var(--dim)}
@media(max-width:820px){.wrap{grid-template-columns:1fr}
.list{border-right:0;border-bottom:1px solid var(--line);max-height:230px}}
</style></head><body>
<header>
  <h1>검수함</h1>
  <span class="sub" id="요약"></span>
  <span style="flex:1"></span>
  <button onclick="내보내기()">고친 내용 내보내기</button>
  <button onclick="되돌리기()">전부 되돌리기</button>
</header>
<div class="wrap">
  <div class="list" id="목록"></div>
  <main id="상세"><div class="empty">왼쪽에서 한 건을 고르세요.</div></main>
</div>
<script>
const 자료 = __DATA__;
const 타이머분 = __MIN__;
const 열쇠 = 'saju_검수함_v1';
let 상태 = {};
try { 상태 = JSON.parse(localStorage.getItem(열쇠) || '{}'); } catch(e) { 상태 = {}; }
let 지금보는 = null, 연시각 = null;

function 상태가져오기(o){
  if(!상태[o.번호]){
    // 게이트가 걸린 건은 타이머를 타지 않는다 — 보류로 시작한다.
    // 이 판정은 코드가 이미 해 두었다 (poc/confirm.py · poc/safety.py).
    const 보류로시작 = o.보고.확인필요;
    상태[o.번호] = {
      단계: 보류로시작 ? 'held' : 'review',
      마감: 보류로시작 ? null : Date.now() + 타이머분*60000,
      수정: {}, 검수초: 0, 연횟수: 0
    };
  }
  return 상태[o.번호];
}
function 저장(){ try{ localStorage.setItem(열쇠, JSON.stringify(상태)); }catch(e){} }

function 남은(s){
  if(s.단계==='sent') return -1;
  if(s.단계==='held'||!s.마감) return null;
  return Math.max(0, Math.floor((s.마감 - Date.now())/1000));
}
function 시분(초){
  if(초===null) return '멈춤';
  const m=Math.floor(초/60), x=초%60;
  return m+':'+String(x).padStart(2,'0');
}

function 목록그리기(){
  const el = document.getElementById('목록');
  const 줄 = 자료.map(o=>{
    const s = 상태가져오기(o), 초 = 남은(s);
    let 표, cls;
    if(s.단계==='sent'){ 표='발송됨'; cls='p-sent'; }
    else if(s.단계==='held'){ 표='보류'; cls='p-hold'; }
    else { 표=시분(초)+' 뒤 발송'; cls='p-wait'; }
    const 고침 = Object.keys(s.수정).length;
    return `<div class="row ${지금보는===o.번호?'on':''}" onclick="열기('${o.번호}')">
      <div class="nm">${o.보고.이름||'(이름 없음)'} <span class="pill ${cls}">${표}</span></div>
      <div class="mt">${o.번호} · ${o.입력.birth_date||'-'} ·
        ${(o.보고.주제||[]).join(', ')}${고침?` · 고침 ${고침}`:''}</div>
    </div>`;
  }).join('');
  el.innerHTML = 줄;
  const 보류 = 자료.filter(o=>상태가져오기(o).단계==='held').length;
  const 발송 = 자료.filter(o=>상태가져오기(o).단계==='sent').length;
  document.getElementById('요약').textContent =
    `전체 ${자료.length} · 보류 ${보류} · 대기 ${자료.length-보류-발송} · 발송 ${발송}`;
}

function 열기(번호){
  if(지금보는 && 연시각){ 검수시간적립(); }
  지금보는 = 번호; 연시각 = Date.now();
  const s = 상태가져오기(자료.find(x=>x.번호===번호));
  s.연횟수 = (s.연횟수||0)+1; 저장();
  그리기(); 목록그리기();
}
function 검수시간적립(){
  if(!지금보는||!연시각) return;
  const s = 상태[지금보는];
  if(s){ s.검수초 = (s.검수초||0) + Math.round((Date.now()-연시각)/1000); 저장(); }
  연시각 = Date.now();
}

function 그리기(){
  const o = 자료.find(x=>x.번호===지금보는);
  if(!o) return;
  const s = 상태가져오기(o), b = o.보고, i = o.입력;
  const 초 = 남은(s);

  let 왜 = '';
  if(b.확인필요){
    왜 = `<div class="card why"><h3>보내기 전에 확인하십시오</h3><ul>
      ${(b.확인이유||[]).map(x=>`<li>${x}</li>`).join('')}
      ${(b.확인경고||[]).map(x=>`<li class="warn">⚠ ${x}</li>`).join('')}
    </ul><div style="margin-top:9px;font-size:13.5px">
      <b>읽어 드릴 문장</b> — “${b.대본||''}”</div></div>`;
  }

  const 기둥 = Object.entries(b.원국||{})
    .map(([k,v])=>`<td style="text-align:center">${v||'—'}</td>`).join('');
  const 머리 = Object.keys(b.원국||{})
    .map(k=>`<th style="text-align:center;width:auto">${k}</th>`).join('');

  const 칸 = (라벨, 키, 값, 줄=3) =>
    `<div class="fld"><label>${라벨}</label>
     <textarea rows="${줄}" data-k="${키}" oninput="고침(this)"
     >${(s.수정[키] ?? 값 ?? '')}</textarea></div>`;

  let 초안 = '';
  (b.사주풀이||[]).forEach((t,n)=> 초안 += 칸(`사주 풀이 ${n+1}`, `s${n}`, t));
  (b.이번달흐름||[]).forEach((t,n)=> 초안 += 칸(`이번 달 흐름 ${n+1}`, `m${n}`, t));
  Object.entries(b.조언||{}).forEach(([k,t])=> 초안 += 칸(`조언 · ${k}`, `a_${k}`, t, 4));

  document.getElementById('상세').innerHTML = `
  ${왜}
  <div class="card"><h2>손님이 적은 값 <span class="meta">— 대조용</span></h2>
    <table>
      <tr><th>이름</th><td>${i.name||'—'}</td><th>성별</th><td>${i.gender||'—'}</td></tr>
      <tr><th>생년월일</th><td>${i.birth_date||'—'} (${i.calendar_type==='lunar'?'음력':'양력'}${i.is_leap?' 윤달':''})</td>
          <th>시각</th><td>${i.birth_time||'모름'}</td></tr>
      <tr><th>출생지</th><td>${i.birth_place||'모름'}</td>
          <th>고민</th><td>${i.question||'—'}</td></tr>
    </table></div>

  <div class="card"><h2>계산 결과 <span class="meta">— 고칠 수 없음</span></h2>
    <div class="lock"><table><tr>${머리}</tr><tr>${기둥}</tr></table>
      <div style="margin-top:9px;font-size:13.5px">
        오행 ${Object.entries(b.오행||{}).map(([k,v])=>k+' '+v).join(', ')}
        &nbsp;→&nbsp; ${(b.판정||[]).join(', ')}<br>
        이번 달 ${b.세운||'—'}<br>
        ${(b.보정메모||[]).map(x=>'· '+x).join('<br>')}</div>
      <div class="lockmsg">이 값은 코드가 정한 사실입니다. 고쳐야 한다면
        입력값이 틀린 것이므로 <b>손님에게 되물어야</b> 합니다.</div>
    </div></div>

  <div class="card"><h2>초안 <span class="meta">— 여기만 고칠 수 있습니다</span></h2>
    ${초안 || '<div class="meta">초안이 없습니다. ' + (b.생성메모||'') + '</div>'}
    <div class="bar">
      <span class="timer ${초!==null&&초<300?'urgent':''}" id="타이머">
        ${s.단계==='sent'?'발송됨':(초===null?'타이머 멈춤':시분(초)+' 뒤 자동 발송')}</span>
      <span style="flex:1"></span>
      <span class="meta">검수 ${Math.floor((s.검수초||0)/60)}분 ${(s.검수초||0)%60}초
        · 고친 칸 ${Object.keys(s.수정).length}</span>
      <button class="hold" onclick="보류()">보류</button>
      <button class="go" onclick="보내기()">지금 보내기</button>
    </div>
  </div>`;
}

function 고침(el){
  const s = 상태[지금보는], k = el.dataset.k;
  const 원본 = 원본값(k);
  if(el.value === 원본){ delete s.수정[k]; el.classList.remove('dirty'); }
  else { s.수정[k] = el.value; el.classList.add('dirty'); }
  저장(); 목록그리기();
  document.querySelector('.bar .meta').textContent =
    `검수 ${Math.floor((s.검수초||0)/60)}분 ${(s.검수초||0)%60}초 · 고친 칸 ${Object.keys(s.수정).length}`;
}
function 원본값(k){
  const b = 자료.find(x=>x.번호===지금보는).보고;
  if(k[0]==='s') return (b.사주풀이||[])[+k.slice(1)];
  if(k[0]==='m') return (b.이번달흐름||[])[+k.slice(1)];
  if(k.startsWith('a_')) return (b.조언||{})[k.slice(2)];
  return '';
}
function 보내기(){
  검수시간적립();
  const s = 상태[지금보는]; s.단계='sent'; s.마감=null; s.보낸시각=Date.now();
  저장(); 그리기(); 목록그리기();
}
function 보류(){
  검수시간적립();
  const s = 상태[지금보는];
  if(s.단계==='held'){ s.단계='review'; s.마감 = Date.now()+타이머분*60000; }
  else { s.단계='held'; s.마감=null; }
  저장(); 그리기(); 목록그리기();
}
function 되돌리기(){
  if(!confirm('고친 내용과 상태를 전부 지웁니다. 계속할까요?')) return;
  상태={}; localStorage.removeItem(열쇠); 지금보는=null;
  document.getElementById('상세').innerHTML='<div class="empty">왼쪽에서 한 건을 고르세요.</div>';
  목록그리기();
}
function 내보내기(){
  검수시간적립();
  const 나갈것 = 자료.map(o=>{
    const s = 상태[o.번호]||{};
    const 수정 = Object.entries(s.수정||{}).map(([k,v])=>({칸:k, 전:원본값2(o,k), 후:v}));
    return {번호:o.번호, 이름:o.보고.이름, 단계:s.단계, 검수초:s.검수초||0,
            연횟수:s.연횟수||0, 게이트: o.보고.확인필요, 고친칸수:수정.length, 수정};
  });
  const b = new Blob([JSON.stringify({내보낸시각:new Date().toISOString(),
    타이머분, 주문:나갈것}, null, 2)], {type:'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(b); a.download = '검수기록.json'; a.click();
}
function 원본값2(o,k){
  const b=o.보고;
  if(k[0]==='s') return (b.사주풀이||[])[+k.slice(1)];
  if(k[0]==='m') return (b.이번달흐름||[])[+k.slice(1)];
  if(k.startsWith('a_')) return (b.조언||{})[k.slice(2)];
  return '';
}

setInterval(()=>{
  let 바뀜=false;
  자료.forEach(o=>{
    const s=상태가져오기(o);
    if(s.단계==='review' && 남은(s)===0){ s.단계='sent'; s.마감=null;
      s.자동=true; s.보낸시각=Date.now(); 바뀜=true; }
  });
  if(바뀜) 저장();
  목록그리기();
  if(지금보는){
    const s=상태[지금보는], 초=남은(s), el=document.getElementById('타이머');
    if(el) { el.textContent = s.단계==='sent' ? (s.자동?'자동 발송됨':'발송됨')
      : (초===null?'타이머 멈춤':시분(초)+' 뒤 자동 발송');
      el.className = 'timer' + (초!==null&&초<300?' urgent':''); }
  }
}, 1000);

목록그리기();
</script></body></html>
"""


def main() -> int:
    주문 = 모으기()
    표본확인("검수할 주문", 주문, 최소=1)
    나올것 = 뿌리 / "out" / "검수함.html"
    나올것.write_text(
        HTML.replace("__DATA__", json.dumps(주문, ensure_ascii=False))
            .replace("__MIN__", str(타이머분)),
        encoding="utf-8")

    걸림 = sum(1 for o in 주문 if o["보고"]["확인필요"])
    print(f"■ 검수함을 만들었습니다 — {나올것}")
    print(f"  주문 {len(주문)}건 · 자동 발송 {len(주문)-걸림} · 보류(사람에게) {걸림}")
    print(f"  타이머 {타이머분}분. 파일을 브라우저로 열면 바로 돕니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
