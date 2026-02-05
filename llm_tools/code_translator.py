from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, List

from ollama import Client  # Official Ollama Python library


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

        response = self.client.chat(
            model=self.config.model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            options=options,
        )

        content = self._extract_chat_content(response)
        return self._normalize_to_3_5_bullets(content)

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

