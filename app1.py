import base64
import hashlib
import json
import os
from html import escape
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from backend import GameAIClient

load_dotenv(Path(__file__).with_name(".env"), override=True)
st.set_page_config(page_title="Indie Game Studio Pro", layout="wide")
st.markdown("""
<style>
.stApp { background-color: #0f172a; color: #f8fafc; }
.card { background: #1e293b; border: 1px solid #475569; border-radius: 12px;
        padding: 20px; min-height: 170px; margin-bottom: 12px; }
.card h3 { color: #38bdf8; }
</style>
""", unsafe_allow_html=True)

DEFAULTS = {
    "view": "home", "selected_item": None, "selected_cat": None,
    "proposals": None, "visible_items": {}, "hidden_items": {},
    "generated_media": {}, "wiki_genre": None, "wiki_data": None,
    "wiki_result": None, "pdfs": {},
}
for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

credentials = (os.getenv("GOOGLE_API_KEY", ""), os.getenv("HF_TOKEN", ""))
if st.session_state.get("credentials") != credentials:
    st.session_state.game_client = GameAIClient(*credentials)
    st.session_state.credentials = credentials
client = st.session_state.game_client


def run_task(message, function, *args, **kwargs):
    """Show API failures in place while preserving the current page."""
    try:
        with st.spinner(message):
            return function(*args, **kwargs)
    except Exception as exc:
        st.error(f"Operation failed: {exc}")
        return None


def go_home():
    st.session_state.view = "home"
    st.rerun()


def show_item(item, category, view="modal"):
    st.session_state.selected_item = item
    st.session_state.selected_cat = category
    st.session_state.view = view
    st.rerun()


def save_proposals(data):
    st.session_state.proposals = data
    for category, key, count in (("achievable", "achievable_genres", 3), ("demos", "demo_ideas", 2)):
        items = data[key]
        st.session_state.visible_items[category] = items[:count]
        st.session_state.hidden_items[category] = items[count:]
    go_home()


def constraints(max_team=20, max_months=24, max_budget=10000, prefix="sidebar"):
    story = st.text_area("Story Idea", "A cyberpunk detective solving crimes in dreams...", key=f"{prefix}_story")
    left, right = st.columns(2)
    team = left.number_input("Team Size", 1, max_team, 3, key=f"{prefix}_team")
    months = right.number_input("Months", 1, max_months, 6, key=f"{prefix}_months")
    budget = st.slider("Budget ($)", 0, max_budget, 1000, key=f"{prefix}_budget")
    return story, team, months, budget


def render_sidebar():
    with st.sidebar:
        st.title("Project Lab")
        if not client.api_key:
            st.warning("Add GOOGLE_API_KEY to .env, save it and rerun the page to enable AI analysis.")
        values = constraints()
        if st.button("Analyze & Generate", type="primary", disabled=not client.api_key, use_container_width=True):
            data = run_task("Analyzing feasibility and generating proposals...", client.generate_proposal, *values)
            if data is not None:
                save_proposals(data)


def render_home():
    st.title("Indie Game Studio Pro")
    st.write("Your AI co-founder for game development. Explore genres or generate a proposal in the sidebar.")
    st.subheader("Genres Explorer")
    genres = ["Roguelike", "Metroidvania", "Cyberpunk RPG", "Visual Novel", "Hypercasual",
              "Turn-based Strategy", "Survival Horror", "Platformer", "Deckbuilder",
              "Idle Clicker", "Tower Defense", "Puzzle", "FPS", "MOBA"]
    columns = st.columns(4)
    for index, genre in enumerate(genres):
        if columns[index % 4].button(genre, key=f"genre_{index}", disabled=not client.api_key, use_container_width=True):
            info = run_task(f"Fetching {genre}...", client.get_genre_wiki_info, genre)
            if info is not None:
                st.session_state.wiki_genre = genre
                st.session_state.wiki_data = info
                st.session_state.wiki_result = None
                st.session_state.view = "wiki"
                st.rerun()
    if st.session_state.proposals is None:
        st.info("Enter your constraints and select Analyze & Generate to start.")
        return
    for category, heading, count in (("achievable", "Achievable Game Genres", 3), ("demos", "Recommended Prototypes", 2)):
        st.subheader(heading)
        columns = st.columns(count)
        items = st.session_state.visible_items.get(category, [])
        if not items:
            st.info("No proposals available in this category. Try adjusting your constraints.")
        for index, item in enumerate(items):
            with columns[index % count]:
                st.markdown(f"<div class='card'><h3>{escape(item['name'])}</h3><p>{escape(item['reason'][:160])}</p></div>", unsafe_allow_html=True)
                if st.button(f"Analyze {item['name']}", key=f"{category}_{index}"):
                    show_item(item, category)


def render_modal():
    item = st.session_state.selected_item
    st.title(f"Evaluate Strategy: {item['name']}")
    st.write(item["reason"])
    st.write(f"Estimated development cycle: {item.get('cycle', 'N/A')}")
    left, right = st.columns(2)
    if left.button("Not Interested (Hide & Swap)", use_container_width=True):
        category = st.session_state.selected_cat
        visible = st.session_state.visible_items[category]
        visible.remove(item)
        hidden = st.session_state.hidden_items.get(category, [])
        if hidden:
            visible.append(hidden.pop(0))
        go_home()
    if right.button("Interested (Deep Dive)", type="primary", use_container_width=True):
        st.session_state.view = "detail"
        st.rerun()
    if st.button("Back to Dashboard"):
        go_home()


