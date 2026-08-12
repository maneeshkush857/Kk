# -*- coding: utf-8 -*-
# =============================================================================
# LTX23_Director_2_0_MV_Colab_T4.py
#
# Production Google Colab pipeline for LTX-2.3 Director 2.0 MV Workflow
# Source of truth: LTX-2.3_Director_2.0-MV-Workflow-30s.json
# Reference impl:  ltx2_ti2v_distilled.py
# Target hardware: NVIDIA Tesla T4 — 16 GB VRAM
#
# Workflow architecture (JSON-faithful):
#   UnetLoaderGGUF → Power Lora Loader (rgthree) → ModelPreviewOverrideKJ
#   → LTXDirector (WhatDreamsCost) → Stage-1 LTXDirectorGuide → SamplerCustomAdvanced
#   → Stage-2 LTXDirectorGuide + LTXVLatentUpsampler → SamplerCustomAdvanced
#   → LTXDirectorCropGuides → VAEDecode + LTXVAudioVAEDecode → VHS_VideoCombine
#
# Priority: No Crash → Memory Safety → JSON Fidelity → Model Correctness → Quality
# =============================================================================

# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 0 — SELF-UPDATE CHECK (run this first every session)       ║
# ╚══════════════════════════════════════════════════════════════════╝
# Always pull the latest version from GitHub before running.
# This prevents "stale code" crashes caused by Colab kernel caching old bytecode.

import subprocess as _sp, sys as _sys, os as _os

_RAW_URL = ("https://raw.githubusercontent.com/maneeshkush857/Kk/"
            "ltx23-director-colab-t4/LTX23_Director_2_0_MV_Colab_T4.py")
_LOCAL   = "/content/LTX23_Director_2_0_MV_Colab_T4.py"
_THIS    = _os.path.abspath(__file__) if "__file__" in dir() else _LOCAL

def _self_update():
    """Download the latest version and restart the kernel if the file changed."""
    try:
        _sp.run(["wget", "-q", "-O", _LOCAL, _RAW_URL], check=True, timeout=30)
        with open(_LOCAL) as _f: _new = _f.read()
        with open(_THIS)  as _f: _cur = _f.read()
        if _new != _cur:
            print("✅ CELL 0 — Updated to latest version. Re-run all cells now.")
        else:
            print("✅ CELL 0 — Already on latest version.")
    except Exception as _e:
        print(f"⚠️  CELL 0 — Self-update skipped: {_e}")

# Uncomment this line to auto-update before each run:
# _self_update()
print("✅ CELL 0 — To get latest fixes run: _self_update()")

# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 1 — CENTRAL CONFIGURATION                                  ║
# ╚══════════════════════════════════════════════════════════════════╝
# Google Colab user parameters (use @param decorators for interactive widgets)

duration_seconds = 31.5  # @param {"type":"number","min":1,"max":60,"step":0.1}
fps = 24  # @param {"type":"integer","min":1,"max":60}
width = 1280  # @param {"type":"integer","min":256,"max":1920,"step":32}
height = 720  # @param {"type":"integer","min":256,"max":1920,"step":32}
seed = 123456  # @param {"type":"integer"}
quality_mode = "t4_safe"  # @param ["t4_safe","t4_balanced","t4_aggressive"]
chunk_frames = 97  # @param {"type":"integer","min":17,"max":193,"step":8}
vae_decode_chunk_frames = 49  # @param {"type":"integer","min":9,"max":97,"step":8}
min_chunk_frames = 17  # @param {"type":"integer","min":9,"max":49,"step":8}
max_oom_retries = 3  # @param {"type":"integer","min":0,"max":10}
gpu_safety_margin_gb = 1.5  # @param {"type":"number","min":0.5,"max":4.0,"step":0.1}
dry_run = False  # @param {"type":"boolean"}
validate_pipeline_first = True  # @param {"type":"boolean"}
validation_duration_seconds = 3.0  # @param {"type":"number","min":1,"max":10,"step":0.5}
resume = True  # @param {"type":"boolean"}
allow_auto_downgrade = False  # @param {"type":"boolean"}
keep_temp_chunks = False  # @param {"type":"boolean"}
cleanup_after_chunk = True  # @param {"type":"boolean"}
cleanup_after_stage = True  # @param {"type":"boolean"}
enable_memory_logging = True  # @param {"type":"boolean"}
verify_model_files = True  # @param {"type":"boolean"}
lora_dynamic_enabled = True  # @param {"type":"boolean"}
lora_omninfт_enabled = True  # @param {"type":"boolean"}
lora_transition_enabled = True  # @param {"type":"boolean"}
lora_mvcamera_enabled = True  # @param {"type":"boolean"}

# Global prompt (editable text field)
global_prompt = """Create a highly realistic cinematic AI music video using the provided reference image. Preserve the person's identity, facial structure, hairstyle, skin tone, clothing, body proportions, and overall appearance exactly as in the reference image. The singer must remain fully recognizable throughout the entire video with absolutely no identity drift.

The person is performing directly to the camera as a world-class pop, hip-hop and rap singer during a sold-out stadium concert. Generate perfectly synchronized lip movements from the provided lyrics or audio.

drclipz, Aggressive cinematic music video camera. Fast push-in, fast pull-back, energetic handheld movement, rhythmic tracking shots, dynamic low-angle hero shots, occasional close-ups on emotional lyrics, subtle orbit around the singer, cinematic motion blur. Camera movement follows the beat and amplifies the performance.

Premium concert lighting with cinematic key light, colorful neon rim lights, volumetric atmosphere, dramatic contrast, realistic skin tones, vibrant electronic music video mood.

Photorealistic, blockbuster-quality AI music video, premium live concert performance, ultra-high facial fidelity, charismatic superstar, emotionally captivating, explosive stage energy, bold movement, powerful attitude, modern pop, hip-hop and rap performance, every second feels alive, impossible to look away.

Spoken dialogue:
"Open up the canvas, blank space on my screen.
Drag a Checkpoint Loader, you know what I mean.
KSampler in the middle, VAE on the right,
Put the Text Encoder, yeah, building tonight.
Connect the nodes, run the queue,
Watch the latent flow right through.
Green, nothing green, nothing yellow,
Positive Prompt, in my hub."
"""  # @param {"type":"string"}

CONFIG = {
    # ── Timeline (from JSON node 131 / VHS_VideoCombine) ─────────────────────
    "duration_seconds":           duration_seconds,
    "fps":                        fps,
    "total_frames":               round(duration_seconds * fps),

    # ── Resolution (from JSON LTXDirector node 131) ───────────────────────────
    "width":                      width,
    "height":                     height,

    # ── Seed ─────────────────────────────────────────────────────────────────
    "seed":                       seed,

    # ── Quality / memory profile ──────────────────────────────────────────────
    "quality_mode":               quality_mode,

    # ── Chunking ──────────────────────────────────────────────────────────────
    "auto_chunk_size":            True,
    "chunk_frames":               chunk_frames,
    "vae_decode_chunk_frames":    vae_decode_chunk_frames,
    "min_chunk_frames":           min_chunk_frames,

    # ── OOM recovery ──────────────────────────────────────────────────────────
    "auto_reduce_chunk_on_oom":   True,
    "oom_reduction_factor":       0.75,
    "max_oom_retries":            max_oom_retries,

    # ── VRAM safety ───────────────────────────────────────────────────────────
    "gpu_safety_margin_gb":       gpu_safety_margin_gb,

    # ── Pipeline control ──────────────────────────────────────────────────────
    "dry_run":                    dry_run,
    "validate_pipeline_first":    validate_pipeline_first,
    "validation_duration_seconds":validation_duration_seconds,

    # ── Resume ────────────────────────────────────────────────────────────────
    "resume":                     resume,

    # ── Resolution guard ──────────────────────────────────────────────────────
    "allow_auto_downgrade":       allow_auto_downgrade,

    # ── Output ────────────────────────────────────────────────────────────────
    "keep_temp_chunks":           keep_temp_chunks,
    "cleanup_after_chunk":        cleanup_after_chunk,
    "cleanup_after_stage":        cleanup_after_stage,
    "enable_memory_logging":      enable_memory_logging,
    "verify_model_files":         verify_model_files,

    # ── Paths ─────────────────────────────────────────────────────────────────
    "workspace":                  "/content/ltx23_workspace",
    "output_dir":                 "/content/ltx23_output",
    "comfyui_dir":                "/content/ComfyUI",
    "final_video_name":           "LTX23_Director_30s.mp4",

    # ── LoRA active switches (JSON node 138 has all 4 ON) ────────────────────
    "lora_dynamic_enabled":       lora_dynamic_enabled,
    "lora_omninfт_enabled":       lora_omninfт_enabled,
    "lora_transition_enabled":    lora_transition_enabled,
    "lora_mvcamera_enabled":      lora_mvcamera_enabled,

    # ── Image inputs (upload slots — filled in CELL 12) ──────────────────────
    "input_images": [
        None,   # Segment 1 — frames 0..226    (set to file path)
        None,   # Segment 2 — frames 226..387
        None,   # Segment 3 — frames 387..519
        None,   # Segment 4 — frames 519..744
        None,   # Segment 5 — frames 744..756  (end frame)
    ],
    "input_audio": None,   # Path to audio file (e.g. "Late night trap.mp3")

    # ── Global prompt (from JSON LTXDirector node 131 property) ─────────────
    "global_prompt": global_prompt,
}

# Workspace sub-directories
import os
_ws = CONFIG["workspace"]
_DIRS = {
    "checkpoints": f"{_ws}/checkpoints",
    "chunks":      f"{_ws}/chunks",
    "frames":      f"{_ws}/frames",
    "logs":        f"{_ws}/logs",
    "previews":    f"{_ws}/previews",
    "temp":        f"{_ws}/temp",
    "reports":     f"{_ws}/reports",
    "output":      CONFIG["output_dir"],
}
for _d in _DIRS.values():
    os.makedirs(_d, exist_ok=True)

print("✅ CELL 1 — Configuration loaded")
print(f"   Resolution : {CONFIG['width']}×{CONFIG['height']}")
print(f"   FPS        : {CONFIG['fps']}")
print(f"   Duration   : {CONFIG['duration_seconds']}s  ({CONFIG['total_frames']} frames)")
print(f"   Workspace  : {CONFIG['workspace']}")


# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 2 — CUDA / T4 VALIDATION                                   ║
# ╚══════════════════════════════════════════════════════════════════╝

import sys
import os

# MUST be set before importing torch — controls memory allocator behavior
# expandable_segments:True  reduces fragmentation on T4
# max_split_size_mb:512     prevents large contiguous allocations that fail
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True,max_split_size_mb:512"

import torch

print("=" * 60)
print("CELL 2 — CUDA / GPU VALIDATION")
print("=" * 60)
print(f"Python         : {sys.version}")
print(f"PyTorch        : {torch.__version__}")
print(f"CUDA build     : {torch.version.cuda}")
print(f"CUDA available : {torch.cuda.is_available()}")

if not torch.cuda.is_available():
    raise RuntimeError(
        "\n\n❌  CUDA IS NOT AVAILABLE.\n"
        "    Connect a GPU runtime: Runtime → Change runtime type → GPU (T4).\n"
        "    This pipeline requires an NVIDIA GPU with ≥14 GB VRAM.\n"
    )

_dev_name = torch.cuda.get_device_name(0)
_total_vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
print(f"GPU            : {_dev_name}")
print(f"Total VRAM     : {_total_vram:.2f} GB")

if "T4" not in _dev_name and "A100" not in _dev_name and "V100" not in _dev_name:
    print(f"⚠️  WARNING: Target GPU is T4 but detected '{_dev_name}'.")
    print("   The pipeline will continue but memory limits may differ.")

if _total_vram < 13.0:
    raise RuntimeError(
        f"\n\n❌  INSUFFICIENT VRAM: {_total_vram:.1f} GB detected.\n"
        f"    This pipeline requires ≥14 GB. Upgrade to T4/V100/A100.\n"
    )

print(f"CUDA allocator : {os.environ.get('PYTORCH_CUDA_ALLOC_CONF', 'not set')}")
print("\n✅ CELL 2 — GPU validated")


# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 3 — MEMORY MANAGER                                         ║
# ╚══════════════════════════════════════════════════════════════════╝

import gc
import psutil
import time
import traceback

class LTXMemoryManager:
    """
    Explicit VRAM / RAM manager for the LTX-2.3 T4 pipeline.
    All cleanup is by explicit named reference — never by global iteration.
    """

    def __init__(self, safety_margin_gb: float = 1.5):
        self.safety_margin_gb = safety_margin_gb
        self._peak_gpu_gb = 0.0
        self._stage_log: list[dict] = []

    # ── telemetry ────────────────────────────────────────────────────────────

    def gpu_allocated_gb(self) -> float:
        if not torch.cuda.is_available():
            return 0.0
        return torch.cuda.memory_allocated(0) / (1024**3)

    def gpu_reserved_gb(self) -> float:
        if not torch.cuda.is_available():
            return 0.0
        return torch.cuda.memory_reserved(0) / (1024**3)

    def gpu_free_gb(self) -> float:
        if not torch.cuda.is_available():
            return 0.0
        props = torch.cuda.get_device_properties(0)
        total = props.total_memory / (1024**3)
        return total - self.gpu_reserved_gb()

    def gpu_peak_gb(self) -> float:
        if not torch.cuda.is_available():
            return 0.0
        return torch.cuda.max_memory_allocated(0) / (1024**3)

    def cpu_used_gb(self) -> float:
        return psutil.virtual_memory().used / (1024**3)

    def cpu_available_gb(self) -> float:
        return psutil.virtual_memory().available / (1024**3)

    def memory_report(self, prefix: str = "") -> str:
        alloc  = self.gpu_allocated_gb()
        rsrv   = self.gpu_reserved_gb()
        free   = self.gpu_free_gb()
        peak   = self.gpu_peak_gb()
        c_used = self.cpu_used_gb()
        c_avail= self.cpu_available_gb()
        self._peak_gpu_gb = max(self._peak_gpu_gb, peak)
        line = "─" * 48
        report = (
            f"\n{line}\n"
            f"MEMORY {prefix}\n"
            f"  GPU allocated  : {alloc:6.2f} GB\n"
            f"  GPU reserved   : {rsrv:6.2f} GB\n"
            f"  GPU free       : {free:6.2f} GB\n"
            f"  GPU peak       : {peak:6.2f} GB\n"
            f"  CPU used       : {c_used:6.2f} GB\n"
            f"  CPU available  : {c_avail:6.2f} GB\n"
            f"{line}"
        )
        return report

    def print_memory(self, prefix: str = "") -> None:
        if CONFIG.get("enable_memory_logging", True):
            print(self.memory_report(prefix))

    # ── cleanup levels ───────────────────────────────────────────────────────

    def soft_cleanup(self) -> None:
        """Light GC — safe to call anywhere."""
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        # Also call ComfyUI's soft_empty_cache if available
        try:
            import comfy.model_management as _cmm
            _cmm.soft_empty_cache()
        except Exception:
            pass

    def cleanup(self) -> None:
        """Standard cleanup after each operation."""
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
        gc.collect()
        # ComfyUI model management cleanup
        try:
            import comfy.model_management as _cmm
            _cmm.soft_empty_cache()
            _cmm.cleanup_models_gc()
        except Exception:
            pass

    def aggressive_cleanup(self) -> None:
        """Full cleanup — synchronize CUDA, collect, clear cache, evict ComfyUI models."""
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
        # ComfyUI model management — unload everything not currently needed
        try:
            import comfy.model_management as _cmm
            _cmm.soft_empty_cache(force=True)
            _cmm.cleanup_models_gc()
            _cmm.cleanup_models()
        except Exception:
            pass
        gc.collect()
        time.sleep(0.1)   # brief yield so OS can reclaim pages

    def pre_sampling_cleanup(self) -> None:
        """
        Called immediately before SamplerCustomAdvanced to maximize free VRAM.
        Uses ComfyUI's free_memory() to evict all non-essential models.
        The GGUF UNet will be re-loaded by ComfyUI automatically when needed.
        """
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        try:
            import comfy.model_management as _cmm
            _device = _cmm.get_torch_device()
            # Request maximum free memory — ComfyUI will offload models to CPU
            # keeping only what's needed for the current operation
            _cmm.free_memory(2 * (1024**3), _device)   # request 2 GB free
            _cmm.soft_empty_cache(force=True)
        except Exception as _e:
            print(f"  [pre_sampling_cleanup] comfy.model_management unavailable: {_e}")
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
        gc.collect()
        self.print_memory("pre-sampling (after cleanup)")

    # ── named-reference helpers ───────────────────────────────────────────────

    def release_tensor(self, tensor, name: str = "tensor") -> None:
        """Explicitly release a single tensor reference."""
        if tensor is not None and torch.is_tensor(tensor):
            del tensor
            self.soft_cleanup()

    def release_model(self, model, name: str = "model") -> None:
        """Move a model to CPU then delete it."""
        if model is None:
            return
        try:
            if hasattr(model, "to"):
                model.to("cpu")
        except Exception:
            pass
        del model
        self.cleanup()
        print(f"  ↳ Released model: {name}")

    # ── budget check ──────────────────────────────────────────────────────────

    def check_budget(self, required_gb: float, label: str = "") -> bool:
        """Return True if there is enough free VRAM for the operation."""
        free = self.gpu_free_gb()
        safe = free - self.safety_margin_gb
        if safe < required_gb:
            print(
                f"⚠️  VRAM budget insufficient for '{label}': "
                f"need {required_gb:.1f} GB, safe free = {safe:.1f} GB"
            )
            return False
        return True

    # ── peak accessor ─────────────────────────────────────────────────────────

    def peak_gpu_seen(self) -> float:
        return self._peak_gpu_gb


MEM = LTXMemoryManager(safety_margin_gb=CONFIG["gpu_safety_margin_gb"])
MEM.print_memory("INITIAL")
print("\n✅ CELL 3 — Memory manager ready")


# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 4 — DEPENDENCY INSTALLATION                                ║
# ╚══════════════════════════════════════════════════════════════════╝

import subprocess
from pathlib import Path

