import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

import extra_streamlit_components as stx
import streamlit as st

from app.analyzers.gap_detector import detect_gaps
from app.analyzers.spending import analyze_spending
from app.collectors.reddit import RedditCollector
from app.collectors.web import WebCollector
from app.collectors.youtube import YouTubeCollector
from app.collectors.marketplaces import MarketplaceCollector
from app.config import BASE_DIR, MAX_ITEMS_PER_SOURCE, REPORT_DIR
from app.backup import create_project_backup
from app.database.db import ReportStore
from app.database.models import Report
from app.pdf.generator import generate_pdf
from app.product.architect import architect_opportunities
from app.product.launch_suite import build_blueprint, build_launch_kit
from app.processors.cleaner import normalize_evidence
from app.processors.problem_miner import mine_problems
from app.processors.objection_framework import build_objection_matrix
from app.search_utils import normalize_query


QUICK_TOPICS = {"Meal Prep": "meal prep", "SaaS Ideas": "SaaS ideas", "Parenting": "parenting"}
AUTH_COOKIE = "dpe_auth_session"


def _set_example(topic: str) -> None:
    st.session_state["topic_input"] = topic


def _restore_cookie_session(store: ReportStore, cookies: stx.CookieManager) -> None:
    if st.session_state.get("auth_user"):
        return
    token = cookies.get(AUTH_COOKIE)
    if token:
        user = store.authenticate_session(token)
        if user:
            st.session_state["auth_user"] = user
            st.session_state["session_token"] = token


def _render_auth(store: ReportStore, cookies: stx.CookieManager) -> str | None:
    if st.session_state.get("auth_user"):
        user = st.session_state["auth_user"]
        st.sidebar.subheader("Account")
        st.sidebar.success(f"Signed in as **{user['username']}**")
        if st.sidebar.button("Log out", key="logout_button"):
            token = st.session_state.get("session_token", "")
            store.revoke_session(token)
            cookies.delete(AUTH_COOKIE, key="delete_auth_cookie")
            st.session_state.pop("auth_user", None)
            st.session_state.pop("session_token", None)
            st.session_state.pop("report", None)
            st.session_state.pop("pdf_path", None)
            st.rerun()
        return user["user_id"]

    st.subheader("Welcome — sign in to begin")
    st.caption("Your scans are stored locally and kept private to your account.")
    login_tab, register_tab = st.tabs(["Log in", "Register"])
    with login_tab:
        with st.form("main_login_form"):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Log in")
        if submitted:
            user = store.authenticate(username, password)
            if user:
                token = store.create_session(user["user_id"], days=30)
                cookies.set(AUTH_COOKIE, token, key="set_auth_cookie", expires_at=datetime.now(timezone.utc) + timedelta(days=30), max_age=30 * 24 * 60 * 60, path="/", secure=True, same_site="lax")
                st.session_state["auth_user"] = user
                st.session_state["session_token"] = token
                st.rerun()
            st.error("Invalid username or password.")
    with register_tab:
        with st.form("main_register_form"):
            new_username = st.text_input("New username", key="register_username")
            new_password = st.text_input("Password (8+ characters)", type="password", key="register_password")
            confirm_password = st.text_input("Confirm password", type="password", key="register_confirm")
            registered = st.form_submit_button("Create account")
        if registered:
            if new_password != confirm_password:
                st.error("Passwords do not match.")
            else:
                ok, message = store.register_user(new_username, new_password)
                (st.success if ok else st.error)(message)
    st.info("Log in or create a free local account to run scans and access private history.")
    return None


def run_engine(topic: str, sources: list[str], limit: int) -> Report:
    topic = normalize_query(topic)
    collectors = {"Reddit": RedditCollector(), "YouTube": YouTubeCollector(), "Web": WebCollector()}
    evidence, notes = [], []
    with ThreadPoolExecutor(max_workers=len(sources) + 1) as pool:
        futures = {pool.submit(collectors[s].collect, topic, limit): s for s in sources}
        marketplace_future = pool.submit(MarketplaceCollector().collect, topic, min(limit, 10))
        for future in as_completed(futures):
            source = futures[future]
            try:
                evidence.extend(future.result())
            except Exception as exc:
                notes.append(f"{source} failed: {exc}")
        try:
            marketplace_gaps = marketplace_future.result()
        except Exception as exc:
            marketplace_gaps = []
            notes.append(f"Marketplace collection failed: {exc}")
    evidence = normalize_evidence(evidence)
    problems = mine_problems(evidence)
    objection_matrix = build_objection_matrix(problems)
    spending = analyze_spending(evidence)
    gaps = detect_gaps(evidence)
    opportunities = architect_opportunities(topic, problems, spending, gaps, len(evidence))
    top_opportunity = opportunities[0] if opportunities else None
    top_problem = problems[0] if problems else None
    product_blueprint = build_blueprint(topic, top_opportunity, top_problem) if top_opportunity else {}
    launch_kit = build_launch_kit(topic, top_opportunity, top_problem, marketplace_gaps) if top_opportunity else {}
    best = opportunities[0].validation_score if opportunities else 0
    summary = f"The scan found {len(evidence)} normalized evidence items and {len(problems)} recurring problem signals across {', '.join(sources)}. The strongest concept scored {best}/100. Treat this as a ranked hypothesis set: public web evidence can reveal language and friction, but interviews, a paid pilot, or a pre-sale are still required to confirm demand and pricing."
    sales_hooks = [opportunity.value_hook for opportunity in opportunities if opportunity.value_hook]
    return Report(id=uuid.uuid4().hex, topic=topic, evidence=evidence, problems=problems, opportunities=opportunities, objection_matrix=objection_matrix, sales_hooks=sales_hooks, marketplace_gaps=marketplace_gaps, product_blueprint=product_blueprint, launch_kit=launch_kit, executive_summary=summary, collection_notes=notes + [spending["interpretation"], f"Gap signals: {len(gaps['gaps'])}"])


