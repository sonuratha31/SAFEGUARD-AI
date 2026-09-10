"""
SAFEGUARD AI - IBM WatsonX Integration
LLM inference using IBM Granite models via WatsonX.ai
Falls back gracefully when credentials are not configured.
"""
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

try:
    from ibm_watsonx_ai import Credentials
    from ibm_watsonx_ai.foundation_models import ModelInference
    from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams
    WATSONX_SDK_AVAILABLE = True
except ImportError:
    WATSONX_SDK_AVAILABLE = False
    logger.info("IBM WatsonX AI SDK not installed. LLM features will use rule-based fallback.")

from backend.config import settings


class WatsonXClient:
    """
    Client for IBM WatsonX LLM inference.
    Automatically falls back to rule-based text generation when not configured.
    """

    def __init__(self):
        self._model = None
        self._available = False
        self._init()

    def _init(self):
        if not WATSONX_SDK_AVAILABLE:
            return
        if not settings.ibm_configured:
            logger.info("IBM WatsonX not configured. Set IBM_WATSONX_API_KEY and IBM_WATSONX_PROJECT_ID.")
            return
        try:
            credentials = Credentials(
                url=settings.IBM_WATSONX_URL,
                api_key=settings.IBM_WATSONX_API_KEY,
            )
            self._model = ModelInference(
                model_id=settings.IBM_LLM_MODEL_ID,
                credentials=credentials,
                project_id=settings.IBM_WATSONX_PROJECT_ID,
                params={
                    GenParams.MAX_NEW_TOKENS: 500,
                    GenParams.TEMPERATURE: 0.1,
                    GenParams.TOP_P: 0.9,
                },
            )
            self._available = True
            logger.info(f"IBM WatsonX LLM initialized: {settings.IBM_LLM_MODEL_ID}")
        except Exception as e:
            logger.warning(f"WatsonX LLM initialization failed: {e}")

    @property
    def available(self) -> bool:
        return self._available

    def generate(self, prompt: str, max_tokens: int = 500) -> str:
        """Generate text from a prompt. Returns fallback message if unavailable."""
        if not self._available or self._model is None:
            return self._rule_based_fallback(prompt)

        try:
            response = self._model.generate_text(
                prompt=prompt,
                params={GenParams.MAX_NEW_TOKENS: max_tokens},
            )
            return response.strip() if response else ""
        except Exception as e:
            logger.error(f"WatsonX generation error: {e}")
            return self._rule_based_fallback(prompt)

    def summarize_risk(self, machine_name: str, risk_assessment: Dict[str, Any]) -> str:
        """Generate a human-readable risk summary using IBM Granite."""
        if not self._available:
            return self._format_risk_summary_fallback(machine_name, risk_assessment)

        factors_text = "\n".join([
            f"  - {f['name']}: +{f['contribution']} pts ({f['explanation']})"
            for f in risk_assessment.get("risk_factors", [])
        ])
        prompt = f"""You are a safety engineer analyzing machine risk data.

Machine: {machine_name}
Risk Score: {risk_assessment.get('risk_score', 0)}/100
Risk Level: {risk_assessment.get('risk_level', 'unknown').upper()}

Contributing factors:
{factors_text}

Provide a concise, professional 2-3 sentence summary of the safety situation and most urgent concern.
Do not fabricate information. Only describe what is shown in the data above.
Summary:"""

        return self.generate(prompt, max_tokens=200)

    def enhance_recommendation(self, recommendation: Dict[str, Any], context: str) -> str:
        """Use IBM Granite to add context-aware nuance to a recommendation."""
        if not self._available:
            return recommendation.get("corrective_action", "")

        prompt = f"""You are an industrial safety expert.

Issue: {recommendation.get('issue', '')}
Severity: {recommendation.get('severity', '').upper()}
Machine Context: {context}

Current corrective action: {recommendation.get('corrective_action', '')}

Provide a brief enhancement or clarification based on the machine context. Be specific and practical.
Keep response to 1-2 sentences. Do not fabricate standards or regulations.
Enhancement:"""

        return self.generate(prompt, max_tokens=150)

    @staticmethod
    def _rule_based_fallback(prompt: str) -> str:
        """Simple fallback when IBM WatsonX is not available."""
        return "[IBM WatsonX not configured — rule-based analysis applied]"

    @staticmethod
    def _format_risk_summary_fallback(machine_name: str, risk: Dict[str, Any]) -> str:
        score = risk.get("risk_score", 0)
        level = risk.get("risk_level", "unknown").upper()
        factors = risk.get("risk_factors", [])
        top = sorted(factors, key=lambda f: f.get("contribution", 0), reverse=True)[:2]
        top_names = " and ".join(f["name"] for f in top) if top else "multiple parameters"
        return (
            f"{machine_name} is operating at {level} risk (score: {score}/100). "
            f"Primary concerns: {top_names}. "
            f"Review the risk factors and recommendations below for detailed guidance."
        )


# Module-level singleton
watsonx_client = WatsonXClient()
