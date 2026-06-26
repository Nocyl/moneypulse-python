"""Money-Pulse Python SDK"""
import requests
from typing import Any, Dict, Optional


class MoneyPulseError(Exception):
    def __init__(self, message: str, code: str = "unknown", status_code: int = 0):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class _Resource:
    def __init__(self, client: "MoneyPulseClient", prefix: str, create_prefix: str = None):
        self._client = client
        self._prefix = prefix
        self._create_prefix = create_prefix or prefix

    def create(self, **params) -> Dict[str, Any]:
        return self._client._request("POST", self._create_prefix, json=params)

    def retrieve(self, id: str) -> Dict[str, Any]:
        return self._client._request("GET", f"{self._prefix}/{id}")

    def verify(self, id: str) -> Dict[str, Any]:
        return self._client._request("GET", f"{self._prefix}/{id}/verify")

    def list(self, page: int = 1, limit: int = 20, **filters) -> Dict[str, Any]:
        params = {"page": page, "limit": limit, **filters}
        return self._client._request("GET", self._prefix, params=params)


class _PaymentResource(_Resource):
    def __init__(self, client: "MoneyPulseClient"):
        super().__init__(client, "/api/v1/payments", "/api/v1/payments/initiate")

    def retrieve(self, id: str) -> Dict[str, Any]:
        # FIX (F-055) : le backend n'expose pas GET /api/v1/payments/{id}.
        # La seule route de lecture par identifiant est /:transactionId/status
        # (cf backend/src/routes/payments.ts).
        return self._client._request("GET", f"{self._prefix}/{id}/status")

    def verify(self, id: str) -> Dict[str, Any]:
        # FIX (F-055) : aucune route backend /api/v1/payments/{id}/verify
        # n'existe. On retombe sur le meme endpoint que retrieve() (status)
        # plutot que de laisser un appel qui echoue toujours en 404.
        return self.retrieve(id)


class _PayoutResource(_Resource):
    def __init__(self, client: "MoneyPulseClient"):
        # FIX (F-055) : le backend expose POST /api/v1/payouts (sans
        # /initiate) — cf backend/src/routes/payouts.ts.
        super().__init__(client, "/api/v1/payouts", "/api/v1/payouts")

    def retrieve(self, id: str) -> Dict[str, Any]:
        raise NotImplementedError(
            "GET /api/v1/payouts/{id} n'existe pas cote backend. "
            "Utilisez list() pour retrouver un payout, ou demandez la creation "
            "de cette route avant de re-activer cette methode."
        )

    def verify(self, id: str) -> Dict[str, Any]:
        raise NotImplementedError(
            "GET /api/v1/payouts/{id}/verify n'existe pas cote backend."
        )


class MoneyPulseClient:
    """
    Official Money-Pulse Python client.

    Usage:
        import moneypulse
        client = moneypulse.Client("mp_live_votre_cle_api")
        payment = client.payments.create(
            amount=10000, currency="XOF", country="CI",
            customer={"email": "client@email.com"},
            callback_url="https://your-site.com/webhook"
        )
    """

    def __init__(self, api_key: str, base_url: str = "https://api.money-pulse.org"):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({
            "X-Api-Key": self._api_key,
            "Content-Type": "application/json",
            "X-SDK": "moneypulse-python/1.0.0",
        })
        self.payments = _PaymentResource(self)
        self.payouts = _PayoutResource(self)

    def _request(self, method: str, path: str, json: Optional[dict] = None, params: Optional[dict] = None) -> Dict[str, Any]:
        url = f"{self._base_url}{path}"
        response = self._session.request(method, url, json=json, params=params, timeout=30)

        data = response.json()

        if response.status_code >= 400:
            error = data.get("error", {})
            msg = error.get("message", str(error)) if isinstance(error, dict) else str(error)
            code = error.get("code", "unknown") if isinstance(error, dict) else "unknown"
            raise MoneyPulseError(msg, code, response.status_code)

        return data.get("data", data)
