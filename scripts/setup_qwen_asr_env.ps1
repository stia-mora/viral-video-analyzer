param(
  [string]$EnvName = 'douyin-qwen-asr'
)

$ErrorActionPreference = 'Stop'
$env:PYTHONNOUSERSITE = '1'

conda create -y -n $EnvName python=3.12
conda run -n $EnvName python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
conda run -n $EnvName python -m pip install --no-cache-dir -r requirements-qwen-asr.txt
conda run -n $EnvName python -c "import torch, qwen_asr; print('torch', torch.__version__); print('cuda', torch.cuda.is_available()); print('gpu', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu'); print('qwen_asr', qwen_asr.__file__)"