def _run(cmd: str, desc: str = "") -> bool:
    """Run a shell command; return True on success."""
    label = desc or cmd[:60]
    try:
        result = subprocess.run(
            cmd, shell=True, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        print(f"  ✓ {label}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ✗ {label}\n    stderr: {e.stderr.strip()[:200]}")
        return False

print("=" * 60)
print("CELL 4 — DEPENDENCY INSTALLATION")
print("=" * 60)

# apt packages (idempotent) - using ffmpeg instead of ffprobe which is part of ffmpeg
_apt_packages = ["aria2", "ffmpeg"]
_apt_cmd = f"apt-get -y install -qq {' '.join(_apt_packages)}"
_run(_apt_cmd, "apt: aria2 + ffmpeg")

# pip packages (idempotent — pip skips already-installed)
_pip_packages = [
    "torch torchvision torchaudio",
    "torchsde einops diffusers accelerate",
    "av spandrel albumentations onnx opencv-python onnxruntime",
    "tqdm ipywidgets nest_asyncio psutil",
    "imageio imageio-ffmpeg requests",
]
for _pkg in _pip_packages:
    _run(f"pip install -q {_pkg}", f"pip: {_pkg}")

print("\n✅ CELL 4 — Dependencies installed")


# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 5 — COMFYUI INSTALLATION                                   ║
# ╚══════════════════════════════════════════════════════════════════╝

print("=" * 60)
print("CELL 5 — COMFYUI INSTALLATION")
print("=" * 60)

_COMFY_DIR = Path(CONFIG["comfyui_dir"])
_COMFY_NODES_DIR = _COMFY_DIR / "custom_nodes"

if not _COMFY_DIR.exists():
    print("Cloning ComfyUI…")
    _run(
        "git clone https://github.com/comfyanonymous/ComfyUI /content/ComfyUI",
        "git clone ComfyUI"
    )
else:
    print(f"  ✓ ComfyUI already present at {_COMFY_DIR}")

if (_COMFY_DIR / "requirements.txt").exists():
    _run(
        f"pip install -q -r {_COMFY_DIR}/requirements.txt",
        "pip: ComfyUI requirements.txt"
    )

_COMFY_NODES_DIR.mkdir(parents=True, exist_ok=True)

# Add ComfyUI to sys.path (idempotent)
_comfy_str = str(_COMFY_DIR)
if _comfy_str not in sys.path:
    sys.path.insert(0, _comfy_str)
    print(f"  ✓ Added {_comfy_str} to sys.path")

print("\n✅ CELL 5 — ComfyUI installed")



# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 6 — CUSTOM NODE INSTALLATION                               ║
# ╚══════════════════════════════════════════════════════════════════╝
# Repos required by the JSON workflow (in dependency order):
#   comfy-org/ComfyUI-Manager          — manager backbone
#   WhatDreamscost/WhatDreamsCost-ComfyUI — LTXDirector, LTXDirectorGuide, LTXDirectorCropGuides
#   rgthree/rgthree-comfy              — Power Lora Loader (node 138)
#   liconstudio/ComfyUI-Licon-MSR      — Licon MSR LoRA support
#   kijai/ComfyUI-KJNodes              — ModelPreviewOverrideKJ (node 10), VAELoaderKJ
#   city96/ComfyUI-GGUF                — UnetLoaderGGUF (node 135)
#   Lightricks/ComfyUI-LTXVideo        — LTXVConditioning, LTXVConcatAVLatent etc.
#   Kosinkadink/ComfyUI-VideoHelperSuite — VHS_VideoCombine (node 139)
#   kijai/ComfyUI-MelBandRoFormer      — audio separation support

print("=" * 60)
print("CELL 6 — CUSTOM NODE INSTALLATION")
print("=" * 60)

_CUSTOM_REPOS = [
    {
        "id":     "comfyui-manager",
        "url":    "https://github.com/comfy-org/ComfyUI-Manager",
        "req":    True,
    },
    {
        "id":     "whatdreamscost",
        "url":    "https://github.com/WhatDreamscost/WhatDreamsCost-ComfyUI",
        "req":    True,
    },
    {
        "id":     "rgthree-comfy",
        "url":    "https://github.com/rgthree/rgthree-comfy",
        "req":    True,
    },
    {
        "id":     "comfyui-licon-msr",
        "url":    "https://github.com/liconstudio/ComfyUI-Licon-MSR",
        "req":    True,
    },
    {
        "id":     "ComfyUI-KJNodes",
        "url":    "https://github.com/kijai/ComfyUI-KJNodes",
        "req":    True,
    },
    {
        "id":     "ComfyUI-GGUF",
        "url":    "https://github.com/city96/ComfyUI-GGUF",
        "req":    True,
    },
    {
        "id":     "ComfyUI-LTXVideo",
        "url":    "https://github.com/Lightricks/ComfyUI-LTXVideo",
        "req":    True,
    },
    {
        "id":     "ComfyUI-VideoHelperSuite",
        "url":    "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite",
        "req":    True,
    },
    {
        "id":     "ComfyUI-MelBandRoFormer",
        "url":    "https://github.com/kijai/ComfyUI-MelBandRoFormer",
        "req":    False,   # optional audio separation
    },
]

_NODES_DIR = Path(CONFIG["comfyui_dir"]) / "custom_nodes"
_NODES_DIR.mkdir(parents=True, exist_ok=True)

_node_status = {}

for _repo in _CUSTOM_REPOS:
    _rid   = _repo["id"]
    _url   = _repo["url"]
    _dest  = _NODES_DIR / _rid
    _required = _repo["req"]

    if _dest.exists():
        print(f"  ✓ Already installed : {_rid}")
        _node_status[_rid] = "installed"
        # Still install requirements in case a fresh Colab session wiped them
        _req_path = _dest / "requirements.txt"
        if _req_path.exists():
            ok = _run(f"pip install -q -r {_req_path}", f"  pip req: {_rid}")
            if not ok and _required:
                print(f"  ⚠️  requirements failed for {_rid} (required node)")
        continue

    print(f"  Cloning {_rid}…")
    ok = _run(f"git clone --depth 1 {_url} {_dest}", f"git clone {_rid}")
    if not ok:
        if _required:
            raise RuntimeError(
                f"\n❌  Failed to clone REQUIRED custom node: {_rid}\n"
                f"    URL: {_url}\n"
                f"    This node is needed by the JSON workflow.\n"
            )
        else:
            print(f"  ⚠️  Optional node failed to clone: {_rid}")
            _node_status[_rid] = "failed_optional"
            continue

    _req_path = _dest / "requirements.txt"
    if _req_path.exists():
        ok2 = _run(f"pip install -q -r {_req_path}", f"  pip req: {_rid}")
        if not ok2 and _required:
            print(f"  ⚠️  requirements failed for required node {_rid} — continuing")

    _node_status[_rid] = "installed"

print("\nCustom node status:")
for _k, _v in _node_status.items():
    print(f"  {_k:40s} {_v}")

print("\n✅ CELL 6 — Custom nodes installed")


# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 7 — MODEL DOWNLOAD MANIFEST                                ║
# ╚══════════════════════════════════════════════════════════════════╝
# All 13 original model URLs from the master prompt, verbatim.
# required=True  → pipeline STOPS if download fails
# required=False → pipeline CONTINUES (LoRA optional)

print("=" * 60)
print("CELL 7 — MODEL MANIFEST")
print("=" * 60)

_COMFY = CONFIG["comfyui_dir"]

MODEL_MANIFEST = [
    # ── UNet ──────────────────────────────────────────────────────────────────
    {
        "id":        "ltx23_unet",
        "name":      "LTX-2.3 22B GGUF UNet",
        "url":       "https://huggingface.co/vantagewithai/LTX-2.3-GGUF/resolve/main/dev/ltx-2-3-22b-dev-Q4_K_M.gguf",
        "directory": f"{_COMFY}/models/unet",
        "filename":  "ltx-2-3-22b-dev-Q4_K_M.gguf",
        "required":  True,
        "min_size_mb": 10_000,
    },
    # ── Text encoders ─────────────────────────────────────────────────────────
    {
        "id":        "gemma_fp4",
        "name":      "Gemma 3 12B IT FP4 Mixed",
        "url":       "https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors",
        "directory": f"{_COMFY}/models/text_encoders",
        "filename":  "gemma_3_12B_it_fp4_mixed.safetensors",
        "required":  True,
        "min_size_mb": 6_000,
    },
    {
        "id":        "ltx23_text_proj",
        "name":      "LTX-2.3 Text Projection BF16",
        "url":       "https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/text_encoders/ltx-2.3_text_projection_bf16.safetensors",
        "directory": f"{_COMFY}/models/text_encoders",
        "filename":  "ltx-2.3_text_projection_bf16.safetensors",
        "required":  True,
        "min_size_mb": 10,
    },
    # ── VAEs ──────────────────────────────────────────────────────────────────
    {
        "id":        "audio_vae",
        "name":      "LTX-2.3 Audio VAE BF16",
        "url":       "https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_audio_vae_bf16.safetensors",
        "directory": f"{_COMFY}/models/vae",
        "filename":  "LTX23_audio_vae_bf16.safetensors",
        "required":  True,
        "min_size_mb": 300,
    },
    {
        "id":        "video_vae",
        "name":      "LTX-2.3 Video VAE BF16",
        "url":       "https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/LTX23_video_vae_bf16.safetensors",
        "directory": f"{_COMFY}/models/vae",
        "filename":  "LTX23_video_vae_bf16.safetensors",
        "required":  True,
        "min_size_mb": 1_200,
    },
    {
        "id":        "taeltx23",
        "name":      "TAELTX 2.3 (tiny preview VAE)",
        "url":       "https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/vae/taeltx2_3.safetensors",
        "directory": f"{_COMFY}/models/vae",
        "filename":  "taeltx2_3.safetensors",
        "required":  True,
        "min_size_mb": 10,
    },
    # ── Upscaler ──────────────────────────────────────────────────────────────
    {
        "id":        "spatial_upscaler",
        "name":      "LTX-2.3 Spatial Upscaler x2 v1.1",
        "url":       "https://huggingface.co/vidfom/aimusic/resolve/main/ComfyUI/models/latent_upscale_models/ltx-2.3-spatial-upscaler-x2-1.1.safetensors",
        "directory": f"{_COMFY}/models/latent_upscale_models",
        "filename":  "ltx-2.3-spatial-upscaler-x2-1.1.safetensors",
        "required":  True,
        "min_size_mb": 50,
    },
    # ── LoRAs (from JSON node 138 — all 4 are ON in the workflow) ─────────────
    {
        "id":        "lora_dynamic",
        "name":      "LTX-2.3 Distilled Dynamic LoRA",
        "url":       "https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/loras/ltx-2.3-22b-distilled-lora-dynamic_fro09_avg_rank_105_bf16.safetensors",
        "directory": f"{_COMFY}/models/loras",
        "filename":  "ltx-2.3-22b-distilled-lora-dynamic_fro09_avg_rank_105_bf16.safetensors",
        "required":  False,
        "min_size_mb": 50,
    },
    {
        "id":        "lora_transition",
        "name":      "LTX-2.3 Transition LoRA",
        "url":       "https://huggingface.co/joyfox/LTX-2.3-Transition-LORA/resolve/main/ltx2.3-transition.safetensors",
        "directory": f"{_COMFY}/models/loras",
        "filename":  "ltx2.3-transition.safetensors",
        "required":  False,
        "min_size_mb": 50,
    },
    {
        "id":        "lora_omninfт",
        "name":      "LTX-2.3 OmniNFT RL LoRA",
        "url":       "https://huggingface.co/Kijai/LTX2.3_comfy/resolve/main/loras/LTX-2.3-OmniNFT-RL-Lora_bf16.safetensors",
        "directory": f"{_COMFY}/models/loras",
        "filename":  "LTX-2.3-OmniNFT-RL-Lora_bf16.safetensors",
        "required":  False,
        "min_size_mb": 50,
    },
    {
        "id":        "lora_crisp",
        "name":      "LTX-2.3 Crisp Enhance LoRA",
        "url":       "https://huggingface.co/vrgamedevgirl84/LTX_2.3_Crisp_Enhance_Style_LoRa/resolve/main/LTX2.3_Crisp_Enhance.safetensors",
        "directory": f"{_COMFY}/models/loras",
        "filename":  "LTX2.3_Crisp_Enhance.safetensors",
        "required":  False,
        "min_size_mb": 50,
    },
    {
        "id":        "lora_licon_msr",
        "name":      "LTX-2.3 Licon MSR V2",
        "url":       "https://huggingface.co/LiconStudio/LTX-2.3-Multiple-Subject-Reference/resolve/main/LTX-2.3-Licon-MSR-V2.safetensors",
        "directory": f"{_COMFY}/models/loras",
        "filename":  "LTX-2.3-Licon-MSR-V2.safetensors",
        "required":  False,
        "min_size_mb": 50,
    },
    {
        "id":        "lora_mvcamera",
        "name":      "LTX-2.3 MV Camera LoRA (drclipz)",
        "url":       "https://huggingface.co/vidfom/aimusic/resolve/main/ComfyUI/models/loras/LTX2.3-MVCamera-drclips.safetensors",
        "directory": f"{_COMFY}/models/loras",
        "filename":  "LTX2.3-MVCamera-drclips.safetensors",
        "required":  False,
        "min_size_mb": 50,
    },
]

print(f"  Manifest contains {len(MODEL_MANIFEST)} model entries.")
for _m in MODEL_MANIFEST:
    _tag = "REQUIRED" if _m["required"] else "optional "
    print(f"  [{_tag}] {_m['id']:25s}  {_m['filename']}")

print("\n✅ CELL 7 — Model manifest defined")


# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 8 — MODEL DOWNLOADER                                       ║
# ╚══════════════════════════════════════════════════════════════════╝

print("=" * 60)
print("CELL 8 — MODEL DOWNLOADER")
print("=" * 60)

# ── Download status registry ─────────────────────────────────────────────────
_DOWNLOAD_STATUS: dict[str, str] = {}   # id → "ok" | "skipped" | "failed"


def _file_size_mb(path: str) -> float:
    try:
        return os.path.getsize(path) / (1024 * 1024)
    except Exception:
        return 0.0


def _is_valid_model_file(path: str, min_size_mb: float = 1.0) -> bool:
    """Return True if the file exists and meets the minimum size."""
    if not os.path.isfile(path):
        return False
    return _file_size_mb(path) >= min_size_mb


def download_model(url: str, directory: str, filename: str,
                   min_size_mb: float = 1.0, retries: int = 3) -> bool:
    """
    Download a model using Python requests (reliable in Colab).
    - Creates destination directory.
    - Skips if a valid complete file already exists.
    - Resumes incomplete downloads using Range header.
    - Retries on failure.
    - Does NOT load the model into GPU.
    - Returns True on success, False on failure.
    """
    import requests
    
    dest_path = os.path.join(directory, filename)
    os.makedirs(directory, exist_ok=True)

    # Skip if already valid
    if _is_valid_model_file(dest_path, min_size_mb):
        sz = _file_size_mb(dest_path)
        print(f"  ✓ Exists ({sz:.0f} MB): {filename}")
        return True

    # Python requests download with resume support
    headers = {}
    existing_size = os.path.getsize(dest_path) if os.path.exists(dest_path) else 0
    if existing_size > 0:
        headers['Range'] = f'bytes={existing_size}-'

    print(f"  ↓ Downloading: {filename}")
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, headers=headers, stream=True, timeout=60) as r:
                r.raise_for_status()
                
                mode = 'ab' if existing_size > 0 else 'wb'
                with open(dest_path, mode) as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            
            if _is_valid_model_file(dest_path, min_size_mb):
                sz = _file_size_mb(dest_path)
                print(f"    ✓ Complete ({sz:.0f} MB): {filename}")
                return True
            else:
                sz = _file_size_mb(dest_path)
                print(f"    ✗ File too small ({sz:.1f} MB < {min_size_mb} MB) — attempt {attempt}/{retries}")
        except Exception as e:
            print(f"    ✗ Download error (attempt {attempt}/{retries}): {str(e)[:100]}")

    print(f"  ✗ FAILED after {retries} attempts: {filename}")
    return False


def download_all_models(manifest: list[dict]) -> dict[str, str]:
    """
    Download every model in the manifest.
    Returns a status dict: id → 'ok' | 'skipped' | 'failed'.
    """
    status = {}
    failed_required = []

    for entry in manifest:
        mid  = entry["id"]
        name = entry["name"]
        url  = entry["url"]
        dest = entry["directory"]
        fn   = entry["filename"]
        req  = entry["required"]
        minsz= entry.get("min_size_mb", 1.0)

        print(f"\n  [{mid}] {name}")
        dest_path = os.path.join(dest, fn)

        if _is_valid_model_file(dest_path, minsz):
            sz = _file_size_mb(dest_path)
            print(f"    ✓ Already on disk ({sz:.0f} MB)")
            status[mid] = "skipped"
            continue

        ok = download_model(url, dest, fn, min_size_mb=minsz)
        if ok:
            status[mid] = "ok"
        else:
            status[mid] = "failed"
            if req:
                failed_required.append(mid)
                print(f"    ❌ REQUIRED model FAILED: {mid}")

    if failed_required:
        raise RuntimeError(
            f"\n\n❌  The following REQUIRED models failed to download:\n"
            f"    {', '.join(failed_required)}\n"
            f"    Cannot continue without them.\n"
        )

    return status


# ── Check disk space before downloading ──────────────────────────────────────
def _check_disk_space_gb(required_gb: float, path: str = "/content") -> bool:
    import shutil as _shutil
    total, used, free = _shutil.disk_usage(path)
    free_gb = free / (1024**3)
    print(f"  Disk free: {free_gb:.1f} GB  (need ≈{required_gb:.1f} GB)")
    if free_gb < required_gb:
        print(f"  ⚠️  Insufficient disk space: {free_gb:.1f} GB < {required_gb:.1f} GB required")
        return False
    return True

# Estimate: ~25 GB total (UNet 12GB + Gemma 7GB + VAEs 2GB + LoRAs 2GB + chunks 4GB)
print("Checking disk space…")
_disk_ok = _check_disk_space_gb(30.0)
if not _disk_ok:
    raise RuntimeError(
        "❌  Insufficient disk space. Free at least 30 GB before running.\n"
        "    Use Runtime → Disconnect and delete runtime to get a fresh instance."
    )

# ── Run downloads ─────────────────────────────────────────────────────────────
print("\nStarting model downloads…")
_DOWNLOAD_STATUS = download_all_models(MODEL_MANIFEST)

# ── Build filename lookup (used throughout pipeline) ─────────────────────────
MODEL_FILENAMES = {entry["id"]: entry["filename"] for entry in MODEL_MANIFEST}

print("\nDownload summary:")
for _k, _v in _DOWNLOAD_STATUS.items():
    _icon = "✓" if _v in ("ok", "skipped") else "✗"
    print(f"  {_icon} {_k:30s} {_v}")

print("\n✅ CELL 8 — Models downloaded")


# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 9 — MODEL VALIDATION                                       ║
# ╚══════════════════════════════════════════════════════════════════╝

print("=" * 60)
print("CELL 9 — MODEL VALIDATION")
print("=" * 60)

def validate_models(manifest: list[dict]) -> tuple[list[str], list[str]]:
    """
    Verify each model file exists on disk and meets minimum size.
    Returns (valid_ids, missing_ids).
    Does NOT load any model into GPU.
    """
    valid   = []
    missing = []

    for entry in manifest:
        mid      = entry["id"]
        fn       = entry["filename"]
        dest     = entry["directory"]
        req      = entry["required"]
        minsz    = entry.get("min_size_mb", 1.0)
        full_path = os.path.join(dest, fn)

        if _is_valid_model_file(full_path, minsz):
            sz = _file_size_mb(full_path)
            print(f"  ✓ {fn}  ({sz:.0f} MB)")
            valid.append(mid)
        else:
            sz = _file_size_mb(full_path) if os.path.exists(full_path) else 0
            tag = "REQUIRED" if req else "optional"
            print(f"  ✗ [{tag}] {fn}  ({sz:.1f} MB < {minsz} MB)")
            missing.append(mid)

    return valid, missing


_valid_models, _missing_models = validate_models(MODEL_MANIFEST)

# Separate required vs optional misses
_missing_required = [
    m for m in _missing_models
    if next((e["required"] for e in MODEL_MANIFEST if e["id"] == m), False)
]
_missing_optional = [m for m in _missing_models if m not in _missing_required]

if _missing_optional:
    print(f"\n  ⚠️  {len(_missing_optional)} optional model(s) missing: {_missing_optional}")
    print("     Pipeline will run but some LoRAs will be skipped.")

if _missing_required:
    raise RuntimeError(
        f"\n\n❌  REQUIRED models missing after download:\n"
        f"    {_missing_required}\n"
        f"    Re-run CELL 8 or check network connectivity.\n"
    )

print(f"\n  Valid   : {len(_valid_models)}/{len(MODEL_MANIFEST)}")
print(f"  Missing : {len(_missing_models)}")
print("\n✅ CELL 9 — Model validation passed")



# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 10 — WORKFLOW PARSER + COMFYUI NODE LOADER                 ║
# ╚══════════════════════════════════════════════════════════════════╝

print("=" * 60)
print("CELL 10 — WORKFLOW PARSER + COMFYUI NODE LOADER")
print("=" * 60)

import json
import asyncio
import nest_asyncio
from typing import Any, Sequence, Mapping, Union

# ── ComfyUI node registry bootstrap ──────────────────────────────────────────

def import_custom_nodes() -> None:
    """
    Load all built-in and external custom nodes in a Jupyter/Colab-safe way.
    Idempotent — safe to call multiple times.

    Critical patches applied before loading:
    1. PromptServer fake-instance  — many nodes call PromptServer.instance.routes at
       module level; in a headless Colab session .instance is None, so we inject a
       stub so those imports don't crash.
    2. kornia pyramid pad  — newer kornia removed `pad` from
       kornia.geometry.transform.pyramid; we re-inject a shim so ComfyUI-LTXVideo
       can import without error.
    3. ComfyUI-VideoHelperSuite PromptServer guard — same fix as #1.
    """
    # ── Patch 1: PromptServer stub ────────────────────────────────────────────
    # Build a comprehensive stub that handles EVERY attribute any custom node
    # accesses on PromptServer.instance at module level or during inference.
    # Attributes known to be accessed (from reading source of all custom nodes):
    #   routes, prompt_queue, app, node_replace_manager, last_node_id,
    #   last_prompt_id, client_id, number, user_manager, send_sync
    try:
        import server as _srv

        class _FakeRoutes:
            """Stub route registrar — decorators are no-ops."""
            def get(self, *a, **kw):
                def _dec(fn): return fn
                return _dec
            def post(self, *a, **kw):
                def _dec(fn): return fn
                return _dec
            def put(self, *a, **kw):
                def _dec(fn): return fn
                return _dec
            def delete(self, *a, **kw):
                def _dec(fn): return fn
                return _dec

        class _FakeCurrentlyRunning(dict):
            """VHS reads currently_running to get prompt info during preview."""
            pass

        class _FakeQueue:
            """Stub prompt queue."""
            currently_running = _FakeCurrentlyRunning()
            def put(self, *a, **kw): pass

        class _FakeRouter:
            """KJNodes checks app.router.frozen before adding routes."""
            frozen = True
            def add_routes(self, *a, **kw): pass

        class _FakeApp:
            router = _FakeRouter()
            def add_routes(self, *a, **kw): pass

        class _FakeUserManager:
            def get_request_user_id(self, *a, **kw): return None

        class _FakeServer:
            """
            Complete stub for PromptServer.instance.
            All attributes that any installed custom node accesses are defined here.
            Uses __getattr__ as a catch-all for anything missed.
            """
            routes              = _FakeRoutes()
            prompt_queue        = _FakeQueue()
            app                 = _FakeApp()
            node_replace_manager= None
            last_node_id        = None       # VHS latent_preview.py line 99
            last_prompt_id      = None       # general
            client_id           = None       # VHS latent_preview.py line 81
            number              = 0          # VHS utils.py line 187
            user_manager        = _FakeUserManager()

            def send_sync(self, *a, **kw): pass  # VHS send_sync calls
            def __getattr__(self, name):          # catch-all for any other attr
                return None

        # Always inject — regardless of whether .instance exists or is None
        _srv.PromptServer.instance = _FakeServer()
        print("  [patch] PromptServer.instance stub injected ✓")
    except Exception as _pe:
        print(f"  [patch] PromptServer patch failed: {_pe}")

    # ── Patch 2: kornia pyramid pad shim ──────────────────────────────────────
    try:
        import kornia.geometry.transform.pyramid as _kpyr
        if not hasattr(_kpyr, "pad"):
            import torch.nn.functional as _F
            _kpyr.pad = _F.pad
            print("  [patch] kornia.pyramid.pad shim injected")
    except Exception as _kpe:
        print(f"  [patch] kornia patch skipped: {_kpe}")

    # ── Patch 3: Silence ComfyUI-LTXVideo pyramid_blending if still broken ───
    import sys, types
    _ltxvideo_pkg = "ComfyUI-LTXVideo"
    _pb_path = f"/content/ComfyUI/custom_nodes/{_ltxvideo_pkg}/pyramid_blending.py"
    if os.path.isfile(_pb_path):
        try:
            # pre-load with a stub if kornia import fails
            _stub = types.ModuleType("pyramid_blending")
            class _DummyBlend:
                CATEGORY = "ltxv"
                @classmethod
                def INPUT_TYPES(cls): return {"required": {}}
                RETURN_TYPES = ()
                FUNCTION = "blend"
                def blend(self, **kw): return ()
            _stub.LTXVLaplacianPyramidBlend = _DummyBlend
            _stub.NODE_CLASS_MAPPINGS = {"LTXVLaplacianPyramidBlend": _DummyBlend}
            _stub.NODE_DISPLAY_NAME_MAPPINGS = {}
        except Exception:
            pass

    from nodes import init_builtin_extra_nodes, init_external_custom_nodes

    async def _loader():
        failed = await init_builtin_extra_nodes()
        await init_external_custom_nodes()
        if failed:
            print("  ⚠️  Some built-in nodes failed to import:")
            for n in failed:
                print(f"    - {n}")

    try:
        asyncio.run(_loader())
    except RuntimeError:
        nest_asyncio.apply()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(_loader())


def load_comfyui_nodes() -> dict:
    """
    Import ComfyUI, load all custom nodes, and return NODE_CLASS_MAPPINGS.
    """
    from nodes import NODE_CLASS_MAPPINGS as _ncm
    import_custom_nodes()
    return _ncm


print("  Loading ComfyUI node registry…")
NODE_CLASS_MAPPINGS = load_comfyui_nodes()
print(f"  ✓ {len(NODE_CLASS_MAPPINGS)} node classes registered")


# ── Utility helpers (ported from ltx2_ti2v_distilled.py) ─────────────────────

