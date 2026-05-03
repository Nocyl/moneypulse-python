# moneypulse

Official Python SDK for [Money-Pulse](https://money-pulse.org).

## Installation

```bash
pip install moneypulse
```

## Quick start

```python
import moneypulse
client = moneypulse.Client("mp_live_xxx")

payment = client.payments.create(
    amount=10000, currency="XOF", country="CI",
    customer={"email": "client@email.com", "phone": "+22507000000"},
    callback_url="https://your-site.com/webhook",
)
print(payment["checkout_url"])
```

## Payouts

```python
payout = client.payouts.create(
    amount=50000, currency="XOF", country="CI",
    recipient={"type": "mobile_money", "phone": "+22507000000", "name": "Jean Kouassi"},
)
```

## Webhook verification (HMAC SHA-256)

### Django

```python
import hmac, hashlib, json
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def mp_webhook(request):
    signature = request.headers.get("X-MoneyPulse-Signature", "")
    expected = hmac.new(
        settings.MP_WEBHOOK_SECRET.encode(),
        request.body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return HttpResponse(status=401)

    event = json.loads(request.body)
    if event["type"] == "payment.success":
        # fulfill order
        pass
    return HttpResponse(status=200)
```

### FastAPI

```python
from fastapi import FastAPI, Request, HTTPException
import hmac, hashlib

app = FastAPI()

@app.post("/webhook")
async def webhook(req: Request):
    body = await req.body()
    signature = req.headers.get("x-moneypulse-signature", "")
    expected = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(401)
    return {"received": True}
```

## Simulation mode

```python
result = client.payments.create(
    amount=1000, currency="XOF", country="CI",
    customer={"email": "t@t.com"},
    simulate=True,  # no funds, no webhook, no billing
)
```

## Error handling

```python
from moneypulse.client import MoneyPulseError

try:
    client.payments.create(...)
except MoneyPulseError as e:
    print(e.code, e.status_code, e)
```

## License

MIT © NOCYL-PULSE
