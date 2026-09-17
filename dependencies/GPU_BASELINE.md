# GPU compatibility baseline

The GPU image uses one deliberately pinned compatibility set. Do not update one
row independently: rebuild and smoke-test closed-set TensorRT inference and
open-set YOLOE whenever this set changes.

| Component | Pinned value | Reason |
| --- | --- | --- |
| Container OS / Python | Ubuntu 24.04 / Python 3.12 | ROS 2 Jazzy binary platform |
| CUDA toolkit | `nvidia/cuda:12.8.1-devel-ubuntu24.04` | First CUDA/PyTorch family supporting Blackwell; includes NVCC/runtime |
| TensorRT | 10.9.0.34 for CUDA 12.8 | Ubuntu 24.04 + CUDA 12.8 release; Blackwell support |
| PyTorch | 2.7.0 `cu128` | Pinned Awesome-DCIST-T4 compatibility reference |
| torchvision | 0.22.0 `cu128` | Official match for PyTorch 2.7.0 |
| cuDNN | 9.7.1.26, supplied by the PyTorch wheel | Official PyTorch 2.7 CUDA 12.8 wheel dependency |
| Ultralytics | 8.4.130 | Repository Python dependency lock |

The CUDA base tag, exact TensorRT apt version, and PyTorch wheel index are
declared in `docker/Dockerfile.gpu`; Python package versions are in
`dependencies/gpu.requirements.txt`. The image build asserts the installed
PyTorch, torchvision, CUDA toolkit, and TensorRT-compatible build. Its single
semantic-inference virtual environment also contains the bag conversion tools,
while ROS Python packages remain available through the sourced ROS environment.

## Host driver and GPU

The host needs an NVIDIA driver and NVIDIA Container Toolkit; it does **not**
need a host CUDA toolkit. The `CUDA Version` shown by `nvidia-smi` is the newest
CUDA driver API the installed driver supports, not the toolkit version that a
container must use. A host reporting CUDA 13.0 can therefore run this CUDA 12.8
image.

Use NVIDIA Linux driver **570.124.06 or newer**, the CUDA 12.8 Update 1 release
baseline. The reported RTX 5060 Ti with driver 580.173.02 satisfies that
requirement. This image targets NVIDIA architectures supported by TensorRT 10.9
(compute capability 7.5 or newer, including Turing, Ampere, Ada, Hopper, and
Blackwell). Older GPUs require a separately qualified stack rather than an
independent CUDA or PyTorch override.

After building on another GPU, run:

```bash
make models PROFILE=gpu
make gpu-smoke
```

The smoke test checks the installed versions, CUDA availability, device name,
and YOLOE model loading. Closed-set and open-set end-to-end smoke tests remain
required before declaring a newly qualified GPU/driver combination supported.

## Why the image does not start from `pytorch/pytorch`

The matching `pytorch/pytorch:2.7.0-cuda12.8-cudnn9-runtime` image uses an
Ubuntu 22.04/Conda Python stack. ROS 2 Jazzy binary packages target Ubuntu 24.04
and system Python 3.12. Starting from the PyTorch image would mix incompatible
OS/Python assumptions. This repository instead starts the standalone GPU image
from NVIDIA's CUDA 12.8.1 development image for Ubuntu 24.04, installs Jazzy,
and then installs the official `cu128` wheels into a Python 3.12 virtual
environment. The retained development toolchain is intentional: debuggability
and build reliability take priority over final image size.

## Upstream references

- [PyTorch 2.7 release](https://pytorch.org/blog/pytorch-2-7/)
- [PyTorch previous-version wheel matrix](https://pytorch.org/get-started/previous-versions/)
- [CUDA 12.8 Update 1 release notes](https://docs.nvidia.com/cuda/archive/12.8.1/cuda-toolkit-release-notes/)
- [TensorRT 10.9 support matrix](https://docs.nvidia.com/deeplearning/tensorrt/10.9.0/getting-started/support-matrix.html)
- [NVIDIA CUDA compatibility](https://docs.nvidia.com/deploy/cuda-compatibility/)