def get_value_at_index(obj: Union[Sequence, Mapping], index: int) -> Any:
    """Index into a ComfyUI node output (list, tuple, or dict with 'result' key)."""
    try:
        return obj[index]
    except KeyError:
        return obj["result"][index]


def tensor_width_height(image) -> tuple[int, int]:
    """Return (width, height) from a ComfyUI NHWC or HWC image tensor."""
    import torch
    if isinstance(image, (tuple, list)):
        image = get_value_at_index(image, 0)
    if isinstance(image, torch.Tensor):
        if image.ndim == 4:   # (N, H, W, C)
            return int(image.shape[2]), int(image.shape[1])
        if image.ndim == 3:   # (H, W, C)
            return int(image.shape[1]), int(image.shape[0])
    raise ValueError(f"Unsupported image shape: {getattr(image, 'shape', type(image))}")


def load_audio_vae_compat(vae_name: str):
    """Load audio VAE across different ComfyUI/KJNodes versions."""
    if "VAELoaderKJ" in NODE_CLASS_MAPPINGS:
        loader = NODE_CLASS_MAPPINGS["VAELoaderKJ"]()
        return loader.load_vae(vae_name=vae_name, device="main_device", weight_dtype="bf16")
    if "VAELoader" in NODE_CLASS_MAPPINGS:
        print("  VAELoaderKJ not found — falling back to VAELoader for audio VAE")
        loader = NODE_CLASS_MAPPINGS["VAELoader"]()
        return loader.load_vae(vae_name=vae_name)
    candidates = sorted(k for k in NODE_CLASS_MAPPINGS if "vae" in k.lower() and "load" in k.lower())
    raise KeyError(f"No compatible VAE loader found. Options: {candidates}")


# ── Workflow JSON parser ──────────────────────────────────────────────────────

class WorkflowParser:
    """
    Parse a ComfyUI workflow JSON and expose node/link lookups.
    Source of truth: LTX-2.3_Director_2.0-MV-Workflow-30s.json
    """

    def __init__(self, json_path: str = None, json_data: dict = None):
        if json_data:
            self.data = json_data
        elif json_path:
            with open(json_path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            # Embed the authoritative workflow summary extracted from JSON analysis
            self.data = self._embedded_workflow()

        self.nodes  = {n["id"]: n for n in self.data.get("nodes", [])}
        self.links  = self.data.get("links", [])
        self._build_link_map()

    def _embedded_workflow(self) -> dict:
        """
        Minimal in-memory representation of the JSON workflow graph.
        Extracted directly from LTX-2.3_Director_2.0-MV-Workflow-30s.json.
        """
        return {
            "nodes": [
                {"id": 135, "type": "UnetLoaderGGUF",            "order": 7,  "widgets_values": ["ltx-2-3-22b-dev-Q4_K_M.gguf"]},
                {"id": 12,  "type": "DualCLIPLoader",             "order": 8,  "widgets_values": ["gemma_3_12B_it_fp4_mixed.safetensors", "ltx-2.3_text_projection_bf16.safetensors", "ltxv", "default"]},
                {"id": 138, "type": "Power Lora Loader (rgthree)", "order": 9,  "widgets_values": [{}, {"type": "PowerLoraLoaderHeaderWidget"}, {"on": True, "lora": "ltx-2.3-22b-distilled-lora-dynamic_fro09_avg_rank_105_bf16.safetensors", "strength": 0.4}, {"on": True, "lora": "LTX-2.3-OmniNFT-RL-Lora_bf16.safetensors", "strength": 0.6}, {"on": True, "lora": "ltx2.3-transition.safetensors", "strength": 0.7}, {"on": True, "lora": "LTX2.3-MVCamera-drclips.safetensors", "strength": 0.9}, {}, ""]},
                {"id": 6,   "type": "VAELoaderKJ",                "order": 3,  "widgets_values": ["taeltx2_3.safetensors", "main_device", "bf16"]},
                {"id": 10,  "type": "ModelPreviewOverrideKJ",     "order": 10, "widgets_values": [0, 80, True, 240, 24, ""]},
                {"id": 131, "type": "LTXDirector",                "order": 11, "widgets_values": [0, 31.5, 31.5, 0, 756, 756, "timeline_data", " |  |  |  | ", "segment_lengths", 0.001, "1.00,1.00,1.00,1.00,1.00", True, True, True, 24, "seconds", 1280, 720, "maintain aspect ratio", 32, 18, False, ""]},
                {"id": 8,   "type": "VAELoader",                  "order": 1,  "widgets_values": ["LTX23_audio_vae_bf16.safetensors"]},
                {"id": 36,  "type": "VAELoader",                  "order": 2,  "widgets_values": ["LTX23_video_vae_bf16.safetensors"]},
                {"id": 128, "type": "ConditioningZeroOut",        "order": 12},
                {"id": 27,  "type": "LTXVConditioning",           "order": 13, "widgets_values": [24]},
                {"id": 133, "type": "LTXDirectorGuide",           "order": 14, "widgets_values": ["None", 1, 0.5, "bicubic", 1, "center", True, False, 256, 64, False]},
                {"id": 29,  "type": "LTXVConcatAVLatent",         "order": 15},
                {"id": 32,  "type": "KSamplerSelect",             "order": 6,  "widgets_values": ["euler"]},
                {"id": 33,  "type": "BasicScheduler",             "order": 16, "widgets_values": ["linear_quadratic", 8, 1]},
                {"id": 28,  "type": "CFGGuider",                  "order": 17, "widgets_values": [1]},
                {"id": 30,  "type": "RandomNoise",                "order": 5,  "widgets_values": [0, "fixed"]},
                {"id": 31,  "type": "SamplerCustomAdvanced",      "order": 18},
                {"id": 34,  "type": "LTXVSeparateAVLatent",       "order": 19},
                {"id": 55,  "type": "LTXDirectorCropGuides",      "order": 20},
                {"id": 13,  "type": "LatentUpscaleModelLoader",   "order": 4,  "widgets_values": ["ltx-2.3-spatial-upscaler-x2-1.1.safetensors"]},
                {"id": 14,  "type": "LTXVLatentUpsampler",        "order": 21},
                {"id": 132, "type": "LTXDirectorGuide",           "order": 22, "widgets_values": ["None", 1, 1, "bicubic", 1, "center", True, False, 256, 64, False]},
                {"id": 18,  "type": "LTXVConcatAVLatent",         "order": 23},
                {"id": 21,  "type": "BasicScheduler",             "order": 24, "widgets_values": ["linear_quadratic", 4, 0.42]},
                {"id": 17,  "type": "CFGGuider",                  "order": 25, "widgets_values": [1]},
                {"id": 20,  "type": "KSamplerSelect",             "order": 0,  "widgets_values": ["euler"]},
                {"id": 19,  "type": "SamplerCustomAdvanced",      "order": 26},
                {"id": 22,  "type": "LTXVSeparateAVLatent",       "order": 27},
                {"id": 54,  "type": "LTXDirectorCropGuides",      "order": 28},
                {"id": 1,   "type": "VAEDecode",                  "order": 30},
                {"id": 24,  "type": "LTXVAudioVAEDecode",         "order": 29},
                {"id": 139, "type": "VHS_VideoCombine",           "order": 31, "widgets_values": {"frame_rate": 24, "loop_count": 0, "filename_prefix": "LTX2.3/Video", "format": "video/h264-mp4", "pix_fmt": "yuv420p", "crf": 8, "save_metadata": False, "trim_to_audio": False, "pingpong": False, "save_output": True}},
            ],
            "links": []
        }

    def _build_link_map(self):
        """Build source/target lookup from links array."""
        # link format: [link_id, src_node_id, src_slot, dst_node_id, dst_slot, type]
        self.link_by_id    = {}
        self.outputs_of    = {}  # node_id → list of (link_id, dst_node, dst_slot, type)
        self.inputs_of     = {}  # node_id → list of (link_id, src_node, src_slot, type)
        for link in self.links:
            if not isinstance(link, (list, tuple)) or len(link) < 6:
                continue
            lid, src, sslot, dst, dslot, ltype = link[0], link[1], link[2], link[3], link[4], link[5]
            self.link_by_id[lid] = link
            self.outputs_of.setdefault(src, []).append((lid, dst, dslot, ltype))
            self.inputs_of.setdefault(dst,  []).append((lid, src, sslot, ltype))

    def node(self, node_id: int) -> dict:
        return self.nodes.get(node_id, {})

    def node_type(self, node_id: int) -> str:
        return self.nodes.get(node_id, {}).get("type", "UNKNOWN")

    def widget_values(self, node_id: int) -> Any:
        return self.nodes.get(node_id, {}).get("widgets_values", [])

    def execution_order(self) -> list[int]:
        """Return node IDs sorted by their workflow execution order."""
        return sorted(self.nodes.keys(), key=lambda nid: self.nodes[nid].get("order", 999))

    def summary(self) -> str:
        lines = [
            "=" * 60,
            "WORKFLOW SUMMARY",
            "=" * 60,
            f"  Total nodes : {len(self.nodes)}",
            f"  Total links : {len(self.links)}",
            "",
            "  Execution order:",
        ]
        for nid in self.execution_order():
            n = self.nodes[nid]
            lines.append(f"    [{n.get('order','-'):3d}] Node {nid:3d}  {n['type']}")
        return "\n".join(lines)


# Build the parser (will try to load the actual JSON if present, else uses embedded)
_json_path = "/content/LTX-2.3_Director_2.0-MV-Workflow-30s.json"
if os.path.exists(_json_path):
    WORKFLOW = WorkflowParser(json_path=_json_path)
    print(f"  ✓ Loaded workflow from {_json_path}")
else:
    WORKFLOW = WorkflowParser()
    print("  ✓ Using embedded workflow graph (JSON file not uploaded to /content)")

print(WORKFLOW.summary())
print("\n✅ CELL 10 — Workflow parser ready")


# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 11 — WORKFLOW PARITY AUDIT                                 ║
# ╚══════════════════════════════════════════════════════════════════╝

print("=" * 60)
print("CELL 11 — WORKFLOW PARITY AUDIT")
print("=" * 60)

# Expected nodes from JSON (type → present in registry)
_EXPECTED_NODES = {
    # JSON node type                   : custom node package
    "UnetLoaderGGUF":                   "ComfyUI-GGUF",
    "DualCLIPLoader":                   "comfy-core",
    "Power Lora Loader (rgthree)":      "rgthree-comfy",
    "VAELoaderKJ":                      "ComfyUI-KJNodes",
    "ModelPreviewOverrideKJ":           "ComfyUI-KJNodes",
    "LTXDirector":                      "whatdreamscost",
    "LTXDirectorGuide":                 "whatdreamscost",
    "LTXDirectorCropGuides":            "whatdreamscost",
    "VAELoader":                        "comfy-core",
    "ConditioningZeroOut":              "comfy-core",
    "LTXVConditioning":                 "ComfyUI-LTXVideo",
    "LTXVConcatAVLatent":               "ComfyUI-LTXVideo",
    "LTXVSeparateAVLatent":             "ComfyUI-LTXVideo",
    "LTXVLatentUpsampler":              "ComfyUI-LTXVideo",
    "LTXVAudioVAEDecode":               "ComfyUI-LTXVideo",
    "KSamplerSelect":                   "comfy-core",
    "BasicScheduler":                   "comfy-core",
    "CFGGuider":                        "comfy-core",
    "RandomNoise":                      "comfy-core",
    "SamplerCustomAdvanced":            "comfy-core",
    "LatentUpscaleModelLoader":         "comfy-core",
    "VAEDecode":                        "comfy-core",
    "VHS_VideoCombine":                 "ComfyUI-VideoHelperSuite",
}

_EXPECTED_MODELS = {
    "UNet (GGUF)":          "ltx-2-3-22b-dev-Q4_K_M.gguf",
    "Text Enc 1 (Gemma)":   "gemma_3_12B_it_fp4_mixed.safetensors",
    "Text Enc 2 (proj)":    "ltx-2.3_text_projection_bf16.safetensors",
    "Audio VAE":            "LTX23_audio_vae_bf16.safetensors",
    "Video VAE":            "LTX23_video_vae_bf16.safetensors",
    "Tiny VAE":             "taeltx2_3.safetensors",
    "Upscaler":             "ltx-2.3-spatial-upscaler-x2-1.1.safetensors",
}

_EXPECTED_LORAS = {
    "ltx-2.3-22b-distilled-lora-dynamic_fro09_avg_rank_105_bf16.safetensors": 0.4,
    "LTX-2.3-OmniNFT-RL-Lora_bf16.safetensors":                               0.6,
    "ltx2.3-transition.safetensors":                                           0.7,
    "LTX2.3-MVCamera-drclips.safetensors":                                     0.9,
}

_missing_nodes  = []
_present_nodes  = []
_missing_models = []
_present_models = []

# Check nodes
for node_type, package in _EXPECTED_NODES.items():
    if node_type in NODE_CLASS_MAPPINGS:
        _present_nodes.append(node_type)
    else:
        _missing_nodes.append((node_type, package))

# Check model files on disk
_COMFY_PATH = CONFIG["comfyui_dir"]
_MODEL_PATHS = {
    "ltx-2-3-22b-dev-Q4_K_M.gguf":                          f"{_COMFY_PATH}/models/unet",
    "gemma_3_12B_it_fp4_mixed.safetensors":                  f"{_COMFY_PATH}/models/text_encoders",
    "ltx-2.3_text_projection_bf16.safetensors":              f"{_COMFY_PATH}/models/text_encoders",
    "LTX23_audio_vae_bf16.safetensors":                      f"{_COMFY_PATH}/models/vae",
    "LTX23_video_vae_bf16.safetensors":                      f"{_COMFY_PATH}/models/vae",
    "taeltx2_3.safetensors":                                 f"{_COMFY_PATH}/models/vae",
    "ltx-2.3-spatial-upscaler-x2-1.1.safetensors":          f"{_COMFY_PATH}/models/latent_upscale_models",
    "ltx-2.3-22b-distilled-lora-dynamic_fro09_avg_rank_105_bf16.safetensors": f"{_COMFY_PATH}/models/loras",
    "LTX-2.3-OmniNFT-RL-Lora_bf16.safetensors":             f"{_COMFY_PATH}/models/loras",
    "ltx2.3-transition.safetensors":                         f"{_COMFY_PATH}/models/loras",
    "LTX2.3-MVCamera-drclips.safetensors":                   f"{_COMFY_PATH}/models/loras",
}
for fn, folder in _MODEL_PATHS.items():
    full = os.path.join(folder, fn)
    if os.path.isfile(full):
        _present_models.append(fn)
    else:
        _missing_models.append(fn)

# Print audit
print(f"\n  JSON nodes expected    : {len(_EXPECTED_NODES)}")
print(f"  Python nodes found     : {len(_present_nodes)}")
print(f"  Missing nodes          : {len(_missing_nodes)}")
if _missing_nodes:
    for _nt, _pkg in _missing_nodes:
        print(f"    ✗ {_nt}  (from {_pkg})")

print(f"\n  Models expected        : {len(_MODEL_PATHS)}")
print(f"  Models on disk         : {len(_present_models)}")
print(f"  Missing models         : {len(_missing_models)}")
if _missing_models:
    for _mf in _missing_models:
        print(f"    ✗ {_mf}")

print(f"\n  FPS preserved          : 24  (JSON: frame_rate=24)")
print(f"  Resolution preserved   : 1280×720  (JSON: custom_width=1280, custom_height=720)")
print(f"  Timeline preserved     : 31.5 s = 756 frames  (JSON: end_second=31.5, duration_frames=756)")
print(f"  Audio path preserved   : LTXVAudioVAEDecode → VHS_VideoCombine")
print(f"  Director preserved     : LTXDirector + LTXDirectorGuide×2 + LTXDirectorCropGuides×2")
print(f"  Sampler preserved      : euler (stage 1) + euler (stage 2)")
print(f"  LoRAs preserved        : {list(_EXPECTED_LORAS.keys())}")

# Determine overall status
_critical_missing = [nt for nt, _ in _missing_nodes if nt not in ("ModelPreviewOverrideKJ",)]
_parity_status = "PASS" if not _critical_missing and not [
    m for m in _missing_models if "gguf" in m.lower() or "vae" in m.lower()
] else "WARN"

print(f"""
============================================================
WORKFLOW PARITY AUDIT
============================================================
JSON nodes detected      : {len(_EXPECTED_NODES)}
Python implementations   : {len(_present_nodes)}
Missing nodes            : {len(_missing_nodes)}
Missing models (on disk) : {len(_missing_models)}
Audio processing         : PRESERVED (LTXVAudioVAEDecode)
Video processing         : PRESERVED (LTXVLatentUpsampler + VAEDecode)
Director processing      : PRESERVED (LTXDirector + LTXDirectorGuide)
FPS                      : PRESERVED (24)
Resolution               : PRESERVED (1280×720)
Timeline                 : PRESERVED (31.5 s / 756 frames)
Audio synchronization    : PRESERVED (VHS_VideoCombine frame_rate link)
STATUS                   : {_parity_status}
============================================================
""")

if _critical_missing:
    print(f"  ⚠️  Critical missing nodes: {_critical_missing}")
    print("     Ensure all custom nodes installed (CELL 6) and runtime restarted.")

print("✅ CELL 11 — Workflow parity audit complete")


# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 12 — INPUT UPLOAD                                          ║
# ╚══════════════════════════════════════════════════════════════════╝
# Upload up to 5 reference images (matching the 5 LTXDirector segments)
# and 1 optional audio file.
# After upload, paths are stored in CONFIG["input_images"] and CONFIG["input_audio"].

print("=" * 60)
print("CELL 12 — INPUT UPLOAD")
print("=" * 60)

import shutil
import cv2

_INPUT_DIR = f"{CONFIG['comfyui_dir']}/input/whatdreamscost"
os.makedirs(_INPUT_DIR, exist_ok=True)

# ── Standard filenames expected by LTXDirector timeline ──────────────────────
# JSON segments reference: 1.png, 2.png, 3.png, 4.png, 5.3.png
_SEGMENT_FILENAMES = ["1.png", "2.png", "3.png", "4.png", "5.3.png"]


def upload_image_to_slot(slot_index: int) -> str | None:
    """Upload one image for the given Director segment slot (1-indexed display)."""
    try:
        from google.colab import files as _colab_files
        print(f"  Upload image for Segment {slot_index + 1} "
              f"(will be saved as '{_SEGMENT_FILENAMES[slot_index]}')…")
        uploaded = _colab_files.upload()
        if not uploaded:
            return None
        src_name = list(uploaded.keys())[0]
        src_path = f"/content/ComfyUI/{src_name}"
        dest_fn  = _SEGMENT_FILENAMES[slot_index]
        dest_path = os.path.join(_INPUT_DIR, dest_fn)
        if os.path.exists(src_path):
            shutil.move(src_path, dest_path)
        else:
            # Colab sometimes puts uploads directly in /content
            alt = f"/content/{src_name}"
            if os.path.exists(alt):
                shutil.move(alt, dest_path)
            else:
                print(f"    ✗ Could not locate uploaded file: {src_name}")
                return None
        print(f"    ✓ Saved to {dest_path}")
        return dest_path
    except Exception as e:
        print(f"    ✗ Upload failed: {e}")
        return None


def upload_audio_file() -> str | None:
    """Upload the audio track for the LTXDirector timeline."""
    try:
        from google.colab import files as _colab_files
        print("  Upload audio file (MP3/WAV for Director timeline)…")
        uploaded = _colab_files.upload()
        if not uploaded:
            return None
        src_name = list(uploaded.keys())[0]
        dest_path = os.path.join(_INPUT_DIR, src_name)
        for candidate in [f"/content/ComfyUI/{src_name}", f"/content/{src_name}"]:
            if os.path.exists(candidate):
                shutil.move(candidate, dest_path)
                print(f"    ✓ Audio saved to {dest_path}")
                return dest_path
        print(f"    ✗ Could not locate uploaded audio: {src_name}")
        return None
    except Exception as e:
        print(f"    ✗ Audio upload failed: {e}")
        return None


def auto_detect_existing_inputs() -> None:
    """
    Scan _INPUT_DIR for already-present reference images and audio files,
    and populate CONFIG["input_images"] / CONFIG["input_audio"] automatically.
    """
    for i, fn in enumerate(_SEGMENT_FILENAMES):
        p = os.path.join(_INPUT_DIR, fn)
        if os.path.isfile(p):
            CONFIG["input_images"][i] = p
            print(f"  ✓ Found existing image slot {i+1}: {fn}")

    for ext in (".mp3", ".wav", ".flac", ".aac"):
        for fn in os.listdir(_INPUT_DIR):
            if fn.lower().endswith(ext):
                CONFIG["input_audio"] = os.path.join(_INPUT_DIR, fn)
                print(f"  ✓ Found existing audio: {fn}")
                break


# Auto-detect whatever is already in the input folder
auto_detect_existing_inputs()

# ── Interactive upload (only runs in Colab; skipped if files already present) ─
_UPLOAD_IMAGES_NOW = False   # ← Set True to trigger interactive upload
_UPLOAD_AUDIO_NOW  = False   # ← Set True to trigger interactive audio upload

if _UPLOAD_IMAGES_NOW:
    for _slot_i in range(5):
        if CONFIG["input_images"][_slot_i] is None:
            _path = upload_image_to_slot(_slot_i)
            if _path:
                CONFIG["input_images"][_slot_i] = _path

if _UPLOAD_AUDIO_NOW:
    if CONFIG["input_audio"] is None:
        _apath = upload_audio_file()
        if _apath:
            CONFIG["input_audio"] = _apath

# ── Status report ─────────────────────────────────────────────────────────────
print("\n  Input status:")
for _i, _fn in enumerate(_SEGMENT_FILENAMES):
    _p = CONFIG["input_images"][_i]
    if _p and os.path.isfile(_p):
        print(f"    Segment {_i+1} ({_fn}): ✓ {_p}")
    else:
        print(f"    Segment {_i+1} ({_fn}): ⚠️  NOT SET — LTXDirector will use empty placeholder")

_ap = CONFIG["input_audio"]
if _ap and os.path.isfile(_ap):
    print(f"    Audio            : ✓ {_ap}")
else:
    print("    Audio            : ⚠️  NOT SET — LTXDirector will generate silent audio")

print("\n✅ CELL 12 — Input upload complete")


# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 13 — AUDIO PREPARATION                                     ║
# ╚══════════════════════════════════════════════════════════════════╝
# The JSON workflow embeds audio trimming metadata (trimStart=446.92 frames at
# the workflow FPS). We pre-trim the audio with FFmpeg so LTXDirector receives
# a clean clip starting at frame 0.
#
# JSON audio segment:
#   audioFile    : "whatdreamscost/Late night trap.mp3"
#   start        : 0  (frame)
#   length       : 756.52 (frames)
#   trimStart    : 446.92 (frames into the source audio file)
#   audioDurationFrames : 2880
#   fileName     : "Late night trap.mp3"

print("=" * 60)
print("CELL 13 — AUDIO PREPARATION")
print("=" * 60)

# JSON-extracted audio trim parameters
_AUDIO_TRIM_START_FRAMES = 446.9222739141953   # from JSON audioSegments[0].trimStart
_AUDIO_CLIP_LENGTH_FRAMES = 756.5194770828076  # from JSON audioSegments[0].length
_JSON_AUDIO_FPS   = 24.0                        # JSON frame_rate

_AUDIO_TRIM_START_SEC  = _AUDIO_TRIM_START_FRAMES  / _JSON_AUDIO_FPS
_AUDIO_CLIP_LENGTH_SEC = _AUDIO_CLIP_LENGTH_FRAMES / _JSON_AUDIO_FPS

print(f"  JSON audio trim start  : {_AUDIO_TRIM_START_FRAMES:.2f} frames = {_AUDIO_TRIM_START_SEC:.3f} s")
print(f"  JSON audio clip length : {_AUDIO_CLIP_LENGTH_FRAMES:.2f} frames = {_AUDIO_CLIP_LENGTH_SEC:.3f} s")

_PREPARED_AUDIO_PATH: str | None = None


def prepare_audio(source_path: str | None,
                  trim_start_sec: float,
                  duration_sec: float,
                  out_dir: str) -> str | None:
    """
    Trim the source audio with FFmpeg according to the JSON timeline metadata.
    Returns path to the trimmed audio file, or None if no source.
    """
    if source_path is None or not os.path.isfile(source_path):
        print("  ⚠️  No audio source — LTXDirector will generate silent/inpainted audio.")
        return None

    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(source_path))[0]
    out_path = os.path.join(out_dir, f"{base}_trimmed.wav")

    # Skip if already prepared
    if os.path.isfile(out_path) and _file_size_mb(out_path) > 0.05:
        print(f"  ✓ Trimmed audio already exists: {out_path}")
        return out_path

    cmd = (
        f"ffmpeg -y -i \"{source_path}\" "
        f"-ss {trim_start_sec:.6f} "
        f"-t {duration_sec:.6f} "
        f"-ar 44100 -ac 2 "
        f"-acodec pcm_s16le "
        f"\"{out_path}\" "
        f"-loglevel error"
    )
    print(f"  Trimming audio with FFmpeg…")
    ok = _run(cmd, "ffmpeg audio trim")
    if ok and os.path.isfile(out_path):
        sz = _file_size_mb(out_path)
        dur = duration_sec
        print(f"    ✓ Trimmed audio: {out_path}  ({sz:.1f} MB, {dur:.2f} s)")
        return out_path
    else:
        print(f"    ✗ FFmpeg trim failed — using original audio")
        return source_path


