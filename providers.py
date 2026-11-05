# -*- coding: utf-8 -*-
"""
ZTLStudio: the LLM provider layer. The translator speaks in messages;
this module speaks HTTP to whichever backend the user chose. Two
families:

  * OpenAI-compatible (Groq, OpenAI, OpenRouter, DeepSeek, xAI, Together)
    — one chat/completions shape;
  * Anthropic (Claude) — its own messages endpoint and system field.

A weaker model mis-formalizes (the curator's crocodile: llama produced
imp(not(Tr(K)),Tr(C)) instead of the clean R:Tr(M), M:not(Tr(R))), so
the studio must let a stronger model in. Keys live in the environment
or in local untracked files tool/.<provider>_key (the repo is public —
never in code); the UI may also pass a key/model per request, which
wins over the stored one.
"""

import json
import os
import threading
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))

# name -> (family, url, default model, env var, key-file, label, key-console)
PROVIDERS = {
    "groq": ("openai", "https://api.groq.com/openai/v1/chat/completions",
             "openai/gpt-oss-120b", "GROQ_API_KEY", ".groq_key",
             "Groq (free · weaker, may misformalize)",
             "https://console.groq.com/keys"),
    "anthropic": ("anthropic", "https://api.anthropic.com/v1/messages",
                  "claude-sonnet-5", "ANTHROPIC_API_KEY",
                  ".anthropic_key", "Anthropic (Claude)",
                  "https://console.anthropic.com/settings/keys"),
    "openai": ("openai", "https://api.openai.com/v1/chat/completions",
               "gpt-5", "OPENAI_API_KEY", ".openai_key", "OpenAI",
               "https://platform.openai.com/api-keys"),
    "openrouter": ("openai",
                   "https://openrouter.ai/api/v1/chat/completions",
                   "anthropic/claude-sonnet-4", "OPENROUTER_API_KEY",
                   ".openrouter_key", "OpenRouter (any model)",
                   "https://openrouter.ai/keys"),
    "deepseek": ("openai", "https://api.deepseek.com/v1/chat/completions",
                 "deepseek-reasoner", "DEEPSEEK_API_KEY", ".deepseek_key",
                 "DeepSeek", "https://platform.deepseek.com/api_keys"),
    "gemini": ("openai",
               "https://generativelanguage.googleapis.com/v1beta/openai/"
               "chat/completions",
               "gemini-2.5-pro", "GEMINI_API_KEY", ".gemini_key",
               "Google Gemini", "https://aistudio.google.com/apikey"),
    "xai": ("openai", "https://api.x.ai/v1/chat/completions",
            "grok-4", "XAI_API_KEY", ".xai_key", "xAI (Grok)",
            "https://console.x.ai"),
    # NVIDIA — каталог на build.nvidia.com, вход OpenAI-совместимый.
    # Заведено 2026-08-30 по слову куратора. Не все модели каталога доступны
    # каждому ключу: nemotron-70b, 51b и kimi-k2.6 отвечали 404 «not found for
    # account», deepseek-v4 не уложился в минуту. Проверять живым вызовом, а не
    # присутствием в списке — список врёт про доступность.
    "nvidia": ("openai", "https://integrate.api.nvidia.com/v1/chat/completions",
               "nvidia/nemotron-3-ultra-550b-a55b", "NVIDIA_API_KEY", ".nvidia_key",
               "NVIDIA (каталог build.nvidia.com)",
               "https://build.nvidia.com"),
}