def _render_source_links(report: Report) -> None:
    sources = sorted({item.source for item in report.evidence})
    for source in sources:
        with st.expander(f"{source} source links ({sum(item.source == source for item in report.evidence)})"):
            for item in [item for item in report.evidence if item.source == source]:
                label = item.title or item.url or "Open source"
                st.markdown(f"- [{label}]({item.url})" if item.url else f"- {label}")


def _load_history_report(report: Report) -> None:
    pdf_path = REPORT_DIR / f"opportunity-report-{report.id}.pdf"
    if not pdf_path.exists():
        generate_pdf(report, pdf_path)
    st.session_state["report"] = report
    st.session_state["pdf_path"] = str(pdf_path)


def _render_history(store: ReportStore, user_id: str) -> None:
    st.sidebar.subheader("Past Opportunity Scans")
    history = store.recent(user_id=user_id, limit=12)
    if not history:
        st.sidebar.caption("Your completed scans will appear here.")
        return
    for saved_report in history:
        timestamp = saved_report.created_at.strftime("%Y-%m-%d %H:%M")
        label = saved_report.topic[:42] + ("…" if len(saved_report.topic) > 42 else "")
        if st.sidebar.button(label, key=f"history_{saved_report.id}", help=f"Load scan from {timestamp}"):
            _load_history_report(saved_report)
        st.sidebar.caption(f"{timestamp} · {len(saved_report.problems)} problem signals")


