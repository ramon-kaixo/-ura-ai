from typing import Any


def to_dict(self) -> dict[str, Any]:
    return {
        "record_id": self.record_id,
        "record_type": self.record_type,
        "reason": self.reason,
        "policy": self.policy,
        "timestamp": self.timestamp,
        "importance": self.importance,
        "age_days": round(self.age_days, 1),
    }
