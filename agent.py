import re
from PyQt6.QtCore import QThread, pyqtSignal
from executor import execute
from copilot_api import copilot_prompt

def extract_code(text):
    """Wyciągnij kod z markdowna Copilota."""
    match = re.search(r"```(?:python)?\n(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()

class AgentWorker(QThread):
    progress = pyqtSignal(int, str)
    log      = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, description, settings, model_name="model"):
        super().__init__()
        self.description = description
        self.settings = settings
        self.model_name = re.sub(r"[^\w\-]", "_", model_name)

    def run(self):
        try:
            self._run_pipeline(self.settings)
        except Exception:
            import traceback
            self.error.emit(f"Nieoczekiwany błąd:\n{traceback.format_exc()}")

    def _run_pipeline(self, s):
        summary = {"history": []}
        api_model = s.model if hasattr(s, "model") else "gpt-4o"

        self.log.emit(f"[Agent] Start | AI model: {api_model}, backend: {s.backend}")

        # Prompt: wprowadzenie + opis użytkownika
        system = (
            "Jesteś ekspertem CAD, Twoim zadaniem jest: "
            "1) analiza opisu modelu, "
            "2) wylistowanie wszystkich elementów, 3) wyznaczenie dokładnego 3D layoutu z translate(), "
            "4) wygenerowanie pełnego skryptu CadQuery/Fusion (z eksportem STEP!), "
            "5) jeśli kod jest błędny – zidentyfikuj i napraw automatycznie, wyjaśnij powód naprawy. "
            "Przy każdym retry zapisz krótko co i dlaczego poprawiasz. "
            "Odpowiedzi zawsze bez zbędnych tłumaczeń, wyraź wyodrębnij kod ```python ... ```."
        )

        # Budujemy kontekst historii
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": self.description}]

        script = None
        last_report = ""
        max_retries = getattr(s, "max_retries", 3)

        for attempt in range(1, max_retries+1):
            self.progress.emit(1, f"Próba {attempt} pipeline AI…")
            self.log.emit(f"\n[AI] GENERACJA / NAPRAWA | Attempt {attempt}")

            ai_response = copilot_prompt(messages, max_tokens=8192, model=api_model)
            script = extract_code(ai_response)
            summary["history"].append({"attempt": attempt, "ai_response": ai_response[:800]})

            self.log.emit(f"[AI] Wygenerowany kod:\n\n{script[:500]}...\n[...]")

            # Wykonaj (lokalnie — executor nie zmienia się)
            self.progress.emit(2, f"Wykonywanie ({s.backend})…")
            exec_result = execute(
                script=script,
                backend=s.backend,
                output_dir=s.output_dir,
                model_name=self.model_name,
                python_exe=s.cq_python,
                keep_script=s.keep_scripts,
                fusion_url=s.fusion_url,
                fusion_timeout=s.fusion_timeout,
            )

            if exec_result.ok:
                self.log.emit(f"[AI] SUKCES! Wygenerowano: {exec_result.step_path}")
                self.finished.emit({
                    "step_path": exec_result.step_path,
                    "script": script,
                    "ai_history": summary["history"],
                    "backend": s.backend,
                    "attempts": attempt,
                })
                return

            else:
                err_report = (
                    f"Skrypt się nie wykonał:\n{exec_result.error}\n"
                    f"stderr:\n{exec_result.stderr[:600]}"
                )
                self.log.emit(f"[AI] Blad wykonania, retry…")

                # Dodaj krótki prompt po polsku (lub angielsku) – do Copilota jako kontekst "dlaczego retry"
                messages.append({"role": "assistant", "content": ai_response})
                messages.append({"role": "user", "content": f"Poprzedni kod wywołał błąd runtime:\n{err_report}\n\nPopraw kod, wytłumacz co było źle i wykonaj ponownie całą pipeline."})
                last_report = err_report

        # Wszystkie próby wyczerpane
        self.error.emit(f"AI nie wygenerował działającego skryptu po {max_retries} próbach.\nOstatni raport:\n{last_report}")
