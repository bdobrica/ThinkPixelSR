# Changelog

## 0.2.0 — unpublished

- Add async HTTPX client with shared token renewal, cancellation and operation deadlines.
- Reuse sync wire validation and parsing; preserve the existing synchronous API.

## 0.1.0 — unpublished

- Initial synchronous SDK for existing API keys, JWT exchange/cache, store and search.
- Typed results, partial acceptance, bounded 401 replay and sanitized errors.
- Explicit key overrides `THINKPIXEL_API_KEY`; registration remains deferred.
