#!/bin/sh
# 無音の zenen_reel.mp4 に BGM を重ねて zenen_reel_bgm.mp4 を作る（映像は再エンコードしない）。
# BGM は冒頭から30秒を使い、最初0.3秒でフェードイン、最後2.5秒でフェードアウト、-14 LUFS に正規化。
set -e
cd "$(dirname "$0")"
ffmpeg -y -loglevel error -i zenen_reel.mp4 -i music/Paper_Lanterns.mp3 \
  -filter_complex "[1:a]atrim=0:30,asetpts=PTS-STARTPTS,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000,afade=t=in:st=0:d=0.3,afade=t=out:st=27.5:d=2.5[a]" \
  -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k -t 30 -movflags +faststart zenen_reel_bgm.mp4