def render():
    st.set_page_config(page_title="Opportunity Engine", page_icon="◎", layout="centered")
    st.markdown("<style>.block-container{max-width:900px;padding-top:2rem}.stButton>button{width:100%;border-radius:10px;background:#123B5D;color:white;padding:.7rem}.metric-card{padding:1rem;border:1px solid #d9e3e8;border-radius:12px}</style>", unsafe_allow_html=True)
    st.title("Global Digital Product Opportunity Engine")
    st.caption("Turn a niche, topic, or customer problem into a ranked, evidence-backed digital product system scan.")
    store = ReportStore()
    cookies = stx.CookieManager(key="auth_cookie_manager")
    _restore_cookie_session(store, cookies)
    user_id = _render_auth(store, cookies)
    if not user_id:
        st.warning("Please log in to use the opportunity engine.")
        return
    _render_history(store, user_id)
    backup_bytes = create_project_backup(BASE_DIR)
    st.sidebar.download_button("Download full project backup (.zip)", data=backup_bytes, file_name="digital-product-engine-backup.zip", mime="application/zip", key="full_project_backup")

    st.text_input("Niche, topic, or problem statement", placeholder="e.g., onboarding systems for independent consultants", key="topic_input")
    st.caption("Quick examples")
    example_cols = st.columns(len(QUICK_TOPICS))
    for column, (label, value) in zip(example_cols, QUICK_TOPICS.items()):
        with column:
            st.button(label, key=f"quick_{label.lower().replace(' ', '_')}", on_click=_set_example, args=(value,))

    with st.form("research_form"):
        sources = st.multiselect("Public sources", ["Reddit", "YouTube", "Web"], default=["Reddit", "YouTube", "Web"])
        limit = st.slider("Maximum items per source", 5, MAX_ITEMS_PER_SOURCE, min(15, MAX_ITEMS_PER_SOURCE))
        submitted = st.form_submit_button("Run opportunity scan")
    if submitted:
        topic = st.session_state.get("topic_input", "").strip()
        if not topic:
            st.error("Enter a niche or problem statement first.")
            return
        if not sources:
            st.error("Choose at least one source.")
            return
        with st.status("Collecting and analyzing public evidence…", expanded=True) as status:
            st.write("Fetching problem-focused source results in parallel.")
            report = run_engine(topic, sources, limit)
            report.user_id = user_id
            st.write(f"Normalized {len(report.evidence)} evidence items.")
            st.write(f"Mined {len(report.problems)} recurring problem signals.")
            status.update(label="Opportunity scan complete", state="complete")
        store.save(report, user_id=user_id)
        pdf_path = REPORT_DIR / f"opportunity-report-{report.id}.pdf"
        generate_pdf(report, pdf_path)
        st.session_state["report"] = report
        st.session_state["pdf_path"] = str(pdf_path)

    report = st.session_state.get("report")
    if report:
        st.divider()
        top_score = report.opportunities[0].validation_score if report.opportunities else 0
        metrics = st.columns(3)
        metrics[0].metric("Evidence Items", len(report.evidence))
        metrics[1].metric("Problem Signals", len(report.problems))
        metrics[2].metric("Top Score", f"{top_score}/100")
        if not report.problems:
            st.warning("No explicit customer pain points were found for this query. Try a more specific topic or include a customer segment, workflow, or frustration.")
        st.subheader("Executive summary")
        st.info(report.executive_summary)
        st.subheader("Top opportunities")
        for opportunity in report.opportunities[:5]:
            with st.expander(f"{opportunity.name} · {opportunity.validation_score}/100"):
                st.write(opportunity.promise)
                st.write(f"**Audience:** {opportunity.audience}")
                st.write(f"**Formats:** {', '.join(opportunity.format)}")
                st.write(f"**Pricing hypothesis:** {opportunity.pricing['starter']} starter · {opportunity.pricing['core']} core · {opportunity.pricing['premium']} premium")
                st.write(f"**Value hook:** {opportunity.value_hook}")
                st.write(f"**Objection bucket:** {opportunity.objection_bucket}")
                st.write(f"**Pricing rationale:** {opportunity.pricing_rationale}")
                st.write("**Next steps:** " + "; ".join(opportunity.next_steps))
        st.subheader("Objection Matrix")
        matrix_cols = st.columns(3)
        for column, (bucket, problems) in zip(matrix_cols, report.objection_matrix.items()):
            with column:
                st.markdown(f"**{bucket}**")
                for problem in problems:
                    st.write(f"- {problem}")
                if not problems:
                    st.caption("No explicit signals")
        st.subheader("Hormozi Sales Hooks")
        for hook in report.sales_hooks:
            st.info(hook)
        st.subheader("Marketplace Gap Table")
        if report.marketplace_gaps:
            st.dataframe([{"Marketplace": gap.marketplace, "Product": gap.title, "Price": gap.price, "Format": gap.format, "Rating": gap.rating, "Gap signal": gap.gap_signal, "URL": gap.url} for gap in report.marketplace_gaps], use_container_width=True, hide_index=True)
            with st.expander("Marketplace review insights"):
                for gap in report.marketplace_gaps:
                    st.markdown(f"**{gap.marketplace}: {gap.title}**")
                    for insight in gap.review_insights:
                        st.write(f"- {insight}")
        else:
            st.info("No public Etsy or Gumroad marketplace results were available. The blueprint below is based on customer pain evidence only.")
        st.subheader("Day-1 Deliverable Blueprint")
        blueprint = report.product_blueprint
        if blueprint:
            st.write(f"**Product:** {blueprint.get('product_name', 'Top opportunity')}")
            st.write(f"**Promise:** {blueprint.get('one_sentence_promise', '')}")
            for module in blueprint.get("modules", []):
                with st.expander(module.get("name", "Module")):
                    for page in module.get("pages", []):
                        st.write(f"- {page}")
            st.write("**Bonuses:** " + "; ".join(blueprint.get("bonuses", [])))
            st.write("**Build order:** " + " → ".join(blueprint.get("day_one_build_order", [])))
        else:
            st.info("A product blueprint will appear when at least one explicit opportunity is found.")
        st.subheader("Launch & Marketing Kit")
        kit = report.launch_kit
        if kit:
            st.markdown("**Listing description**")
            st.write(kit.get("listing_description", ""))
            st.markdown("**SEO tags**")
            st.write(", ".join(kit.get("seo_tags", [])))
            st.markdown("**Short-form video hooks**")
            for hook in kit.get("short_form_hooks", []):
                st.info(hook)
            st.markdown("**ROI justification**")
            st.write(kit.get("roi_justification", ""))
        else:
            st.info("The launch kit will appear when at least one explicit opportunity is found.")
        st.subheader("Raw source links")
        _render_source_links(report)
        with st.expander("Collection notes"):
            for note in report.collection_notes:
                st.write(note)
        st.subheader("Download report")
        with open(st.session_state["pdf_path"], "rb") as handle:
            st.download_button("Download styled PDF report", handle, file_name=Path(st.session_state["pdf_path"]).name, mime="application/pdf")


if __name__ == "__main__":
    render()
