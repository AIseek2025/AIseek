#!/bin/bash
mkdir -p bgm
echo "Generating dummy BGM files..."
# Generate 10s simple tones
ffmpeg -y -f lavfi -i sine=f=440:b=4 -t 10 -c:a libmp3lame -q:a 2 bgm/tech_1.mp3
ffmpeg -y -f lavfi -i sine=f=523:b=4 -t 10 -c:a libmp3lame -q:a 2 bgm/cheerful_1.mp3
ffmpeg -y -f lavfi -i sine=f=330:b=4 -t 10 -c:a libmp3lame -q:a 2 bgm/serious_1.mp3
echo "Done. Created tech_1.mp3, cheerful_1.mp3, serious_1.mp3 in bgm/"
