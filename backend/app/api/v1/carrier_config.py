from __future__ import annotations

"""
Carrier Configuration API — Phase 3.

Endpoints:
  Calc Engine Config:
    GET  /api/v1/admin/calc-config/{carrier_id}      TENANT_ADMIN
    PUT  /api/v1/admin/calc-config/{carrier_id}      TENANT_ADMIN
    GET  /api/v1/admin/tenant-calc-config            TENANT_ADMIN
    PUT  /api/v1/admin/tenant-calc-config            TENANT_ADMIN
    GET  /api/v1/carrier-calc-config/{carrier_id}    REVIEWER+ (read-only for UI)

  Calc Rules:
    GET  /api/v1/admin/calc-rules                    TENANT_ADMIN
    GET  /api/v1/admin/calc-rules/{rule_id}          TENANT_ADMIN
    PUT  /api/v1/admin/calc-rules/{rule_id}          TENANT_ADMIN (edit expression → DRAFT)
    POST /api/v1/admin/calc-rules/{rule_id}/submit   TENANT_ADMIN (DRAFT → PENDING_REVIEW)
    POST /api/v1/admin/calc-rules/{rule_id}/approve  TENANT_ADMIN (PENDING_REVIEW → ACTIVE)
    POST /api/v1/admin/calc-rules/{rule_id}/revert   TENANT_ADMIN (PENDING_REVIEW → DRAFT)
    POST /api/v1/admin/calc-rules/{rule_id}/deactivate TENANT_ADMIN (ACTIVE → DEACTIVATED)
    POST /api/v1/admin/calc-rules                    TENANT_ADMIN (new EDITABLE rule)
    GET  /api/v1/admin/calc-rules/{rule_id}/history  TENANT_ADMIN
    POST /api/v1/admin/calc-rules/test-expression    TENANT_ADMIN
    POST /api/v1/admin/calc-rules/ai-suggest         TENANT_ADMIN
"""

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.security import get_current_user, verify_carrier_scope, verify_role, verify_tenant
from app.schemas.auth import Role, TokenPayload
from app.services.audit_calculation_service import (
    AuditCalculationService,
    LOCKED_RULE_KEYS,
    SAFE_FUNCTIONS,
    SAFE_NAMES,
)

# simpleeval is imported at module level so that NameNotDefined / FunctionNotDefined
# are always bound when _validate_expression's except clauses reference them.
# A missing package surfaces immediately at startup rather than as an UnboundLocalError
# inside a try/except block at call time.
from simpleeval import (
    EvalWithCompoundTypes,
    FunctionNotDefined,
    InvalidExpression,
    NameNotDefined,
)

router = APIRouter()
_calc_svc = AuditCalculationService()


# ---------------------------------------------------------------------------
# Pydantic schemas for this router
# ---------------------------------------------------------------------------

class CalcConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    carrier_id: int
    use_calculation_engine: bool
    updated_at: datetime


class CalcConfigUpdate(BaseModel):
    use_calculation_engine: bool


class TenantCalcConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    use_calculation_engine: bool
    updated_at: datetime


class CalcRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    rule_id: int
    carrier_id: int
    rule_key: str
    rule_label: str
    rule_description: Optional[str]
    expression: str
    is_editable: bool
    rule_status: str
    submitted_by: Optional[str]
    submitted_at: Optional[datetime]
    approved_by: Optional[str]
    approved_at: Optional[datetime]
    effective_from: datetime


class CalcRuleUpdate(BaseModel):
    expression: str


class CalcRuleCreate(BaseModel):
    rule_key: str
    rule_label: str
    rule_description: Optional[str] = None
    expression: str


class ExpressionTestRequest(BaseModel):
    expression: str
    carrier_id: int
    sample_values: dict[str, Any] = {}


class ExpressionTestResponse(BaseModel):
    result: Optional[Any]
    error: Optional[str]
    evaluated_expression: str


class AISuggestRequest(BaseModel):
    description: str
    carrier_id: int


class AISuggestResponse(BaseModel):
    suggested_expression: str
    explanation: str


# ---------------------------------------------------------------------------
# Valid rule status transitions (server-enforced)
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT":          {"PENDING_REVIEW"},
    "PENDING_REVIEW": {"ACTIVE", "DRAFT"},
    "ACTIVE":         {"DEACTIVATED"},
    "DEACTIVATED":    set(),
}


