# This script will install all required dependencies for 1-whisperX.py on a Linux environment.
# Usage: bash setup.sh
sudo apt-get update
sudo apt-get install -y nano
#1-whisperX
mkdir -p THS-ST/output
python3 -m pip install --upgrade pip
python3 -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
python3 -m pip install whisperx
sudo apt-get install -y ffmpeg
#2-BERT
