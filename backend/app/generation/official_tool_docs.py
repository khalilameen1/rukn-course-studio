"""Official Tool Documentation Gate — current tools beat old courses/PDFs.

Silent influence only. Never leak docs URLs, citations, or research notes
into Teleprompter DOCX.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.generation.market_evergreen import _FRAGILE_UI, _BUTTON_CLICK_HEAVY
from app.generation.source_memory_store import normalize_gap_key
from app.schemas.generation import CourseMap, FinalCourse, FinalModule, FinalReel

# --- DOCX leak strings (must never appear in spoken export) -----------------
OFFICIAL_TOOL_DOCX_LEAKS: tuple[str, ...] = (
    "official docs",
    "official documentation",
    "according to official",
    "help center says",
    "changelog",
    "release notes",
    "tool_dependencies",
    "official tool memory",
    "official_tool_memory",
    "docs research need",
    "outdated workflow",
    "source conflict with docs",
    "according to meta ads help",
)

# Known current tools / platforms (aliases → canonical name).
_TOOL_ALIASES: dict[str, str] = {
    "meta ads": "Meta Ads",
    "facebook ads": "Meta Ads",
    "instagram ads": "Meta Ads",
    "fb ads": "Meta Ads",
    "google ads": "Google Ads",
    "adwords": "Google Ads",
    "tiktok ads": "TikTok Ads",
    "tik tok ads": "TikTok Ads",
    "canva": "Canva",
    "shopify": "Shopify",
    "woocommerce": "WooCommerce",
    "woo commerce": "WooCommerce",
    "wordpress": "WordPress",
    "wp ": "WordPress",
    "capcut": "CapCut",
    "cap cut": "CapCut",
    "notion": "Notion",
    "chatgpt": "ChatGPT",
    "chat gpt": "ChatGPT",
    "openai": "ChatGPT",
    "claude": "Claude",
    "anthropic": "Claude",
    "excel": "Microsoft Excel",
    "microsoft excel": "Microsoft Excel",
    "google sheets": "Google Sheets",
    "figma": "Figma",
    "hubspot": "HubSpot",
    "mailchimp": "Mailchimp",
    "stripe": "Stripe",
    "zapier": "Zapier",
    "make.com": "Make",
    "n8n": "n8n",
}

# Freshness for platform-current tool research (days).
TOOL_FRESHNESS_DAYS = 14


class ToolDependency(BaseModel):
    tool_name: str
    official_docs_needed: bool = True
    why_needed: str = ""
    affected_modules: list[str] = Field(default_factory=list)
    affected_lessons: list[str] = Field(default_factory=list)
    feature_area: str = "current workflow and features"


class OfficialDocsResearchNeed(BaseModel):
    tool_name: str
    feature_area: str
    why_needed: str
    course_id: int | None = None
    module_id: str | None = None
    lesson_id: str | None = None
    existing_source_conflict: str | None = None
    acceptable_source_types: list[str] = Field(
        default_factory=lambda: [
            "official_docs",
            "help_center",
            "changelog",
            "official_academy",
        ]
    )
    stop_condition: str = "relevant official-page summary for this feature area"


class OfficialToolMemoryEntry(BaseModel):
    tool_name: str
    feature_area: str = "general"
    official_urls: list[str] = Field(default_factory=list)
    docs_titles: list[str] = Field(default_factory=list)
    retrieved_at: str = ""
    relevant_current_behaviors: list[str] = Field(default_factory=list)
    changed_or_deprecated_behaviors: list[str] = Field(default_factory=list)
    current_terms: list[str] = Field(default_factory=list)
    evergreen_teaching_notes: list[str] = Field(default_factory=list)
    affected_course_ids: list[int] = Field(default_factory=list)
    freshness_policy: str = "platform_current"
    research_need_key: str = ""
    tokens_used: int = 0


class OfficialToolMemoryStore(BaseModel):
    """Persisted on Course.official_tool_memory_json (internal only)."""

    tool_dependencies: list[ToolDependency] = Field(default_factory=list)
    entries: list[OfficialToolMemoryEntry] = Field(default_factory=list)
    needs_logged: list[dict[str, Any]] = Field(default_factory=list)
    outdated_source_flags: list[dict[str, Any]] = Field(default_factory=list)
    authority_conflicts: list[dict[str, Any]] = Field(default_factory=list)

    def find(
        self, tool_name: str, feature_area: str = ""
    ) -> OfficialToolMemoryEntry | None:
        key = _need_key(tool_name, feature_area)
        for entry in self.entries:
            if entry.research_need_key == key:
                return entry
            if entry.tool_name.lower() == tool_name.lower() and (
                not feature_area
                or entry.feature_area.lower() == feature_area.lower()
                or feature_area.lower() in entry.feature_area.lower()
            ):
                return entry
        return None


def _need_key(tool_name: str, feature_area: str) -> str:
    return normalize_gap_key(f"{tool_name}|{feature_area or 'general'}")


def detect_tool_dependencies(
    *,
    title: str = "",
    audience: str = "",
    outcome: str = "",
    special_notes: str = "",
    course_domain: str = "",
    map_text: str = "",
    source_snippets: list[str] | None = None,
) -> list[ToolDependency]:
    """Detect current tools/platforms from brief, domain, map, sources."""
    parts = [
        title,
        audience,
        outcome,
        special_notes or "",
        course_domain or "",
        map_text or "",
        " ".join(source_snippets or []),
    ]
    blob = " ".join(parts).lower()
    # Normalize separators for alias matching.
    blob_norm = re.sub(r"[_/|+]+", " ", blob)
    found: dict[str, ToolDependency] = {}
    # Longer aliases first.
    for alias in sorted(_TOOL_ALIASES.keys(), key=len, reverse=True):
        canonical = _TOOL_ALIASES[alias]
        if alias in blob_norm or alias.replace(" ", "") in blob_norm.replace(" ", ""):
            if canonical not in found:
                found[canonical] = ToolDependency(
                    tool_name=canonical,
                    official_docs_needed=True,
                    why_needed=(
                        f"Course depends on {canonical}; official docs required "
                        "so outdated courses/PDFs do not define current tool behavior."
                    ),
                    feature_area=_infer_feature_area(canonical, blob_norm),
                )
    # Domain field alone (e.g. meta_ads).
    domain = (course_domain or "").strip().lower().replace("-", "_")
    if domain:
        domain_space = domain.replace("_", " ")
        for alias, canonical in _TOOL_ALIASES.items():
            if domain_space == alias or domain.replace("_", "") == alias.replace(" ", ""):
                if canonical not in found:
                    found[canonical] = ToolDependency(
                        tool_name=canonical,
                        official_docs_needed=True,
                        why_needed=f"course_domain={course_domain}",
                        feature_area=_infer_feature_area(canonical, blob_norm),
                    )
    return list(found.values())


def _infer_feature_area(tool: str, blob: str) -> str:
    if tool == "Meta Ads":
        if "campaign" in blob or "ad set" in blob or "creative" in blob:
            return "campaign structure and creation"
        return "ads manager current workflow"
    if tool in {"Google Ads", "TikTok Ads"}:
        return "campaign creation and objectives"
    if tool in {"Shopify", "WooCommerce", "WordPress"}:
        return "storefront / publishing workflow"
    if tool in {"Canva", "CapCut", "Figma"}:
        return "creation workflow and export"
    if tool in {"ChatGPT", "Claude"}:
        return "current product capabilities and limits"
    return "current workflow and features"


def annotate_dependencies_from_map(
    deps: list[ToolDependency], course_map: CourseMap
) -> list[ToolDependency]:
    """Fill affected_modules / lessons when map titles mention the tool."""
    out: list[ToolDependency] = []
    for dep in deps:
        name_l = dep.tool_name.lower()
        modules: list[str] = []
        lessons: list[str] = []
        for mod in course_map.modules:
            mod_blob = f"{mod.title} {mod.purpose}".lower()
            hit_mod = name_l in mod_blob or any(
                a in mod_blob for a, c in _TOOL_ALIASES.items() if c == dep.tool_name
            )
            lesson_hits: list[str] = []
            for reel in mod.reels:
                rblob = f"{reel.title} {reel.purpose} {' '.join(reel.must_cover)}".lower()
                if name_l in rblob or hit_mod:
                    lesson_hits.append(reel.reel_id)
            if hit_mod or lesson_hits:
                modules.append(mod.module_id)
                lessons.extend(lesson_hits)
        out.append(
            dep.model_copy(
                update={
                    "affected_modules": modules or dep.affected_modules,
                    "affected_lessons": lessons or dep.affected_lessons,
                }
            )
        )
    return out


def memory_is_fresh(entry: OfficialToolMemoryEntry) -> bool:
    if not entry.retrieved_at:
        return False
    try:
        retrieved = datetime.fromisoformat(entry.retrieved_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    age = datetime.now(timezone.utc) - retrieved
    return age.days <= TOOL_FRESHNESS_DAYS


def build_official_docs_need(
    dep: ToolDependency, *, course_id: int | None = None
) -> OfficialDocsResearchNeed:
    return OfficialDocsResearchNeed(
        tool_name=dep.tool_name,
        feature_area=dep.feature_area,
        why_needed=dep.why_needed,
        course_id=course_id,
        stop_condition=(
            f"Enough official current behavior for {dep.tool_name} "
            f"({dep.feature_area}) to avoid teaching outdated workflows"
        ),
    )


def should_reuse_tool_memory(
    store: OfficialToolMemoryStore, dep: ToolDependency
) -> tuple[bool, OfficialToolMemoryEntry | None, str]:
    entry = store.find(dep.tool_name, dep.feature_area)
    if entry is None:
        return False, None, "miss"
    if not memory_is_fresh(entry):
        return False, entry, "stale"
    if not entry.relevant_current_behaviors and not entry.evergreen_teaching_notes:
        return False, entry, "empty"
    return True, entry, "hit"


def entry_from_research_facts(
    *,
    dep: ToolDependency,
    titles: list[str],
    urls: list[str],
    summaries: list[str],
    course_id: int | None = None,
) -> OfficialToolMemoryEntry:
    behaviors = [s[:400] for s in summaries if s.strip()][:6]
    notes = [
        f"Teach {dep.tool_name} via goals and feature categories, not fragile UI positions.",
        "If UI moved, learner should verify in the official help center.",
        "Old courses/PDFs are not authority for current tool clicks.",
    ]
    deprecated: list[str] = []
    joined = " ".join(summaries).lower()
    if any(w in joined for w in ("deprecated", "retired", "no longer", "legacy", "automated")):
        deprecated.append(
            "Official materials mention retired/automated steps — do not teach obsolete manual workflows."
        )
    return OfficialToolMemoryEntry(
        tool_name=dep.tool_name,
        feature_area=dep.feature_area,
        official_urls=[u for u in urls if u][:8],
        docs_titles=[t for t in titles if t][:8],
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        relevant_current_behaviors=behaviors,
        changed_or_deprecated_behaviors=deprecated,
        current_terms=[dep.tool_name],
        evergreen_teaching_notes=notes,
        affected_course_ids=[course_id] if course_id else [],
        freshness_policy="platform_current",
        research_need_key=_need_key(dep.tool_name, dep.feature_area),
    )


def flag_outdated_old_course_overlap(
    *,
    source_texts: list[str],
    memory: OfficialToolMemoryStore,
) -> list[dict[str, Any]]:
    """Internal flags when old-course text teaches UI/clicks that conflict with memory."""
    flags: list[dict[str, Any]] = []
    if not memory.tool_dependencies:
        return flags
    for text in source_texts:
        if not text or len(text) < 40:
            continue
        if not (_FRAGILE_UI.search(text) or _BUTTON_CLICK_HEAVY.search(text)):
            continue
        lower = text.lower()
        hit_any = False
        for dep in memory.tool_dependencies:
            aliases = [dep.tool_name.lower()] + [
                a for a, c in _TOOL_ALIASES.items() if c == dep.tool_name
            ]
            if any(a in lower for a in aliases):
                hit_any = True
                flags.append(
                    {
                        "tool_name": dep.tool_name,
                        "reason": "old_source_fragile_ui",
                        "action": "prefer_official_docs_principles_only",
                    }
                )
        if not hit_any:
            # Course is tool-dependent and source teaches fragile UI — prefer docs.
            flags.append(
                {
                    "tool_name": memory.tool_dependencies[0].tool_name,
                    "reason": "old_source_fragile_ui",
                    "action": "prefer_official_docs_principles_only",
                }
            )
    return flags


def compile_official_tool_guidance(store: OfficialToolMemoryStore | None) -> str:
    """Runtime prompt pack — compact, no URLs in final teaching voice."""
    if store is None or (not store.tool_dependencies and not store.entries):
        return (
            "Official Tool Documentation Gate: if the course uses a current "
            "tool/platform, current official behavior beats old courses/PDFs/blogs. "
            "Teach the principle and decision before showing the current tool as one "
            "example; never make fragile button positions or temporary prices/stats a rule. "
            "Never put docs links, citations, or research notes in script_text."
        )
    lines = [
        "Official Tool Documentation Gate (silent — never DOCX):",
        "- Official current docs/help center beat old uploaded courses, books, and tutorials for tool behavior.",
        "- Extract principles from old sources only; rebuild outdated workflows from official current behavior.",
        "- Teach the durable principle and decision first; use the current tool/UI only as an example.",
        "- Prefer goals + feature categories + how to verify in help center over exact UI click paths.",
        "- Temporary prices, limits, dates, specifications, and stats are not permanent teaching rules.",
        "- Keep the capability evergreen if the UI changes or a better competing tool becomes appropriate.",
        "Tools in this course:",
    ]
    for dep in store.tool_dependencies:
        lines.append(f"- {dep.tool_name}: {dep.feature_area} ({dep.why_needed})")
    for entry in store.entries[:8]:
        if entry.relevant_current_behaviors:
            lines.append(
                f"  Current notes ({entry.tool_name}): "
                + "; ".join(entry.relevant_current_behaviors[:2])
            )
        if entry.changed_or_deprecated_behaviors:
            lines.append(
                f"  Avoid obsolete ({entry.tool_name}): "
                + "; ".join(entry.changed_or_deprecated_behaviors[:2])
            )
        for note in entry.evergreen_teaching_notes[:2]:
            lines.append(f"  Teach: {note}")
    lines.append("Never say 'according to official docs' or paste help URLs in the script.")
    return "\n".join(lines)


def map_official_tool_feedback(
    course_map: CourseMap, store: OfficialToolMemoryStore | None
) -> list[str]:
    """Local map review: drop/reframe fragile or obsolete tool-UI lessons."""
    if not store or not store.tool_dependencies:
        return []
    feedback: list[str] = []
    tool_names = {d.tool_name.lower() for d in store.tool_dependencies}
    for mod in course_map.modules:
        for reel in mod.reels:
            blob = (
                f"{mod.title} {mod.purpose} {reel.title} {reel.purpose} "
                f"{' '.join(reel.must_cover)}"
            )
            lower = blob.lower()
            if _FRAGILE_UI.search(blob) or _BUTTON_CLICK_HEAVY.search(blob):
                if any(t in lower for t in tool_names):
                    from app.generation.knowledge_priority_ladder import (
                        preserve_user_intent_correct_outdated_tool,
                    )

                    guidance, conflict = preserve_user_intent_correct_outdated_tool(
                        user_intent=reel.purpose or course_map.main_thread or "learner outcome",
                        outdated_detail=f"fragile UI path in lesson '{reel.title}'",
                        current_behavior_hint=(
                            "current official workflow principles for the tool"
                        ),
                    )
                    store.authority_conflicts = list(store.authority_conflicts or []) + [
                        conflict.model_dump(mode="json")
                    ]
                    feedback.append(
                        f"Rebuild lesson '{reel.title}': {guidance}"
                    )
            # Exact "legacy / old dashboard" teaching as permanent module.
            if re.search(r"\b(old dashboard|legacy ads manager|classic editor only)\b", blob, re.I):
                feedback.append(
                    f"Reframe or remove outdated tool lesson '{reel.title}' "
                    "— prefer current official workflow. Preserve user intent; "
                    "do not copy the outdated step."
                )
    if store.outdated_source_flags:
        feedback.append(
            "Uploaded old-course material conflicts with official tool docs for some UI steps — "
            "keep principles only; rebuild map lessons from current official behavior. "
            "Official docs win; never mention the conflict in DOCX."
        )
    return feedback


def lesson_official_tool_instructions(store: OfficialToolMemoryStore | None) -> list[str]:
    if not store or not store.tool_dependencies:
        return []
    return [
        "Use Official Tool Memory for current tool behavior; never copy outdated click paths from old courses.",
        "Teach what the learner is trying to achieve and which feature category to find — not top-left button folklore.",
        "Do not mention official docs, help centers, or research in the spoken script.",
    ]


def rewrite_script_official_tool(script: str) -> str:
    """Silent rewrite: strip docs leaks + soften fragile UI positions."""
    from app.generation.knowledge_priority_ladder import strip_conflict_notes_from_script

    text = script or ""
    for leak in OFFICIAL_TOOL_DOCX_LEAKS:
        text = re.sub(re.escape(leak), "", text, flags=re.IGNORECASE)
    text = re.sub(r"https?://\S+", "", text, flags=re.IGNORECASE)
    # Soften common fragile UI lines without inventing new product copy.
    replacements = [
        (
            re.compile(
                r"click\s+the\s+(blue|green|red|yellow)\s+button\s+(at\s+the\s+)?(top|bottom)\s*(left|right)?",
                re.I,
            ),
            "open the action from the campaign creation area",
        ),
        (
            re.compile(r"you\s+will\s+find\s+(it|the\s+button)\s+(at\s+the\s+)?top\s*left", re.I),
            "look for the create/new campaign control in the ads workspace",
        ),
        (
            re.compile(r"الزر\s+(الأزرق|الأخضر)\s+في\s+أعلى\s+(يسار|يمين)", re.I),
            "من منطقة إنشاء الحملة أو الإجراء الرئيسي في الأداة",
        ),
    ]
    for pattern, repl in replacements:
        text = pattern.sub(repl, text)
    text = strip_conflict_notes_from_script(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def apply_official_tool_to_final_course(final: FinalCourse) -> FinalCourse:
    modules: list[FinalModule] = []
    for mod in final.modules:
        reels: list[FinalReel] = []
        for reel in mod.reels:
            reels.append(
                reel.model_copy(
                    update={"script_text": rewrite_script_official_tool(reel.script_text)}
                )
            )
        modules.append(mod.model_copy(update={"reels": reels}))
    full = rewrite_script_official_tool(final.full_text)
    return final.model_copy(update={"modules": modules, "full_text": full})


def run_official_tool_docs_pass(
    *,
    title: str,
    audience: str,
    outcome: str,
    special_notes: str | None = None,
    course_domain: str | None = None,
    map_text: str = "",
    source_snippets: list[str] | None = None,
    source_texts_for_conflict: list[str] | None = None,
    cached: OfficialToolMemoryStore | dict | None = None,
    course_id: int | None = None,
    research_backend: Any | None = None,
    prefer_fake: bool = True,
    allow_fetch: bool = True,
) -> OfficialToolMemoryStore:
    """Detect tools, reuse memory, fetch focused official-docs needs only."""
    if isinstance(cached, OfficialToolMemoryStore):
        store = cached.model_copy(deep=True)
    else:
        from app.services.json_coerce import coerce_json_dict

        cached_dict = cached if isinstance(cached, dict) else coerce_json_dict(cached)
        if cached_dict:
            store = OfficialToolMemoryStore.model_validate(cached_dict)
        else:
            store = OfficialToolMemoryStore()

    deps = detect_tool_dependencies(
        title=title,
        audience=audience,
        outcome=outcome,
        special_notes=special_notes or "",
        course_domain=course_domain or "",
        map_text=map_text,
        source_snippets=source_snippets,
    )
    store.tool_dependencies = deps
    if not deps:
        return store

    store.outdated_source_flags = flag_outdated_old_course_overlap(
        source_texts=source_texts_for_conflict or source_snippets or [],
        memory=store,
    )
    from app.generation.knowledge_priority_ladder import (
        conflicts_from_outdated_tool_flags,
        conflicts_to_log_dicts,
    )

    store.authority_conflicts = conflicts_to_log_dicts(
        conflicts_from_outdated_tool_flags(store.outdated_source_flags)
    )

    backend = research_backend
    if backend is None and allow_fetch:
        from app.generation.web_research import get_research_backend

        backend = get_research_backend(prefer_fake=prefer_fake)

    for dep in deps:
        need = build_official_docs_need(dep, course_id=course_id)
        store.needs_logged.append(need.model_dump(mode="json"))
        reuse, entry, _reason = should_reuse_tool_memory(store, dep)
        if reuse and entry is not None:
            if course_id and course_id not in entry.affected_course_ids:
                entry.affected_course_ids = [*entry.affected_course_ids, course_id]
            continue
        if not allow_fetch or backend is None:
            # Seed minimal teaching notes without a network/docs fetch.
            store.entries.append(
                OfficialToolMemoryEntry(
                    tool_name=dep.tool_name,
                    feature_area=dep.feature_area,
                    retrieved_at=datetime.now(timezone.utc).isoformat(),
                    relevant_current_behaviors=[
                        f"Treat {dep.tool_name} as a living platform; verify current workflow in official help."
                    ],
                    evergreen_teaching_notes=[
                        "Teach objectives and feature categories, not pixel-perfect clicks.",
                    ],
                    affected_course_ids=[course_id] if course_id else [],
                    research_need_key=_need_key(dep.tool_name, dep.feature_area),
                )
            )
            continue
        query = (
            f"{dep.tool_name} official documentation {dep.feature_area} "
            f"current workflow help center"
        )
        facts = backend.fetch_facts(query, sensitive=True) or []
        # Prefer docs-like authority when present.
        titles = [f.title for f in facts]
        urls = [f.url for f in facts]
        summaries = [f.summary for f in facts]
        if not summaries:
            summaries = [
                f"Current {dep.tool_name} teaching should follow official help/docs. "
                "Prefer goals and settings categories over brittle UI geography."
            ]
        new_entry = entry_from_research_facts(
            dep=dep,
            titles=titles,
            urls=urls,
            summaries=summaries,
            course_id=course_id,
        )
        # Replace same key if stale.
        store.entries = [
            e
            for e in store.entries
            if e.research_need_key != new_entry.research_need_key
        ]
        store.entries.append(new_entry)

    return store


def tool_memory_excerpts(store: OfficialToolMemoryStore) -> list[tuple[str, str]]:
    """Compact (title, summary) pairs for prompt compiler — fenced as untrusted facts."""
    out: list[tuple[str, str]] = []
    for entry in store.entries:
        body = " ".join(entry.relevant_current_behaviors[:3])
        if entry.changed_or_deprecated_behaviors:
            body += " Avoid: " + " ".join(entry.changed_or_deprecated_behaviors[:2])
        if body.strip():
            out.append((f"Tool memory: {entry.tool_name}", body[:900]))
    return out
