"""
SAFEGUARD AI - IBM Langflow Integration
Interfaces with IBM Langflow for RAG and agent workflow orchestration.
Falls back gracefully when Langflow is not configured.
"""
import logging
import json
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    logger.warning("httpx not installed. Langflow integration will be unavailable.")

from backend.config import settings


class LangflowClient:
    """
    Client for IBM Langflow API.

    When configured, this routes RAG and agent tasks through Langflow flows.
    When not configured, the system uses its built-in RAG pipeline and rule-based agents.

    IBM Langflow setup:
    1. Install and start Langflow: pip install langflow && langflow run
    2. Import the flows from /langflow/*.json
    3. Set LANGFLOW_BASE_URL and LANGFLOW_FLOW_ID_* in .env
    """

    def __init__(self):
        self._available = False
        self._base_url = settings.LANGFLOW_BASE_URL
        self._api_key = settings.LANGFLOW_API_KEY
        self._rag_flow_id = settings.LANGFLOW_FLOW_ID_RAG
        self._agent_flow_id = settings.LANGFLOW_FLOW_ID_AGENT

        if settings.langflow_configured and HTTPX_AVAILABLE:
            self._available = True
            logger.info(f"Langflow client configured: {self._base_url}")
        else:
            logger.info("Langflow not configured. Using built-in RAG pipeline.")

    @property
    def available(self) -> bool:
        return self._available

    def query_rag_flow(
        self,
        query: str,
        machine_type: Optional[str] = None,
        top_k: int = 5,
    ) -> Optional[Dict[str, Any]]:
        """
        Send a RAG query to the Langflow RAG flow.
        Returns structured response with retrieved documents and generated answer.
        """
        if not self._available or not HTTPX_AVAILABLE:
            return None

        try:
            payload = {
                "input_value": query,
                "output_type": "chat",
                "input_type": "chat",
                "tweaks": {
                    "machine_type": machine_type or "",
                    "top_k": top_k,
                },
            }
            headers = {}
            if self._api_key:
                headers["x-api-key"] = self._api_key

            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self._base_url}/api/v1/run/{self._rag_flow_id}",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                return response.json()

        except Exception as e:
            logger.warning(f"Langflow RAG query failed: {e}")
            return None

    def run_safety_agent(
        self,
        machine_id: str,
        risk_data: Dict[str, Any],
        compliance_data: List[Dict[str, Any]],
    ) -> Optional[str]:
        """
        Run the multi-agent safety analysis flow in Langflow.
        Returns AI-generated narrative analysis.
        """
        if not self._available or not HTTPX_AVAILABLE:
            return None

        try:
            payload = {
                "input_value": json.dumps({
                    "machine_id": machine_id,
                    "risk_data": risk_data,
                    "compliance_data": compliance_data,
                }),
                "output_type": "chat",
                "input_type": "chat",
            }
            headers = {}
            if self._api_key:
                headers["x-api-key"] = self._api_key

            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{self._base_url}/api/v1/run/{self._agent_flow_id}",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                result = response.json()
                # Extract text output from Langflow response
                outputs = result.get("outputs", [])
                if outputs and outputs[0].get("outputs"):
                    return outputs[0]["outputs"][0].get("results", {}).get("message", {}).get("text", "")
                return None

        except Exception as e:
            logger.warning(f"Langflow agent run failed: {e}")
            return None


# Module-level singleton
langflow_client = LangflowClient()
