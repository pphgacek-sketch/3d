import os
import re
import subprocess
import tempfile
import time
import urllib.request
import urllib.error
import json
from dataclasses import dataclass
from typing import Optional

@dataclass
class ExecutionResult:
    ok: bool
    step_path: Optional[str]
    stdout: str
    stderr: str
    error: Optional[str]

def _inject_output_path(script: str, step_path: str) -> str:
    replacement = 'r"' + step_path + '"'
    repl_escaped = replacement.replace('\\', '\\\\')
    script = re.sub(r'''["']?OUTPUT_PATH["']?''', repl_escaped, script)
    script = re.sub(
        r'''r?["']([A-Za-z]:[/\\][^"']*\.step|/[^"']*\.step)["']''',
        repl_escaped,
        script,
    )
    return script

def run_cadquery(script: str, output_dir: str, model_name: str,
                 python_exe: str = "python",
                 keep_script: bool = True) -> ExecutionResult:
    os.makedirs(output_dir, exist_ok=True)
    step_path = os.path.join(output_dir, f"{model_name}.step")
    script_final = _inject_output_path(script, step_path)
    if keep_script:
        script_path = os.path.join(output_dir, f"{model_name}.py")
    else:
        tmp = tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8")
        tmp.write(script_final)
        tmp.close()
        script_path = tmp.name
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_final)
    try:
        result = subprocess.run(
            [python_exe, script_path],
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8",
            errors="replace",
        )
        stdout = result.stdout
        stderr = result.stderr
        if result.returncode != 0:
            return ExecutionResult(
                ok=False,
                step_path=None,
                stdout=stdout,
                stderr=stderr,
                error=f"Skrypt zakonczyl sie bledem (exit code {result.returncode}):\n{stderr}",
            )
        if not os.path.exists(step_path):
            return ExecutionResult(
                ok=False,
                step_path=None,
                stdout=stdout,
                stderr=stderr,
                error=(
                    f"Skrypt wykonal sie bez bledow, ale plik STEP nie powstal: {step_path}\n"
                    f"Sprawdz czy sciezka eksportu jest poprawna w skrypcie."
                ),
            )
        return ExecutionResult(
            ok=True,
            step_path=step_path,
            stdout=stdout,
            stderr=stderr,
            error=None,
        )
    except subprocess.TimeoutExpired:
        return ExecutionResult(
            ok=False, step_path=None, stdout="", stderr="",
            error="Timeout: skrypt nie zakonczyl sie w 120 sekund",
        )
    except FileNotFoundError:
        return ExecutionResult(
            ok=False, step_path=None, stdout="", stderr="",
            error=(
                f"Nie znaleziono interpretera Python: '{python_exe}'\n"
                f"Ustaw sciezke w Ustawienia -> Python (CadQuery).\n"
                f"Przyklad: C:\\Users\\<user>\\miniconda3\\envs\\cadquery\\python.exe"
            ),
        )
    finally:
        if not keep_script and os.path.exists(script_path):
            try:
                os.unlink(script_path)
            except Exception:
                pass

def run_fusion(script: str, output_dir: str, model_name: str,
               fusion_url: str = "http://localhost:7634",
               timeout: int = 60) -> ExecutionResult:
    os.makedirs(output_dir, exist_ok=True)
    step_path = os.path.join(output_dir, f"{model_name}.step")
    script_final = _inject_output_path(script, step_path)
    try:
        urllib.request.urlopen(f"{fusion_url}/ping", timeout=5).read()
    except Exception as e:
        return ExecutionResult(
            ok=False, step_path=None, stdout="", stderr="",
            error=(
                f"FusionBridge niedostepny pod {fusion_url}\n"
                f"Upewnij sie ze Fusion 360 jest uruchomiony z FusionBridge Add-In.\n"
                f"Szczegoly: {e}"
            ),
        )
    payload = json.dumps({
        "script": script_final,
        "model_name": model_name,
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            f"{fusion_url}/run_script",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result_data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return ExecutionResult(
            ok=False, step_path=None, stdout="", stderr="",
            error=f"FusionBridge HTTP {e.code}: {body}",
        )
    except urllib.error.URLError as e:
        return ExecutionResult(
            ok=False, step_path=None, stdout="", stderr="",
            error=f"Blad polaczenia z FusionBridge: {e.reason}",
        )
    except Exception as e:
        return ExecutionResult(
            ok=False, step_path=None, stdout="", stderr="",
            error=f"Nieoczekiwany blad: {e}",
        )
    fusion_ok = result_data.get("ok", False)
    fusion_result = result_data.get("result", "")
    fusion_error = result_data.get("error", "")
    if not fusion_ok:
        return ExecutionResult(
            ok=False, step_path=None,
            stdout=fusion_result, stderr="",
            error=f"Fusion 360 zwrocil blad:\n{fusion_error}",
        )
    for _ in range(10):
        if os.path.exists(step_path):
            break
        time.sleep(0.5)
    if not os.path.exists(step_path):
        return ExecutionResult(
            ok=False, step_path=None,
            stdout=fusion_result, stderr="",
            error=(
                f"Fusion wykonal skrypt ale plik STEP nie powstal: {step_path}\n"
                f"Odpowiedz Fusion: {fusion_result}"
            ),
        )
    return ExecutionResult(
        ok=True,
        step_path=step_path,
        stdout=fusion_result,
        stderr="",
        error=None,
    )

def execute(script: str, backend: str, output_dir: str, model_name: str,
            python_exe: str = "python",
            keep_script: bool = True,
            fusion_url: str = "http://localhost:7634",
            fusion_timeout: int = 60) -> ExecutionResult:
    if backend == "cadquery":
        return run_cadquery(
            script, output_dir, model_name,
            python_exe=python_exe,
            keep_script=keep_script,
        )
    elif backend == "fusion":
        return run_fusion(
            script, output_dir, model_name,
            fusion_url=fusion_url,
            timeout=fusion_timeout,
        )
    else:
        return ExecutionResult(
            ok=False, step_path=None, stdout="", stderr="",
            error=f"Nieznany backend: {backend}",
        )
