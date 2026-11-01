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

GEMINI_MODELS = [
    {
        "id": os.getenv("GEMINI_DEFAULT_MODEL", "gemini-2.5-flash"),
        "name": "Gemini 2.5 Flash",
        "provider": "gemini",
        "size": "Cloud",
        "description": "Modelo de Google mediante Gemini API",
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


class GeminiProvider:

    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.api_url = "https://generativelanguage.googleapis.com/v1beta/models"

    def chat(self, model_id, messages):
        if not self.api_key:
            raise RuntimeError("Gemini API no está configurada. Define GEMINI_API_KEY en el backend.")

        contents = []
        system_instruction = None
        for message in messages:
            role = message.get("role", "user")
            content = str(message.get("content", ""))
            if role == "system":
                system_instruction = {"parts": [{"text": content}]}
                continue
            contents.append({
                "role": "model" if role == "assistant" else "user",
                "parts": [{"text": content}],
            })

        if not contents:
            raise RuntimeError("Gemini necesita al menos un mensaje de usuario.")

        payload = {
            "contents": contents,
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 512},
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction

        response = requests.post(
            f"{self.api_url}/{model_id}:generateContent",
            headers={
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )
        if not response.ok:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text[:1500]
            logging.error(
                "Gemini chat request failed: status=%s model=%s response=%s",
                response.status_code, model_id, detail,
            )
            raise RuntimeError(
                f"Gemini rechazó la solicitud (HTTP {response.status_code}) "
                f"para el modelo '{model_id}': {detail}"
            )

        result = response.json()
        try:
            parts = result["candidates"][0]["content"]["parts"]
            content = "".join(part.get("text", "") for part in parts)
        except (KeyError, IndexError, TypeError) as exc:
            logging.error("Respuesta inesperada de Gemini: %s", result)
            raise RuntimeError(f"Gemini devolvió una respuesta inesperada para '{model_id}'.") from exc

        return {"message": {"content": content}}


class LLMService:

    def __init__(self):
        self.hf = HFProvider()
        self.ollama = OllamaProvider()
        self.gemini = GeminiProvider()

    def get_available_models(self):
        models = {"hf": HF_MODELS, "ollama": OLLAMA_MODELS, "gemini": []}
        if self.gemini.api_key:
            models["gemini"] = GEMINI_MODELS
        return models

    def is_model_available(self, model_id):
        return any(
            model["id"] == model_id
            for provider_models in self.get_available_models().values()
            for model in provider_models
        )

    def get_default_model(self):
        if self.gemini.api_key and os.getenv("GEMINI_DEFAULT_MODEL"):
            return os.getenv("GEMINI_DEFAULT_MODEL")
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
        for m in self.get_available_models()["gemini"]:
            if m["id"] == model_id:
                return "gemini"
        raise ValueError(f"Modelo no disponible o no configurado: {model_id}")

    def chat(self, model_id, messages):
        provider = self._resolve_provider(model_id)
        if provider == "hf":
            return self.hf.chat(model_id, messages)
        if provider == "gemini":
            return self.gemini.chat(model_id, messages)
        return self.ollama.chat(model_id, messages)
