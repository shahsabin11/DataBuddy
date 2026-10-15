"""Shared enums for the tenancy and analysis schema."""

from enum import StrEnum


class MembershipRole(StrEnum):
    STUDENT = "student"
    INSTITUTION_ADMIN = "institution_admin"


class MembershipStatus(StrEnum):
    ACTIVE = "active"
    LEFT = "left"
    SUSPENDED = "suspended"


class OAuthProvider(StrEnum):
    GOOGLE = "google"
    MICROSOFT = "microsoft"


class ProjectMemberSource(StrEnum):
    OWNER = "owner"
    INVITE = "invite"
    BREAK_GLASS = "break_glass"


class DatasetStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    DELETING = "deleting"


class AgentStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    NEEDS_DECISION = "needs_decision"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DECLINED = "declined"


class ArtifactKind(StrEnum):
    PLOT = "plot"
    TABLE = "table"
    REPORT = "report"
    RESULT_JSON = "result_json"
