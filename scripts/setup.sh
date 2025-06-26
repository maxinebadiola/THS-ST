#dependency installer (linux)
set -e
sudo apt-get update
sudo apt-get install -y python3 python3-pip ffmpeg nano
mkdir -p THS-ST/output
python3 -m pip install --upgrade pip

python3 -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
python3 -m pip install whisperx
python3 -m pip install numpy scikit-learn sentence-transformers pandas

echo "All dependencies installed successfully."
