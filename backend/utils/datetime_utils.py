from datetime import datetime, timezone


class DateTimeUtils:

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
