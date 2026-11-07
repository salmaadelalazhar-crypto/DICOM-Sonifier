"""Run the built exe for 30 seconds; pass if it is still alive (did not crash/close)."""
import subprocess
import sys
import time

exe = sys.argv[1] if len(sys.argv) > 1 else r"dist\DICOMSonifier\DICOMSonifier.exe"
proc = subprocess.Popen([exe])
for _ in range(30):
    time.sleep(1)
    if proc.poll() is not None:
        print(f"FAIL: app exited early with code {proc.returncode}")
        sys.exit(1)
print("PASS: app ran for 30 seconds without closing")
proc.kill()
sys.exit(0)
