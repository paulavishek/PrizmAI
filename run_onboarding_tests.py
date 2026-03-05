"""
Run onboarding tests and write results to test_onboarding_result.txt
Usage: python run_onboarding_tests.py
"""
import subprocess
import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

result = subprocess.run(
    [sys.executable, "manage.py", "test",
     "tests.test_kanban.test_onboarding",
     "--no-input", "-v", "2", "--traceback"],
    capture_output=True,
    text=True,
    timeout=300,
)

output = result.stdout + "\n" + result.stderr

with open("test_onboarding_result.txt", "w", encoding="utf-8") as f:
    f.write(output)

print(f"Exit code: {result.returncode}")
print(f"Results written to test_onboarding_result.txt")
