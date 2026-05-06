# WSL Quickstart

You are using the WSL2 distribution named `UbuntuBio`.

## What Codex Can Do

Codex can call WSL from Windows using commands like:

```powershell
wsl.exe -d UbuntuBio -- bash -lc "cd /home/zhizi/projects/ncppb-xanthomonas-audit && pwd"
```

This means Codex can create folders, write scripts, run Python, inspect outputs, and debug errors inside UbuntuBio.

## What You May Need To Do Manually

Some actions require your Linux password, especially commands beginning with `sudo`. If virtual environment creation fails with `ensurepip is not available`, run this inside UbuntuBio:

```bash
sudo apt update
sudo apt install -y python3.12-venv python3-pip
```

Then create the project environment:

```bash
cd /home/zhizi/projects/ncppb-xanthomonas-audit
python3 -m venv --clear .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Basic Commands To Know

```bash
pwd         # show current directory
ls          # list files
cd folder   # enter a folder
cd ..       # go up one folder
mkdir name  # create a folder
source .venv/bin/activate  # activate Python environment
python --version           # check active Python
```

## Where Files Are

Linux project path:

```text
/home/zhizi/projects/ncppb-xanthomonas-audit
```

Windows Downloads path as seen from WSL:

```text
/mnt/c/Users/0329z/Downloads
```