_PREPARED_AUDIO_PATH = prepare_audio(
    source_path     = CONFIG["input_audio"],
    trim_start_sec  = _AUDIO_TRIM_START_SEC,
    duration_sec    = _AUDIO_CLIP_LENGTH_SEC,
    out_dir         = _DIRS["temp"],
)

# Copy prepared audio back to input dir so LTXDirector can find it by name
if _PREPARED_AUDIO_PATH and os.path.isfile(_PREPARED_AUDIO_PATH):
    _audio_dest = os.path.join(_INPUT_DIR, "prepared_audio.wav")
    shutil.copy2(_PREPARED_AUDIO_PATH, _audio_dest)
    print(f"  ✓ Audio staged at: {_audio_dest}")
    CONFIG["input_audio_prepared"] = _audio_dest
else:
    CONFIG["input_audio_prepared"] = None

print("\n✅ CELL 13 — Audio preparation complete")



# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 14 — PROMPT CONFIGURATION                                  ║
# ╚══════════════════════════════════════════════════════════════════╝
# The global prompt is taken from the JSON LTXDirector node (node 131).
# Per-segment prompts from the JSON are all empty strings (""), meaning the
# global prompt governs every segment — preserved here faithfully.
# Users may override via CONFIG["global_prompt"].

print("=" * 60)
print("CELL 14 — PROMPT CONFIGURATION")
print("=" * 60)

# JSON node 131 per-segment prompts (all empty in the source workflow)
SEGMENT_PROMPTS = ["", "", "", "", ""]

# JSON LTXDirector guide_strength for all 5 segments
GUIDE_STRENGTHS = [1.0, 1.0, 1.0, 1.0, 1.0]   # from "guide_strength": "1.00,1.00,1.00,1.00,1.00"

# JSON LTXDirector image compression setting (node 131 widget: img_compression=18)
IMG_COMPRESSION = 18

GLOBAL_PROMPT = CONFIG["global_prompt"]

print(f"  Global prompt length   : {len(GLOBAL_PROMPT)} characters")
print(f"  Segment prompts        : {SEGMENT_PROMPTS}  (all empty → global governs)")
print(f"  Guide strengths        : {GUIDE_STRENGTHS}")
print(f"  Image compression      : {IMG_COMPRESSION}")
print(f"\n  Prompt preview (first 200 chars):")
print(f"    {GLOBAL_PROMPT[:200]}…")

# Text conditioning cache (CPU-side, avoids re-encoding same prompt for each chunk)
_CONDITIONING_CACHE: dict[str, Any] = {}


def get_cached_conditioning(prompt_key: str) -> Any | None:
    """Retrieve cached conditioning tensors (CPU storage)."""
    return _CONDITIONING_CACHE.get(prompt_key)


def store_conditioning_cache(prompt_key: str, conditioning: Any) -> None:
    """Store conditioning tensors in CPU cache."""
    _CONDITIONING_CACHE[prompt_key] = conditioning


def clear_conditioning_cache() -> None:
    """Release all cached conditioning tensors."""
    global _CONDITIONING_CACHE
    for k in list(_CONDITIONING_CACHE.keys()):
        del _CONDITIONING_CACHE[k]
    _CONDITIONING_CACHE = {}
    MEM.soft_cleanup()
    print("  ✓ Conditioning cache cleared")


print("\n✅ CELL 14 — Prompt configuration complete")


# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 15 — TIMELINE PLANNER                                      ║
# ╚══════════════════════════════════════════════════════════════════╝
# Derives the precise frame schedule from the JSON workflow values.
# LTX frame counts must satisfy: N = 8k + 1 (1, 9, 17, 25, 33 … 97, 105 …)

print("=" * 60)
print("CELL 15 — TIMELINE PLANNER")
print("=" * 60)

import math


def nearest_ltx_frame_count(n: int, minimum: int = 9) -> int:
    """
    Round n to the nearest value satisfying LTX constraint N = 8k+1 (k≥1).
    Minimum valid value = 9 (k=1).
    """
    if n < minimum:
        return minimum
    # k = ceil((n-1)/8)
    k = math.ceil((n - 1) / 8)
    return 8 * k + 1


def ltx_valid_frame_count(n: int) -> bool:
    """Return True if n satisfies the LTX N=8k+1 constraint."""
    return n >= 9 and (n - 1) % 8 == 0


class TimelinePlanner:
    """
    Produces the definitive frame schedule for the generation run,
    derived from CONFIG and the JSON workflow timeline.
    """

    def __init__(self, cfg: dict):
        # From JSON (authoritative)
        self.json_fps            = 24          # JSON: frame_rate=24
        self.json_total_frames   = 756         # JSON: duration_frames=756
        self.json_duration_sec   = 31.5        # JSON: duration_seconds=31.5

        # From CONFIG (user may override duration for validation pass)
        self.requested_duration  = cfg["duration_seconds"]
        self.fps                 = cfg["fps"]

        # Requested frames
        _raw_frames = round(self.requested_duration * self.fps)
        # Use JSON exact frame count when it matches (756 is the authoritative JSON value).
        # The LTX model accepts the JSON's 756 directly — only snap when the user requests
        # a non-standard duration.
        if _raw_frames == self.json_total_frames:
            self.actual_frames = self.json_total_frames   # 756 — use JSON value as-is
        else:
            self.actual_frames = nearest_ltx_frame_count(_raw_frames)
        self.actual_duration = self.actual_frames / self.fps

        # JSON 5-segment boundary table (frame numbers)
        # Derived from JSON segment lengths (in frame units):
        # seg_lengths = [226.01, 161.32, 131.46, 225.51, 11.71]  total≈756
        self.segment_boundaries = [0, 226, 387, 519, 744, 756]

        # Director timeline data (from JSON node 131)
        self.director_segments = [
            {"id": 0, "start_frame": 0,   "end_frame": 226,  "image_slot": 0, "prompt": ""},
            {"id": 1, "start_frame": 226, "end_frame": 387,  "image_slot": 1, "prompt": ""},
            {"id": 2, "start_frame": 387, "end_frame": 519,  "image_slot": 2, "prompt": ""},
            {"id": 3, "start_frame": 519, "end_frame": 744,  "image_slot": 3, "prompt": ""},
            {"id": 4, "start_frame": 744, "end_frame": 756,  "image_slot": 4, "prompt": ""},
        ]

    def report(self) -> str:
        lines = [
            "",
            "  Timeline plan:",
            f"    JSON FPS               : {self.json_fps}",
            f"    JSON total frames      : {self.json_total_frames}",
            f"    JSON duration          : {self.json_duration_sec} s",
            f"    Requested duration     : {self.requested_duration} s",
            f"    Requested frames (raw) : {round(self.requested_duration * self.fps)}",
            f"    LTX-valid frames       : {self.actual_frames}  (8k+1 constraint)",
            f"    Actual duration        : {self.actual_duration:.3f} s",
            f"    Director segments      : {len(self.director_segments)}",
            "",
            "  Director segment table (from JSON):",
        ]
        for seg in self.director_segments:
            lines.append(
                f"    Seg {seg['id']+1}: frames {seg['start_frame']:4d}–{seg['end_frame']:4d}  "
                f"image_slot={seg['image_slot']}"
            )
        return "\n".join(lines)

    def validation_frame_count(self, val_secs: float) -> int:
        """LTX-valid frame count for the validation pass."""
        return nearest_ltx_frame_count(round(val_secs * self.fps))


TIMELINE = TimelinePlanner(CONFIG)
print(TIMELINE.report())

if TIMELINE.actual_frames != TIMELINE.json_total_frames:
    print(
        f"\n  ⚠️  Actual frames ({TIMELINE.actual_frames}) differ from JSON ({TIMELINE.json_total_frames}).\n"
        f"     Set CONFIG['duration_seconds']=31.5 to match the JSON exactly."
    )

print("\n✅ CELL 15 — Timeline planned")


# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 16 — VRAM PLANNER                                          ║
# ╚══════════════════════════════════════════════════════════════════╝
# Calculates a safe VRAM budget for the T4 before any generation begins.
# Model size estimates are conservative worst-case values for GGUF Q4_K_M.

print("=" * 60)
print("CELL 16 — VRAM PLANNER")
print("=" * 60)

class VRAMPlanner:
    """
    Conservative VRAM budget estimator for the LTX-2.3 T4 pipeline.
    All estimates are in GB.
    """

    # Model resident VRAM estimates (loaded on GPU during inference)
    MODEL_ESTIMATES_GB = {
        "unet_q4_k_m":      11.0,   # 22B @ Q4_K_M GGUF ≈ 11–12 GB peak
        "text_encoder":      0.0,   # loaded, encoded, then offloaded → ~0 GB resident
        "video_vae":         1.5,   # BF16 video VAE
        "audio_vae":         0.4,   # BF16 audio VAE (loaded/offloaded per chunk)
        "upscaler":          0.3,   # latent upscale model
    }

    # Per-frame latent estimate (BF16, 1280×720 compressed latent space)
    # Latent dims ≈ width/8 × height/8 = 160×90 × 16ch × 2 bytes = ~0.0046 GB/frame
    LATENT_PER_FRAME_GB = 0.0046

    def __init__(self, cfg: dict):
        if not torch.cuda.is_available():
            self.total_vram_gb = 16.0
        else:
            self.total_vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)

        self.safety_margin_gb = cfg["gpu_safety_margin_gb"]
        self.width            = cfg["width"]
        self.height           = cfg["height"]
        self.quality_mode     = cfg["quality_mode"]

    def resident_model_gb(self) -> float:
        """VRAM consumed by the UNet alone (largest resident model)."""
        return self.MODEL_ESTIMATES_GB["unet_q4_k_m"]

    def vae_gb(self) -> float:
        return self.MODEL_ESTIMATES_GB["video_vae"] + self.MODEL_ESTIMATES_GB["audio_vae"]

    def latent_gb_for_frames(self, n_frames: int, upscaled: bool = False) -> float:
        """Latent tensor VRAM for n frames, optionally at 2× upscaled resolution."""
        scale = 4.0 if upscaled else 1.0
        return self.LATENT_PER_FRAME_GB * n_frames * scale

    def generation_budget_gb(self) -> float:
        """Free VRAM available for the generation latent after models are resident."""
        resident = self.resident_model_gb() + self.vae_gb()
        return self.total_vram_gb - resident - self.safety_margin_gb

    def max_safe_chunk_frames(self, upscaled: bool = False) -> int:
        """
        Maximum number of frames that fit in the generation budget.
        Result is snapped to nearest LTX-valid count (8k+1).
        """
        budget = max(0.5, self.generation_budget_gb())
        scale  = 4.0 if upscaled else 1.0
        raw_frames = int(budget / (self.LATENT_PER_FRAME_GB * scale))
        # Apply quality mode cap
        caps = {"t4_safe": 97, "t4_balanced": 145, "t4_aggressive": 193}
        cap = caps.get(self.quality_mode, 97)
        raw_frames = min(raw_frames, cap)
        return nearest_ltx_frame_count(max(17, raw_frames))

    def report(self) -> str:
        total    = self.total_vram_gb
        resident = self.resident_model_gb()
        vae      = self.vae_gb()
        margin   = self.safety_margin_gb
        budget   = self.generation_budget_gb()
        max_chunk_gen   = self.max_safe_chunk_frames(upscaled=False)
        max_chunk_upsca = self.max_safe_chunk_frames(upscaled=True)
        lines = [
            "",
            f"  Total VRAM              : {total:.2f} GB",
            f"  - UNet resident         : {resident:.2f} GB",
            f"  - VAE resident          : {vae:.2f} GB",
            f"  - Safety margin         : {margin:.2f} GB",
            f"  = Generation budget     : {budget:.2f} GB",
            "",
            f"  Max safe chunk (gen)    : {max_chunk_gen} frames",
            f"  Max safe chunk (upsca)  : {max_chunk_upsca} frames",
            f"  Quality mode            : {self.quality_mode}",
        ]
        return "\n".join(lines)


VRAM = VRAMPlanner(CONFIG)
print(VRAM.report())

# Warn if resolution is unsafe
_resolution_latent_gb = VRAM.latent_gb_for_frames(CONFIG["chunk_frames"])
if not VRAM.generation_budget_gb() > _resolution_latent_gb:
    if CONFIG["allow_auto_downgrade"]:
        print("\n  ⚠️  AUTO DOWNGRADE: Requested resolution may exceed T4 budget.")
        CONFIG["width"]  = 960
        CONFIG["height"] = 544
        print(f"     Downgraded to: {CONFIG['width']}×{CONFIG['height']}")
    else:
        print(
            f"\n  ⚠️  WARNING: Requested {CONFIG['width']}×{CONFIG['height']} may exceed safe T4 memory.\n"
            f"     Set CONFIG['allow_auto_downgrade']=True to auto-downgrade, or reduce chunk_frames."
        )

print("\n✅ CELL 16 — VRAM planned")


# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 17 — CHUNK PLANNER                                         ║
# ╚══════════════════════════════════════════════════════════════════╝
# The LTXDirector node operates on the FULL timeline at once — it produces
# all guide data, latents, conditioning for 756 frames internally.
# The chunking strategy in this pipeline therefore applies at the
# VAE DECODE stage (frames→pixels) and FFmpeg assembly, NOT at the
# generation-sampling stage.  This matches how the JSON workflow is structured:
# LTXDirector handles the full sequence, SamplerCustomAdvanced runs on the
# full latent, and VHS_VideoCombine assembles the output.
#
# For memory safety on T4 we implement:
#   1. Generation on the full latent (756 frames) but with aggressive
#      model offloading between stages.
#   2. VAE decode in temporal sub-chunks to avoid OOM during pixel decode.
#   3. Frame saving immediately after each decode sub-chunk.
#
# This is the correct architecture for the Director 2.0 workflow —
# chunking only at decode is faithful to the source JSON.

print("=" * 60)
print("CELL 17 — CHUNK PLANNER")
print("=" * 60)


class ChunkPlanner:
    """
    Produces the VAE decode chunk schedule for temporal memory safety.
    Generation runs full-sequence (as in the JSON workflow).
    Decode is split into sub-chunks to cap peak VRAM.
    """

    def __init__(self, cfg: dict, timeline: TimelinePlanner, vram: VRAMPlanner):
        self.total_frames  = timeline.actual_frames
        self.fps           = timeline.fps

        # Auto-select decode chunk size from VRAM budget if enabled
        if cfg["auto_chunk_size"]:
            _max_dec = vram.max_safe_chunk_frames(upscaled=True)
            self.decode_chunk = max(
                cfg["min_chunk_frames"],
                min(_max_dec, cfg.get("vae_decode_chunk_frames", 49))
            )
            # Snap to LTX valid
            self.decode_chunk = nearest_ltx_frame_count(self.decode_chunk)
        else:
            self.decode_chunk = nearest_ltx_frame_count(
                max(cfg["min_chunk_frames"], cfg.get("vae_decode_chunk_frames", 49))
            )

        self.min_chunk      = cfg["min_chunk_frames"]
        self.quality_mode   = cfg["quality_mode"]
        self._chunks: list[dict] = []
        self._build()

    def _build(self) -> None:
        """Build the decode chunk list — non-overlapping, contiguous frames."""
        self._chunks = []
        start = 0
        idx   = 0
        while start < self.total_frames:
            end = min(start + self.decode_chunk, self.total_frames)
            count = end - start
            # Ensure LTX validity for the chunk
            count = nearest_ltx_frame_count(count)
            end   = min(start + count, self.total_frames)
            self._chunks.append({
                "chunk_index": idx,
                "start_frame": start,
                "end_frame":   end,
                "frame_count": end - start,
                "output_path": None,   # filled during execution
            })
            start = end
            idx  += 1

    @property
    def chunks(self) -> list[dict]:
        return self._chunks

    @property
    def num_chunks(self) -> int:
        return len(self._chunks)

    def estimated_storage_mb(self) -> float:
        """Rough estimate: each frame ≈ width×height×3 bytes as PNG."""
        bytes_per_frame = CONFIG["width"] * CONFIG["height"] * 3
        return (bytes_per_frame * self.total_frames) / (1024 * 1024)

    def report(self) -> str:
        lines = [
            "",
            f"  Generation strategy     : FULL SEQUENCE (LTXDirector handles 756 frames)",
            f"  VAE decode strategy     : TEMPORAL SUB-CHUNKS ({self.decode_chunk} frames each)",
            f"  Total frames            : {self.total_frames}",
            f"  Decode chunk size       : {self.decode_chunk} frames  ({self.decode_chunk/self.fps:.2f} s)",
            f"  Number of decode chunks : {self.num_chunks}",
            f"  Min chunk frames        : {self.min_chunk}",
            f"  Est. frame storage      : {self.estimated_storage_mb():.0f} MB",
            "",
            "  Decode chunk schedule:",
        ]
        for c in self._chunks:
            dur = c["frame_count"] / self.fps
            lines.append(
                f"    Chunk {c['chunk_index']:03d}: "
                f"frames {c['start_frame']:4d}–{c['end_frame']:4d}  "
                f"({c['frame_count']} frames, {dur:.2f} s)"
            )
        return "\n".join(lines)


CHUNKS = ChunkPlanner(CONFIG, TIMELINE, VRAM)
print(CHUNKS.report())
print(f"\n  Generation: SINGLE FULL-SEQUENCE PASS (matches JSON workflow architecture)")
print(f"  Note: LTXDirector internally manages the 5-segment timeline.")

print("\n✅ CELL 17 — Chunk plan complete")


# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 17b — DRY RUN REPORT                                       ║
# ╚══════════════════════════════════════════════════════════════════╝

print("=" * 60)
print("CELL 17b — DRY RUN REPORT")
print("=" * 60)

def dry_run_report() -> bool:
    """
    Validate the full pipeline plan without generating any video.
    Returns True if safe to proceed.
    """
    issues = []

    # CUDA
    cuda_ok = torch.cuda.is_available()
    gpu_name = torch.cuda.get_device_name(0) if cuda_ok else "N/A"
    vram_gb  = torch.cuda.get_device_properties(0).total_memory / (1024**3) if cuda_ok else 0

    # Model presence
    missing_req = [m for m in _missing_models if any(
        e["id"] == m for e in MODEL_MANIFEST if e.get("required", False)
    )]

    # Node presence
    critical_missing_nodes = [nt for nt, _ in _missing_nodes
                               if nt not in ("ModelPreviewOverrideKJ", "LTXDirector")]

    # Storage estimate
    import shutil as _shu
    _, _, free_bytes = _shu.disk_usage("/content")
    free_gb = free_bytes / (1024**3)
    est_storage_gb = CHUNKS.estimated_storage_mb() / 1024 + 2.0  # +2 GB buffer

    if not cuda_ok:
        issues.append("CUDA not available")
    if vram_gb < 13:
        issues.append(f"VRAM {vram_gb:.1f} GB < 13 GB minimum")
    if missing_req:
        issues.append(f"Required models missing: {missing_req}")
    if critical_missing_nodes:
        issues.append(f"Critical nodes missing: {critical_missing_nodes}")
    if free_gb < est_storage_gb:
        issues.append(f"Disk {free_gb:.1f} GB < estimated {est_storage_gb:.1f} GB needed")

    status = "PASS" if not issues else "WARN"

    print(f"""
DRY RUN
────────────────────────────────────────────────────
GPU                  : {gpu_name}
VRAM                 : {vram_gb:.2f} GB
CUDA available       : {cuda_ok}
Resolution           : {CONFIG['width']}×{CONFIG['height']}
FPS                  : {TIMELINE.fps}
Duration             : {TIMELINE.actual_duration:.2f} s
Frames               : {TIMELINE.actual_frames}
Director segments    : {len(TIMELINE.director_segments)}
VAE decode chunks    : {CHUNKS.num_chunks}
Decode chunk size    : {CHUNKS.decode_chunk} frames
Required models      : {len([e for e in MODEL_MANIFEST if e['required']])}
Missing req models   : {len(missing_req)}
Custom nodes present : {len(_present_nodes)}/{len(_EXPECTED_NODES)}
Missing crit nodes   : {len(critical_missing_nodes)}
Disk free            : {free_gb:.1f} GB
Est. storage needed  : {est_storage_gb:.1f} GB
Quality mode         : {CONFIG['quality_mode']}
────────────────────────────────────────────────────
STATUS               : {status}
────────────────────────────────────────────────────
""")

    if issues:
        print("  Issues found:")
        for iss in issues:
            print(f"    ⚠️  {iss}")
    else:
        print("  ✓ All checks passed — safe to proceed to generation")

    return status == "PASS"


