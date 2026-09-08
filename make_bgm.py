# 저작권 걱정 없는 배경음을 ffmpeg 사인파 합성으로 생성한다. 실제 음원을 구하면 이 파일들을 덮어쓰면 된다
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).parent / "assets" / "bgm"
DURATION = 70  # 가장 긴 릴스(55초)보다 길게

# 각 트랙 = 저음 드론 2~3개(화음) + 주기적으로 감쇠하는 펄스(리듬)
# exp(-k*mod(t,p)) 가 p초마다 튕기는 소리를 만든다. k가 클수록 짧고 또렷하다
TRACKS = {
    # 차분한 테크 — A minor 계열, 0.75초 펄스
    "calm_tech_01": "0.18*sin(2*PI*110*t)+0.12*sin(2*PI*164.8*t)+0.16*sin(2*PI*440*t)*exp(-6*mod(t,0.75))",
    # 밝고 경쾌 — A major 계열, 0.5초 펄스
    "upbeat_lofi_02": "0.15*sin(2*PI*220*t)+0.10*sin(2*PI*277.2*t)+0.17*sin(2*PI*554.4*t)*exp(-9*mod(t,0.5))",
    # 미니멀 — 낮은 드론 + 짧고 잦은 클릭
    "minimal_pulse_03": "0.20*sin(2*PI*82.4*t)+0.15*sin(2*PI*659.3*t)*exp(-14*mod(t,0.4))",
    # 따뜻함 — D major 계열, 1초 펄스로 느긋하게
    "warm_acoustic_04": "0.16*sin(2*PI*146.8*t)+0.12*sin(2*PI*220*t)+0.14*sin(2*PI*293.7*t)*exp(-5*mod(t,1.0))",
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, expr in TRACKS.items():
        path = OUT / f"{name}.mp3"
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", f"aevalsrc='{expr}':s=44100:d={DURATION}",
            # lowpass로 사인파의 날카로움을 깎고, 양끝을 페이드해 뚝 끊기지 않게 한다
            "-af", f"lowpass=f=2200,afade=t=in:d=2,afade=t=out:st={DURATION - 3}:d=3",
            "-ac", "2", "-c:a", "libmp3lame", "-b:a", "128k",
            str(path),
        ]
        subprocess.run(cmd, check=True)
        print(f"{path.name}  {path.stat().st_size / 1024:.0f}KB")
    print(f"\n{len(TRACKS)}곡 생성 완료 → {OUT}")


if __name__ == "__main__":
    sys.exit(main())
