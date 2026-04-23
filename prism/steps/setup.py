"""Step 1 — Run Setup.

Three phases:

1. **Form** (default): PM fills in hypothesis, markets, product context, variants,
   panel size, and pass criteria. Dynamic lists for markets and variants
   (+/– buttons) live outside a form so they re-render immediately.
2. **Review**: PM clicks "Review before proceeding". We validate shape + path
   existence in Python, then call the orchestrator for a structured summary
   that gets appended to `state.history`. The bubble is shown below the form.
3. **Proceed**: PM clicks "Proceed". We persist the payload to `state.setup`,
   mark the step COMPLETE, propagate staleness downstream, and navigate to
   the Method step.

Draft form data lives entirely in `st.session_state` until "Proceed" — this
avoids writing half-baked setup payloads into `state.json`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st
from pydantic import ValidationError

from prism import orchestrator
from prism import state as S
from prism.ui import chat, progress


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def render(state: S.State, step: str) -> None:
    progress.header(state, step)

    review_key = f"setup_review_{state.run_id}"
    in_review = st.session_state.get(review_key, False)

    _ensure_draft_initialized(state)

    _render_form(state)

    if in_review:
        st.divider()
        _render_review(state)

    # Show any existing orchestrator history for this step (older sessions)
    if not in_review:
        prior_msg = orchestrator.latest_message_for(state, S.STEP_SETUP)
        if prior_msg is not None:
            st.divider()
            st.caption("Last orchestrator confirmation for this step:")
            chat.render_orchestrator_message(prior_msg)


# ---------------------------------------------------------------------------
# Draft state (session_state-scoped)
# ---------------------------------------------------------------------------


def _draft_key(name: str, state: S.State) -> str:
    return f"setup_{name}_{state.run_id}"


def _ensure_draft_initialized(state: S.State) -> None:
    """Seed session_state with defaults pulled from state.setup if present."""
    if st.session_state.get(_draft_key("initialized", state)):
        return

    existing = state.setup
    if existing is not None:
        st.session_state[_draft_key("hypothesis", state)] = existing.hypothesis
        st.session_state[_draft_key("source_locale", state)] = existing.source_market.locale
        st.session_state[_draft_key("source_country", state)] = existing.source_market.country
        st.session_state[_draft_key("markets", state)] = [
            {"locale": m.locale, "country": m.country} for m in existing.target_markets
        ]
        st.session_state[_draft_key("variants", state)] = [
            {
                "id": v.id,
                "label": v.label,
                "path": v.path,
                "is_control": v.is_control,
            }
            for v in existing.variants
        ]
        pc = existing.product_context
        st.session_state[_draft_key("application", state)] = pc.application
        st.session_state[_draft_key("product_unit", state)] = pc.product_unit
        st.session_state[_draft_key("feature", state)] = pc.feature
        st.session_state[_draft_key("asset_type", state)] = pc.asset_type
        st.session_state[_draft_key("use_case", state)] = pc.use_case
        st.session_state[_draft_key("panel_size", state)] = existing.panel_size_per_market
        st.session_state[_draft_key("min_top_share", state)] = existing.pass_criteria.min_top_variant_share
        st.session_state[_draft_key("max_red_flags", state)] = existing.pass_criteria.max_cultural_red_flags
    else:
        st.session_state[_draft_key("markets", state)] = [
            {"locale": "ja-JP", "country": "Japan"},
        ]
        st.session_state[_draft_key("variants", state)] = [
            {"id": "A", "label": "Control", "path": "", "is_control": True},
            {"id": "B", "label": "Candidate", "path": "", "is_control": False},
        ]

    st.session_state[_draft_key("initialized", state)] = True


# ---------------------------------------------------------------------------
# Form
# ---------------------------------------------------------------------------


def _render_form(state: S.State) -> None:
    st.markdown(
        "Define the run. The orchestrator will review your inputs, flag "
        "inconsistencies, and confirm before the step is locked."
    )

    # --- Hypothesis ---
    st.subheader("Hypothesis")
    st.text_area(
        "What are you trying to validate?",
        key=_draft_key("hypothesis", state),
        placeholder=(
            "Variant B (the Japan-localized poster) is a culturally appropriate "
            "substitute for Variant A when shown to Japanese SMB users."
        ),
        height=90,
    )

    # --- Markets ---
    st.subheader("Markets")
    col_src_l, col_src_c = st.columns([1, 2])
    with col_src_l:
        st.text_input(
            "Source locale",
            key=_draft_key("source_locale", state),
            value=st.session_state.get(_draft_key("source_locale", state), "en-US"),
        )
    with col_src_c:
        st.text_input(
            "Source country",
            key=_draft_key("source_country", state),
            value=st.session_state.get(_draft_key("source_country", state), "United States"),
        )

    st.markdown("**Target markets** — separate panels run in each.")
    markets = st.session_state[_draft_key("markets", state)]
    to_remove: list[int] = []
    for i, m in enumerate(markets):
        c1, c2, c3 = st.columns([1, 2, 0.3])
        with c1:
            m["locale"] = st.text_input(
                "Locale",
                value=m.get("locale", ""),
                key=f"mkt_loc_{state.run_id}_{i}",
                label_visibility="collapsed" if i > 0 else "visible",
                placeholder="ja-JP",
            )
        with c2:
            m["country"] = st.text_input(
                "Country",
                value=m.get("country", ""),
                key=f"mkt_cty_{state.run_id}_{i}",
                label_visibility="collapsed" if i > 0 else "visible",
                placeholder="Japan",
            )
        with c3:
            if i > 0:
                st.markdown("<br/>", unsafe_allow_html=True)
            if st.button("✕", key=f"mkt_rm_{state.run_id}_{i}", help="Remove market"):
                to_remove.append(i)

    for idx in reversed(to_remove):
        markets.pop(idx)
    if to_remove:
        st.rerun()

    if st.button("+ Add market", key=f"mkt_add_{state.run_id}"):
        markets.append({"locale": "", "country": ""})
        st.rerun()

    # --- Product context ---
    st.subheader("Product context")
    c1, c2 = st.columns(2)
    with c1:
        st.text_input(
            "Application",
            key=_draft_key("application", state),
            value=st.session_state.get(_draft_key("application", state), "Adobe Express"),
        )
        st.text_input(
            "Product unit",
            key=_draft_key("product_unit", state),
            value=st.session_state.get(_draft_key("product_unit", state), "Digital Assets"),
        )
        st.text_input(
            "Feature",
            key=_draft_key("feature", state),
            value=st.session_state.get(_draft_key("feature", state), "Culturalization"),
        )
    with c2:
        st.text_input(
            "Asset type",
            key=_draft_key("asset_type", state),
            value=st.session_state.get(_draft_key("asset_type", state), "promotional_poster"),
        )
        st.text_area(
            "Use case",
            key=_draft_key("use_case", state),
            value=st.session_state.get(
                _draft_key("use_case", state),
                "SMB users creating promotional posters for storefront marketing.",
            ),
            height=110,
        )

    # --- Variants ---
    st.subheader("Variants")
    st.caption("Each variant is shown to respondents in every target market (ranking panel).")
    variants = st.session_state[_draft_key("variants", state)]
    to_remove_v: list[int] = []
    for i, v in enumerate(variants):
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([1, 2, 0.6, 0.3])
            with c1:
                v["id"] = st.text_input(
                    "ID",
                    value=v.get("id", ""),
                    key=f"var_id_{state.run_id}_{i}",
                )
            with c2:
                v["label"] = st.text_input(
                    "Label",
                    value=v.get("label", ""),
                    key=f"var_lbl_{state.run_id}_{i}",
                    placeholder="Japan-localized candidate",
                )
            with c3:
                v["is_control"] = st.checkbox(
                    "Control",
                    value=v.get("is_control", False),
                    key=f"var_ctl_{state.run_id}_{i}",
                )
            with c4:
                st.markdown("<br/>", unsafe_allow_html=True)
                if len(variants) > 2 and st.button(
                    "✕", key=f"var_rm_{state.run_id}_{i}", help="Remove variant"
                ):
                    to_remove_v.append(i)
            v["path"] = st.text_input(
                "Image path (relative to repo root)",
                value=v.get("path", ""),
                key=f"var_pth_{state.run_id}_{i}",
                placeholder="assets/variant_b.png",
            )
            # Inline existence check (live, before submit)
            if v["path"]:
                full = S.REPO_ROOT / v["path"]
                if full.exists():
                    st.caption(f"✅ Found `{v['path']}`")
                else:
                    st.caption(f"⚠️  `{v['path']}` not found under {S.REPO_ROOT}")

    for idx in reversed(to_remove_v):
        variants.pop(idx)
    if to_remove_v:
        st.rerun()

    if st.button("+ Add variant", key=f"var_add_{state.run_id}"):
        next_id = _next_variant_id([v.get("id", "") for v in variants])
        variants.append({"id": next_id, "label": "", "path": "", "is_control": False})
        st.rerun()

    # --- Panel + pass criteria ---
    st.subheader("Panel + pass criteria")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.number_input(
            "Panel size per market",
            min_value=4,
            max_value=40,
            step=1,
            key=_draft_key("panel_size", state),
            value=st.session_state.get(_draft_key("panel_size", state), 12),
        )
    with c2:
        st.number_input(
            "Min share for top variant",
            min_value=0.0,
            max_value=1.0,
            step=0.05,
            key=_draft_key("min_top_share", state),
            value=st.session_state.get(_draft_key("min_top_share", state), 0.65),
        )
    with c3:
        st.number_input(
            "Max cultural red flags",
            min_value=0,
            max_value=10,
            step=1,
            key=_draft_key("max_red_flags", state),
            value=st.session_state.get(_draft_key("max_red_flags", state), 1),
        )

    # --- Submit ---
    st.divider()
    submit = st.button(
        "Review before proceeding",
        key=f"setup_submit_{state.run_id}",
        type="primary",
    )
    if submit:
        _handle_submit(state)


def _next_variant_id(existing_ids: list[str]) -> str:
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        if letter not in existing_ids:
            return letter
    return f"V{len(existing_ids) + 1}"


# ---------------------------------------------------------------------------
# Submit -> validate -> orchestrator
# ---------------------------------------------------------------------------


def _collect_payload(state: S.State) -> dict[str, Any]:
    """Gather the current form values into a Setup-shaped payload."""
    return {
        "hypothesis": (st.session_state.get(_draft_key("hypothesis", state), "") or "").strip(),
        "source_market": {
            "locale": (st.session_state.get(_draft_key("source_locale", state), "") or "").strip(),
            "country": (st.session_state.get(_draft_key("source_country", state), "") or "").strip(),
        },
        "target_markets": [
            {"locale": m.get("locale", "").strip(), "country": m.get("country", "").strip()}
            for m in st.session_state.get(_draft_key("markets", state), [])
            if m.get("locale") or m.get("country")
        ],
        "product_context": {
            "application": (st.session_state.get(_draft_key("application", state), "") or "").strip(),
            "product_unit": (st.session_state.get(_draft_key("product_unit", state), "") or "").strip(),
            "feature": (st.session_state.get(_draft_key("feature", state), "") or "").strip(),
            "asset_type": (st.session_state.get(_draft_key("asset_type", state), "") or "").strip(),
            "use_case": (st.session_state.get(_draft_key("use_case", state), "") or "").strip(),
        },
        "variants": [
            {
                "id": (v.get("id", "") or "").strip(),
                "label": (v.get("label", "") or "").strip(),
                "path": (v.get("path", "") or "").strip(),
                "is_control": bool(v.get("is_control", False)),
            }
            for v in st.session_state.get(_draft_key("variants", state), [])
            if (v.get("id") or v.get("label") or v.get("path"))
        ],
        "panel_size_per_market": int(
            st.session_state.get(_draft_key("panel_size", state), 12) or 12
        ),
        "pass_criteria": {
            "min_top_variant_share": float(
                st.session_state.get(_draft_key("min_top_share", state), 0.65) or 0.65
            ),
            "max_cultural_red_flags": int(
                st.session_state.get(_draft_key("max_red_flags", state), 1) or 1
            ),
        },
    }


def _local_validate(payload: dict[str, Any]) -> list[str]:
    """Cheap checks done in Python before the orchestrator is called."""
    errors: list[str] = []

    if len(payload["hypothesis"]) < 15:
        errors.append("Hypothesis is too short (aim for at least one full sentence).")

    if not payload["source_market"]["locale"] or not payload["source_market"]["country"]:
        errors.append("Source market locale and country are both required.")

    if not payload["target_markets"]:
        errors.append("At least one target market is required.")

    seen_locales = set()
    for m in payload["target_markets"]:
        if not m["locale"] or not m["country"]:
            errors.append(f"Target market is missing locale or country: {m}")
        if m["locale"] in seen_locales:
            errors.append(f"Duplicate target market locale: {m['locale']}")
        seen_locales.add(m["locale"])

    pc = payload["product_context"]
    for field in ("application", "product_unit", "feature", "asset_type", "use_case"):
        if not pc.get(field):
            errors.append(f"Product context `{field}` is required.")

    if len(payload["variants"]) < 2:
        errors.append("At least two variants are required.")

    seen_ids = set()
    controls = 0
    for v in payload["variants"]:
        if not v["id"]:
            errors.append(f"Variant is missing an ID: {v}")
        elif v["id"] in seen_ids:
            errors.append(f"Duplicate variant ID: {v['id']}")
        seen_ids.add(v["id"])

        if not v["label"]:
            errors.append(f"Variant `{v.get('id','?')}` is missing a label.")
        if not v["path"]:
            errors.append(f"Variant `{v.get('id','?')}` is missing an image path.")
        else:
            full = S.REPO_ROOT / v["path"]
            if not full.exists():
                errors.append(f"Variant `{v['id']}` path not found: {v['path']}")
        if v["is_control"]:
            controls += 1

    if controls == 0:
        errors.append("Mark exactly one variant as Control.")
    elif controls > 1:
        errors.append(f"Only one variant may be Control; found {controls}.")

    return errors


def _handle_submit(state: S.State) -> None:
    payload = _collect_payload(state)

    # Shape-level validation via Pydantic first (gives clearer errors)
    try:
        S.Setup.model_validate(payload)
    except ValidationError as e:
        st.error("Setup payload failed schema validation:")
        for err in e.errors():
            loc = ".".join(str(x) for x in err["loc"])
            st.markdown(f"- `{loc}`: {err['msg']}")
        return

    # Local semantic checks
    local_errors = _local_validate(payload)
    if local_errors:
        st.error("Please resolve these before the orchestrator reviews:")
        for msg in local_errors:
            st.markdown(f"- {msg}")
        return

    # Call orchestrator for a confirmation bubble
    with st.spinner("Orchestrator reviewing your setup..."):
        try:
            summary = orchestrator.summarize_step(state, S.STEP_SETUP, payload)
        except Exception as e:  # noqa: BLE001
            st.error(f"Orchestrator call failed: {e}")
            return

    orchestrator.record_message(state, S.STEP_SETUP, summary)
    S.save(state)

    # Stash draft + move to review phase
    st.session_state[f"setup_draft_payload_{state.run_id}"] = payload
    st.session_state[f"setup_review_{state.run_id}"] = True
    st.rerun()


# ---------------------------------------------------------------------------
# Review phase
# ---------------------------------------------------------------------------


def _render_review(state: S.State) -> None:
    st.subheader("Orchestrator review")
    details = orchestrator.latest_message_for(state, S.STEP_SETUP)
    if details:
        chat.render_orchestrator_message(details)
    else:
        st.info("No orchestrator message yet — resubmit the form above.")
        return

    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button(
            "Proceed to Method",
            type="primary",
            use_container_width=True,
            key=f"setup_proceed_{state.run_id}",
        ):
            _proceed(state)
    with c2:
        if st.button(
            "Edit setup",
            use_container_width=True,
            key=f"setup_edit_{state.run_id}",
        ):
            st.session_state[f"setup_review_{state.run_id}"] = False
            st.rerun()


def _proceed(state: S.State) -> None:
    payload = st.session_state.get(f"setup_draft_payload_{state.run_id}")
    if payload is None:
        st.error("No setup draft in session — resubmit the form.")
        return

    was_complete = state.step_status.get(S.STEP_SETUP) == S.StepStatus.COMPLETE

    state.setup = S.Setup.model_validate(payload)
    S.mark_status(state, S.STEP_SETUP, S.StepStatus.COMPLETE)

    if was_complete:
        stale = S.mark_downstream_stale(state, S.STEP_SETUP)
        if stale:
            st.toast(f"Marked {len(stale)} downstream step(s) stale.")

    S.append_history(
        state,
        actor="pm",
        action="setup_confirmed",
        details={
            "target_markets": [m["locale"] for m in payload["target_markets"]],
            "variant_ids": [v["id"] for v in payload["variants"]],
        },
    )
    S.save(state)

    # Clear session flags and navigate
    st.session_state.pop(f"setup_review_{state.run_id}", None)
    st.session_state.pop(f"setup_draft_payload_{state.run_id}", None)
    st.session_state.current_step = S.STEP_METHOD
    st.rerun()