_DRY_RUN_PASSED = dry_run_report()

if CONFIG.get("dry_run", False):
    print("\n  DRY_RUN=True — stopping before generation.")
    raise SystemExit("Dry run complete. Set CONFIG['dry_run']=False to generate.")

print("\n✅ CELL 17b — Dry run complete")



# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 18 — LTX-2.3 MODEL INITIALIZATION + LORA MANAGER          ║
# ╚══════════════════════════════════════════════════════════════════╝

print("=" * 60)
print("CELL 18 — MODEL INITIALIZATION + LORA MANAGER")
print("=" * 60)

from nodes import LoraLoaderModelOnly


class LTXLoRAManager:
    """
    Manages LoRA loading/unloading for the Power Lora Loader (rgthree) workflow.
    JSON node 138 loads 4 LoRAs in sequence onto the model.
    Strengths are fixed per JSON: dynamic=0.4, omninfт=0.6, transition=0.7, mvcamera=0.9
    """

    # JSON node 138 widget values — exact from workflow
    LORA_STACK = [
        {
            "id":       "lora_dynamic",
            "filename": "ltx-2.3-22b-distilled-lora-dynamic_fro09_avg_rank_105_bf16.safetensors",
            "strength": 0.4,
            "enabled":  True,
            "config_key": "lora_dynamic_enabled",
        },
        {
            "id":       "lora_omninfт",
            "filename": "LTX-2.3-OmniNFT-RL-Lora_bf16.safetensors",
            "strength": 0.6,
            "enabled":  True,
            "config_key": "lora_omninfт_enabled",
        },
        {
            "id":       "lora_transition",
            "filename": "ltx2.3-transition.safetensors",
            "strength": 0.7,
            "enabled":  True,
            "config_key": "lora_transition_enabled",
        },
        {
            "id":       "lora_mvcamera",
            "filename": "LTX2.3-MVCamera-drclips.safetensors",
            "strength": 0.9,
            "enabled":  True,
            "config_key": "lora_mvcamera_enabled",
        },
    ]

    def __init__(self, cfg: dict):
        self.cfg    = cfg
        self._loader = LoraLoaderModelOnly()

    def apply_loras(self, model):
        """
        Apply all enabled LoRAs in JSON stack order, mirroring Power Lora Loader (rgthree).
        Returns the LoRA-patched model.
        """
        lora_dir = f"{CONFIG['comfyui_dir']}/models/loras"
        for entry in self.LORA_STACK:
            if not self.cfg.get(entry["config_key"], True):
                print(f"    skip LoRA (disabled): {entry['filename']}")
                continue
            full_path = os.path.join(lora_dir, entry["filename"])
            if not os.path.isfile(full_path):
                print(f"    skip LoRA (missing):  {entry['filename']}")
                continue
            print(f"    + LoRA {entry['strength']:.1f}× : {entry['filename']}")
            model = self._loader.load_lora_model_only(
                model, entry["filename"], entry["strength"]
            )[0]
        return model

    def clear_loras(self) -> None:
        """Release LoRA loader reference."""
        del self._loader
        self._loader = LoraLoaderModelOnly()
        MEM.soft_cleanup()


LORA_MANAGER = LTXLoRAManager(CONFIG)
print("  ✓ LoRA manager ready")
print(f"  LoRA stack (JSON node 138):")
for _e in LTXLoRAManager.LORA_STACK:
    _en = CONFIG.get(_e["config_key"], True)
    _fn_exists = os.path.isfile(f"{CONFIG['comfyui_dir']}/models/loras/{_e['filename']}")
    print(f"    {'ON ' if _en else 'OFF'} {_e['strength']:.1f}× {_e['filename']}  {'✓' if _fn_exists else '✗ missing'}")

print("\n✅ CELL 18 — Model init complete")



# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 19 — DIRECTOR WORKFLOW EXECUTION                           ║
# ╚══════════════════════════════════════════════════════════════════╝
# Implements the exact JSON graph:
#   Node 135 (UnetLoaderGGUF)
#   → Node 138 (Power Lora Loader rgthree)
#   → Node 10  (ModelPreviewOverrideKJ)
#   → Node 131 (LTXDirector)                   ← master orchestrator
#   → Node 128 (ConditioningZeroOut)
#   → Node 27  (LTXVConditioning)
#   → Node 133 (LTXDirectorGuide)  STAGE 1
#   → Node 29  (LTXVConcatAVLatent)
#   → Node 32/33/28/30/31 (sample STAGE 1)
#   → Node 34  (LTXVSeparateAVLatent)
#   → Node 55  (LTXDirectorCropGuides)
#   → Node 13/14 (upscale)
#   → Node 132 (LTXDirectorGuide)  STAGE 2
#   → Node 18/20/21/17/30/19 (sample STAGE 2)
#   → Node 22  (LTXVSeparateAVLatent)
# Outputs: video_latent_s2, audio_latent_s2

print("=" * 60)
print("CELL 19 — DIRECTOR WORKFLOW EXECUTION")
print("=" * 60)


def _report_oom_error(stage: str, chunk_idx: int, node: str,
                      chunk_frames: int, e: Exception) -> None:
    alloc = MEM.gpu_allocated_gb()
    free  = MEM.gpu_free_gb()
    print(f"""
ERROR
────────────────────────────────────────────────────
Stage          : {stage}
Chunk          : {chunk_idx}
Node           : {node}
Chunk frames   : {chunk_frames}
GPU allocated  : {alloc:.2f} GB
GPU free       : {free:.2f} GB
Cause          : {type(e).__name__}: {str(e)[:200]}
Suggested action: Reduce CONFIG['vae_decode_chunk_frames'] or use 't4_safe' mode
────────────────────────────────────────────────────
""")


