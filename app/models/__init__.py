"""SQLAlchemy ORM models.

Every model is imported here so `Base.metadata` is fully populated. Alembic's
env.py imports `Base` from this package, so any new model file MUST be added
to this list or autogenerate will miss it.
"""

from app.models.activity import ActivityModel
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.cast_member import CastMemberModel
from app.models.edit import EditCommentModel, EditVersionModel
from app.models.enums import (
    Category,
    EditStatus,
    PipelineStage,
    Role,
    ShootStatus,
    TokenPurpose,
)
from app.models.location import LocationModel
from app.models.location_photo import LocationPhotoModel
from app.models.notification import NotificationModel, PushSubscriptionModel
from app.models.one_time_token import OneTimeTokenModel
from app.models.project import ProjectModel
from app.models.script import ScriptCommentModel, ScriptModel, ScriptVersionModel
from app.models.shoot import ShootModel
from app.models.user import UserModel

__all__ = [
    "ActivityModel",
    "Base",
    "CastMemberModel",
    "Category",
    "EditCommentModel",
    "EditStatus",
    "EditVersionModel",
    "LocationModel",
    "LocationPhotoModel",
    "NotificationModel",
    "OneTimeTokenModel",
    "PipelineStage",
    "ProjectModel",
    "PushSubscriptionModel",
    "Role",
    "ScriptCommentModel",
    "ScriptModel",
    "ScriptVersionModel",
    "ShootModel",
    "ShootStatus",
    "TimestampMixin",
    "TokenPurpose",
    "UUIDPrimaryKeyMixin",
    "UserModel",
]
