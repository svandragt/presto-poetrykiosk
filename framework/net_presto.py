import ntptime


class PrestoNetwork:
    def __init__(self, presto):
        self.presto = presto

    def connect(self) -> None:
        # Presto handles Wi-Fi plumbing internally
        self.presto.connect()

    def sync_time(self) -> None:
        # Good for TLS reliability; matches your known-working script
        ntptime.settime()
