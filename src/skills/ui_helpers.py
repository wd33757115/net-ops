# SPDX-FileCopyrightText: 2026 wangdong <wangdong5919@163.com>
# SPDX-License-Identifier: Apache-2.0

"""
Skill UI Helpers - Minimal Grok-style components
"""
from typing import Any

import streamlit as st


def render_skill_card_minimal(
    skill_name: str,
    description: str,
    category: str,
    tags: list[str],
    enabled: bool,
):
    """Render a minimal, Grok-style skill card using HTML/CSS"""
    status_color = "#155724" if enabled else "#721c24"
    status_bg = "#d4edda" if enabled else "#f8d7da"
    status_label = "active" if enabled else "inactive"
    tags_html = " · ".join(tags[:4]) if tags else ""

    st.markdown(f"""
    <div class="skill-card">
    <div style="display:flex;align-items:center;justify-content:space-between;">
    <div>
    <span style="font-weight:600;font-size:15px;">{skill_name}</span>
    <span style="margin-left:10px;font-size:11px;color:{status_color};background:{status_bg};padding:2px 8px;border-radius:10px;">
    {status_label}
    </span>
    </div>
    <span style="font-size:11px;color:#6c757d;">{category}</span>
    </div>
    <p style="color:#6c757d;font-size:13px;margin:8px 0 4px 0;">{description[:120]}</p>
    <div style="font-size:11px;color:#adb5bd;">{tags_html}</div>
    </div>
    """, unsafe_allow_html=True)


def render_skill_list_item(skill: dict[str, Any], manager):
    """Render a single skill list item with actions"""
    enabled = skill.get("enabled", True)

    render_skill_card_minimal(
        skill_name=skill["name"],
        description=skill.get("description", ""),
        category=skill.get("category", ""),
        tags=skill.get("tags", []),
        enabled=enabled,
    )

    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1:
        st.caption(f"v{skill.get('version', '1.0')}")
    with c2:
        new_state = st.toggle("Active", enabled, key=f"tog_{skill['name']}", label_visibility="visible")
        if new_state != enabled:
            manager.toggle_skill(skill['name'], new_state)
            st.rerun()
    with c3:
        if st.button("View", key=f"vw_{skill['name']}", use_container_width=True):
            content = manager.get_skill_content(skill['name'])
            if content:
                with st.expander(skill['name'], expanded=True):
                    st.code(content, language="markdown")
    with c4:
        if st.button("Reload", key=f"rl_{skill['name']}", use_container_width=True):
            manager.reload_skill(skill['name'])
            st.toast(f"Reloaded {skill['name']}")
            st.rerun()


def render_skill_form_basic(prefix=""):
    """Render basic skill info fields"""
    col_a, col_b = st.columns(2)
    with col_a:
        name = st.text_input("Name *", placeholder="my-skill", key=f"{prefix}name")
        category = st.selectbox("Category", ["network", "security", "compute", "storage", "monitoring", "general"], key=f"{prefix}cat")
    with col_b:
        description = st.text_area("Description *", placeholder="What does this skill do?", key=f"{prefix}desc")
        version = st.text_input("Version", "1.0.0", key=f"{prefix}ver")
    triggers_raw = st.text_area("Triggers (one per line)", placeholder="Execute backup\nConfig backup", key=f"{prefix}trig")
    tags_raw = st.text_input("Tags (comma-separated)", placeholder="network, backup", key=f"{prefix}tags")

    triggers = [t.strip() for t in triggers_raw.split("\n") if t.strip()] if triggers_raw else []
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

    return {"name": name, "description": description, "category": category, "version": version, "triggers": triggers, "tags": tags}


def render_skill_stats(stats: dict[str, Any]):
    c1, c2, c3 = st.columns(3)
    c1.metric("Total", stats.get("total_skills", 0))
    c2.metric("Active", stats.get("enabled_skills", 0))
    c3.metric("Categories", len(stats.get("categories", {})))
