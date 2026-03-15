mkdir -p /root/AIseek-Trae-v1/worker/assets/bg_variants
cd /root/AIseek-Trae-v1/worker/assets/bg_variants
for color in red blue green orange purple; do
    ffmpeg -y -f lavfi -i color=c=$color:s=1080x1920:r=30 -t 30 -c:v libx264 -pix_fmt yuv420p "bg_$color.mp4"
done
