# NVIDIA Brev CLI (excerpt for the wizard demo)

> Illustrative excerpt assembled from Brev's public CLI docs, used only to
> demonstrate `pilot wizard`'s doc analysis offline.

## Install

Linux / WSL:

```bash
curl -fsSL https://raw.githubusercontent.com/brevdev/brev-cli/main/bin/install-latest.sh | bash
```

Then authenticate:

```bash
brev login
```

## Common commands

```bash
brev ls
brev create my-gpu-box --gpu A100:1
brev shell my-gpu-box
brev stop my-gpu-box
brev create another-box --gpu g5.xlarge:A10G:1
brev ls
```
