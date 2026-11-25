# OmniParser V2 local validation

The optional environment is installed at `.aiwork/omni/venv`. Microsoft
source and all three Hugging Face snapshots match the pins in
`aiwork/perception.py`. EasyOCR loaded its cached English detection and
recognition weights. The RTX 5070 Laptop GPU reported compute capability
12.0 on driver 616.56. PyTorch 2.7.1+cu128 and torchvision 0.22.1+cu128
passed a CUDA tensor operation and CUDA non-maximum suppression. Offline
Florence checkpoint loading reported no missing or mismatched keys.

The public Hugging Face setup uses anonymous downloads because the
machine's cached token was expired. Serial downloads avoid a concurrent
cache symlink race on Windows. No system permissions were changed.

## One synthetic GPU benchmark

The fixture was a 1050×650 fabricated project settings screen. The controller
ran one offline parse under the existing exclusive laptop GPU reservation
and the 4 GiB free-RAM and 6 GiB free-VRAM admission floors.

| Measurement | Result |
| --- | --- |
| Initialization, including imports and loading models | 11.531 s |
| OCR, detection and caption inference, with GPU synchronization | 2.891 s |
| Total controller elapsed | 16.187 s |
| Detected elements | 15, comprising 6 text regions and 9 detector regions |
| CUDA peak allocated by PyTorch | 1.994 GiB |
| System RAM available | 11.862 GiB before, 9.149 GiB sampled minimum, 11.900 GiB after cleanup |
| GPU free memory | 7.706 GiB before, 5.324 GiB minimum, 7.706 GiB after cleanup |
| Cleanup | Owned worker exited and free VRAM returned to its preflight reading |

There were 29 system memory samples. Windows reported a 0.25 GiB difference
between total and free VRAM before and after, so the free-memory readings
are the basis for the reported change. The controller samples are
system-wide and can reflect other processes. The one-shot timing is for a
fresh parser process after installation checks. Detector counts include
buttons and overlapping regions, and several captions were imprecise.

[Benchmark receipt](evidence/local-omniparser/benchmark.json) ·
[CUDA receipt](evidence/local-omniparser/cuda-receipt.json) ·
[Synthetic PNG](evidence/local-omniparser/synthetic-ui.png)

## Interactive capture and preview

The live loopback capture path returned a 1707×1067 image while a controlled
solid-color fixture was foreground. Every returned pixel matched the
fixture, and the check retained no pixels. The in-app browser loaded the
synthetic benchmark image and replayed its measured observations. It
displayed all 15 elements, drew annotations, highlighted the selected
region, and enabled local JSON export. This reused the one benchmark
result. The temporary fixture window, browser tab and listener were closed.

[Capture receipt](evidence/local-omniparser/capture-receipt.json) ·
[Preview observations](evidence/local-omniparser/preview-receipt.json)

## Restored regression coverage

| Previously skipped dependency group | Tests |
| --- | ---: |
| Installed OpenCode, inert provider and loopback | 10 |
| Offline Docker verification image | 8 |
| OpenCode and offline Docker together | 2 |
| Installed Pi SDK with inert provider | 6 |
| Offline Jinja image for pinned Qwen template rendering | 1 |

All 27 were gated by opt-in environment variables. The run enabled the
installed harnesses and pinned images, then passed all 271 existing tests.
It used no real language-model inference. New screen-tool tests cover
exact approval hashes, rejection of remote or automatic routing, frozen
evidence drift, bounded read-only retrieval and provider-facing OpenCode
catalog behavior.
The first integrated test rejected the new tool at the existing MCP preflight.
The corrected preflight requires the screen schema only for an approved job.
After that correction, all 25 focused tests passed, including an installed
OpenCode invocation with an inert provider that called the tool successfully.

The baseline wheel at `be627c6` retained SHA-256
`5e2111e936de977e8fd9a9b51059d3255d8e01843f8fa084795e8783103f92bb`.
No A100 services were contacted or changed.