def render_detail():
    item = st.session_state.selected_item
    details = item["details"]
    if st.button("Back to Dashboard"):
        go_home()
    st.title(f"Design Blueprint: {item['name']}")
    cache_key = hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()
    media = st.session_state.generated_media.setdefault(cache_key, {})
    left, right = st.columns([1, 1.5])
    with left:
        if media.get("image"):
            st.image(base64.b64decode(media["image"]), use_container_width=True)
        if not client.hf_token:
            st.info("Configure HF_TOKEN to enable cover art generation.")
        if st.button("Generate / Regenerate Cover Art", disabled=not client.hf_token):
            prompt = item.get("visual_prompt") or f"Game cover art: {item['name']}, {details.get('release_blurb', '')}"
            image = run_task("Generating cover art...", client.generate_image, prompt)
            if image:
                media["image"] = image
                st.rerun()
        st.subheader("Soundtrack Preview")
        if os.getenv("MUSIC_BACKEND", "hf").lower() == "hf":
            st.caption("AI soundtrack generated by your remote MusicGen endpoint.")
            if not client.hf_token or not os.getenv("HF_MUSIC_ENDPOINT"):
                st.info("Configure HF_TOKEN and HF_MUSIC_ENDPOINT to generate music.")
        else:
            st.caption("Local MusicGen. The first run downloads model weights.")
        if media.get("audio"):
            st.audio(base64.b64decode(media["audio"]), format="audio/wav")
        music_ready = (
            os.getenv("MUSIC_BACKEND", "hf").lower() != "hf"
            or bool(client.hf_token and os.getenv("HF_MUSIC_ENDPOINT"))
        )
        if st.button("Generate Soundtrack", disabled=not music_ready):
            def compose():
                return client.generate_audio(client.compose_music_prompt(item))
            audio = run_task("Composing soundtrack...", compose)
            if audio:
                media["audio"] = audio
                st.rerun()
    with right:
        st.subheader("Narrative & Gameplay")
        for key, label in (("release_blurb", "One-Liner"), ("optimized_outline", "Design Outline"),
                           ("protagonist", "Protagonist"), ("storyline", "Story Arc"), ("core_loop", "Core Loop")):
            st.markdown(f"**{label}**")
            st.write(details.get(key, "N/A"))
        prediction = details.get("full_game_prediction") or {}
        if prediction:
            st.subheader("Full Game Projection")
            st.write(f"Cycle: {prediction.get('cycle', 'N/A')}")
            st.write(f"Budget: {prediction.get('budget', 'N/A')}")
        for ref in item.get("classic_references", []):
            url = ref.get("url", "")
            if isinstance(url, str) and url.startswith(("https://", "http://")):
                st.link_button(str(ref.get("title", "Reference")), url)
    st.divider()
    ai_design = st.checkbox("Use AI HTML layout for PDF")
    pdf_key = f"{cache_key}_{ai_design}_{hashlib.sha256(media.get('image', '').encode()).hexdigest()}"
    if st.button("Export Professional GDD (PDF)", type="primary"):
        pdf = run_task("Compiling PDF report...", client.export_pdf, item, media.get("image"), use_ai_design=ai_design)
        if pdf:
            st.session_state.pdfs[pdf_key] = pdf
    if pdf_key in st.session_state.pdfs:
        st.download_button("Download PDF", data=st.session_state.pdfs[pdf_key], file_name="Game_Design_Document.pdf", mime="application/pdf")


def render_genre_wiki():
    genre = st.session_state.wiki_genre
    info = st.session_state.wiki_data
    if st.button("Back to Home"):
        go_home()
    st.title(f"{genre}")
    st.write(info["summary"])
    st.write(" ".join(info["tags"]))
    st.subheader(f"Build a {genre} Project")
    with st.form("wiki_feasibility"):
        values = constraints(50, 36, 100000, "wiki")
        submitted = st.form_submit_button("Analyze Feasibility", disabled=not client.api_key)
    if submitted:
        result = run_task("Analyzing production feasibility...", client.evaluate_specific_genre, genre, *values)
        if result is not None:
            st.session_state.wiki_result = {"result": result, "constraints": values}
    saved = st.session_state.wiki_result
    if not saved:
        return
    result = saved["result"]
    if result["status"] in ("feasible_game", "feasible_demo"):
        st.success("Full game feasible." if result["status"] == "feasible_game" else "A vertical slice is recommended.")
        st.write(result.get("reason", ""))
        if st.button("Open Design Blueprint"):
            show_item(result["data"], "wiki_generated", "detail")
    else:
        st.warning(result.get("reason", "This genre is not feasible with these constraints."))
        if st.button("Auto-Recommend Suitable Genres"):
            data = run_task("Finding suitable genres...", client.generate_proposal, *saved["constraints"])
            if data is not None:
                save_proposals(data)


render_sidebar()
views = {"home": render_home, "modal": render_modal, "detail": render_detail, "wiki": render_genre_wiki}
views.get(st.session_state.view, render_home)()
