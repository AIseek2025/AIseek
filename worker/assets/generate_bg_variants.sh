#!/bin/bash
mkdir -p bg_variants
cd bg_variants

# Generate 5 different colored videos
colors=("red" "blue" "green" "orange" "purple")
for i in "${!colors[@]}"; do
    color=${colors[$i]}
    filename="bg_color_$((i+1)).mp4"
    echo "Generating $filename with color $color..."
    ffmpeg -y -f lavfi -i color=c=$color:s=1080x1920:r=30 -t 30 -c:v libx264 -pix_fmt yuv420p "$filename"
done