# FLAGSHIP models only (Sonnet-level or above) — weaker models mis-formalize.
# First = default. VERIFY IDS: only the Anthropic ids are known-current here;
# the others (gpt-5, o3, gemini-2.5-pro, grok-4, deepseek-reasoner) are best
# guesses at each provider's frontier — adjust if a call 404s.
MODELS = {
    "anthropic":  ["claude-sonnet-5", "claude-opus-4-8"],
    "openai":     ["gpt-5", "o3"],
    "gemini":     ["gemini-2.5-pro"],
    "xai":        ["grok-4"],
    "openrouter": ["anthropic/claude-sonnet-5", "anthropic/claude-opus-4-8",
                   "openai/gpt-5", "google/gemini-2.5-pro"],
    "deepseek":   ["deepseek-reasoner"],
    # gpt-oss-120b added 2026-08-13 on the curator's tip and measured before
    # being made the default: on the five-question battery it fills the table
    # correctly where llama-3.3-70b invents a row to hold the answer. Still
    # free, and the label no longer has to warn quite so loudly.
    # MEASURED 2026-11-05 by a one-word call: gpt-oss-120b 0.6 s, qwen3.8-27b 1.8 s, gpt-oss-20b 0.6 s.
    # Groq снимает модели без предупреждения: llama-3.3-70b-versatile умерла
    # 2026-08-20 (HTTP 404, не 403 — 403 это отсутствующий User-Agent).
    # Живой список: GET https://api.groq.com/openai/v1/models
    # 2026-11-05 (the curator: "groq, several, if one hits its limit the others take over"): the live list
    # (GET /models) — qwen3.6-27b is gone, qwen3.8-27b is there. Groq limits each MODEL separately, so a chain
    # over three models survives one model's 429. translator.llm walks this list in order.
    "groq":       ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"],
    # Проверено живым вызовом 2026-08-30: kimi-k3 ответила за 1.9 с,
    # nemotron-3-super-120b за ~10 с (и трижды отдал 503 под нагрузкой).
    # 2026-11-05: kimi-k3 reached end of life on 2026-10-15 (HTTP 410), nemotron-3-nano is gone from the catalogue.
    # LISTED is not AVAILABLE: MEASURED by a one-word call the same day — nemotron-3-super and kimi-k2.6 answer 404
    # "not found for account", deepseek-v4.1-flash timed out at 90 s; nemotron-3-ultra (1.2 s) and
    # nemotron-3.5-lightning (1.7 s) answered. The backup behind Groq.
    "nvidia":     ["nvidia/nemotron-3-ultra-550b-a55b", "nvidia/nemotron-3.5-lightning-30b-a3b"],
}


class ProviderError(Exception):
    pass


# Файлы вида KEY=value, где ключ уже лежит у куратора. Читаем их, чтобы не
# заводить второй экземпляр секрета: секрет, размноженный по файлам, потом
# меняют в одном месте и забывают в другом.
EXTRA_KEY_FILES = {
    "nvidia": os.path.expanduser("~/.config/nvidia-nim.env"),
}


def get_key(provider):
    """Env var first, then the local untracked key file, then a known env-file."""
    if provider not in PROVIDERS:
        return None
    env, keyfile = PROVIDERS[provider][3], PROVIDERS[provider][4]
    key = os.environ.get(env)
    if key:
        return key.strip()
    path = os.path.join(HERE, keyfile)
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    extra = EXTRA_KEY_FILES.get(provider)
    if extra and os.path.exists(extra):
        import re
        with open(extra, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = re.match(rf"\s*{re.escape(env)}\s*=\s*(.+?)\s*$", line)
                if m:
                    return m.group(1).strip().strip("'\"")
    return None


def available():
    """[{provider, label, default_model, has_key}] for the settings UI."""
    out = []
    for name, tup in PROVIDERS.items():
        out.append({"provider": name, "label": tup[5],
                    "default_model": tup[2], "has_key": bool(get_key(name)),
                    "console": tup[6],
                    "models": MODELS.get(name, [tup[2]])})
    return out


def _post(url, body, headers, wait_on_limit=True):
    """wait_on_limit=False: a 429 is raised at once, so a CHAIN of models moves to the next one instead of
    sleeping 15+30+45 s on this one (MEASURED 2026-08-31: the sleeps made a live request miss its 120 s)."""
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                         headers=headers)
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3 and wait_on_limit:       # rate limit: breathe
                time.sleep(15 * (attempt + 1))
                continue
            detail = ""
            try:
                detail = e.read().decode()[:200]
            except Exception:
                pass
            if (e.code == 400 and "temperature" in detail.lower()
                    and "temperature" in body):
                body.pop("temperature", None)   # newer models deprecate it
                continue
            raise ProviderError(f"HTTP {e.code}: {detail or e.reason}")
        except Exception as e:
            raise ProviderError(str(e))
    # Не выпасть из цикла в None. Крайний случай — 429×3, затем temperature-400
    # на последней попытке: обе ветки делают continue, range(4) исчерпывается, и
    # раньше функция молча возвращала None → chat() падал на .get у None.
    raise ProviderError("провайдер не ответил за отведённые попытки")


