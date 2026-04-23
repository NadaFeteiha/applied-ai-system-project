import requests

OLLAMA_BASE = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"


def generate(prompt: str, model: str = DEFAULT_MODEL) -> str | None:
    """Return the LLM response string, or None if Ollama is unreachable."""
    try:
        resp = requests.post(
            f"{OLLAMA_BASE}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except requests.exceptions.ConnectionError:
        return None
    except Exception as exc:
        return f"[LLM error: {exc}]"


def available_models() -> list[str]:
    """Return list of model names pulled in Ollama, or [] if unreachable."""
    try:
        resp = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
        if resp.status_code == 200:
            return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        pass
    return []


def is_available(model: str = DEFAULT_MODEL) -> bool:
    models = available_models()
    return any(model in m for m in models)
