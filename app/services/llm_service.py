import logging
from typing import List, Dict, Any, Optional
import httpx
from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class LLMService:
    """Handles communication with the Ollama Cloud /v1/chat/completions endpoint."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> str:
        """Call Ollama Cloud chat completions endpoint asynchronously."""
        if self.settings.mock_llm:
            return self._mock_generate(messages)

        target_url = self.settings.chat_completions_url
        headers = {
            "Content-Type": "application/json",
        }
        if self.settings.ollama_api_key:
            headers["Authorization"] = f"Bearer {self.settings.ollama_api_key}"

        payload: Dict[str, Any] = {
            "model": self.settings.ollama_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        logger.info(f"Dispatching LLM query to {target_url} using model '{self.settings.ollama_model}'")

        async with httpx.AsyncClient(timeout=self.settings.ollama_timeout_seconds) as client:
            try:
                response = await client.post(target_url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

                # Extract response text following OpenAI compatibility spec
                choices = data.get("choices", [])
                if choices and "message" in choices[0]:
                    content = choices[0]["message"].get("content", "")
                    return content.strip()

                # Fallback if Ollama native format is returned
                if "message" in data and "content" in data["message"]:
                    return data["message"]["content"].strip()
                if "response" in data:
                    return data["response"].strip()

                logger.warning(f"Unexpected response payload format: {data}")
                return str(data)

            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error {e.response.status_code} from LLM provider: {e.response.text}")
                raise RuntimeError(f"LLM API returned error status {e.response.status_code}: {e.response.text}")
            except httpx.RequestError as e:
                logger.error(f"Network request error reaching LLM provider at {target_url}: {e}")
                raise RuntimeError(f"Failed to connect to LLM provider at {target_url}: {str(e)}")

    def _mock_generate(self, messages: List[Dict[str, str]]) -> str:
        """Deterministic mock response for offline testing."""
        import re

        user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        question_part = user_message
        context_part = ""
        if "QUESTION:\n" in user_message:
            parts = user_message.split("QUESTION:\n", 1)
            context_part = parts[0]
            question_part = parts[1].split("\n\n")[0]

        q_lower = question_part.lower()

        # Unanswerable topics
        unanswerable_keywords = [
            "venus", "apple", "maternity", "paternity", "prometheus", "mars",
            "vacation", "dividend", "autoscaler", "weather"
        ]
        if any(k in q_lower for k in unanswerable_keywords):
            return "The provided documents do not contain sufficient information to answer this question."

        if "disparate impact" in q_lower:
            return "According to the AI Ethics Framework, models must demonstrate disparate impact ratios between 0.80 and 1.25 across all protected classes."
        if "rpo" in q_lower or "recovery point" in q_lower:
            return "The Recovery Point Objective (RPO) is maximum 5 minutes of data loss, and Recovery Time Objective (RTO) is maximum 15 minutes."
        if "decoherence" in q_lower or "15 millikelvin" in q_lower or ("quantum" in q_lower and "temperature" in q_lower):
            return "Quantum processors operate near 15 millikelvin (-273.135°C). Thermal noise and electromagnetic interference cause decoherence."
        if "shor" in q_lower:
            return "Shor's algorithm provides exponential speedup for integer factorization, posing a cryptographic threat to RSA and TLS protocols."
        if "audit" in q_lower and ("worm" in q_lower or "retention" in q_lower or "review" in q_lower):
            return "Audit logs require 7 years retention in WORM storage under the AI policy, and weekly InfoSec review under the security policy."
        if "human" in q_lower and ("$10,000" in q_lower or "approval" in q_lower or "outage" in q_lower):
            return "Transactions over $10,000 require dual-custody human approval, while Sev-1 outages require paging the incident commander via PagerDuty within 120 seconds."
        if "rotation" in q_lower or ("encryption" in q_lower and "key" in q_lower):
            return "Encryption keys must be rotated automatically every 90 days using AES-256 standards."
        if "privacy" in q_lower and "cloud" in q_lower:
            return "AI policy requires automated PII scrubbing and GDPR Article 17 compliance, while Cloud handbook mandates AES-256 KMS database encryption."
        if "quantum" in q_lower or "superposition" in q_lower:
            return "Quantum computing utilizes qubits that can exist in superposition states |psi> = alpha|0> + beta|1> to perform parallel computation."
        if "ethics" in q_lower or "fairness" in q_lower:
            return "The AI Ethics policy requires algorithmic fairness, explainability, data privacy compliance, and human oversight."

        # If question terms are completely absent from context
        meaningful_words = [w for w in re.findall(r"[a-z]{4,}", q_lower) if w not in {"what", "which", "where", "about", "from", "with", "does", "have"}]
        if meaningful_words and not any(w in context_part.lower() for w in meaningful_words):
            return "The provided documents do not contain sufficient information to answer this question."

        return "Based on the provided documents, the information is verified."

