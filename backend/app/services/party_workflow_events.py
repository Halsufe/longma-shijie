from __future__ import annotations

from typing import Final


PARTY_ACTIVITY_PUBLISHED: Final = "party.activity_published"
PARTY_REGISTRATION_DEADLINE_APPROACHING: Final = (
    "party.registration_deadline_approaching"
)
PARTY_ACTIVITY_STARTING: Final = "party.activity_starting"
PARTY_ACTIVITY_FINISHED: Final = "party.activity_finished"
PARTY_STATUS_CHANGED: Final = "party.status_changed"
PARTY_POLITICAL_STATUS_APPROVED: Final = "party.political_status_approved"

PARTY_WORKFLOW_EVENT_DEFINITIONS: Final = {
    PARTY_ACTIVITY_PUBLISHED: {
        "payload_fields": ("activity_id", "target_user_ids"),
        "destination": "notification_center",
    },
    PARTY_REGISTRATION_DEADLINE_APPROACHING: {
        "payload_fields": ("activity_id", "registered_user_ids"),
        "destination": "notification_center",
    },
    PARTY_ACTIVITY_STARTING: {
        "payload_fields": ("activity_id", "registered_user_ids"),
        "destination": "notification_center",
    },
    PARTY_ACTIVITY_FINISHED: {
        "payload_fields": ("activity_id",),
        "destination": "participation_record_and_archive_reminder",
    },
    PARTY_STATUS_CHANGED: {
        "payload_fields": ("user_id", "from_status", "to_status"),
        "destination": "notification_and_audit",
    },
}

POLITICAL_WORKFLOW_EVENT_DEFINITIONS: Final = {
    PARTY_POLITICAL_STATUS_APPROVED: {
        "payload_fields": ("review_id", "user_id", "political_status"),
        "destination": "notification_center",
    }
}

PARTY_WORKFLOW_EVENTS: Final = (
    PARTY_ACTIVITY_PUBLISHED,
    PARTY_REGISTRATION_DEADLINE_APPROACHING,
    PARTY_ACTIVITY_STARTING,
    PARTY_ACTIVITY_FINISHED,
    PARTY_STATUS_CHANGED,
)
WORKFLOW_EVENT_DEFINITIONS: Final = {
    **PARTY_WORKFLOW_EVENT_DEFINITIONS,
    **POLITICAL_WORKFLOW_EVENT_DEFINITIONS,
}
