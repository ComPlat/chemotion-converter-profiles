from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, List, Union

try:
    from ollama import Client  # Official Ollama Python library
except ImportError:  # optional, local-only dependency (deliberately not in requirements.txt)
    Client = None


class ExplainError(RuntimeError):
    """Raised when an explanation could not be produced (bad input, no client, LLM failure)."""


@dataclass(frozen=True)
class OllamaConfig:
    """
    Configuration for the local Ollama client.

    Notes:
        - Default Ollama host is typically http://localhost:11434
        - Ensure you pulled the model locally (e.g., `ollama pull llama3:8b`)
    """
    host: str = "http://localhost:11434"
    model: str = "qwen3:8B"
    temperature: float = 0.2
    num_ctx: Optional[int] = 4096


class ReaderFunctionBlockExplainer:
    """
    Explains a Python function block (belonging to a Reader) as 3–5 bullet points
    using a local Ollama LLM via the official Ollama Python library.

    Output contract:
        - EXACTLY 3–5 lines
        - Each line starts with "- "
        - No additional text
    """

    def __init__(self, config: OllamaConfig):
        if Client is None:
            raise ExplainError(
                "The 'ollama' package is not installed. Install it locally with `pip install ollama` "
                "to regenerate explanations."
            )
        self.config = config
        self.client = Client(host=config.host)

    def explain(self, code_block: str) -> str:
        """
        Args:
            code_block: Python function code as a string (optionally fenced with ```python ... ```).

        Returns:
            A string containing 3–5 bullet points.

        Raises:
            ValueError: If the input doesn't look like a Python function definition.
            ExplainError: If the LLM call itself fails (server down, model missing, timeout).
        """
        code = self._extract_python_from_fences(code_block).strip()
        if not self._looks_like_function(code):
            raise ValueError(
                "Input does not appear to contain a Python function definition. "
                "Please provide a block that includes at least one `def ...`."
            )

        system_msg = (
            "You are a technical documentation assistant.\n"
            "Context: The code belongs to a Reader component (reading/parsing/iterating over input).\n"
            "Rules:\n"
            "- Output ONLY 3 to 5 bullet points.\n"
            "- Each bullet describes one concrete responsibility or behavior.\n"
            "- Keep each bullet short (ideally <= 18 words).\n"
            "- No headings, no preface, no numbering, no extra text.\n"
            "- Use '-' as the bullet marker."
        )

        user_msg = (
            "Explain the following Python function block as 3–5 bullets:\n\n"
            f"```python\n{code}\n```"
        )

        options = {"temperature": self.config.temperature}
        if self.config.num_ctx is not None:
            options["num_ctx"] = self.config.num_ctx

        try:
            response = self.client.chat(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                options=options,
            )
        except KeyboardInterrupt:
            # Never swallow an interrupt; the caller keeps whatever it has cached so far.
            raise
        except Exception as exc:
            raise ExplainError(
                f"Ollama call failed for model {self.config.model!r} at {self.config.host}: {exc}"
            ) from exc

        content = self._extract_chat_content(response)
        return self._normalize_to_3_5_bullets(content)

    def explain_safe(self, code_block: str, name: str = "") -> Optional[str]:
        """
        Guarded variant of `explain`: never raises (except on KeyboardInterrupt), returns
        None on failure so a single bad reader cannot abort a whole build run.
        """
        label = name or "<unnamed block>"
        try:
            return self.explain(code_block)
        except KeyboardInterrupt:
            raise
        except (ValueError, ExplainError) as exc:
            print(f"Skipping {label}: {exc}")
        except Exception as exc:  # unexpected shapes from the client library
            print(f"Skipping {label}: unexpected error during explanation: {exc}")
        return None

    @staticmethod
    def _extract_chat_content(chat_response: dict) -> str:
        """
        The ollama-python chat response contains the generated text in:
            response['message']['content']
        """
        try:
            return str(chat_response["message"]["content"])
        except Exception:
            # Best-effort fallback for unexpected shapes
            return str(chat_response)

    @staticmethod
    def _extract_python_from_fences(text: str) -> str:
        match = re.search(
            r"```(?:python)?\s*(.*?)\s*```",
            text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        return match.group(1) if match else text

    @staticmethod
    def _looks_like_function(code: str) -> bool:
        return bool(re.search(r"^\s*def\s+\w+\s*\(", code, flags=re.MULTILINE))

    @staticmethod
    def _normalize_to_3_5_bullets(text: str) -> str:
        """
        Enforce output constraints:
            - 3–5 bullets
            - each bullet is one line starting with '- '
        """
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

        bullets: List[str] = []
        for ln in lines:
            if re.match(r"^[-*•]\s+", ln):
                bullets.append(re.sub(r"^[-*•]\s+", "", ln).strip())

        if not bullets:
            # Fallback: turn sentences into bullets
            joined = " ".join(lines)
            sentences = re.split(r"(?<=[.!?])\s+", joined)
            bullets = [s.strip().rstrip(".") for s in sentences if s.strip()]

        bullets = [re.sub(r"\s+", " ", b).strip(" -•*\t\r\n") for b in bullets]
        bullets = [b for b in bullets if b]

        # Ensure at least 3 bullets (best-effort splitting)
        if len(bullets) < 3:
            expanded: List[str] = []
            for b in bullets:
                parts = re.split(r"[;]\s+|,\s+(?=[A-Za-z])", b)
                parts = [p.strip() for p in parts if p.strip()]
                expanded.extend(parts if len(parts) > 1 else [b])
            bullets = expanded

        bullets = bullets[:5]
        while len(bullets) < 3:
            bullets.append("Performs a reader-related processing step based on the provided inputs")

        bullets = bullets[:5]
        return "\n".join(f"- {b}" for b in bullets)


# --- Translation cache (code_explainer.json) -------------------------------------------
# These helpers deliberately do not touch the Ollama client, so they stay importable in
# CI where the optional `ollama` package is absent.

def load_translations(path: Union[str, Path]) -> Dict[str, str]:
    """
    Load the explanation cache. Returns an empty dict if the file is missing, unreadable
    or contains invalid/unexpected JSON - a broken cache must never break the build.
    """
    cache_path = Path(path)
    if not cache_path.exists():
        return {}

    try:
        with cache_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        print(f"Ignoring unreadable translation cache {cache_path}: {exc}")
        return {}

    if not isinstance(data, dict):
        print(f"Ignoring translation cache {cache_path}: expected a JSON object")
        return {}

    return {str(k): v for k, v in data.items() if isinstance(v, str)}


def save_translations(path: Union[str, Path], translations: Dict[str, str]) -> bool:
    """
    Write the cache atomically (temp file + replace) so an interrupted run cannot leave a
    truncated JSON behind. Returns True on success, False if writing failed.
    """
    cache_path = Path(path)
    tmp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")

    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(translations, handle, ensure_ascii=False, indent=2)
        tmp_path.replace(cache_path)
        return True
    except OSError as exc:
        print(f"Could not write translation cache {cache_path}: {exc}")
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        return False


_BULLET_MARKER_RE = re.compile(r"^[-*•]\s+")
_INLINE_CODE_RE = re.compile(r"(`[^`]+`)")


def bullets_to_html(text: str) -> str:
    """
    Render a cached bullet block for display in an HTML table cell.

    The cache keeps the raw LLM answer (markdown-ish, with `backticks`), so this
    conversion happens at render time and stays re-runnable. The output is HTML-escaped
    and uses inline elements only, which keeps it compatible with the existing
    `pulletPointCellRenderer` in docs/assets/app.js (a <p> with white-space: pre-wrap) -
    no frontend change required.
    """
    if not isinstance(text, str) or not text.strip():
        return ""

    rendered_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        marker = ""
        if _BULLET_MARKER_RE.match(stripped):
            stripped = _BULLET_MARKER_RE.sub("", stripped)
            marker = "• "

        body = "".join(
            f"<code>{html.escape(part[1:-1])}</code>"
            if part.startswith("`") and part.endswith("`") and len(part) > 2
            else html.escape(part)
            for part in _INLINE_CODE_RE.split(stripped)
        )
        rendered_lines.append(marker + body)

    return "\n".join(rendered_lines)


if __name__ == "__main__":
    example = """
    def check(self):
    \"""
        :return: True if it fits
        \"""
    if self.file.suffix.lower() in ('.txt', '.aif') and self.file.mime_type == 'text/plain':
        first_line = self.file.string.splitlines()[0]
        return 'raw2aif' in first_line
    return False""".strip()

    explainer = ReaderFunctionBlockExplainer(
        OllamaConfig(
            host="http://localhost:11434",
            model="qwen3:8B",
            temperature=0.2,
            num_ctx=4096,
        )
    )

    print(explainer.explain(example))

