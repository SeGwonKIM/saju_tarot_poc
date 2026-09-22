# 상담 텍스트를 합성 음성(wav)으로 만든다 — STT 경로를 실제로 돌리기 위해.
#
# ⚠ 이건 **실제 녹취가 아니다.** 윈도우 TTS(Heami)가 또박또박 읽은 소리다.
#    실제 통화에는 잡음·말 겹침·사투리·끊김이 있고, 그건 이 파일로는 못 잰다.
#    그래도 "STT 를 한 번도 안 돌렸다"(유형 B)는 상태보다는 낫다.
#    STT 를 거치면 추출이 얼마나 나빠지는지 **방향**은 볼 수 있다.
#
# 상담자/의뢰인 두 사람이므로 목소리를 바꿔 가며 읽는다.
# 한국어 음성이 하나뿐이라 속도로 구분한다 — 화자 분리까지 흉내 내지는 못한다.
#
# 쓰는 법:  powershell -ExecutionPolicy Bypass -File samples/make_audio.ps1 -번호 001

param([string]$번호 = "001")

Add-Type -AssemblyName System.Speech

$여기   = Split-Path -Parent $MyInvocation.MyCommand.Path
$원본   = Join-Path $여기 "상담_$번호.txt"
$나올것 = Join-Path $여기 "상담_$번호.wav"

if (-not (Test-Path $원본)) { Write-Error "$원본 이 없습니다"; exit 1 }

$합성 = New-Object System.Speech.Synthesis.SpeechSynthesizer
$한국어 = $합성.GetInstalledVoices() |
    Where-Object { $_.VoiceInfo.Culture.Name -eq "ko-KR" } |
    Select-Object -First 1
if ($null -eq $한국어) { Write-Error "한국어 음성이 없습니다"; exit 1 }
$합성.SelectVoice($한국어.VoiceInfo.Name)
$합성.SetOutputToWaveFile($나올것)

$줄수 = 0
foreach ($줄 in (Get-Content $원본 -Encoding UTF8)) {
    if ([string]::IsNullOrWhiteSpace($줄)) { continue }
    # "상담자:" / "의뢰인:" 표시는 읽지 않는다 — 실제 녹취에는 없는 글자다.
    if ($줄 -match '^(상담자|의뢰인)\s*:\s*(.*)$') {
        $말 = $Matches[2]
        $합성.Rate = if ($Matches[1] -eq '상담자') { 0 } else { -1 }
    } else {
        $말 = $줄
    }
    if ([string]::IsNullOrWhiteSpace($말)) { continue }
    $합성.Speak($말)
    $합성.Speak(" ")          # 발화 사이 짧은 쉼
    $줄수++
}
$합성.SetOutputToNull()
$합성.Dispose()

$크기 = [math]::Round((Get-Item $나올것).Length / 1MB, 2)
Write-Output "상담_$번호.wav 만듦 — 발화 $줄수 개, $크기 MB"
Write-Output "음성: $($한국어.VoiceInfo.Name)  (합성 음성 · 실제 녹취 아님)"