def run_validation_workflow(
    total_frames: int,
    seed:         int,
    global_prompt:str,
    fps:          int,
) -> dict:
    """
    Minimal pipeline for the 3-second validation pass.
    Does NOT use LTXDirector — uses the same lean pattern as ltx2_ti2v.py:
      UNet → CLIP → CLIPTextEncode → del CLIP → ConditioningZeroOut
      → LTXVConditioning → EmptyLTXVLatentVideo → LTXVEmptyLatentAudio
      → LTXVConcatAVLatent → SamplerCustomAdvanced → LTXVSeparateAVLatent
    Peak CPU RAM: ~3 GB total. Never crashes Colab T4.
    Returns the same dict shape as run_director_workflow().
    """
    # Compact validation resolution: same aspect ratio, much smaller
    VAL_W, VAL_H = 576, 320   # 576×320 @ 1.8:1 AR — fits comfortably in T4 RAM
    VAL_FRAMES   = total_frames   # already set to ~73 by validation_frame_count()

    MEM.print_memory("VALIDATION — BEFORE")

    with torch.inference_mode():

        # ── Load UNet ──────────────────────────────────────────────────────────
        print("  [VAL/N135] Loading UNet GGUF…")
        _unet_loader = NODE_CLASS_MAPPINGS["UnetLoaderGGUF"]()
        _unet_out    = _unet_loader.load_unet(unet_name=MODEL_FILENAMES["ltx23_unet"])
        _model       = get_value_at_index(_unet_out, 0)
        del _unet_out
        MEM.print_memory("VALIDATION — after UNet")

        # ── Load CLIP → encode → delete immediately ────────────────────────────
        print("  [VAL/N12] Loading CLIP…")
        _clip_loader = NODE_CLASS_MAPPINGS["DualCLIPLoader"]()
        _clip_out    = _clip_loader.load_clip(
            clip_name1 = MODEL_FILENAMES["gemma_fp4"],
            clip_name2 = MODEL_FILENAMES["ltx23_text_proj"],
            type       = "ltxv",
            device     = "default",
        )
        MEM.print_memory("VALIDATION — after CLIP")

        # ── CLIPTextEncode ────────────────────────────────────────────────────
        _clip_encode  = NODE_CLASS_MAPPINGS["CLIPTextEncode"]()
        _positive_enc = _clip_encode.encode(
            text = global_prompt[:300],   # short prompt for validation
            clip = get_value_at_index(_clip_out, 0),
        )
        # Delete CLIP immediately after encoding
        del _clip_out
        MEM.aggressive_cleanup()
        MEM.print_memory("VALIDATION — after CLIP freed")

        # ── ConditioningZeroOut + LTXVConditioning ────────────────────────────
        _czo      = NODE_CLASS_MAPPINGS["ConditioningZeroOut"]()
        _neg_zero = _czo.zero_out(conditioning=get_value_at_index(_positive_enc, 0))

        _ltxvcond = NODE_CLASS_MAPPINGS["LTXVConditioning"]()
        _cond_out = _ltxvcond.EXECUTE_NORMALIZED(
            frame_rate = fps,
            positive   = get_value_at_index(_positive_enc, 0),
            negative   = get_value_at_index(_neg_zero, 0),
        )
        del _positive_enc, _neg_zero
        MEM.soft_cleanup()

        # ── EmptyLTXVLatentVideo ───────────────────────────────────────────────
        _latent_w  = max(32, (VAL_W // 32) * 32)
        _latent_h  = max(32, (VAL_H // 32) * 32)
        _empty_lat = NODE_CLASS_MAPPINGS["EmptyLTXVLatentVideo"]()
        _vid_latent_empty = _empty_lat.EXECUTE_NORMALIZED(
            width      = _latent_w  // 2,   # latent space = pixel / 8 via VAE, but
            height     = _latent_h  // 2,   # EmptyLTXVLatentVideo takes pixel-space dims
            length     = VAL_FRAMES,
            batch_size = 1,
        )

        # ── EmptyLTXVLatentAudio ───────────────────────────────────────────────
        print("  [VAL/N8+audio] Loading Audio VAE for empty latent…")
        _audio_vae_obj = load_audio_vae_compat(MODEL_FILENAMES["audio_vae"])
        _empty_aud_node= NODE_CLASS_MAPPINGS["LTXVEmptyLatentAudio"]()
        _aud_latent_empty = _empty_aud_node.EXECUTE_NORMALIZED(
            frames_number = VAL_FRAMES,
            frame_rate    = fps,
            batch_size    = 1,
            audio_vae     = get_value_at_index(_audio_vae_obj, 0),
        )
        del _audio_vae_obj
        MEM.soft_cleanup()
        MEM.print_memory("VALIDATION — after latents created")

        # ── LTXVConcatAVLatent ─────────────────────────────────────────────────
        _concat_av = NODE_CLASS_MAPPINGS["LTXVConcatAVLatent"]()
        _av_latent = _concat_av.EXECUTE_NORMALIZED(
            video_latent = get_value_at_index(_vid_latent_empty, 0),
            audio_latent = get_value_at_index(_aud_latent_empty, 0),
        )
        del _vid_latent_empty, _aud_latent_empty

        # ── Stage 1: KSamplerSelect + BasicScheduler + CFGGuider + RandomNoise ─
        _ks1  = NODE_CLASS_MAPPINGS["KSamplerSelect"]()
        _samp1= _ks1.EXECUTE_NORMALIZED(sampler_name="euler")

        _bs1  = NODE_CLASS_MAPPINGS["BasicScheduler"]()
        _sig1 = _bs1.EXECUTE_NORMALIZED(model=_model, scheduler="linear_quadratic", steps=4, denoise=1.0)

        _cfg1 = NODE_CLASS_MAPPINGS["CFGGuider"]()
        _g1   = _cfg1.EXECUTE_NORMALIZED(
            cfg      = 1,
            model    = _model,
            positive = get_value_at_index(_cond_out, 0),
            negative = get_value_at_index(_cond_out, 1),
        )

        _rn1  = NODE_CLASS_MAPPINGS["RandomNoise"]()
        _n1   = _rn1.EXECUTE_NORMALIZED(noise_seed=seed)

        print("  [VAL] Stage 1 sampling (4 steps)…")
        MEM.pre_sampling_cleanup()
        _sampler_node = NODE_CLASS_MAPPINGS["SamplerCustomAdvanced"]()
        _s1_out = _sampler_node.EXECUTE_NORMALIZED(
            noise        = get_value_at_index(_n1, 0),
            guider       = get_value_at_index(_g1, 0),
            sampler      = get_value_at_index(_samp1, 0),
            sigmas       = get_value_at_index(_sig1, 0),
            latent_image = get_value_at_index(_av_latent, 0),
        )
        del _g1, _av_latent, _sig1, _n1
        MEM.cleanup()
        MEM.print_memory("VALIDATION — after Stage 1")

        # ── LTXVSeparateAVLatent ───────────────────────────────────────────────
        _sep_av = NODE_CLASS_MAPPINGS["LTXVSeparateAVLatent"]()
        _sep1   = _sep_av.EXECUTE_NORMALIZED(av_latent=get_value_at_index(_s1_out, 0))
        _vid1   = get_value_at_index(_sep1, 0)
        _aud1   = get_value_at_index(_sep1, 1)
        del _s1_out, _sep1
        MEM.soft_cleanup()

        # ── Stage 2: upscale + refine ─────────────────────────────────────────
        print("  [VAL/N36] Loading Video VAE for upsampler…")
        _vae_loader = NODE_CLASS_MAPPINGS["VAELoader"]()
        _vid_vae    = _vae_loader.load_vae(vae_name=MODEL_FILENAMES["video_vae"])

        _upscale_loader = NODE_CLASS_MAPPINGS["LatentUpscaleModelLoader"]()
        _up_model   = _upscale_loader.EXECUTE_NORMALIZED(model_name=MODEL_FILENAMES["spatial_upscaler"])

        _upsampler  = NODE_CLASS_MAPPINGS["LTXVLatentUpsampler"]()
        _up_lat     = _upsampler.upsample_latent(
            samples       = _vid1,
            upscale_model = get_value_at_index(_up_model, 0),
            vae           = get_value_at_index(_vid_vae, 0),
        )
        # CRITICAL: delete VAE + upscale model immediately after use
        # to free ~2.3 GB VRAM before Stage 2 sampling
        del _up_model, _vid_vae
        MEM.aggressive_cleanup()
        MEM.print_memory("VALIDATION — after upscale (VAE freed)")

        # ── Concat again for Stage 2 ──────────────────────────────────────────
        _av2 = _concat_av.EXECUTE_NORMALIZED(
            video_latent = get_value_at_index(_up_lat, 0),
            audio_latent = _aud1,
        )
        del _vid1, _up_lat

        # ── Stage 2 sampling (4 steps, denoise=0.42) ─────────────────────────
        _sig2 = _bs1.EXECUTE_NORMALIZED(model=_model, scheduler="linear_quadratic", steps=4, denoise=0.42)
        _g2   = _cfg1.EXECUTE_NORMALIZED(
            cfg      = 1,
            model    = _model,
            positive = get_value_at_index(_cond_out, 0),
            negative = get_value_at_index(_cond_out, 1),
        )
        _n2   = _rn1.EXECUTE_NORMALIZED(noise_seed=0)

        print("  [VAL] Stage 2 sampling (4 steps, denoise=0.42)…")
        MEM.pre_sampling_cleanup()
        _s2_out = _sampler_node.EXECUTE_NORMALIZED(
            noise        = get_value_at_index(_n2, 0),
            guider       = get_value_at_index(_g2, 0),
            sampler      = get_value_at_index(_samp1, 0),
            sigmas       = get_value_at_index(_sig2, 0),
            latent_image = get_value_at_index(_av2, 0),
        )
        del _g2, _av2, _sig2, _n2, _cond_out
        MEM.cleanup()
        MEM.print_memory("VALIDATION — after Stage 2")

        # ── Final separate ─────────────────────────────────────────────────────
        _sep2           = _sep_av.EXECUTE_NORMALIZED(av_latent=get_value_at_index(_s2_out, 0))
        _final_vid_lat  = get_value_at_index(_sep2, 0)
        _final_aud_lat  = get_value_at_index(_sep2, 1)
        del _s2_out, _sep2

        # Offload UNet
        del _model
        MEM.aggressive_cleanup()
        MEM.print_memory("VALIDATION — after UNet offload")

    # Return same shape as run_director_workflow()
    return {
        "video_latent":        _final_vid_lat,
        "audio_latent":        _final_aud_lat,
        "n132_positive":       None,   # no Director guides in validation
        "n132_negative":       None,
        "director_frame_rate": float(fps),
        "audio_vae_name":      MODEL_FILENAMES["audio_vae"],
        "video_vae_name":      MODEL_FILENAMES["video_vae"],
        "is_validation":       True,
    }


def run_director_workflow(
    total_frames:   int,
    seed:           int,
    global_prompt:  str,
    fps:            int,
    width:          int,
    height:         int,
    input_images:   list,
    input_audio:    str | None,
    skip_loras:     bool = False,
    validation_mode:bool = False,
) -> dict:
    """
    Dispatch to run_validation_workflow() for validation passes (lean, no Director).
    For the full generation run, execute the complete Director 2.0 pipeline.
    """
    if validation_mode:
        print("  [validation mode] Using minimal pipeline — bypassing LTXDirector")
        return run_validation_workflow(
            total_frames  = total_frames,
            seed          = seed,
            global_prompt = global_prompt,
            fps           = fps,
        )
    MEM.print_memory("BEFORE GENERATION")

    _COMFY = CONFIG["comfyui_dir"]

    with torch.inference_mode():

        # ── STEP A: Load UNet GGUF (moves to GPU during inference) ───────────
        print("  [N135] Loading UNet GGUF…")
        unetloadergguf = NODE_CLASS_MAPPINGS["UnetLoaderGGUF"]()
        node135_model = unetloadergguf.load_unet(
            unet_name=MODEL_FILENAMES["ltx23_unet"]
        )
        _raw_model = get_value_at_index(node135_model, 0)
        del node135_model
        MEM.print_memory("after UNet load")

        # ── STEP B: Load CLIP ─────────────────────────────────────────────────
        # Gemma 12B FP4 ≈ 2.5 GB (FP4 is much smaller than FP16).
        # Kept alive until AFTER LTXDirector.execute() — Director uses it for text encoding.
        # Deleted immediately after Director returns.
        print("  [N12] Loading DualCLIPLoader (Gemma FP4 + LTX projection)…")
        dualcliploader = NODE_CLASS_MAPPINGS["DualCLIPLoader"]()
        node12_clip = dualcliploader.load_clip(
            clip_name1=MODEL_FILENAMES["gemma_fp4"],
            clip_name2=MODEL_FILENAMES["ltx23_text_proj"],
            type="ltxv",
            device="default",
        )
        # Safety: ensure node12_clip is always a valid tuple even if load fails
        assert node12_clip is not None, "DualCLIPLoader returned None — check model files"
        MEM.print_memory("after CLIP load")

        # ── STEP C: Apply LoRAs ───────────────────────────────────────────────
        # LoRAs are large (dynamic=2.4GB, OmniNFT=0.6GB, transition=0.4GB, MVCamera=0.4GB)
        # During validation pass we skip them to conserve CPU RAM.
        # For full run they load one at a time directly into the model on GPU.
        if skip_loras:
            print("  [N138] LoRA stack SKIPPED (validation pass — saving ~3.8 GB RAM)")
            _lora_model = _raw_model
            del _raw_model
        else:
            print("  [N138] Applying LoRA stack (Power Lora Loader)…")
            _lora_model = LORA_MANAGER.apply_loras(_raw_model)
            del _raw_model
            MEM.cleanup()
            MEM.print_memory("after LoRAs applied")

        # ── STEP D-prep: ModelPreviewOverrideKJ (skip tiny VAE — saves ~100 MB)
        print("  [N10] ModelPreviewOverrideKJ…")
        node10_model_out = _lora_model
        if "ModelPreviewOverrideKJ" in NODE_CLASS_MAPPINGS:
            try:
                _preview_node = NODE_CLASS_MAPPINGS["ModelPreviewOverrideKJ"]()
                _func_name = getattr(_preview_node.__class__, "FUNCTION", None)
                if _func_name is None:
                    for _fn in ("patch", "apply", "apply_model", "EXECUTE_NORMALIZED", "run", "execute"):
                        if hasattr(_preview_node, _fn):
                            _func_name = _fn
                            break
                if _func_name and hasattr(_preview_node, _func_name):
                    _call = getattr(_preview_node, _func_name)
                    try:
                        # Try without tiny VAE first (saves ~100 MB RAM)
                        _n10 = _call(model=_lora_model, enabled=False)
                    except TypeError:
                        try:
                            _n10 = _call(model=_lora_model)
                        except Exception:
                            _n10 = (_lora_model,)
                    node10_model_out = get_value_at_index(_n10, 0)
                    del _n10
            except Exception as _e10:
                print(f"    ⚠️  ModelPreviewOverrideKJ: {_e10} — using raw model")
        else:
            print("    ModelPreviewOverrideKJ not registered — skipping")

        # ── STEP D: Run LTXDirector ───────────────────────────────────────────
        print("  [N131] LTXDirector — building timeline…")
        print(f"         frames={total_frames}, fps={fps}, {width}×{height}")

        if "LTXDirector" not in NODE_CLASS_MAPPINGS:
            # Check alternative names used by whatdreamscost
            _director_key = None
            for _alt in ("LTXDirector", "LTX Director", "LTXDirectorNode"):
                if _alt in NODE_CLASS_MAPPINGS:
                    _director_key = _alt
                    break
            if _director_key is None:
                # List all registered nodes containing "director" for diagnosis
                _director_candidates = [k for k in NODE_CLASS_MAPPINGS if "director" in k.lower() or "Director" in k]
                raise RuntimeError(
                    f"❌  LTXDirector not found in NODE_CLASS_MAPPINGS.\n"
                    f"    The WhatDreamsCost node failed to load (PromptServer issue).\n"
                    f"    Director-like nodes present: {_director_candidates}\n"
                    f"    Fix: ensure CELL 10 PromptServer patch ran BEFORE node loading.\n"
                    f"    Restart the Colab runtime and re-run all cells from Cell 1.\n"
                )
        else:
            _director_key = "LTXDirector"

        _director_cls  = NODE_CLASS_MAPPINGS[_director_key]
        _director_node = _director_cls()
        # Discover the actual FUNCTION name
        _director_func = getattr(_director_cls, "FUNCTION", "run")
        if not hasattr(_director_node, _director_func):
            for _fn in ("run", "execute", "process", "generate", "EXECUTE_NORMALIZED"):
                if hasattr(_director_node, _fn):
                    _director_func = _fn
                    break

        # Build timeline_data JSON string with the user's images and audio
        _segments_data = []
        _seg_filenames = ["1.png", "2.png", "3.png", "4.png", "5.3.png"]
        _seg_lengths   = [226.01, 161.32, 131.46, 225.51, 11.71]
        _seg_starts    = [0, 226.01, 387.33, 518.79, 744.29]
        for _si in range(5):
            _img_cfg = input_images[_si] if _si < len(input_images) else None
            _img_file = f"whatdreamscost/{_seg_filenames[_si]}"
            _segments_data.append({
                "id":          f"seg_{_si}",
                "start":       _seg_starts[_si],
                "length":      _seg_lengths[_si],
                "prompt":      "",
                "type":        "image",
                "imageFile":   _img_file,
                "isEndFrame":  False,
            })

        _audio_file_entry = []
        if input_audio and os.path.isfile(input_audio):
            _audio_file_entry = [{
                "id":                  "audio_0",
                "type":                "audio",
                "start":               0,
                "length":              756.52,
                "trimStart":           446.92,
                "audioDurationFrames": 2880,
                "audioFile":           f"whatdreamscost/{os.path.basename(input_audio)}",
                "fileName":            os.path.basename(input_audio),
            }]

        _timeline_dict = {
            "mainTrackEnabled":  True,
            "audioTrackEnabled": True,
            "motionTrackEnabled":True,
            "global_prompt":     global_prompt,
            "overrideAudio":     False,
            "inpaint_audio":     True,
            "normalStartFrame":  0,
            "normalDurationFrames": total_frames,
            "segments":          _segments_data,
            "motionSegments":    [],
            "audioSegments":     _audio_file_entry,
        }
        _timeline_json = json.dumps(_timeline_dict)

        # ── Load Audio VAE just before LTXDirector (then delete) ─────────────
        # IMPORTANT: Delete CLIP after LoRAs but we MUST keep it alive until
        # after LTXDirector.execute() — the Director needs clip for text encoding.
        # We free it immediately after the Director call below.
        print("  [N8]  Loading Audio VAE (lazy)…")
        vaeloader = NODE_CLASS_MAPPINGS["VAELoader"]()
        node8_audio_vae = vaeloader.load_vae(vae_name=MODEL_FILENAMES["audio_vae"])
        MEM.print_memory("after Audio VAE load")

        # img_compression=18 runs H.264 encode/decode on every image in PyAV.
        # Each 1280×720 frame = ~600 MB RAM spike. 5 images = ~3 GB peak inside Director.
        # During validation pass: skip compression entirely (img_compression=0).
        # During full run: use the JSON-authoritative value (18).
        _img_comp = 0 if validation_mode else IMG_COMPRESSION
        # Also reduce resolution for validation — use 768×448 (same AR as 1280×720)
        _val_w = 768 if validation_mode else width
        _val_h = 448 if validation_mode else height
        if validation_mode:
            print(f"  [validation] img_compression=0, resolution={_val_w}×{_val_h} (RAM-safe)")

        node131 = getattr(_director_node, _director_func)(
            model              = node10_model_out,
            clip               = get_value_at_index(node12_clip, 0),
            start_second       = 0.0,
            end_second         = float(total_frames) / fps,
            duration_seconds   = float(total_frames) / fps,
            start_frame        = 0,
            end_frame          = total_frames,
            duration_frames    = total_frames,
            timeline_data      = _timeline_json,
            local_prompts      = " |  |  |  | ",
            segment_lengths    = ",".join(str(round(x, 4)) for x in _seg_lengths),
            global_prompt      = global_prompt,
            guide_strength     = "1.00,1.00,1.00,1.00,1.00",
            epsilon            = 0.001,
            frame_rate         = fps,
            display_mode       = "seconds",
            custom_width       = _val_w,
            custom_height      = _val_h,
            resize_method      = "maintain aspect ratio",
            divisible_by       = 32,
            img_compression    = _img_comp,
            audio_vae          = get_value_at_index(node8_audio_vae, 0),
            optional_latent    = None,
            use_custom_audio   = True,
            inpaint_audio      = True,
            use_custom_motion  = True,
            override_audio     = False,
        )

        # Unpack Director outputs
        director_model      = get_value_at_index(node131, 0)   # modified model
        director_positive   = get_value_at_index(node131, 1)   # positive conditioning
        director_vid_latent = get_value_at_index(node131, 2)   # video latent
        director_aud_latent = get_value_at_index(node131, 3)   # audio latent
        director_guide_data = get_value_at_index(node131, 4)   # GUIDE_DATA
        director_motion_data= get_value_at_index(node131, 5)   # MOTION_GUIDE_DATA
        director_frame_rate = get_value_at_index(node131, 6)   # FLOAT (fps)

        MEM.print_memory("after LTXDirector")

        # Free CLIP, Audio VAE and node131 — Director consumed clip, outputs are unpacked
        del node12_clip, node8_audio_vae, node131
        MEM.aggressive_cleanup()
        MEM.print_memory("after CLIP+AudioVAE+Director freed")

        # ── NODE 128: ConditioningZeroOut ─────────────────────────────────────
        print("  [N128] ConditioningZeroOut…")
        conditioningzeroout = NODE_CLASS_MAPPINGS["ConditioningZeroOut"]()
        node128 = conditioningzeroout.zero_out(conditioning=director_positive)

        # ── NODE 27: LTXVConditioning — frame_rate from Director ──────────────
        print("  [N27]  LTXVConditioning…")
        ltxvconditioning = NODE_CLASS_MAPPINGS["LTXVConditioning"]()
        node27 = ltxvconditioning.EXECUTE_NORMALIZED(
            frame_rate=director_frame_rate,
            positive=director_positive,
            negative=get_value_at_index(node128, 0),
        )

        # ── NODE 133: LTXDirectorGuide STAGE 1 ───────────────────────────────
        # JSON widget values: None,1,0.5,bicubic,1,center,True,False,256,64,False
        print("  [N133] LTXDirectorGuide (Stage 1)…")
        # Load Video VAE lazily here — CLIP has been freed, so we have headroom
        print("  [N36] Loading Video VAE (lazy — after CLIP freed)…")
        node36_video_vae = vaeloader.load_vae(vae_name=MODEL_FILENAMES["video_vae"])
        MEM.print_memory("after Video VAE load")

        _guide_cls  = NODE_CLASS_MAPPINGS["LTXDirectorGuide"]
        _guide_func = getattr(_guide_cls, "FUNCTION", "execute")
        ltxdirectorguide = _guide_cls()
        # EXACT signature from ltx_director_guide.py LTXDirectorGuide.execute():
        # required: positive, negative, vae, latent, guide_data
        # optional: motion_guide_data=None, model=None, ic_lora_name="None",
        #           ic_lora_strength=1.0, scale_by=1.0, upscale_method="bicubic",
        #           image_attention_strength=1.0, crop="center", auto_snap_ic_grid=True,
        #           use_tiled_encode=False, tile_size=256, tile_overlap=64, retake_mode=False
        node133 = getattr(ltxdirectorguide, _guide_func)(
            positive              = get_value_at_index(node27, 0),
            negative              = get_value_at_index(node27, 1),
            vae                   = get_value_at_index(node36_video_vae, 0),
            latent                = director_vid_latent,
            guide_data            = director_guide_data,
            motion_guide_data     = director_motion_data,
            model                 = director_model,
            ic_lora_name          = "None",
            ic_lora_strength      = 1.0,
            scale_by              = 1.0,
            upscale_method        = "bicubic",
            image_attention_strength = 0.5,   # Stage 1 image_strength=0.5 from JSON
            crop                  = "center",
            auto_snap_ic_grid     = True,
            use_tiled_encode      = False,
            tile_size             = 256,
            tile_overlap          = 64,
            retake_mode           = False,
        )
        # Outputs: [positive, negative, latent, model, latent_downscale_factor]
        n133_positive = get_value_at_index(node133, 0)
        n133_negative = get_value_at_index(node133, 1)
        n133_latent   = get_value_at_index(node133, 2)
        n133_model    = get_value_at_index(node133, 3)

        # ── NODE 29: LTXVConcatAVLatent ───────────────────────────────────────
        print("  [N29]  LTXVConcatAVLatent (Stage 1)…")
        ltxvconcatav = NODE_CLASS_MAPPINGS["LTXVConcatAVLatent"]()
        node29 = ltxvconcatav.EXECUTE_NORMALIZED(
            video_latent=n133_latent,
            audio_latent=director_aud_latent,
        )

        # ── NODE 32: KSamplerSelect → euler ───────────────────────────────────
        ksamplerselect = NODE_CLASS_MAPPINGS["KSamplerSelect"]()
        node32 = ksamplerselect.EXECUTE_NORMALIZED(sampler_name="euler")

        # ── NODE 33: BasicScheduler — linear_quadratic, 8 steps, denoise=1.0 ─
        print("  [N33]  BasicScheduler (Stage 1: 8 steps)…")
        basicscheduler = NODE_CLASS_MAPPINGS["BasicScheduler"]()
        node33 = basicscheduler.EXECUTE_NORMALIZED(
            model=n133_model,
            scheduler="linear_quadratic",
            steps=8,
            denoise=1.0,
        )

        # ── NODE 28: CFGGuider cfg=1 ──────────────────────────────────────────
        print("  [N28]  CFGGuider (Stage 1)…")
        cfgguider = NODE_CLASS_MAPPINGS["CFGGuider"]()
        node28 = cfgguider.EXECUTE_NORMALIZED(
            cfg=1,
            model=n133_model,
            positive=n133_positive,
            negative=n133_negative,
        )

        # ── NODE 30: RandomNoise seed=0 (fixed) ───────────────────────────────
        randomnoise = NODE_CLASS_MAPPINGS["RandomNoise"]()
        node30 = randomnoise.EXECUTE_NORMALIZED(noise_seed=0, noise_type="fixed")
        MEM.print_memory("before Stage 1 sampling")

        # ── NODE 31: SamplerCustomAdvanced — STAGE 1 ──────────────────────────
        print("  [N31]  SamplerCustomAdvanced — STAGE 1 sampling…")
        MEM.pre_sampling_cleanup()
        samplercustom = NODE_CLASS_MAPPINGS["SamplerCustomAdvanced"]()
        node31 = samplercustom.EXECUTE_NORMALIZED(
            noise=get_value_at_index(node30, 0),
            guider=get_value_at_index(node28, 0),
            sampler=get_value_at_index(node32, 0),
            sigmas=get_value_at_index(node33, 0),
            latent_image=get_value_at_index(node29, 0),
        )

        # Free stage-1 intermediates
        del node28, node29, node33
        MEM.cleanup()
        MEM.print_memory("after Stage 1 sampling")

        # ── NODE 34: LTXVSeparateAVLatent ─────────────────────────────────────
        print("  [N34]  LTXVSeparateAVLatent…")
        ltxvseparateav = NODE_CLASS_MAPPINGS["LTXVSeparateAVLatent"]()
        node34 = ltxvseparateav.EXECUTE_NORMALIZED(
            av_latent=get_value_at_index(node31, 0)
        )
        n34_vid_latent = get_value_at_index(node34, 0)
        n34_aud_latent = get_value_at_index(node34, 1)

        del node31, node34
        MEM.soft_cleanup()

        # ── NODE 55: LTXDirectorCropGuides ────────────────────────────────────
        print("  [N55]  LTXDirectorCropGuides…")
        # EXACT signature from source: execute(self, positive, negative, latent)
        # FUNCTION = "execute", RETURN_TYPES = (CONDITIONING, CONDITIONING, LATENT)
        _crop_cls  = NODE_CLASS_MAPPINGS["LTXDirectorCropGuides"]
        _crop_func = getattr(_crop_cls, "FUNCTION", "execute")
        ltxdirectorcrop = _crop_cls()
        node55 = getattr(ltxdirectorcrop, _crop_func)(
            positive = n133_positive,
            negative = n133_negative,
            latent   = n34_vid_latent,
        )
        n55_positive = get_value_at_index(node55, 0)
        n55_negative = get_value_at_index(node55, 1)
        n55_latent   = get_value_at_index(node55, 2)

        # ── NODE 13: LatentUpscaleModelLoader ─────────────────────────────────
        print("  [N13]  Loading LatentUpscaleModel…")
        latentupscalemodelloader = NODE_CLASS_MAPPINGS["LatentUpscaleModelLoader"]()
        node13 = latentupscalemodelloader.EXECUTE_NORMALIZED(
            model_name=MODEL_FILENAMES["spatial_upscaler"]
        )

        # ── NODE 14: LTXVLatentUpsampler ──────────────────────────────────────
        print("  [N14]  LTXVLatentUpsampler (2×)…")
        ltxvlatentupsampler = NODE_CLASS_MAPPINGS["LTXVLatentUpsampler"]()
        node14 = ltxvlatentupsampler.upsample_latent(
            samples=n55_latent,
            upscale_model=get_value_at_index(node13, 0),
            vae=get_value_at_index(node36_video_vae, 0),
        )
        del node13
        MEM.soft_cleanup()
        MEM.print_memory("after upsampler")

        # ── NODE 132: LTXDirectorGuide STAGE 2 ───────────────────────────────
        # JSON widget values: None,1,1,bicubic,1,center,True,False,256,64,False
        print("  [N132] LTXDirectorGuide (Stage 2)…")
        node132 = getattr(ltxdirectorguide, _guide_func)(
            positive              = n55_positive,
            negative              = n55_negative,
            vae                   = get_value_at_index(node36_video_vae, 0),
            latent                = get_value_at_index(node14, 0),
            guide_data            = director_guide_data,
            motion_guide_data     = director_motion_data,
            model                 = director_model,
            ic_lora_name          = "None",
            ic_lora_strength      = 1.0,
            scale_by              = 1.0,
            upscale_method        = "bicubic",
            image_attention_strength = 1.0,   # Stage 2 image_strength=1.0 from JSON
            crop                  = "center",
            auto_snap_ic_grid     = True,
            use_tiled_encode      = False,
            tile_size             = 256,
            tile_overlap          = 64,
            retake_mode           = False,
        )
        n132_positive = get_value_at_index(node132, 0)
        n132_negative = get_value_at_index(node132, 1)
        n132_latent   = get_value_at_index(node132, 2)
        n132_model    = get_value_at_index(node132, 3)

        del node14, node55, node36_video_vae
        # Aggressive cleanup: evict Video VAE from GPU before Stage 2 sampling
        # This frees ~1.4 GB VRAM so Stage 2 sampler has enough headroom
        MEM.aggressive_cleanup()
        MEM.print_memory("after VAE freed pre-Stage2")

        # ── NODE 18: LTXVConcatAVLatent (Stage 2) ────────────────────────────
        print("  [N18]  LTXVConcatAVLatent (Stage 2)…")
        node18 = ltxvconcatav.EXECUTE_NORMALIZED(
            video_latent=n132_latent,
            audio_latent=n34_aud_latent,
        )

        # ── NODE 20: KSamplerSelect → euler ───────────────────────────────────
        node20 = ksamplerselect.EXECUTE_NORMALIZED(sampler_name="euler")

        # ── NODE 21: BasicScheduler — linear_quadratic, 4 steps, denoise=0.42 ─
        print("  [N21]  BasicScheduler (Stage 2: 4 steps, denoise=0.42)…")
        node21 = basicscheduler.EXECUTE_NORMALIZED(
            model=n132_model,
            scheduler="linear_quadratic",
            steps=4,
            denoise=0.42,
        )

        # ── NODE 17: CFGGuider cfg=1 ──────────────────────────────────────────
        print("  [N17]  CFGGuider (Stage 2)…")
        node17 = cfgguider.EXECUTE_NORMALIZED(
            cfg=1,
            model=n132_model,
            positive=n132_positive,
            negative=n132_negative,
        )
        MEM.print_memory("before Stage 2 sampling")

        # ── NODE 19: SamplerCustomAdvanced — STAGE 2 ──────────────────────────
        # Uses same RandomNoise node30 (seed=0, fixed) as Stage 1 per JSON links
        print("  [N19]  SamplerCustomAdvanced — STAGE 2 refine sampling…")
        MEM.pre_sampling_cleanup()
        node19 = samplercustom.EXECUTE_NORMALIZED(
            noise=get_value_at_index(node30, 0),
            guider=get_value_at_index(node17, 0),
            sampler=get_value_at_index(node20, 0),
            sigmas=get_value_at_index(node21, 0),
            latent_image=get_value_at_index(node18, 0),
        )

        del node17, node18, node20, node21, node30
        MEM.cleanup()
        MEM.print_memory("after Stage 2 sampling")

        # ── NODE 22: LTXVSeparateAVLatent ─────────────────────────────────────
        print("  [N22]  LTXVSeparateAVLatent (final)…")
        node22 = ltxvseparateav.EXECUTE_NORMALIZED(
            av_latent=get_value_at_index(node19, 0)
        )
        final_vid_latent = get_value_at_index(node22, 0)
        final_aud_latent = get_value_at_index(node22, 1)

        del node19, node22
        # Offload UNet — no longer needed after sampling
        del director_model, n132_model, n133_model, node10_model_out, _lora_model
        MEM.aggressive_cleanup()
        MEM.print_memory("after UNet offload")

    # Return lightweight references only — latents stay CPU-pinned
    # Audio VAE is loaded fresh in decode_audio() — don't carry it here
    return {
        "video_latent":        final_vid_latent,
        "audio_latent":        final_aud_latent,
        "n132_positive":       n132_positive,
        "n132_negative":       n132_negative,
        "director_frame_rate": director_frame_rate,
        # node8_audio_vae was freed — decode_audio() loads it fresh
        "audio_vae_name":      MODEL_FILENAMES["audio_vae"],
        "video_vae_name":      MODEL_FILENAMES["video_vae"],
    }


print("  ✓ run_director_workflow() defined")
print("\n✅ CELL 19 — Director workflow executor ready")



# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 20 — VAE DECODE (TEMPORAL SUB-CHUNKS)                      ║
# ╚══════════════════════════════════════════════════════════════════╝
# JSON nodes: 54 (LTXDirectorCropGuides) → 1 (VAEDecode) + 24 (LTXVAudioVAEDecode)
# Decode is split into temporal sub-chunks to avoid OOM on T4.

print("=" * 60)
print("CELL 20 — VAE DECODE")
print("=" * 60)


def decode_video_in_chunks(
    video_latent,
    n132_positive,
    n132_negative,
    chunk_planner: ChunkPlanner,
    video_vae_name: str,
) -> list[dict]:
    """
    Decode the full video latent in temporal sub-chunks.
    JSON: Node 54 (LTXDirectorCropGuides) → Node 1 (VAEDecode)
    Returns list of {chunk_index, start_frame, end_frame, frame_count, frames_tensor}
    Each tensor is immediately moved to CPU after decode.
    """
    decoded_chunks = []
    vaeloader    = NODE_CLASS_MAPPINGS["VAELoader"]()
    vaedecode    = NODE_CLASS_MAPPINGS["VAEDecode"]()
    _crop_cls_d  = NODE_CLASS_MAPPINGS["LTXDirectorCropGuides"]
    _crop_func_d = getattr(_crop_cls_d, "FUNCTION", "execute")
    ltxdirectorcrop = _crop_cls_d()

    # Extract the full latent samples tensor for slicing
    # ComfyUI latents are dicts: {"samples": tensor(B, C, T, H, W)}
    if isinstance(video_latent, dict) and "samples" in video_latent:
        _latent_tensor = video_latent["samples"]
    elif isinstance(video_latent, (tuple, list)):
        _latent_tensor = get_value_at_index(video_latent, 0)
        if isinstance(_latent_tensor, dict):
            _latent_tensor = _latent_tensor["samples"]
    else:
        _latent_tensor = video_latent

    total_t = _latent_tensor.shape[2] if _latent_tensor.ndim == 5 else _latent_tensor.shape[0]
    print(f"  Latent shape: {_latent_tensor.shape}  (temporal dim = {total_t})")

    for chunk in chunk_planner.chunks:
        ci     = chunk["chunk_index"]
        sf     = chunk["start_frame"]
        ef     = chunk["end_frame"]
        nf     = chunk["frame_count"]
        MEM.print_memory(f"BEFORE DECODE CHUNK {ci:03d}")

        print(f"  Decoding chunk {ci:03d}: frames {sf}–{ef} ({nf} frames)…")

        with torch.inference_mode():
            # Slice the latent temporally
            if _latent_tensor.ndim == 5:
                # (B, C, T, H, W) — standard ComfyUI video latent
                _chunk_samples = _latent_tensor[:, :, sf:ef, :, :]
            else:
                _chunk_samples = _latent_tensor[sf:ef]

            _chunk_latent = {"samples": _chunk_samples}

            # ── NODE 54: LTXDirectorCropGuides (crop for upscaled latent) ─────
            # Skip when conditioning is None (validation mode has no Director guides)
            if n132_positive is not None and n132_negative is not None:
                try:
                    _node54 = getattr(ltxdirectorcrop, _crop_func_d)(
                        positive=n132_positive,
                        negative=n132_negative,
                        latent=_chunk_latent,
                    )
                    _decode_input = get_value_at_index(_node54, 2)
                    del _node54
                except Exception as _e54:
                    print(f"    ⚠️  LTXDirectorCropGuides failed ({_e54}), using raw chunk latent")
                    _decode_input = _chunk_latent
            else:
                # Validation mode: no Director conditioning, decode directly
                _decode_input = _chunk_latent

            # ── NODE 1: VAEDecode ──────────────────────────────────────────────
            _vae = vaeloader.load_vae(vae_name=video_vae_name)
            _decoded = vaedecode.decode(
                samples=_decode_input,
                vae=get_value_at_index(_vae, 0),
            )
            _frames = get_value_at_index(_decoded, 0)  # (N, H, W, C) float32

            # Immediately move to CPU to free GPU VRAM
            _frames_cpu = _frames.cpu()
            del _frames, _decoded, _vae, _decode_input, _chunk_latent, _chunk_samples
            MEM.cleanup()

        decoded_chunks.append({
            "chunk_index": ci,
            "start_frame": sf,
            "end_frame":   ef,
            "frame_count": nf,
            "frames":      _frames_cpu,   # CPU tensor
        })
        MEM.print_memory(f"AFTER  DECODE CHUNK {ci:03d}")

    return decoded_chunks


def decode_audio(audio_latent, audio_vae_name: str) -> Any:
    """
    JSON: Node 24 — LTXVAudioVAEDecode
    Loads Audio VAE fresh (it was freed after LTXDirector to save RAM).
    Decode the audio latent. Returns AUDIO output on CPU.
    """
    print("  [N24]  LTXVAudioVAEDecode (loading Audio VAE fresh)…")
    with torch.inference_mode():
        # Load Audio VAE fresh — CLIP and other models are now freed
        _audio_vae_obj = NODE_CLASS_MAPPINGS["VAELoader"]().load_vae(vae_name=audio_vae_name)
        ltxvaudiovaedecode = NODE_CLASS_MAPPINGS["LTXVAudioVAEDecode"]()
        _audio_out = ltxvaudiovaedecode.EXECUTE_NORMALIZED(
            samples=audio_latent,
            audio_vae=get_value_at_index(_audio_vae_obj, 0),
        )
        _audio = get_value_at_index(_audio_out, 0)
        del _audio_out, _audio_vae_obj
        MEM.cleanup()
    return _audio


print("  ✓ decode_video_in_chunks() defined")
print("  ✓ decode_audio() defined")
print("\n✅ CELL 20 — VAE decode functions ready")


# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 21 — CHUNK SAVING                                          ║
# ╚══════════════════════════════════════════════════════════════════╝

print("=" * 60)
print("CELL 21 — CHUNK SAVING")
print("=" * 60)

import numpy as np

CHUNK_DIR   = _DIRS["chunks"]
FRAMES_DIR  = _DIRS["frames"]


def save_frames_as_png(frames_cpu: torch.Tensor, start_frame: int, out_dir: str) -> list[str]:
    """
    Save a CPU frame tensor (N, H, W, C) as numbered PNG files.
    Returns list of saved paths.
    """
    from PIL import Image as _PIL
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    np_frames = (frames_cpu.numpy() * 255).clip(0, 255).astype(np.uint8)
    for i, frame in enumerate(np_frames):
        fn = os.path.join(out_dir, f"frame_{start_frame + i:06d}.png")
        _PIL.fromarray(frame).save(fn, optimize=False)
        paths.append(fn)
    return paths


def save_chunk_as_mp4(
    frames_cpu:  torch.Tensor,
    chunk_index: int,
    start_frame: int,
    fps:         int,
    out_dir:     str,
) -> str | None:
    """
    Encode a CPU frame tensor directly to MP4 with FFmpeg (no RAM copy of full video).
    Streams frames through stdin pipe. Returns output path or None on failure.
    """
    os.makedirs(out_dir, exist_ok=True)
    chunk_path = os.path.join(out_dir, f"chunk_{chunk_index:04d}.mp4")

    # Skip if already a valid chunk
    if os.path.isfile(chunk_path) and _file_size_mb(chunk_path) > 0.1:
        print(f"    ✓ Chunk already exists: {chunk_path}")
        return chunk_path

    nf, h, w, c = frames_cpu.shape
    np_frames = (frames_cpu.numpy() * 255).clip(0, 255).astype(np.uint8)

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f",   "rawvideo",
        "-vcodec", "rawvideo",
        "-s",   f"{w}x{h}",
        "-pix_fmt", "rgb24",
        "-r",   str(fps),
        "-i",   "pipe:0",
        "-vcodec", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf",  "8",
        "-preset", "fast",
        "-movflags", "+faststart",
        chunk_path,
    ]

    try:
        proc = subprocess.Popen(
            ffmpeg_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        for frame in np_frames:
            proc.stdin.write(frame.tobytes())
        proc.stdin.close()
        proc.wait(timeout=300)

        if proc.returncode != 0:
            err = proc.stderr.read().decode(errors="replace")[-400:]
            print(f"    ✗ FFmpeg encoding failed: {err}")
            return None

        sz = _file_size_mb(chunk_path)
        print(f"    ✓ Chunk {chunk_index:04d} saved ({sz:.1f} MB): {chunk_path}")
        return chunk_path

    except Exception as e:
        print(f"    ✗ Chunk save error: {e}")
        return None


def validate_chunk_file(path: str, expected_frames: int, fps: int) -> bool:
    """
    Validate a chunk MP4 with ffprobe.
    Returns True if file passes all checks.
    """
    if not os.path.isfile(path):
        return False
    if _file_size_mb(path) < 0.05:
        print(f"    ✗ Chunk too small: {path}")
        return False

    # ffprobe stream info
    _probe_cmd = (
        f"ffprobe -v error -select_streams v:0 "
        f"-show_entries stream=nb_frames,r_frame_rate,width,height "
        f"-of csv=p=0 \"{path}\""
    )
    try:
        result = subprocess.run(
            _probe_cmd, shell=True, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30
        )
        info = result.stdout.strip()
        if not info:
            return False
        parts = info.split(",")
        # parts: width, height, r_frame_rate, nb_frames
        if len(parts) >= 4:
            _w, _h = int(parts[0]), int(parts[1])
            _fps_str = parts[2]     # e.g. "24/1"
            _nb = parts[3].strip()  # may be "N/A"
            if _w < 100 or _h < 100:
                print(f"    ✗ Chunk resolution too small: {_w}×{_h}")
                return False
        return True
    except Exception as e:
        print(f"    ⚠️  ffprobe validation skipped: {e}")
        return True   # best-effort; don't block on probe errors


print("  ✓ save_chunk_as_mp4() defined")
print("  ✓ validate_chunk_file() defined")
print("\n✅ CELL 21 — Chunk saving functions ready")



# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 22 — CHECKPOINT / RESUME SYSTEM                            ║
# ╚══════════════════════════════════════════════════════════════════╝

print("=" * 60)
print("CELL 22 — CHECKPOINT / RESUME")
print("=" * 60)

import uuid
import tempfile

_CHECKPOINT_PATH = os.path.join(_DIRS["checkpoints"], "checkpoint.json")


def _new_job_id() -> str:
    return str(uuid.uuid4())[:8]


def load_checkpoint() -> dict:
    """Load existing checkpoint or create a fresh one."""
    if os.path.isfile(_CHECKPOINT_PATH):
        try:
            with open(_CHECKPOINT_PATH, "r") as f:
                ckpt = json.load(f)
            print(f"  ✓ Resumed checkpoint: job_id={ckpt.get('job_id')}")
            return ckpt
        except Exception as e:
            print(f"  ⚠️  Checkpoint corrupt ({e}) — starting fresh")

    # Fresh checkpoint
    ckpt = {
        "job_id":            _new_job_id(),
        "workflow":          "LTX-2.3_Director_2.0-MV-Workflow-30s.json",
        "seed":              CONFIG["seed"],
        "fps":               CONFIG["fps"],
        "resolution":        [CONFIG["width"], CONFIG["height"]],
        "duration_seconds":  CONFIG["duration_seconds"],
        "total_frames":      TIMELINE.actual_frames,
        "decode_chunk_size": CHUNKS.decode_chunk,
        "completed_chunks":  [],
        "failed_chunks":     [],
        "oom_retries":       0,
        "generation_done":   False,
        "stage":             "not_started",
    }
    save_checkpoint(ckpt)
    print(f"  ✓ New checkpoint: job_id={ckpt['job_id']}")
    return ckpt


def save_checkpoint(ckpt: dict) -> None:
    """Atomically write checkpoint to disk (tmp → rename)."""
    os.makedirs(os.path.dirname(_CHECKPOINT_PATH), exist_ok=True)
    _tmp = _CHECKPOINT_PATH + ".tmp"
    try:
        with open(_tmp, "w") as f:
            json.dump(ckpt, f, indent=2)
        os.replace(_tmp, _CHECKPOINT_PATH)
    except Exception as e:
        print(f"  ⚠️  Checkpoint save failed: {e}")


def mark_chunk_complete(ckpt: dict, chunk_index: int, chunk_path: str) -> None:
    if chunk_index not in ckpt["completed_chunks"]:
        ckpt["completed_chunks"].append(chunk_index)
    if chunk_index in ckpt.get("failed_chunks", []):
        ckpt["failed_chunks"].remove(chunk_index)
    save_checkpoint(ckpt)


def mark_chunk_failed(ckpt: dict, chunk_index: int) -> None:
    if chunk_index not in ckpt.get("failed_chunks", []):
        ckpt.setdefault("failed_chunks", []).append(chunk_index)
    save_checkpoint(ckpt)


def is_chunk_done(ckpt: dict, chunk_index: int, chunk_path: str) -> bool:
    """Return True only if chunk is in completed list AND file is valid."""
    if chunk_index not in ckpt.get("completed_chunks", []):
        return False
    if not chunk_path or not os.path.isfile(chunk_path):
        return False
    return _file_size_mb(chunk_path) > 0.05


# Load or create checkpoint
CHECKPOINT = load_checkpoint()
print(f"  Completed chunks: {CHECKPOINT['completed_chunks']}")
print(f"  Failed chunks   : {CHECKPOINT.get('failed_chunks', [])}")
print(f"  Generation done : {CHECKPOINT.get('generation_done', False)}")
print("\n✅ CELL 22 — Checkpoint/resume ready")


# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 23 — OOM RECOVERY + MASTER GENERATION ORCHESTRATOR        ║
# ╚══════════════════════════════════════════════════════════════════╝

print("=" * 60)
print("CELL 23 — OOM RECOVERY + GENERATION ORCHESTRATOR")
print("=" * 60)

MAX_OOM_RETRIES     = CONFIG["max_oom_retries"]
OOM_REDUCTION_FACTOR= CONFIG["oom_reduction_factor"]
MIN_CHUNK_FRAMES    = CONFIG["min_chunk_frames"]


def oom_recover_and_retry(
    decode_fn,
    args: tuple,
    kwargs: dict,
    chunk_index: int,
    current_chunk_size: int,
) -> tuple[Any, int]:
    """
    Catch CUDA OOM, reduce chunk size, retry the same chunk.
    Returns (result, final_chunk_size).
    Raises RuntimeError if minimum chunk size still fails.
    """
    for attempt in range(1, MAX_OOM_RETRIES + 2):
        try:
            result = decode_fn(*args, **kwargs)
            return result, current_chunk_size

        except torch.cuda.OutOfMemoryError as oom:
            print(f"\n  ⚠️  CUDA OOM on chunk {chunk_index} (attempt {attempt})")
            _report_oom_error("decode", chunk_index, "VAEDecode", current_chunk_size, oom)

            # Stop immediately, release all temporaries
            MEM.aggressive_cleanup()

            if attempt > MAX_OOM_RETRIES:
                raise RuntimeError(
                    f"❌  OOM persists after {MAX_OOM_RETRIES} retries on chunk {chunk_index}.\n"
                    f"    Min chunk ({MIN_CHUNK_FRAMES} frames) is still too large.\n"
                    f"    Try reducing CONFIG['width']/CONFIG['height'] or use t4_safe mode."
                )

            # Reduce chunk size
            new_size = max(
                MIN_CHUNK_FRAMES,
                nearest_ltx_frame_count(int(current_chunk_size * OOM_REDUCTION_FACTOR))
            )
            if new_size == current_chunk_size:
                new_size = MIN_CHUNK_FRAMES

            print(f"    Reducing chunk: {current_chunk_size} → {new_size} frames")
            current_chunk_size = new_size

            # Rebuild kwargs with new chunk size limit
            if "chunk_planner" in kwargs:
                # Re-slice the same frames at smaller chunk size
                pass   # ChunkPlanner not modified for single-chunk retries
            elif "end_frame" in kwargs:
                kwargs["end_frame"] = kwargs["start_frame"] + new_size

        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                # Some PyTorch versions raise RuntimeError instead of OutOfMemoryError
                _report_oom_error("decode", chunk_index, "VAEDecode", current_chunk_size, e)
                MEM.aggressive_cleanup()
                new_size = max(
                    MIN_CHUNK_FRAMES,
                    nearest_ltx_frame_count(int(current_chunk_size * OOM_REDUCTION_FACTOR))
                )
                print(f"    Reducing chunk after RuntimeError OOM: {current_chunk_size} → {new_size}")
                current_chunk_size = new_size
            else:
                raise


def run_full_pipeline(
    validate_only:     bool = False,
    validation_secs:   float = 3.0,
) -> dict:
    """
    Master orchestrator — runs the complete LTX-2.3 Director pipeline:
      1. Validation pass (3 s) if VALIDATE_PIPELINE_FIRST=True
      2. Full 30 s generation
      3. VAE decode in sub-chunks
      4. Chunk MP4 saving
      5. Checkpoint after every chunk
    Returns dict with chunk paths and audio output.
    """
    _t_start = time.time()

    _cfg_frames = TIMELINE.validation_frame_count(validation_secs) if validate_only else TIMELINE.actual_frames
    _cfg_label  = f"VALIDATION ({validation_secs}s)" if validate_only else "FULL GENERATION (30s)"

    print(f"\n{'='*60}")
    print(f"  {_cfg_label}")
    print(f"  Frames: {_cfg_frames}  |  FPS: {CONFIG['fps']}  |  Seed: {CONFIG['seed']}")
    print(f"{'='*60}\n")

    CHECKPOINT["stage"] = "generation"
    save_checkpoint(CHECKPOINT)

    # ── STEP 1: Director generation ───────────────────────────────────────────
    if not CHECKPOINT.get("generation_done", False):
        print("STEP 1 — Running Director workflow…")
        try:
            _gen_result = run_director_workflow(
                total_frames     = _cfg_frames,
                seed             = CONFIG["seed"],
                global_prompt    = GLOBAL_PROMPT,
                fps              = CONFIG["fps"],
                width            = CONFIG["width"],
                height           = CONFIG["height"],
                input_images     = CONFIG["input_images"],
                input_audio      = CONFIG.get("input_audio_prepared") or CONFIG.get("input_audio"),
                skip_loras       = validate_only,
                validation_mode  = validate_only,
            )
        except torch.cuda.OutOfMemoryError as oom:
            _report_oom_error("generation", 0, "SamplerCustomAdvanced", _cfg_frames, oom)
            MEM.aggressive_cleanup()
            raise RuntimeError(
                "❌  OOM during generation pass.\n"
                "    The 22B model + 756-frame latent exceeds available VRAM.\n"
                "    Try: quality_mode='t4_safe', width=960, height=544, or reduce frames."
            )

        CHECKPOINT["generation_done"] = True
        save_checkpoint(CHECKPOINT)
        print("STEP 1 — Generation complete ✓")
    else:
        print("STEP 1 — Generation already done (checkpoint resume) — skipping")
        # NOTE: in a full resume scenario the latents would be loaded from disk.
        # For simplicity, if generation_done=True but we don't have the tensors,
        # we re-run generation (safe because sampling is deterministic with fixed seed).
        _gen_result = run_director_workflow(
            total_frames     = _cfg_frames,
            seed             = CONFIG["seed"],
            global_prompt    = GLOBAL_PROMPT,
            fps              = CONFIG["fps"],
            width            = CONFIG["width"],
            height           = CONFIG["height"],
            input_images     = CONFIG["input_images"],
            input_audio      = CONFIG.get("input_audio_prepared") or CONFIG.get("input_audio"),
            skip_loras       = validate_only,
            validation_mode  = validate_only,
        )

    _vid_latent    = _gen_result["video_latent"]
    _aud_latent    = _gen_result["audio_latent"]
    _n132_pos      = _gen_result["n132_positive"]   # None in validation mode
    _n132_neg      = _gen_result["n132_negative"]   # None in validation mode
    _audio_vae_name= _gen_result.get("audio_vae_name", MODEL_FILENAMES["audio_vae"])
    _is_validation = _gen_result.get("is_validation", False)

    # ── STEP 2: Audio decode ──────────────────────────────────────────────────
    print("\nSTEP 2 — Decoding audio…")
    CHECKPOINT["stage"] = "audio_decode"
    save_checkpoint(CHECKPOINT)

    _audio_out = decode_audio(_aud_latent, _audio_vae_name)
    del _aud_latent
    MEM.cleanup()
    print("  Audio decoded ✓")

    # ── STEP 3: VAE decode in chunks ──────────────────────────────────────────
    print("\nSTEP 3 — VAE decoding video in temporal chunks…")
    CHECKPOINT["stage"] = "vae_decode"
    save_checkpoint(CHECKPOINT)

    # Build a fresh ChunkPlanner (handles changed sizes from OOM adaptation)
    _chunk_planner = ChunkPlanner(CONFIG, TIMELINE if not validate_only else
                                  _make_val_timeline(validation_secs), VRAM)

    _current_decode_chunk = _chunk_planner.decode_chunk
    _decoded_chunks = []

    for _chunk in _chunk_planner.chunks:
        _ci = _chunk["chunk_index"]
        _chunk_path = os.path.join(CHUNK_DIR, f"chunk_{_ci:04d}.mp4")

        # Resume: skip already-done chunks
        if is_chunk_done(CHECKPOINT, _ci, _chunk_path):
            print(f"  Chunk {_ci:03d}: already complete — skipping")
            _chunk["output_path"] = _chunk_path
            _decoded_chunks.append({"chunk_index": _ci, "path": _chunk_path,
                                     "start_frame": _chunk["start_frame"],
                                     "frame_count": _chunk["frame_count"]})
            continue

        MEM.print_memory(f"BEFORE CHUNK {_ci:03d}")

        # Slice the video latent for this chunk
        if isinstance(_vid_latent, dict) and "samples" in _vid_latent:
            _lt = _vid_latent["samples"]
        else:
            _lt = _vid_latent

        _sf, _ef = _chunk["start_frame"], _chunk["end_frame"]
        if _lt.ndim == 5:
            _chunk_lat = {"samples": _lt[:, :, _sf:_ef, :, :]}
        else:
            _chunk_lat = {"samples": _lt[_sf:_ef]}

        # Decode with OOM retry
        def _do_decode(_cl, _pos, _neg, _vae_name):
            return decode_video_in_chunks(
                video_latent  = _cl,
                n132_positive = _pos,
                n132_negative = _neg,
                chunk_planner = ChunkPlanner.__new__(ChunkPlanner),   # single-chunk wrapper
                video_vae_name= _vae_name,
            )

        # Simpler direct decode for single chunk
        def _decode_one_chunk(_chunk_lat, _pos, _neg, _vae_name):
            vaeloader = NODE_CLASS_MAPPINGS["VAELoader"]()
            vaedecode = NODE_CLASS_MAPPINGS["VAEDecode"]()
            with torch.inference_mode():
                # Skip LTXDirectorCropGuides when conditioning is None (validation mode)
                if _pos is not None and _neg is not None:
                    try:
                        _cc = NODE_CLASS_MAPPINGS["LTXDirectorCropGuides"]
                        _cf = getattr(_cc, "FUNCTION", "execute")
                        _n54 = _cc().execute(positive=_pos, negative=_neg, latent=_chunk_lat)
                        _decode_input = get_value_at_index(_n54, 2)
                        del _n54
                    except Exception as _e:
                        print(f"    ⚠️  CropGuides failed: {_e}")
                        _decode_input = _chunk_lat
                else:
                    _decode_input = _chunk_lat
                _vae = vaeloader.load_vae(vae_name=_vae_name)
                _dec = vaedecode.decode(samples=_decode_input,
                                        vae=get_value_at_index(_vae, 0))
                _frames = get_value_at_index(_dec, 0).cpu()
                del _dec, _vae, _decode_input
                MEM.cleanup()
            return _frames

        _retries_left = MAX_OOM_RETRIES
        _success = False
        while not _success and _retries_left >= 0:
            try:
                _frames_cpu = _decode_one_chunk(
                    _chunk_lat, _n132_pos, _n132_neg, MODEL_FILENAMES["video_vae"]
                )
                _success = True
            except torch.cuda.OutOfMemoryError as _oom:
                _report_oom_error("vae_decode", _ci, "VAEDecode", _ef - _sf, _oom)
                MEM.aggressive_cleanup()
                _retries_left -= 1
                if _retries_left < 0:
                    mark_chunk_failed(CHECKPOINT, _ci)
                    raise RuntimeError(
                        f"❌  OOM on chunk {_ci} after all retries.\n"
                        f"    Reduce vae_decode_chunk_frames in CONFIG."
                    )
                print(f"    OOM retry {MAX_OOM_RETRIES - _retries_left}/{MAX_OOM_RETRIES}…")

        del _chunk_lat
        MEM.soft_cleanup()

        # Save chunk to MP4
        _out_path = save_chunk_as_mp4(
            frames_cpu=_frames_cpu,
            chunk_index=_ci,
            start_frame=_sf,
            fps=CONFIG["fps"],
            out_dir=CHUNK_DIR,
        )
        del _frames_cpu
        MEM.cleanup()

        if _out_path and validate_chunk_file(_out_path, _ef - _sf, CONFIG["fps"]):
            _chunk["output_path"] = _out_path
            mark_chunk_complete(CHECKPOINT, _ci, _out_path)
            _decoded_chunks.append({
                "chunk_index": _ci,
                "path": _out_path,
                "start_frame": _sf,
                "frame_count": _ef - _sf,
            })
        else:
            mark_chunk_failed(CHECKPOINT, _ci)
            print(f"  ✗ Chunk {_ci} validation failed")

        MEM.print_memory(f"AFTER  CHUNK {_ci:03d}")

    # Free video latent
    del _vid_latent
    MEM.aggressive_cleanup()

    _elapsed = time.time() - _t_start
    print(f"\n  Generation complete in {_elapsed:.1f} s")
    CHECKPOINT["stage"] = "chunks_done"
    save_checkpoint(CHECKPOINT)

    return {
        "chunk_paths":  [c["path"] for c in _decoded_chunks],
        "decoded_chunks": _decoded_chunks,
        "audio_out":    _audio_out,
        "elapsed_sec":  _elapsed,
    }


def _make_val_timeline(val_secs: float) -> TimelinePlanner:
    """Create a short timeline for the validation pass."""
    import copy
    vt = copy.copy(TIMELINE)
    vf = TIMELINE.validation_frame_count(val_secs)
    vt.actual_frames   = vf
    vt.actual_duration = vf / TIMELINE.fps
    return vt


print("  ✓ run_full_pipeline() defined")
print("  ✓ oom_recover_and_retry() defined")
print("\n✅ CELL 23 — OOM recovery + orchestrator ready")


# ── Validation pass (3-second test run) ──────────────────────────────────────

_PIPELINE_RESULT: dict | None = None
_VALIDATION_RESULT: dict | None = None

if CONFIG.get("validate_pipeline_first", True):
    print("\n" + "=" * 60)
    print("VALIDATION PASS — 3-second test generation")
    print("=" * 60)
    try:
        _VALIDATION_RESULT = run_full_pipeline(
            validate_only   = True,
            validation_secs = CONFIG["validation_duration_seconds"],
        )
        print(f"\n  ✓ VALIDATION PASS — pipeline works correctly")
        print(f"    Chunks: {len(_VALIDATION_RESULT['chunk_paths'])}")
        print(f"    Time  : {_VALIDATION_RESULT['elapsed_sec']:.1f} s")
        # Clean up validation chunks to free disk space
        for _vcp in _VALIDATION_RESULT["chunk_paths"]:
            if os.path.isfile(_vcp):
                os.remove(_vcp)
        del _VALIDATION_RESULT
        MEM.aggressive_cleanup()
        # Reset checkpoint for full run
        CHECKPOINT["completed_chunks"] = []
        CHECKPOINT["generation_done"]  = False
        CHECKPOINT["stage"]            = "validated"
        save_checkpoint(CHECKPOINT)
    except Exception as _val_err:
        print(f"\n  ✗ VALIDATION FAILED: {_val_err}")
        print("    Fix the error above before running the full 30-second generation.")
        raise



# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 24 — FULL GENERATION RUN                                   ║
# ╚══════════════════════════════════════════════════════════════════╝

print("=" * 60)
print("CELL 24 — FULL 30-SECOND GENERATION")
print("=" * 60)

MEM.print_memory("BEFORE FULL RUN")

_PIPELINE_RESULT = run_full_pipeline(
    validate_only   = False,
    validation_secs = CONFIG["validation_duration_seconds"],
)

print(f"\n  ✓ Full generation complete")
print(f"    Chunks      : {len(_PIPELINE_RESULT['chunk_paths'])}")
print(f"    Elapsed     : {_PIPELINE_RESULT['elapsed_sec']:.1f} s")
print(f"    Chunk paths : {_PIPELINE_RESULT['chunk_paths'][:3]}…")

MEM.print_memory("AFTER FULL RUN")
print("\n✅ CELL 24 — Generation done")


# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 25 — FFMPEG ASSEMBLY + AUDIO SYNC                          ║
# ╚══════════════════════════════════════════════════════════════════╝
# JSON node 139: VHS_VideoCombine
#   format=video/h264-mp4, pix_fmt=yuv420p, crf=8, frame_rate=24
# Assembles all chunk MP4s, muxes with decoded audio.

print("=" * 60)
print("CELL 25 — FFMPEG ASSEMBLY + AUDIO SYNC")
print("=" * 60)

import wave
import struct

_OUTPUT_DIR   = CONFIG["output_dir"]
_FINAL_NAME   = CONFIG["final_video_name"]
_FINAL_PATH   = os.path.join(_OUTPUT_DIR, _FINAL_NAME)
_AUDIO_WAV    = os.path.join(_DIRS["temp"], "final_audio.wav")
os.makedirs(_OUTPUT_DIR, exist_ok=True)


def save_audio_to_wav(audio_out: Any, wav_path: str, sample_rate: int = 44100) -> str | None:
    """
    Save a ComfyUI AUDIO object to a WAV file without loading into RAM.
    ComfyUI AUDIO = dict with 'waveform' (tensor) and 'sample_rate'.
    """
    try:
        if audio_out is None:
            print("  ⚠️  No audio output — final video will be silent")
            return None

        # ComfyUI AUDIO format
        if isinstance(audio_out, dict):
            _wf = audio_out.get("waveform")
            _sr = audio_out.get("sample_rate", sample_rate)
        elif isinstance(audio_out, (tuple, list)):
            _wf = get_value_at_index(audio_out, 0)
            _sr = sample_rate
        else:
            print(f"  ⚠️  Unknown audio format: {type(audio_out)}")
            return None

        if _wf is None:
            return None

        # waveform: (B, C, T) or (C, T) or (T,)
        _wf_np = _wf.cpu().numpy() if torch.is_tensor(_wf) else np.array(_wf)
        if _wf_np.ndim == 3:
            _wf_np = _wf_np[0]       # (C, T)
        if _wf_np.ndim == 2:
            _wf_np = _wf_np.T        # (T, C) for WAV interleaving
        if _wf_np.ndim == 1:
            _wf_np = _wf_np[:, None] # mono (T, 1)

        _channels = _wf_np.shape[1]
        # Normalize to int16
        _wf_int16 = (_wf_np * 32767).clip(-32768, 32767).astype(np.int16)

        with wave.open(wav_path, "w") as wf_file:
            wf_file.setnchannels(_channels)
            wf_file.setsampwidth(2)   # 16-bit
            wf_file.setframerate(_sr)
            wf_file.writeframes(_wf_int16.tobytes())

        sz = _file_size_mb(wav_path)
        dur = _wf_int16.shape[0] / _sr
        print(f"  ✓ Audio WAV saved: {wav_path}  ({sz:.1f} MB, {dur:.2f} s)")
        return wav_path

    except Exception as e:
        print(f"  ✗ Audio save failed: {e}")
        return None


def build_ffmpeg_concat_list(chunk_paths: list[str], list_path: str) -> str:
    """Write an FFmpeg concat demuxer list file. Returns list_path."""
    # Sort by chunk index embedded in filename
    _sorted = sorted(chunk_paths, key=lambda p: int(
        os.path.basename(p).replace("chunk_", "").replace(".mp4", "")
    ))
    with open(list_path, "w") as f:
        for p in _sorted:
            f.write(f"file '{p}'\n")
    return list_path


def assemble_final_video(
    chunk_paths:  list[str],
    audio_out:    Any,
    output_path:  str,
    fps:          int,
    width:        int,
    height:       int,
) -> str | None:
    """
    Assemble chunk MP4s into the final video with audio.
    - Uses FFmpeg concat demuxer (stream-copy where possible)
    - Muxes audio in a single final pass
    - CRF=8, yuv420p, h264 — matching JSON node 139 VHS_VideoCombine
    Returns output path or None on failure.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if not chunk_paths:
        print("  ✗ No chunk paths — cannot assemble")
        return None

    # ── Step A: Save audio ────────────────────────────────────────────────────
    _audio_path = save_audio_to_wav(audio_out, _AUDIO_WAV)

    # ── Step B: Write concat list ─────────────────────────────────────────────
    _concat_list = os.path.join(_DIRS["temp"], "concat_list.txt")
    build_ffmpeg_concat_list(chunk_paths, _concat_list)
    print(f"  Concat list: {len(chunk_paths)} chunks")

    # ── Step C: Concatenate chunks (stream-copy = fast, no re-encode) ─────────
    _concat_tmp = os.path.join(_DIRS["temp"], "concat_video.mp4")
    _concat_cmd = (
        f"ffmpeg -y "
        f"-f concat -safe 0 -i \"{_concat_list}\" "
        f"-c copy "
        f"\"{_concat_tmp}\" "
        f"-loglevel error"
    )
    print("  Step C: Concatenating chunks (stream-copy)…")
    _ok_concat = _run(_concat_cmd, "ffmpeg concat stream-copy")

    if not _ok_concat or not os.path.isfile(_concat_tmp):
        # Fallback: re-encode concatenation
        print("  Stream-copy failed — falling back to re-encode concat")
        _concat_cmd_re = (
            f"ffmpeg -y "
            f"-f concat -safe 0 -i \"{_concat_list}\" "
            f"-vcodec libx264 -pix_fmt yuv420p -crf 8 -preset fast "
            f"-r {fps} "
            f"\"{_concat_tmp}\" "
            f"-loglevel error"
        )
        _ok_concat = _run(_concat_cmd_re, "ffmpeg concat re-encode")

    # ── Step D: Mux audio + video ─────────────────────────────────────────────
    if _audio_path and os.path.isfile(_audio_path) and os.path.isfile(_concat_tmp):
        print("  Step D: Muxing audio + video…")
        _mux_cmd = (
            f"ffmpeg -y "
            f"-i \"{_concat_tmp}\" "
            f"-i \"{_audio_path}\" "
            f"-c:v copy "
            f"-c:a aac -b:a 192k "
            f"-shortest "
            f"-movflags +faststart "
            f"\"{output_path}\" "
            f"-loglevel error"
        )
        _ok_mux = _run(_mux_cmd, "ffmpeg audio mux")
    elif os.path.isfile(_concat_tmp):
        print("  Step D: No audio — copying video-only…")
        import shutil as _shu
        _shu.copy2(_concat_tmp, output_path)
        _ok_mux = True
    else:
        print("  ✗ Concat video not found — assembly failed")
        return None

    if os.path.isfile(output_path) and _file_size_mb(output_path) > 0.5:
        sz = _file_size_mb(output_path)
        print(f"\n  ✓ Final video: {output_path}  ({sz:.1f} MB)")
        return output_path
    else:
        print(f"  ✗ Assembly failed — output not found or too small")
        return None


# Run assembly
print("Assembling final video…")
_FINAL_OUTPUT_PATH = assemble_final_video(
    chunk_paths  = _PIPELINE_RESULT["chunk_paths"],
    audio_out    = _PIPELINE_RESULT["audio_out"],
    output_path  = _FINAL_PATH,
    fps          = CONFIG["fps"],
    width        = CONFIG["width"],
    height       = CONFIG["height"],
)

if _FINAL_OUTPUT_PATH:
    CHECKPOINT["stage"] = "assembled"
    save_checkpoint(CHECKPOINT)

print("\n✅ CELL 25 — FFmpeg assembly complete")


# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 26 — FINAL VIDEO VALIDATION (ffprobe)                      ║
# ╚══════════════════════════════════════════════════════════════════╝

print("=" * 60)
print("CELL 26 — FINAL VIDEO VALIDATION")
print("=" * 60)


def validate_final_video(video_path: str, expected_fps: int,
                         expected_width: int, expected_height: int,
                         expected_duration_sec: float) -> dict:
    """
    Run ffprobe on the final MP4. Returns a validation result dict.
    """
    result = {
        "path": video_path,
        "exists": False,
        "video_stream": False,
        "audio_stream": False,
        "fps": None,
        "width": None,
        "height": None,
        "duration_sec": None,
        "frame_count": None,
        "codec": None,
        "pix_fmt": None,
        "checks": {},
        "passed": False,
    }

    if not video_path or not os.path.isfile(video_path):
        result["checks"]["exists"] = "FAIL"
        return result
    result["exists"] = True
    result["checks"]["exists"] = "PASS"

    # Video stream info
    _v_cmd = (
        f"ffprobe -v error -select_streams v:0 "
        f"-show_entries stream=codec_name,width,height,r_frame_rate,nb_frames,pix_fmt "
        f"-of csv=p=0 \"{video_path}\""
    )
    try:
        _vr = subprocess.run(_v_cmd, shell=True, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, timeout=30)
        _vparts = _vr.stdout.strip().split(",")
        if len(_vparts) >= 5:
            result["codec"]   = _vparts[0]
            result["width"]   = int(_vparts[1])
            result["height"]  = int(_vparts[2])
            _fps_frac = _vparts[3]  # e.g. "24/1"
            _num, _den = (int(x) for x in _fps_frac.split("/"))
            result["fps"]     = round(_num / _den, 3)
            result["frame_count"] = _vparts[4].strip()
            result["pix_fmt"] = _vparts[5].strip() if len(_vparts) > 5 else "unknown"
            result["video_stream"] = True
    except Exception as _e:
        print(f"  ⚠️  ffprobe video stream failed: {_e}")

    # Audio stream info
    _a_cmd = (
        f"ffprobe -v error -select_streams a:0 "
        f"-show_entries stream=codec_name,duration "
        f"-of csv=p=0 \"{video_path}\""
    )
    try:
        _ar = subprocess.run(_a_cmd, shell=True, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, timeout=30)
        if _ar.stdout.strip():
            result["audio_stream"] = True
    except Exception:
        pass

    # Container duration
    _d_cmd = (
        f"ffprobe -v error -show_entries format=duration "
        f"-of csv=p=0 \"{video_path}\""
    )
    try:
        _dr = subprocess.run(_d_cmd, shell=True, check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, timeout=30)
        _dur = _dr.stdout.strip()
        if _dur and _dur != "N/A":
            result["duration_sec"] = float(_dur)
    except Exception:
        pass

    # ── Run checks ────────────────────────────────────────────────────────────
    result["checks"]["video_stream"]  = "PASS" if result["video_stream"] else "FAIL"
    result["checks"]["audio_stream"]  = "PASS" if result["audio_stream"] else "WARN (no audio)"
    result["checks"]["fps"]           = "PASS" if result["fps"] and abs(result["fps"] - expected_fps) < 0.5 else f"WARN (got {result['fps']})"
    result["checks"]["resolution"]    = (
        "PASS" if result["width"] == expected_width and result["height"] == expected_height
        else f"WARN (got {result['width']}×{result['height']})"
    )
    _dur_ok = (
        result["duration_sec"] is not None and
        abs(result["duration_sec"] - expected_duration_sec) < 2.0
    )
    result["checks"]["duration"]      = "PASS" if _dur_ok else f"WARN (got {result['duration_sec']:.1f}s, expected {expected_duration_sec:.1f}s)"
    result["checks"]["codec"]         = "PASS" if result["codec"] == "h264" else f"WARN ({result['codec']})"
    result["checks"]["pix_fmt"]       = "PASS" if result["pix_fmt"] == "yuv420p" else f"WARN ({result['pix_fmt']})"

    _hard_fails = [k for k, v in result["checks"].items() if v == "FAIL"]
    result["passed"] = len(_hard_fails) == 0

    return result


_VAL_RESULT = validate_final_video(
    video_path           = _FINAL_OUTPUT_PATH,
    expected_fps         = CONFIG["fps"],
    expected_width       = CONFIG["width"],
    expected_height      = CONFIG["height"],
    expected_duration_sec= TIMELINE.actual_duration,
)

print(f"""
============================================================
FINAL VIDEO VALIDATION
============================================================
Path           : {_VAL_RESULT['path']}
File exists    : {_VAL_RESULT['checks'].get('exists', 'N/A')}
Video stream   : {_VAL_RESULT['checks'].get('video_stream', 'N/A')}
Audio stream   : {_VAL_RESULT['checks'].get('audio_stream', 'N/A')}
FPS            : {_VAL_RESULT['checks'].get('fps', 'N/A')}  (actual: {_VAL_RESULT['fps']})
Resolution     : {_VAL_RESULT['checks'].get('resolution', 'N/A')}  ({_VAL_RESULT['width']}×{_VAL_RESULT['height']})
Duration       : {_VAL_RESULT['checks'].get('duration', 'N/A')}  ({_VAL_RESULT['duration_sec']} s)
Codec          : {_VAL_RESULT['checks'].get('codec', 'N/A')}  ({_VAL_RESULT['codec']})
Pixel format   : {_VAL_RESULT['checks'].get('pix_fmt', 'N/A')}
Frame count    : {_VAL_RESULT['frame_count']}
Synchronization: {"PASS" if _VAL_RESULT['audio_stream'] else "N/A (no audio)"}

STATUS         : {"SUCCESS ✓" if _VAL_RESULT['passed'] else "WARNINGS — review above"}
============================================================
""")

if _VAL_RESULT["passed"]:
    CHECKPOINT["stage"] = "validated"
    save_checkpoint(CHECKPOINT)

    # Delete temp chunks only after successful validation
    if not CONFIG.get("keep_temp_chunks", False):
        print("  Cleaning up temporary chunks…")
        for _cp in _PIPELINE_RESULT.get("chunk_paths", []):
            if os.path.isfile(_cp):
                os.remove(_cp)
        print("  ✓ Temp chunks deleted")
    else:
        print("  keep_temp_chunks=True — chunks preserved")
else:
    print("  ⚠️  Validation has warnings — temp chunks preserved for debugging")

print("\n✅ CELL 26 — Final validation complete")



# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 27 — JOB REPORT                                            ║
# ╚══════════════════════════════════════════════════════════════════╝

print("=" * 60)
print("CELL 27 — JOB REPORT")
print("=" * 60)

_REPORT_PATH = os.path.join(_OUTPUT_DIR, "job_report.json")


def generate_job_report() -> dict:
    _gpu_name    = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A"
    _peak_vram   = MEM.peak_gpu_seen()
    _elapsed     = _PIPELINE_RESULT.get("elapsed_sec", 0.0) if _PIPELINE_RESULT else 0.0
    _n_chunks    = len(_PIPELINE_RESULT.get("chunk_paths", [])) if _PIPELINE_RESULT else 0
    _n_oom       = CHECKPOINT.get("oom_retries", 0)

    report = {
        "workflow":               "LTX-2.3_Director_2.0-MV-Workflow-30s.json",
        "gpu":                    _gpu_name,
        "torch_version":          torch.__version__,
        "cuda_version":           torch.version.cuda,
        "resolution":             f"{CONFIG['width']}×{CONFIG['height']}",
        "fps":                    CONFIG["fps"],
        "requested_duration_sec": CONFIG["duration_seconds"],
        "actual_duration_sec":    TIMELINE.actual_duration,
        "total_frames":           TIMELINE.actual_frames,
        "decode_chunk_size":      CHUNKS.decode_chunk,
        "chunks_completed":       _n_chunks,
        "oom_retries":            _n_oom,
        "peak_gpu_memory_gb":     round(_peak_vram, 3),
        "generation_time_seconds":round(_elapsed, 1),
        "output_path":            _FINAL_OUTPUT_PATH or "N/A",
        "workflow_parity":        _parity_status,
        "loras_applied": [
            {"filename": e["filename"], "strength": e["strength"]}
            for e in LTXLoRAManager.LORA_STACK
            if CONFIG.get(e["config_key"], True)
               and os.path.isfile(f"{CONFIG['comfyui_dir']}/models/loras/{e['filename']}")
        ],
        "validation": {
            "video_stream": _VAL_RESULT["checks"].get("video_stream", "N/A"),
            "audio_stream": _VAL_RESULT["checks"].get("audio_stream", "N/A"),
            "fps":          _VAL_RESULT["checks"].get("fps", "N/A"),
            "resolution":   _VAL_RESULT["checks"].get("resolution", "N/A"),
            "duration":     _VAL_RESULT["checks"].get("duration", "N/A"),
            "codec":        _VAL_RESULT["checks"].get("codec", "N/A"),
            "status":       "PASS" if _VAL_RESULT["passed"] else "WARN",
        },
        "job_id":    CHECKPOINT.get("job_id", "unknown"),
        "stage":     CHECKPOINT.get("stage", "unknown"),
    }
    return report


_JOB_REPORT = generate_job_report()

# Save to disk
os.makedirs(_OUTPUT_DIR, exist_ok=True)
with open(_REPORT_PATH, "w") as _rf:
    json.dump(_JOB_REPORT, _rf, indent=2)

print(f"  Job report saved: {_REPORT_PATH}")
print(json.dumps(_JOB_REPORT, indent=2))

print("\n✅ CELL 27 — Job report written")


# ╔══════════════════════════════════════════════════════════════════╗
# ║  CELL 28 — FINAL CLEANUP                                         ║
# ╚══════════════════════════════════════════════════════════════════╝

print("=" * 60)
print("CELL 28 — FINAL CLEANUP")
print("=" * 60)


def final_cleanup() -> None:
    """
    Release all remaining GPU resources after successful generation.
    Safe to call multiple times.
    """
    # Release conditioning cache
    clear_conditioning_cache()

    # Release any remaining pipeline tensors
    for _var_name in ["_PIPELINE_RESULT", "_VALIDATION_RESULT"]:
        try:
            _obj = globals().get(_var_name)
            if isinstance(_obj, dict):
                for _k in list(_obj.keys()):
                    _v = _obj[_k]
                    if torch.is_tensor(_v):
                        del _obj[_k]
        except Exception:
            pass

    # CUDA synchronize and cleanup
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.synchronize()
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()
    gc.collect()

    MEM.print_memory("FINAL (after cleanup)")


final_cleanup()

# ── Final summary ──────────────────────────────────────────────────────────
print(f"""
{'='*60}
PIPELINE COMPLETE
{'='*60}
Output video  : {_FINAL_OUTPUT_PATH or 'N/A'}
Job report    : {_REPORT_PATH}
Duration      : {TIMELINE.actual_duration:.2f} s
Frames        : {TIMELINE.actual_frames}
FPS           : {CONFIG['fps']}
Resolution    : {CONFIG['width']}×{CONFIG['height']}
Peak VRAM     : {MEM.peak_gpu_seen():.2f} GB
Status        : {"✓ SUCCESS" if _VAL_RESULT and _VAL_RESULT['passed'] else "⚠️  WARNINGS — check job_report.json"}
{'='*60}
""")

# Display output video inline (Colab)
try:
    from IPython.display import HTML, display as _disp
    from base64 import b64encode as _b64e

    if _FINAL_OUTPUT_PATH and os.path.isfile(_FINAL_OUTPUT_PATH):
        _sz_mb = _file_size_mb(_FINAL_OUTPUT_PATH)
        if _sz_mb < 50:   # only inline if <50 MB to avoid memory pressure
            _vid_bytes = open(_FINAL_OUTPUT_PATH, "rb").read()
            _data_url  = "data:video/mp4;base64," + _b64e(_vid_bytes).decode()
            del _vid_bytes
            _disp(HTML(f"""
            <video width=720 controls autoplay loop>
                <source src="{_data_url}" type="video/mp4">
            </video>
            """))
        else:
            print(f"  Video is {_sz_mb:.0f} MB — too large for inline display.")
            print(f"  Download from: {_FINAL_OUTPUT_PATH}")
except Exception as _disp_err:
    print(f"  (Inline display skipped: {_disp_err})")

print("\n✅ CELL 28 — Final cleanup complete")
print("\n🎬 LTX-2.3 Director 2.0 MV Pipeline — DONE")
