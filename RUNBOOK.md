# RUNBOOK (PS 5.1)
cd C:\Users\user\Desktop\Франкинштэйн
python -m venv .venv
.\.venv\Scripts\pip install -r ops\patchpack\requirements.txt
powershell -ExecutionPolicy Bypass -File ops\patchpack\apply_patch.ps1
python factory_master_triage_247.py
