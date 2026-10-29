import os
import logging
import requests
import ollama


HF_MODELS = [
    {
        "id": "google/gemma-3-4b-it",
        "name": "Gemma 3 4B",
        "provider": "hf",
        "size": "4B",
        "description": "Recomendado — rápido y buena calidad",
    },
    {
        "id": "Qwen/Qwen2.5-7B-Instruct",
        "name": "Qwen 2.5 7B",
        "provider": "hf",
        "size": "7B",
        "description": "Bueno para español y datos médicos",
    },
    {
        "id": "meta-llama/Llama-3.1-8B-Instruct",
        "name": "Llama 3.1 8B",
        "provider": "hf",
        "size": "8B",
        "description": "Muy capaz, requiere internet rápido",
    },
]

OLLAMA_MODELS = [
    {
        "id": "gemma3:1b",
        "name": "Gemma 3 1B",
        "provider": "ollama",
        "size": "1B",
        "description": "Rápido local, menor calidad",
    },
    {
        "id": "qwen2.5-coder:14b",
        "name": "Qwen 2.5 Coder 14B",
        "provider": "ollama",
        "size": "14B",
        "description": "Potente local, puede ser lento en CPU",
    },
]


class HFProvider:

    def __init__(self, token=None):
        self.token = token or os.getenv("HF_API_TOKEN", "")
        self.api_url = "https://router.huggingface.co/v1/chat/completions"

    def chat(self, model_id, messages):
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_id,
            "messages": messages,
            "max_tokens": 512,
            "temperature": 0.3,
            "stream": False,
        }
        resp = requests.post(
            self.api_url,
            headers=headers,
            json=payload,
            timeout=120,
        )
        if not resp.ok:
            # Preserve Hugging Face's diagnostic body so the UI/logs reveal
            # whether the model, provider, or request parameters were rejected.
            try:
                error_detail = resp.json()
            except ValueError:
                error_detail = resp.text[:1500]
            logging.error(
                "Hugging Face chat request failed: status=%s model=%s response=%s",
                resp.status_code,
                model_id,
                error_detail,
            )
            raise RuntimeError(
                f"Hugging Face rechazó la solicitud (HTTP {resp.status_code}) "
                f"para el modelo '{model_id}': {error_detail}"
            )

        result = resp.json()
        try:
            content = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            logging.error("Respuesta inesperada de Hugging Face: %s", result)
            raise RuntimeError(
                f"Hugging Face devolvió una respuesta inesperada para '{model_id}'."
            ) from exc
        return {"message": {"content": content}}


class OllamaProvider:

    def chat(self, model_id, messages):
        return ollama.chat(model=model_id, messages=messages)


class LLMService:

    def __init__(self):
        self.hf = HFProvider()
        self.ollama = OllamaProvider()

    def get_available_models(self):
        return {"hf": HF_MODELS, "ollama": OLLAMA_MODELS}

    def get_default_model(self):
        if os.getenv("HF_API_TOKEN"):
            return os.getenv("HF_DEFAULT_MODEL", "google/gemma-3-4b-it")
        return os.getenv("OLLAMA_DEFAULT_MODEL", "gemma3:1b")

    def _resolve_provider(self, model_id):
        for m in HF_MODELS:
            if m["id"] == model_id:
                return "hf"
        for m in OLLAMA_MODELS:
            if m["id"] == model_id:
                return "ollama"
        if "/" in model_id:
            return "hf"
        return "ollama"

    def chat(self, model_id, messages):
        provider = self._resolve_provider(model_id)
        if provider == "hf":
            return self.hf.chat(model_id, messages)
        return self.ollama.chat(model_id, messages)
