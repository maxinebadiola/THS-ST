#dependency installer (linux)
set -e
apt-get update
apt-get install -y python3 python3-pip ffmpeg nano
mkdir -p THS-ST/output
python3 -m pip install --upgrade pip

#script dependencies
python3 -m pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
python3 -m pip install --no-cache-dir whisperx
python3 -m pip install --no-cache-dir numpy scikit-learn sentence-transformers pandas

#clean up caches
rm -rf ~/.cache/pip
rm -rf ~/.cache/torch
rm -rf ~/.cache/huggingface
rm -rf ~/.cache/whisper

apt-get clean
echo "All dependencies installed and caches cleaned."
