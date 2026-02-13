try:
    import urequests as requests
except ImportError:
    import requests


class HttpClient:
    def get_text(self, url: str) -> str:
        r = None
        try:
            r = requests.get(url)
            status = getattr(r, "status_code", 200)
            if status != 200:
                raise RuntimeError("HTTP %d" % status)
            return (r.text or "").strip()
        finally:
            if r is not None:
                try:
                    r.close()
                except Exception:
                    pass
