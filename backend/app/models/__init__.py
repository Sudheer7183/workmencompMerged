# """
# ORM model registry — import all models here so SQLAlchemy metadata
# discovers them for Alembic autogenerate and runtime table resolution.
# """
# from app.models.tenancy import (  # noqa: F401
#     TenantRegistry,
#     TenantBranding,
#     TenantCalcConfig,
#     CarrierThemeConfig,
#     UserThemePref,
# )
# from app.models.policies import Policy  # noqa: F401
# from app.models.facts import (  # noqa: F401
#     PremiumVariance,
#     PayrollVariancePolicy,
#     PayrollVarianceClass,
#     ZeroPayroll,
#     MissingPayroll,
# )
# from app.models.ingestion import (  # noqa: F401
#     IngestionSource,
#     IngestionRun,
#     IngestionError,
#     IngestionSkippedRow,
#     IngestionRollback,
#     IngestionFieldMap,
# )
# from app.models.calc_config import (  # noqa: F401
#     CarrierCalcRule,
#     CarrierCalcConfig,
# )
# from app.models.reports import (  # noqa: F401
#     CarrierReportTemplate,
#     ReportJob,
# )

"""
ORM model registry — import all models here so SQLAlchemy metadata
discovers them for Alembic autogenerate and runtime table resolution.
"""
from app.models.tenancy import (  # noqa: F401
    PublicTenant,
    PublicCarrier,
)
from app.models.policies import (  # noqa: F401
    Policyholder,
    Policy,
)
from app.models.facts import (  # noqa: F401
    PremiumVariance,
    PayrollVariancePolicy,
    PayrollVarianceClass,
    ZeroPayroll,
    MissingPayroll,
)
from app.models.ingestion import (  # noqa: F401
    IngestionSource,
    IngestionRun,
    IngestionError,
    IngestionSkippedRow,
    IngestionRollback,
    IngestionFieldMap,
)
from app.models.calc_config import (  # noqa: F401
    TenantCalcConfig,
    CarrierCalcConfig,
    CarrierCalcRule,
)
from app.models.reports import (  # noqa: F401
    CarrierReportTemplate,
    ReportJob,
)
from app.models.config import (  # noqa: F401
    CarrierUiLabel,
    CarrierDisplayConfig,
    CarrierThemeConfig,
    TenantTheme,
    UserThemePref,
    CleanupRun,
)
from app.models.llm_config import (  # noqa: F401
    CarrierLLMConfig,
)