def _assert_valid_transition(current: str, target: str) -> None:
    allowed = _VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Invalid rule status transition: {current} → {target}. "
                f"Allowed from '{current}': {sorted(allowed) or ['none']}."
            ),
        )


# ---------------------------------------------------------------------------
# Calc Engine Config endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/api/v1/admin/calc-config/{carrier_id}",
    response_model=CalcConfigResponse,
    summary="Get carrier calc engine config (TENANT_ADMIN)",
)
async def get_carrier_calc_config(
    carrier_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> CalcConfigResponse:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
    await verify_carrier_scope(carrier_id, token, db)

    row = await db.execute(
        text(
            "SELECT carrier_id, use_calculation_engine, updated_at "
            "FROM carrier_calc_config WHERE carrier_id = :cid"
        ),
        {"cid": carrier_id},
    )
    record = row.fetchone()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Carrier calc config not found.")

    return CalcConfigResponse(
        carrier_id=record[0],
        use_calculation_engine=record[1],
        updated_at=record[2],
    )


@router.put(
    "/api/v1/admin/calc-config/{carrier_id}",
    response_model=CalcConfigResponse,
    summary="Update carrier calc engine config (TENANT_ADMIN)",
)
async def update_carrier_calc_config(
    carrier_id: int,
    body: CalcConfigUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> CalcConfigResponse:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
    await verify_carrier_scope(carrier_id, token, db)

    now = datetime.now(timezone.utc)
    await db.execute(
        text(
            """
            INSERT INTO carrier_calc_config (carrier_id, use_calculation_engine, updated_at)
            VALUES (:cid, :val, :now)
            ON CONFLICT (carrier_id) DO UPDATE
              SET use_calculation_engine = EXCLUDED.use_calculation_engine,
                  updated_at = EXCLUDED.updated_at
            """
        ),
        {"cid": carrier_id, "val": body.use_calculation_engine, "now": now},
    )
    await db.commit()

    # Invalidate Redis cache
    tenant = request.state.tenant
    await _calc_svc.invalidate_calc_config_cache(tenant.schema_name, carrier_id)

    return CalcConfigResponse(
        carrier_id=carrier_id,
        use_calculation_engine=body.use_calculation_engine,
        updated_at=now,
    )


@router.get(
    "/api/v1/carrier-calc-config/{carrier_id}",
    response_model=CalcConfigResponse,
    summary="Read-only carrier calc config for UI (REVIEWER+)",
)
async def get_carrier_calc_config_readonly(
    carrier_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> CalcConfigResponse:
    verify_role(Role.REVIEWER, token)
    verify_tenant(request, token)
    await verify_carrier_scope(carrier_id, token, db)

    row = await db.execute(
        text(
            "SELECT carrier_id, use_calculation_engine, updated_at "
            "FROM carrier_calc_config WHERE carrier_id = :cid"
        ),
        {"cid": carrier_id},
    )
    record = row.fetchone()
    if record is None:
        # Return default (engine ON) when no row exists
        return CalcConfigResponse(
            carrier_id=carrier_id,
            use_calculation_engine=True,
            updated_at=datetime.now(timezone.utc),
        )

    return CalcConfigResponse(
        carrier_id=record[0],
        use_calculation_engine=record[1],
        updated_at=record[2],
    )


@router.get(
    "/api/v1/admin/tenant-calc-config",
    response_model=TenantCalcConfigResponse,
    summary="Get tenant-level calc engine default (TENANT_ADMIN)",
)
async def get_tenant_calc_config(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> TenantCalcConfigResponse:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)

    row = await db.execute(
        text("SELECT id, use_calculation_engine, updated_at FROM tenant_calc_config LIMIT 1")
    )
    record = row.fetchone()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant calc config not found.")

    return TenantCalcConfigResponse(id=record[0], use_calculation_engine=record[1], updated_at=record[2])


@router.put(
    "/api/v1/admin/tenant-calc-config",
    response_model=TenantCalcConfigResponse,
    summary="Update tenant-level calc engine default (TENANT_ADMIN)",
)
async def update_tenant_calc_config(
    body: CalcConfigUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> TenantCalcConfigResponse:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)

    now = datetime.now(timezone.utc)
    row = await db.execute(
        text(
            "UPDATE tenant_calc_config "
            "SET use_calculation_engine = :val, updated_at = :now "
            "RETURNING id, use_calculation_engine, updated_at"
        ),
        {"val": body.use_calculation_engine, "now": now},
    )
    await db.commit()
    record = row.fetchone()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant calc config not found.")

    return TenantCalcConfigResponse(id=record[0], use_calculation_engine=record[1], updated_at=record[2])


# ---------------------------------------------------------------------------
# Calc Rules endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/api/v1/admin/calc-rules",
    response_model=list[CalcRuleResponse],
    summary="List all calc rules for a carrier (TENANT_ADMIN)",
)
async def list_calc_rules(
    carrier_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> list[CalcRuleResponse]:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
    await verify_carrier_scope(carrier_id, token, db)

    result = await db.execute(
        text(
            "SELECT rule_id, carrier_id, rule_key, rule_label, rule_description, "
            "expression, is_editable, rule_status, submitted_by, submitted_at, "
            "approved_by, approved_at, effective_from "
            "FROM carrier_calc_rules WHERE carrier_id = :cid "
            "ORDER BY rule_key, effective_from DESC"
        ),
        {"cid": carrier_id},
    )
    return [
        CalcRuleResponse(
            rule_id=r[0], carrier_id=r[1], rule_key=r[2], rule_label=r[3],
            rule_description=r[4], expression=r[5], is_editable=r[6],
            rule_status=r[7], submitted_by=r[8], submitted_at=r[9],
            approved_by=r[10], approved_at=r[11], effective_from=r[12],
        )
        for r in result.fetchall()
    ]


# ---------------------------------------------------------------------------
# Available Fields — must be registered BEFORE any /{rule_id} route so that
# FastAPI does not match "available-fields" as a rule_id path parameter.
# ---------------------------------------------------------------------------

from app.rules.field_descriptors import get_all_descriptors, FieldDescriptor as FieldDescriptorSchema


@router.get(
    "/api/v1/admin/calc-rules/available-fields",
    response_model=list[FieldDescriptorSchema],
    summary="List all available SAFE_NAMES fields for the expression builder",
)
async def get_available_fields(
    carrier_id: int,
    token: TokenPayload = Depends(get_current_user),
) -> list[FieldDescriptorSchema]:
    """
    Returns field descriptors for all SAFE_NAMES keys.
    Used by the frontend ExpressionBuilder drag-and-drop widget.
    Registered before /{rule_id} routes to prevent path parameter shadowing.
    All authenticated users may read this endpoint.
    """
    return get_all_descriptors()


@router.get(
    "/api/v1/admin/calc-rules/{rule_id}",
    response_model=CalcRuleResponse,
    summary="Get a single calc rule (TENANT_ADMIN)",
)
async def get_calc_rule(
    rule_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> CalcRuleResponse:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)

    result = await db.execute(
        text(
            "SELECT rule_id, carrier_id, rule_key, rule_label, rule_description, "
            "expression, is_editable, rule_status, submitted_by, submitted_at, "
            "approved_by, approved_at, effective_from "
            "FROM carrier_calc_rules WHERE rule_id = :rid"
        ),
        {"rid": rule_id},
    )
    r = result.fetchone()
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found.")

    await verify_carrier_scope(r[1], token, db)

    return CalcRuleResponse(
        rule_id=r[0], carrier_id=r[1], rule_key=r[2], rule_label=r[3],
        rule_description=r[4], expression=r[5], is_editable=r[6],
        rule_status=r[7], submitted_by=r[8], submitted_at=r[9],
        approved_by=r[10], approved_at=r[11], effective_from=r[12],
    )


@router.put(
    "/api/v1/admin/calc-rules/{rule_id}",
    response_model=CalcRuleResponse,
    summary="Edit an EDITABLE rule expression → sets status to DRAFT (TENANT_ADMIN)",
)
async def update_calc_rule(
    rule_id: int,
    body: CalcRuleUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> CalcRuleResponse:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)

    # Load the rule
    result = await db.execute(
        text("SELECT rule_id, carrier_id, rule_key, is_editable, rule_status "
             "FROM carrier_calc_rules WHERE rule_id = :rid"),
        {"rid": rule_id},
    )
    r = result.fetchone()
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found.")

    if not r[3]:  # is_editable == False
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This rule is LOCKED and cannot be edited.",
        )

    await verify_carrier_scope(r[1], token, db)

    # Validate expression via simpleeval
    _ok, _reason = _validate_expression(body.expression)
    if not _ok:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid expression: {_reason}",
        )

    # Log history entry
    await _log_rule_history(rule_id, r[1], r[4], "DRAFT", token.email, body.expression, db)

    # Update the rule to DRAFT
    now = datetime.now(timezone.utc)
    update_result = await db.execute(
        text(
            "UPDATE carrier_calc_rules "
            "SET expression = :expr, rule_status = 'DRAFT', "
            "submitted_by = NULL, submitted_at = NULL, "
            "approved_by = NULL, approved_at = NULL "
            "WHERE rule_id = :rid "
            "RETURNING rule_id, carrier_id, rule_key, rule_label, rule_description, "
            "expression, is_editable, rule_status, submitted_by, submitted_at, "
            "approved_by, approved_at, effective_from"
        ),
        {"expr": body.expression, "rid": rule_id},
    )
    await db.commit()
    updated = update_result.fetchone()

    return CalcRuleResponse(
        rule_id=updated[0], carrier_id=updated[1], rule_key=updated[2],
        rule_label=updated[3], rule_description=updated[4], expression=updated[5],
        is_editable=updated[6], rule_status=updated[7], submitted_by=updated[8],
        submitted_at=updated[9], approved_by=updated[10], approved_at=updated[11],
        effective_from=updated[12],
    )


@router.post(
    "/api/v1/admin/calc-rules/{rule_id}/submit",
    response_model=CalcRuleResponse,
    summary="Submit DRAFT rule for review: DRAFT → PENDING_REVIEW (TENANT_ADMIN)",
)
async def submit_calc_rule(
    rule_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> CalcRuleResponse:
    return await _transition_rule(rule_id, "PENDING_REVIEW", request, db, token)


@router.post(
    "/api/v1/admin/calc-rules/{rule_id}/approve",
    response_model=CalcRuleResponse,
    summary="Approve PENDING_REVIEW rule: PENDING_REVIEW → ACTIVE (TENANT_ADMIN)",
)
async def approve_calc_rule(
    rule_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> CalcRuleResponse:
    rule_response = await _transition_rule(rule_id, "ACTIVE", request, db, token)

    # Invalidate calc rules cache
    tenant = request.state.tenant
    await _calc_svc.invalidate_calc_rules_cache(tenant.schema_name, rule_response.carrier_id)

    return rule_response


@router.post(
    "/api/v1/admin/calc-rules/{rule_id}/revert",
    response_model=CalcRuleResponse,
    summary="Revert PENDING_REVIEW rule back to DRAFT (TENANT_ADMIN)",
)
async def revert_calc_rule(
    rule_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> CalcRuleResponse:
    return await _transition_rule(rule_id, "DRAFT", request, db, token)


@router.post(
    "/api/v1/admin/calc-rules/{rule_id}/deactivate",
    response_model=CalcRuleResponse,
    summary="Deactivate an ACTIVE EDITABLE rule: ACTIVE → DEACTIVATED (TENANT_ADMIN)",
)
async def deactivate_calc_rule(
    rule_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> CalcRuleResponse:
    # Only EDITABLE rules can be deactivated
    result = await db.execute(
        text("SELECT is_editable FROM carrier_calc_rules WHERE rule_id = :rid"),
        {"rid": rule_id},
    )
    r = result.fetchone()
    if r and not r[0]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="LOCKED rules cannot be deactivated.",
        )
    return await _transition_rule(rule_id, "DEACTIVATED", request, db, token)


@router.post(
    "/api/v1/admin/calc-rules",
    response_model=CalcRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new EDITABLE rule in DRAFT status (TENANT_ADMIN)",
)
async def create_calc_rule(
    body: CalcRuleCreate,
    carrier_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> CalcRuleResponse:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
    await verify_carrier_scope(carrier_id, token, db)

    # rule_key must not collide with LOCKED keys
    if body.rule_key in LOCKED_RULE_KEYS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"rule_key '{body.rule_key}' is reserved for a LOCKED rule.",
        )

    _ok, _reason = _validate_expression(body.expression)
    if not _ok:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid expression: {_reason}",
        )

    now = datetime.now(timezone.utc)
    result = await db.execute(
        text(
            """
            INSERT INTO carrier_calc_rules
              (carrier_id, rule_key, rule_label, rule_description, expression,
               is_editable, rule_status, effective_from)
            VALUES
              (:cid, :key, :label, :desc, :expr, TRUE, 'DRAFT', :now)
            RETURNING rule_id, carrier_id, rule_key, rule_label, rule_description,
              expression, is_editable, rule_status, submitted_by, submitted_at,
              approved_by, approved_at, effective_from
            """
        ),
        {
            "cid": carrier_id, "key": body.rule_key, "label": body.rule_label,
            "desc": body.rule_description, "expr": body.expression, "now": now,
        },
    )
    await db.commit()
    r = result.fetchone()

    return CalcRuleResponse(
        rule_id=r[0], carrier_id=r[1], rule_key=r[2], rule_label=r[3],
        rule_description=r[4], expression=r[5], is_editable=r[6],
        rule_status=r[7], submitted_by=r[8], submitted_at=r[9],
        approved_by=r[10], approved_at=r[11], effective_from=r[12],
    )


@router.get(
    "/api/v1/admin/calc-rules/{rule_id}/history",
    summary="Get rule audit history (TENANT_ADMIN)",
)
async def get_rule_history(
    rule_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> list[dict[str, Any]]:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)

    result = await db.execute(
        text(
            "SELECT id, rule_id, carrier_id, previous_status, new_status, "
            "changed_by, expression_snapshot, changed_at "
            "FROM carrier_calc_rule_audit_log "
            "WHERE rule_id = :rid "
            "ORDER BY changed_at DESC"
        ),
        {"rid": rule_id},
    )
    return [
        {
            "id": r[0], "rule_id": r[1], "carrier_id": r[2],
            "previous_status": r[3], "new_status": r[4],
            "changed_by": r[5], "expression_snapshot": r[6],
            "changed_at": r[7].isoformat() if r[7] else None,
        }
        for r in result.fetchall()
    ]


@router.post(
    "/api/v1/admin/calc-rules/test-expression",
    response_model=ExpressionTestResponse,
    summary="Test a rule expression with sample values (TENANT_ADMIN)",
)
async def test_expression(
    body: ExpressionTestRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> ExpressionTestResponse:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)

    from app.services.audit_calculation_service import SAFE_NAMES
    try:
        evaluator = EvalWithCompoundTypes(names={**SAFE_NAMES, **body.sample_values}, functions={**SAFE_FUNCTIONS})
        result = evaluator.eval(body.expression)
        return ExpressionTestResponse(
            result=result,
            error=None,
            evaluated_expression=body.expression,
        )
    except Exception as exc:
        return ExpressionTestResponse(
            result=None,
            error=str(exc),
            evaluated_expression=body.expression,
        )


@router.post(
    "/api/v1/admin/calc-rules/ai-suggest",
    response_model=AISuggestResponse,
    summary="AI-suggested expression for a described rule (TENANT_ADMIN)",
)
async def ai_suggest_expression(
    body: AISuggestRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> AISuggestResponse:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)

    from app.services.ai_narrative_service import AInarrativeService

    prompt = (
        f"You are a Workers Compensation audit rules engine expert. "
        f"Given this rule description: '{body.description}', "
        f"write a simpleeval-compatible Python expression using ONLY these variables: "
        f"{', '.join(k for k in SAFE_NAMES if not callable(SAFE_NAMES[k]))}. "
        f"Return ONLY the expression on the first line, then an explanation on subsequent lines. "
        f"Example expression: abs(variance_pct) > 0.30"
    )

    svc = AInarrativeService()
    try:
        raw = await svc.generate_raw(prompt)
        lines = raw.strip().split("\n", 1)
        expr = lines[0].strip()
        explanation = lines[1].strip() if len(lines) > 1 else "Expression generated based on rule description."

        # Validate before returning
        _ok, _reason = _validate_expression(expr)
        if not _ok:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid expression for rule {rule_key}: {_reason}",
            )

        return AISuggestResponse(suggested_expression=expr, explanation=explanation)
    except Exception as exc:
        return AISuggestResponse(
            suggested_expression="abs(variance_pct) > 0.30",
            explanation=f"Default expression used. AI suggestion failed: {exc}",
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_expression(expression: str) -> tuple[bool, str | None]:
    """
    Validates that a rule expression is safe to evaluate via simpleeval.

    Returns (True, None) when the expression is safe and well-formed.
    Returns (False, reason) when blocked or syntactically broken.

    NameNotDefined / FunctionNotDefined from simpleeval are intentionally
    treated as *valid* — they mean the expression references runtime
    variables (e.g. variance_pct) that are absent at parse time.
    """
    blocked = ("import", "exec", "eval", "__", "os.", "sys.", "open(", "subprocess")
    for term in blocked:
        if term in expression:
            return False, f"Expression contains forbidden term: '{term}'."

    try:
        evaluator = EvalWithCompoundTypes(names={**SAFE_NAMES}, functions={**SAFE_FUNCTIONS})
        evaluator.eval(expression)
        return True, None
    except (NameNotDefined, FunctionNotDefined):
        # Runtime variable absent at validation time — expression is structurally valid.
        return True, None
    except (InvalidExpression, SyntaxError, ValueError) as exc:
        return False, str(exc)
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


async def _transition_rule(
    rule_id: int,
    target_status: str,
    request: Request,
    db: AsyncSession,
    token: TokenPayload,
) -> CalcRuleResponse:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)

    result = await db.execute(
        text(
            "SELECT rule_id, carrier_id, rule_key, rule_label, rule_description, "
            "expression, is_editable, rule_status, submitted_by, submitted_at, "
            "approved_by, approved_at, effective_from "
            "FROM carrier_calc_rules WHERE rule_id = :rid"
        ),
        {"rid": rule_id},
    )
    r = result.fetchone()
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found.")

    await verify_carrier_scope(r[1], token, db)
    current_status = r[7]
    _assert_valid_transition(current_status, target_status)

    now = datetime.now(timezone.utc)
    extra_fields = ""
    extra_params: dict[str, Any] = {}

    if target_status == "PENDING_REVIEW":
        extra_fields = ", submitted_by = :submitter, submitted_at = :now2"
        extra_params = {"submitter": token.email, "now2": now}
    elif target_status == "ACTIVE":
        extra_fields = ", approved_by = :approver, approved_at = :now2"
        extra_params = {"approver": token.email, "now2": now}

    await _log_rule_history(rule_id, r[1], current_status, target_status, token.email, r[5], db)

    update_result = await db.execute(
        text(
            f"UPDATE carrier_calc_rules "
            f"SET rule_status = :status {extra_fields} "
            f"WHERE rule_id = :rid "
            f"RETURNING rule_id, carrier_id, rule_key, rule_label, rule_description, "
            f"expression, is_editable, rule_status, submitted_by, submitted_at, "
            f"approved_by, approved_at, effective_from"
        ),
        {"status": target_status, "rid": rule_id, **extra_params},
    )
    await db.commit()
    updated = update_result.fetchone()

    return CalcRuleResponse(
        rule_id=updated[0], carrier_id=updated[1], rule_key=updated[2],
        rule_label=updated[3], rule_description=updated[4], expression=updated[5],
        is_editable=updated[6], rule_status=updated[7], submitted_by=updated[8],
        submitted_at=updated[9], approved_by=updated[10], approved_at=updated[11],
        effective_from=updated[12],
    )


async def _log_rule_history(
    rule_id: int,
    carrier_id: int,
    previous_status: str,
    new_status: str,
    changed_by: str,
    expression_snapshot: str,
    db: AsyncSession,
) -> None:
    """Writes one row to carrier_calc_rule_audit_log."""
    try:
        await db.execute(
            text(
                """
                INSERT INTO carrier_calc_rule_audit_log
                  (rule_id, carrier_id, previous_status, new_status,
                   changed_by, expression_snapshot, changed_at)
                VALUES
                  (:rid, :cid, :prev, :new, :by, :expr, now())
                """
            ),
            {
                "rid": rule_id, "cid": carrier_id,
                "prev": previous_status, "new": new_status,
                "by": changed_by, "expr": expression_snapshot,
            },
        )
        # Do NOT commit here — caller commits the full transaction
    except Exception as exc:
        # Log but don't fail the main operation if audit log write fails
        import structlog
        log = structlog.get_logger(__name__)
        log.warning("rule_history.log_failed", rule_id=rule_id, error=str(exc))

# =============================================================================
# Phase 7C — LLM Configuration Schemas & Endpoints
# =============================================================================

from app.services.llm_key_vault_service import llm_key_vault
from app.services.llm_client_factory import LLMClientFactory, SUPPORTED_PROVIDERS


class LLMConfigCreateRequest(BaseModel):
    carrier_id: int
    provider_name: str
    model_name: str
    api_key: str | None = None
    api_base_url: str | None = None


class LLMConfigUpdateRequest(BaseModel):
    model_name: str | None = None
    api_key: str | None = None
    api_base_url: str | None = None


class LLMConfigResponse(BaseModel):
    config_id: int
    carrier_id: int
    provider_name: str | None
    model_name: str | None
    api_key_last4: str | None
    api_base_url: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class LLMTestResult(BaseModel):
    success: bool
    latency_ms: int
    provider: str
    model: str
    error: str | None = None


@router.get(
    "/api/v1/admin/llm-config",
    response_model=Optional[LLMConfigResponse],
    summary="Get LLM config for a carrier",
)
async def get_llm_config(
    carrier_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> Optional[LLMConfigResponse]:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
    schema = request.state.tenant.schema_name

    await db.execute(text(f"SET search_path TO {schema}, public"))
    result = await db.execute(
        text(
            "SELECT config_id, carrier_id, provider_name, model_name, "
            "api_key_enc, api_base_url, is_active, created_at, updated_at "
            "FROM carrier_llm_config WHERE carrier_id = :cid"
        ),
        {"cid": carrier_id},
    )
    row = result.fetchone()
    if row is None:
        return None

    cfg_id, c_id, provider, model, api_key_enc, base_url, active, cat, uat = row
    last4: str | None = None
    if api_key_enc:
        try:
            plain = llm_key_vault.decrypt_key(api_key_enc)
            last4 = llm_key_vault.last4(plain)
        except Exception:
            last4 = "***"

    return LLMConfigResponse(
        config_id=cfg_id, carrier_id=c_id, provider_name=provider,
        model_name=model, api_key_last4=last4, api_base_url=base_url,
        is_active=active, created_at=cat, updated_at=uat,
    )


@router.post(
    "/api/v1/admin/llm-config",
    response_model=LLMConfigResponse,
    summary="Create or replace LLM config for a carrier",
)
async def create_llm_config(
    payload: LLMConfigCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> LLMConfigResponse:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
    schema = request.state.tenant.schema_name

    if payload.provider_name not in SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported provider: {payload.provider_name}.",
        )

    api_key_enc: str | None = None
    last4: str | None = None
    if payload.api_key:
        api_key_enc = llm_key_vault.encrypt_key(payload.api_key)
        last4 = llm_key_vault.last4(payload.api_key)

    await db.execute(text(f"SET search_path TO {schema}, public"))
    now = datetime.now(timezone.utc)
    result = await db.execute(
        text(
            "INSERT INTO carrier_llm_config "
            "(carrier_id, provider_name, model_name, api_key_enc, api_base_url, "
            "is_active, created_at, updated_at, created_by) "
            "VALUES (:cid, :prov, :model, :enc, :base, TRUE, :now, :now, :by) "
            "ON CONFLICT (carrier_id) DO UPDATE SET "
            "provider_name = EXCLUDED.provider_name, "
            "model_name = EXCLUDED.model_name, "
            "api_key_enc = COALESCE(EXCLUDED.api_key_enc, carrier_llm_config.api_key_enc), "
            "api_base_url = EXCLUDED.api_base_url, "
            "is_active = TRUE, "
            "updated_at = EXCLUDED.updated_at "
            "RETURNING config_id, carrier_id, provider_name, model_name, "
            "api_base_url, is_active, created_at, updated_at"
        ),
        {
            "cid": payload.carrier_id, "prov": payload.provider_name,
            "model": payload.model_name, "enc": api_key_enc,
            "base": payload.api_base_url, "now": now,
            "by": token.sub or "tenant_admin",
        },
    )
    await db.commit()
    row = result.fetchone()
    return LLMConfigResponse(
        config_id=row[0], carrier_id=row[1], provider_name=row[2],
        model_name=row[3], api_key_last4=last4, api_base_url=row[4],
        is_active=row[5], created_at=row[6], updated_at=row[7],
    )


@router.put(
    "/api/v1/admin/llm-config/{config_id}",
    response_model=LLMConfigResponse,
    summary="Update LLM config",
)
async def update_llm_config(
    config_id: int,
    payload: LLMConfigUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> LLMConfigResponse:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
    schema = request.state.tenant.schema_name
    await db.execute(text(f"SET search_path TO {schema}, public"))

    updates: list[str] = ["updated_at = now()"]
    params: dict[str, Any] = {"cid": config_id}
    new_last4: str | None = None

    if payload.model_name is not None:
        updates.append("model_name = :model")
        params["model"] = payload.model_name
    if payload.api_base_url is not None:
        updates.append("api_base_url = :base")
        params["base"] = payload.api_base_url
    if payload.api_key is not None:
        params["enc"] = llm_key_vault.encrypt_key(payload.api_key)
        updates.append("api_key_enc = :enc")
        new_last4 = llm_key_vault.last4(payload.api_key)

    result = await db.execute(
        text(
            f"UPDATE carrier_llm_config SET {', '.join(updates)} "
            "WHERE config_id = :cid "
            "RETURNING config_id, carrier_id, provider_name, model_name, "
            "api_key_enc, api_base_url, is_active, created_at, updated_at"
        ),
        params,
    )
    await db.commit()
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="LLM config not found")

    display_last4 = new_last4
    if display_last4 is None and row[4]:
        try:
            plain = llm_key_vault.decrypt_key(row[4])
            display_last4 = llm_key_vault.last4(plain)
        except Exception:
            display_last4 = "***"

    return LLMConfigResponse(
        config_id=row[0], carrier_id=row[1], provider_name=row[2],
        model_name=row[3], api_key_last4=display_last4, api_base_url=row[5],
        is_active=row[6], created_at=row[7], updated_at=row[8],
    )

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
@router.delete("/api/v1/admin/llm-config/{config_id}", status_code=204)
async def delete_llm_config(
    config_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> Response:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
    schema = request.state.tenant.schema_name
    await db.execute(text(f"SET search_path TO {schema}, public"))
    await db.execute(
        text("UPDATE carrier_llm_config SET is_active = FALSE, updated_at = now() "
             "WHERE config_id = :cid"),
        {"cid": config_id},
    )
    await db.commit()
    return Response(status_code=204)  # ← explicit Response object, no body


@router.post(
    "/api/v1/admin/llm-config/test",
    response_model=LLMTestResult,
    summary="Test LLM connection for a carrier",
)
async def test_llm_connection(
    payload: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: TokenPayload = Depends(get_current_user),
) -> LLMTestResult:
    verify_role(Role.TENANT_ADMIN, token)
    verify_tenant(request, token)
    carrier_id: int = int(payload.get("carrier_id", 0))
    schema = request.state.tenant.schema_name
    await db.execute(text(f"SET search_path TO {schema}, public"))

    result = await db.execute(
        text(
            "SELECT provider_name, model_name, api_key_enc, api_base_url "
            "FROM carrier_llm_config WHERE carrier_id = :cid AND is_active = TRUE"
        ),
        {"cid": carrier_id},
    )
    row = result.fetchone()
    if row is None or not row[0]:
        return LLMTestResult(
            success=False, latency_ms=0, provider="none", model="none",
            error="No active LLM configuration found for this carrier.",
        )

    provider_name, model_name, api_key_enc, api_base_url = row
    try:
        api_key = llm_key_vault.decrypt_key(api_key_enc)
        client = LLMClientFactory.create(
            provider_name=provider_name, model_name=model_name or "",
            api_key=api_key, api_base_url=api_base_url,
        )
        success, latency_ms, error = await client.test_connection()
        return LLMTestResult(
            success=success, latency_ms=latency_ms,
            provider=provider_name, model=model_name or "", error=error,
        )
    except Exception as exc:
        return LLMTestResult(
            success=False, latency_ms=0,
            provider=provider_name, model=model_name or "", error=str(exc),
        )


# =============================================================================
# Phase 7D — Available Fields Endpoint
# =============================================================================