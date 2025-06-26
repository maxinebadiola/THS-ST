#dependency installer (linux)
set -e
sudo apt-get update
sudo apt-get install -y python3 python3-pip ffmpeg nano
mkdir -p THS-ST/output
python3 -m pip install --upgrade pip

python3 -m pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
python3 -m pip install --no-cache-dir whisperx
python3 -m pip install --no-cache-dir numpy scikit-learn sentence-transformers pandas

rm -rf ~/.cache/pip
rm -rf ~/.cache/torch
rm -rf ~/.cache/huggingface
rm -rf ~/.cache/whisper

sudo apt-get clean

echo "All dependencies installed and caches cleaned."
