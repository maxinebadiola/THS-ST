#!/bin/bash

# setupTitleGeneration.sh
# Setup script for generateTitles.py dependencies
# Optimized for RTX 4090 24GB VRAM on Linux

set -e

echo "=========================================="
echo "   Title Generation Setup Script"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if running as root or with sudo
if [[ $EUID -eq 0 ]]; then
    echo -e "${YELLOW}[WARNING]${NC} Running as root. This is not recommended for pip installations."
    echo "Consider running without sudo for user-level installations."
    echo ""
fi

# Function to print status messages
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check Python version
print_status "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
MIN_VERSION="3.8"
if python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
    print_success "Python $PYTHON_VERSION detected (>= $MIN_VERSION required)"
else
    print_error "Python $MIN_VERSION or higher is required. Found: $PYTHON_VERSION"
    exit 1
fi

# Check if CUDA is available
print_status "Checking CUDA availability..."
if nvidia-smi &> /dev/null; then
    CUDA_VERSION=$(nvidia-smi | grep "CUDA Version" | sed 's/.*CUDA Version: \([0-9.]*\).*/\1/')
    print_success "CUDA $CUDA_VERSION detected"
    
    # Get GPU info
    GPU_INFO=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits | head -1)
    print_success "GPU: $GPU_INFO"
else
    print_warning "CUDA not detected. The script requires GPU for optimal performance."
    print_warning "The script will exit if no GPU is available when running."
fi

# Check if pip is installed
print_status "Checking pip installation..."
if command -v pip3 &> /dev/null; then
    print_success "pip3 is available"
elif command -v pip &> /dev/null; then
    print_success "pip is available"
else
    print_error "pip is not installed. Please install pip first."
    exit 1
fi

# Upgrade pip
print_status "Upgrading pip..."
python3 -m pip install --upgrade pip

# Create requirements.txt for title generation
print_status "Creating requirements.txt for title generation..."
cat > requirements-titlegen.txt << EOF
# Title Generation Dependencies
# Core PyTorch with CUDA support
torch>=2.0.0
torchvision>=0.15.0
torchaudio>=2.0.0

# Hugging Face transformers for LLM models
transformers>=4.30.0
accelerate>=0.20.0
safetensors>=0.3.0

# Environment and configuration
python-dotenv>=0.19.0

# Optional: For Gemini API support (commented out by default)
# google-generativeai>=0.3.0

# Utility libraries (usually pre-installed)
numpy>=1.21.0
regex
tokenizers
tqdm
huggingface-hub
EOF

print_success "Created requirements-titlegen.txt"

# Install PyTorch with CUDA support
print_status "Installing PyTorch with CUDA 12.1 support..."
python3 -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

if [ $? -eq 0 ]; then
    print_success "PyTorch installation completed"
else
    print_error "PyTorch installation failed"
    exit 1
fi

# Install transformers and related packages
print_status "Installing Hugging Face transformers..."
python3 -m pip install transformers accelerate safetensors

if [ $? -eq 0 ]; then
    print_success "Transformers installation completed"
else
    print_error "Transformers installation failed"
    exit 1
fi

# Install additional dependencies
print_status "Installing additional dependencies..."
python3 -m pip install python-dotenv tqdm huggingface-hub tokenizers regex

if [ $? -eq 0 ]; then
    print_success "Additional dependencies installed"
else
    print_error "Additional dependencies installation failed"
    exit 1
fi

# Verify installations
print_status "Verifying installations..."

# Test PyTorch
python3 -c "
import torch
print(f'PyTorch version: {torch.__version__}')
print(f'CUDA available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'CUDA device count: {torch.cuda.device_count()}')
    print(f'Current CUDA device: {torch.cuda.current_device()}')
    print(f'CUDA device name: {torch.cuda.get_device_name()}')
"

# Test transformers
python3 -c "
import transformers
print(f'Transformers version: {transformers.__version__}')
"

# Test other imports
python3 -c "
try:
    from dotenv import load_dotenv
    print('python-dotenv: OK')
except ImportError as e:
    print(f'python-dotenv: FAILED - {e}')

try:
    import accelerate
    print(f'accelerate version: {accelerate.__version__}')
except ImportError as e:
    print(f'accelerate: FAILED - {e}')
"

# Create directory structure if needed
print_status "Ensuring directory structure..."
mkdir -p output/llm_generated/batch
mkdir -p output/raw_transcripts

print_success "Directory structure created"

# Create .env template
print_status "Creating .env template..."
if [ ! -f .env ]; then
    cat > .env << EOF
# Environment variables for generateTitles.py
# 
# Uncomment and add your API keys if using external APIs:
# GEMINI_API_KEY=your_gemini_api_key_here
# OPENAI_API_KEY=your_openai_api_key_here
#
# GPU Settings (optional overrides)
# CUDA_VISIBLE_DEVICES=0
EOF
    print_success "Created .env template file"
else
    print_warning ".env file already exists, skipping template creation"
fi

# Test GPU functionality
print_status "Testing GPU functionality..."
python3 -c "
import torch
import sys

if not torch.cuda.is_available():
    print('[ERROR] CUDA not available in PyTorch')
    sys.exit(1)

try:
    # Test basic GPU operations
    device = torch.device('cuda')
    test_tensor = torch.tensor([1.0]).to(device)
    print('[SUCCESS] GPU test passed')
    print(f'GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}GB')
    
    # Clear cache
    torch.cuda.empty_cache()
except Exception as e:
    print(f'[ERROR] GPU test failed: {e}')
    sys.exit(1)
"

if [ $? -eq 0 ]; then
    print_success "GPU functionality verified"
else
    print_error "GPU functionality test failed"
    print_warning "The generateTitles.py script may not run properly without GPU support"
fi

# Clean up caches
print_status "Cleaning up caches..."
rm -rf ~/.cache/pip
rm -rf ~/.cache/torch
rm -rf ~/.cache/huggingface

print_success "Caches cleaned"

echo ""
echo "=========================================="
print_success "Title Generation Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Navigate to the project directory: cd /root/THS-ST"
echo "2. Run title generation: python scripts/generateTitles.py --menu"
echo "3. Or run all videos: python scripts/generateTitles.py"
echo ""
echo "Files created:"
echo "- requirements-titlegen.txt (dependency list)"
echo "- .env (environment template)"
echo ""
print_status "GPU Requirements:"
echo "- The script requires CUDA-capable GPU (RTX 4090 recommended)"
echo "- Minimum 8GB VRAM (24GB recommended for optimal performance)"
echo "- CUDA 12.1 or compatible version"
echo ""
print_warning "If you encounter any issues, check that:"
echo "1. NVIDIA drivers are properly installed"
echo "2. CUDA toolkit is installed and compatible"
echo "3. Sufficient GPU memory is available"
echo "4. Required transcript files exist in output/raw_transcripts/"