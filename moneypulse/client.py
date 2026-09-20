"""Money-Pulse Python SDK"""
import requests
import uuid
from typing import Any, Dict, Optional


class MoneyPulseError(Exception):
    def __init__(self, message: str, code: str = "unknown", status_code: int = 0):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _to_camel_case(snake_str: str) -> str:
    parts = snake_str.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


def _camelize_top_level(params: Optional[dict]) -> Optional[dict]:
    """Convertit uniquement les clés top-niveau contenant un "_" en camelCase
    (ex. method_code -> methodCode). Ne touche jamais aux objets imbriqués
    (customer={...}, metadata={...}) : leurs propres clés restent telles que
    l'appelant les a fournies."""
    if not params:
        return params
    return {(_to_camel_case(k) if "_" in k else k): v for k, v in params.items()}


class _Resource:
    def __init__(self, client: "MoneyPulseClient", prefix: str, create_prefix: str = None):
        self._client = client
        self._prefix = prefix
        self._create_prefix = create_prefix or prefix

    def create(self, idempotency_key: Optional[str] = None, **params) -> Dict[str, Any]:
        key = idempotency_key or str(uuid.uuid4())
        return self._client._request("POST", self._create_prefix, json=params, idempotency_key=key)

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
        return self._client._request("GET", f"{self._prefix}/{id}/status")

    def verify(self, id: str) -> Dict[str, Any]:
        return self.retrieve(id)


class _PayoutResource(_Resource):
    def __init__(self, client: "MoneyPulseClient"):
        # FIX ALIGNEMENT (vérification approfondie) : POST /api/v1/payouts
        # (PayoutController.createPayout) lit req.body.destinationDetails,
        # jamais req.body.recipient -- tout payout envoyé via create()
        # voyait son destinataire silencieusement remplacé par des valeurs
        # vides/"N/A", sans erreur. La route qui lit bien `recipient` est
        # /api/v1/payments/payouts/initiate (PaymentController.initiatePayout).
        super().__init__(client, "/api/v1/payouts", "/api/v1/payments/payouts/initiate")

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


class _BillingPlansResource:
    def __init__(self, client: "MoneyPulseClient"):
        self._client = client

    def create(self, **params) -> Dict[str, Any]:
        return self._client._request("POST", "/api/v1/billing/plans", json=params)

    def list(self, include_inactive: bool = False) -> Dict[str, Any]:
        params = {"includeInactive": "true"} if include_inactive else None
        return self._client._request("GET", "/api/v1/billing/plans", params=params)

    def deactivate(self, id: str) -> Dict[str, Any]:
        return self._client._request("DELETE", f"/api/v1/billing/plans/{id}")


class _BillingCustomersResource:
    def __init__(self, client: "MoneyPulseClient"):
        self._client = client

    def upsert(self, **params) -> Dict[str, Any]:
        return self._client._request("POST", "/api/v1/billing/customers", json=params)


class _BillingSubscriptionsResource:
    def __init__(self, client: "MoneyPulseClient"):
        self._client = client

    def create(self, billing_customer_id: str, plan_code: str) -> Dict[str, Any]:
        """Retourne {subscription, invoice, checkoutUrl} -- checkoutUrl est le
        lien de paiement hébergé à présenter à l'utilisateur final (aucun
        débit automatique n'existe côté Money-Pulse)."""
        return self._client._request(
            "POST", "/api/v1/billing/subscriptions",
            json={"billing_customer_id": billing_customer_id, "plan_code": plan_code},
        )

    def cancel(self, id: str, at_period_end: bool = True, reason: Optional[str] = None) -> Dict[str, Any]:
        return self._client._request(
            "POST", f"/api/v1/billing/subscriptions/{id}/cancel",
            json={"at_period_end": at_period_end, "reason": reason},
        )


class _BillingUsageResource:
    def __init__(self, client: "MoneyPulseClient"):
        self._client = client

    def record(self, **params) -> Dict[str, Any]:
        """Enregistre un relevé d'usage (ex. commission sur une vente), agrégé
        à la prochaine facture de l'abonnement concerné."""
        return self._client._request("POST", "/api/v1/billing/usage", json=params)


class _BillingResource:
    """Facturation récurrente : abonnements + usage pour les utilisateurs
    finaux de votre propre application (ex. les vendeurs qui utilisent votre
    plateforme) -- pas pour Money-Pulse lui-même."""

    def __init__(self, client: "MoneyPulseClient"):
        self.plans = _BillingPlansResource(client)
        self.customers = _BillingCustomersResource(client)
        self.subscriptions = _BillingSubscriptionsResource(client)
        self.usage = _BillingUsageResource(client)


class MoneyPulseClient:
    """
    Official Money-Pulse Python client.

    Usage:
        import moneypulse
        client = moneypulse.Client("mp_live_votre_cle_api")
        payment = client.payments.create(
            amount=10000, currency="XOF", country="CI",
            customer={
                "phone": "+2250700000000",   # requis pour mobile money
                "email": "client@email.com",
            },
            method_code="orange_ci",            # recommandé pour éviter le fallback
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
            "X-SDK": "moneypulse-python/2.1.0",
        })
        self.payments = _PaymentResource(self)
        self.payouts = _PayoutResource(self)
        self.billing = _BillingResource(self)

    def _request(self, method: str, path: str, json: Optional[dict] = None, params: Optional[dict] = None, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        url = f"{self._base_url}{path}"
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        response = self._session.request(method, url, json=_camelize_top_level(json), params=params, headers=headers, timeout=30)

        data = response.json()

        if response.status_code >= 400:
            error = data.get("error", {})
            msg = error.get("message", str(error)) if isinstance(error, dict) else str(error)
            code = error.get("code", "unknown") if isinstance(error, dict) else "unknown"
            raise MoneyPulseError(msg, code, response.status_code)

        return data.get("data", data)