# ── СЧЁТ РАСХОДА ──────────────────────────────────────────────────────────
# Заведено 2026-09-03 по слову куратора. Провайдер ВОЗВРАЩАЕТ usage в каждом
# ответе — promt/completion/total, — а мы брали из ответа только текст и всё
# остальное молча выбрасывали. Целый вечер замеров прошёл без единой цифры
# расхода, и «дорого или нет» приходилось оценивать на глаз.
#
# Возвращаемый тип chat() НЕ МЕНЯЕТСЯ: он строка, и десяток вызывающих мест
# на это опирается. Счёт копится СБОКУ. Кто хочет цифру — зовёт usage_report().
#
# Считается ФАКТ провайдера, а не наша оценка по длине текста: оценка по
# знакам врёт на любой токенизации, а usage приходит от того, кто списывает.
_USAGE = {}


def usage_reset():
    """Обнулить счёт. Зовётся ПЕРЕД замером, иначе в него попадёт прошлый."""
    _USAGE.clear()


def usage_report():
    """{provider: {calls, prompt, completion, total}} — только то, что провайдер
    прислал сам. Вызовы, где usage не пришёл, считаются в `без_счёта`: молчание
    провайдера не есть ноль расхода."""
    return {k: dict(v) for k, v in _USAGE.items()}


def _usage_add(provider, model, data):
    u = (data or {}).get("usage") or {}
    d = _USAGE.setdefault(provider, {"calls": 0, "prompt": 0, "completion": 0,
                                     "total": 0, "без_счёта": 0, "models": {}})
    d["calls"] += 1
    d["models"][model or "(default)"] = d["models"].get(model or "(default)", 0) + 1
    if not u:
        d["без_счёта"] += 1
        return
    d["prompt"] += int(u.get("prompt_tokens") or u.get("input_tokens") or 0)
    d["completion"] += int(u.get("completion_tokens") or u.get("output_tokens") or 0)
    d["total"] += int(u.get("total_tokens") or 0) or (
        int(u.get("prompt_tokens") or u.get("input_tokens") or 0)
        + int(u.get("completion_tokens") or u.get("output_tokens") or 0))


_LAST = threading.local()


def last_used():
    """(provider, model) of the last successful chat() in THIS thread — the studio names who answered."""
    return getattr(_LAST, "pm", None)


def chat(messages, provider="groq", model="", key="", temperature=0.2, wait_on_limit=True):
    """messages: [{role: system|user|assistant, content}]. Returns text."""
    if provider not in PROVIDERS:
        raise ProviderError(f"unknown provider: {provider}")
    family, url, default_model, label = (PROVIDERS[provider][0],
        PROVIDERS[provider][1], PROVIDERS[provider][2], PROVIDERS[provider][5])
    model = (model or "").strip() or default_model
    key = (key or "").strip() or get_key(provider)
    if not key:
        raise ProviderError(
            f"no key for {label}: set its env var, drop it into "
            f"tool/{PROVIDERS[provider][4]}, or enter it in Settings")

    if family == "anthropic":
        system = "\n\n".join(m["content"] for m in messages
                             if m["role"] == "system")
        conv = [{"role": m["role"], "content": m["content"]}
                for m in messages if m["role"] in ("user", "assistant")]
        body = {"model": model, "max_tokens": 1500,
                "temperature": temperature, "messages": conv}
        if system:
            body["system"] = system
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01",
                   "content-type": "application/json",
                   "user-agent": "ZTLStudio/1.0"}
        data = _post(url, body, headers, wait_on_limit)
        _usage_add(provider, model, data)
        _LAST.pm = (provider, model)
        parts = data.get("content", [])
        return "".join(p.get("text", "") for p in parts).strip()

    # OpenAI-compatible
    body = {"model": model, "messages": messages, "temperature": temperature}
    headers = {"Authorization": f"Bearer {key}",
               "Content-Type": "application/json",
               "User-Agent": "ZTLStudio/1.0"}
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/inventor1975/ZTL"
        headers["X-Title"] = "ZTLStudio"
    data = _post(url, body, headers, wait_on_limit)
    _usage_add(provider, model, data)
    # Безопасный разбор, как в anthropic-ветке. Пустой choices или content=null
    # (reasoning-only / отказ модели) раньше роняли жёсткую цепочку индексов.
    choices = data.get("choices") or []
    if not choices:
        raise ProviderError("провайдер вернул пустой choices")
    content = (choices[0].get("message") or {}).get("content")
    if content is None:
        raise ProviderError("провайдер вернул пустой ответ (reasoning-only/отказ?)")
    _LAST.pm = (provider, model)
    return content.strip()
