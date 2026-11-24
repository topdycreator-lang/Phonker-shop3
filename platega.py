import json
import logging

import aiohttp

import config

BASE_URL = "https://app.platega.io"


class PlategaError(Exception):
    pass


class PlategaLimit(PlategaError):
    pass


LIMIT_TEXT = ("Сумма заказа слишком большая для оплаты СБП (максимум около {m} ₽ за один платёж). "
              "Разбей заказ на несколько частей или оплати звёздами.")


def cfg(name, default=""):
    return getattr(config, name, default)


def method_list():
    return cfg("PLATEGA_METHODS", [(2, "🏦 СБП (авто)")])


def enabled():
    return bool(cfg("PLATEGA_MERCHANT_ID") and cfg("PLATEGA_SECRET"))


def methods():
    return [(f"pg{mid}", label) for mid, label in method_list()] if enabled() else []


def _headers():
    return {
        "X-MerchantId": cfg("PLATEGA_MERCHANT_ID"),
        "X-Secret": cfg("PLATEGA_SECRET"),
        "Content-Type": "application/json",
    }


async def _request(method, path, body=None):
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.request(method, BASE_URL + path, json=body, headers=_headers()) as resp:
            text = await resp.text()
            if resp.status != 200:
                if "limit" in text.lower():
                    raise PlategaLimit(LIMIT_TEXT.format(m=cfg("PLATEGA_MAX_AMOUNT", 20000)))
                raise PlategaError(f"HTTP {resp.status}: {text[:300]}")
            try:
                return json.loads(text)
            except ValueError:
                raise PlategaError(f"не JSON в ответе: {text[:300]}")


async def create_payment(amount, method_id, description, payload, return_url):
    mx = cfg("PLATEGA_MAX_AMOUNT", 0)
    if mx and amount > mx:
        raise PlategaLimit(LIMIT_TEXT.format(m=mx))
    body = {
        "paymentMethod": method_id,
        "paymentDetails": {"amount": amount, "currency": "RUB"},
        "description": description,
        "return": return_url,
        "failedUrl": return_url,
        "payload": payload,
    }
    data = await _request("POST", "/transaction/process", body)
    tx_id = data.get("transactionId") or data.get("id")
    url = data.get("redirect") or data.get("url")
    if not tx_id or not url:
        raise PlategaError(f"неожиданный ответ: {str(data)[:300]}")
    return tx_id, url


async def get_status(tx_id):
    data = await _request("GET", f"/transaction/{tx_id}")
    status = data.get("status")
    if status is None:
        logging.warning("platega: в ответе нет status: %s", str(data)[:300])
        return None
    return str(status).upper()
