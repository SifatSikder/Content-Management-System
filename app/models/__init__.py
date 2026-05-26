"""SQLAlchemy ORM models.

Every model is imported here so `Base.metadata` is fully populated. Alembic's
env.py imports `Base` from this package, so any new model file MUST be added
to this list or autogenerate will miss it.
"""

from app.models.activity import ActivityModel
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.business import BusinessModel
from app.models.business_membership import BusinessMembershipModel
from app.models.cast_member import CastMemberModel
from app.models.connected_google_account import ConnectedGoogleAccountModel
from app.models.department import DepartmentModel
from app.models.department_membership import DepartmentMembershipModel
from app.models.department_role import DepartmentRoleModel
from app.models.department_role_permission import DepartmentRolePermissionModel
from app.models.department_stage_handoff import DepartmentStageHandoffModel
from app.models.department_template import DepartmentTemplateModel
from app.models.edit import EditCommentModel, EditVersionModel
from app.models.enums import (
    BusinessMembershipStatus,
    Category,
    EditStatus,
    PipelineStage,
    Role,
    ShootStatus,
    TokenPurpose,
)
from app.models.idea_version import (
    IdeaModel,
    IdeaSignoffModel,
    IdeaVersionModel,
    SignoffDecision,
)
from app.models.location import LocationModel
from app.models.location_photo import LocationPhotoModel
from app.models.notification import NotificationModel, PushSubscriptionModel
from app.models.notification_prefs import UserNotificationPrefsModel
from app.models.one_time_token import OneTimeTokenModel
from app.models.project import ProjectModel
from app.models.project_stage_assignment import ProjectStageAssignmentModel
from app.models.raw_cut_submission import RawCutSubmissionModel
from app.models.script import ScriptCommentModel, ScriptModel, ScriptVersionModel
from app.models.shoot import ShootModel
from app.models.user import UserModel

__all__ = [
    "ActivityModel",
    "Base",
    "BusinessMembershipModel",
    "BusinessMembershipStatus",
    "BusinessModel",
    "CastMemberModel",
    "Category",
    "ConnectedGoogleAccountModel",
    "DepartmentMembershipModel",
    "DepartmentModel",
    "DepartmentRoleModel",
    "DepartmentRolePermissionModel",
    "DepartmentStageHandoffModel",
    "DepartmentTemplateModel",
    "EditCommentModel",
    "EditStatus",
    "EditVersionModel",
    "IdeaModel",
    "IdeaSignoffModel",
    "IdeaVersionModel",
    "LocationModel",
    "LocationPhotoModel",
    "NotificationModel",
    "OneTimeTokenModel",
    "PipelineStage",
    "ProjectModel",
    "ProjectStageAssignmentModel",
    "RawCutSubmissionModel",
    "PushSubscriptionModel",
    "Role",
    "SignoffDecision",
    "ScriptCommentModel",
    "ScriptModel",
    "ScriptVersionModel",
    "ShootModel",
    "ShootStatus",
    "TimestampMixin",
    "TokenPurpose",
    "UUIDPrimaryKeyMixin",
    "UserModel",
    "UserNotificationPrefsModel",
]
