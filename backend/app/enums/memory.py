from enum import Enum

class MemoryType(str, Enum):
    preference = "preference"
    fact = "fact"
    decision = "decision"
    task = "task"


class EvidenceType(str, Enum):
    explicit = "explicit"
    repeated = "repeated"
    inferred = "inferred"


class TemporalScope(str, Enum):
    durable = "durable"
    ongoing = "ongoing"
    temporary = "temporary"


class SourceKind(str, Enum):
    statement = "statement"
    question = "question"
    request = "request"
    assistant_claim = "assistant_claim"
    hypothetical = "hypothetical"
    unclear = "unclear"


class ValueSpecificity(str, Enum):
    concrete = "concrete"
    vague = "vague"


class OverwriteRisk(str, Enum):
    none = "none"
    low = "low"
    high = "high"


class ProfileCategory(str, Enum):
    identity = "identity"
    preference = "preference"
    project = "project"
    relationship = "relationship"
    wellbeing = "wellbeing"
    other = "other"