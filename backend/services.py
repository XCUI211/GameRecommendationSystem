import os
import json
import base64
import io
from backend.pdf_generator import create_manual_pdf, convert_html_to_pdf, get_fallback_html
from huggingface_hub import InferenceClient
from backend.text_to_music import generate_local_music

from google import genai


class GameAIClient:
    """
    Handles interactions with AI models (Gemini, Hugging Face)
    and orchestrates data flow.
    """
    def __init__(self, api_key=None, hf_token=None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY", "")
        self.hf_token = hf_token or os.getenv("HF_TOKEN", "")
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.client = (
            genai.Client(api_key=self.api_key, http_options={"timeout": 120_000})
            if self.api_key else None
        )

    def _generate_json(self, prompt, model=None, config=None):
        if self.client is None:
            raise ValueError("Configure GOOGLE_API_KEY in .env before using AI analysis.")
        response = self.client.models.generate_content(
            model=model or self.model,
            contents=prompt,
            config={"response_mime_type": "application/json", **(config or {})},
        )
        result = json.loads(response.text or "")
        if not isinstance(result, dict):
            raise ValueError("AI returned an invalid JSON object. Please retry.")
        return result

    @staticmethod
    def _validate_item(item):
        if not isinstance(item, dict):
            raise ValueError("AI returned an invalid proposal.")
        for key in ("name", "reason"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError(f"AI proposal is missing {key}. Please retry.")
        details = item.get("details")
        if not isinstance(details, dict):
            raise ValueError("AI proposal is missing design details. Please retry.")
        for key in ("optimized_outline", "protagonist", "storyline", "release_blurb", "core_loop"):
            if not isinstance(details.get(key), str):
                raise ValueError(f"AI proposal has invalid {key}. Please retry.")
        prediction = details.get("full_game_prediction")
        if prediction is not None and not isinstance(prediction, dict):
            raise ValueError("AI proposal has invalid full-game predictions.")
        refs = item.get("classic_references", [])
        if not isinstance(refs, list) or any(not isinstance(ref, dict) for ref in refs):
            raise ValueError("AI proposal has invalid game references.")
        return item

    def generate_proposal(self, story, team_size, duration, budget):
        """
        Interacts with Gemini to generate game design proposals.
        Returns detailed JSON with both Achievable concepts and Demo ideas.
        """
        prompt = f"""
        Act as a Senior Executive Game Producer and Architect. Analyze these constraints:
        Story Idea: {story}
        Team: {team_size} people | Duration: {duration} months | Initial Budget: ${budget}

        Task:
        1. "Achievable Genres": Identify 5 genres that can result in a HIGH-QUALITY FULL GAME within these STRICT constraints.
           - Focus: Commercial viability and immediate development.
           - Detail: The 'optimized_outline' and 'reason' must be at least 4 high-density sentences.

        2. "Demo Prototypes": Identify 4 vertical slice/prototype ideas to prove the core mechanic in {duration} months.
           - Focus: Technical feasibility and "fun factor" verification.
           - Logic: These are small-scale tests. If expanded to a full game later, the budget MUST BE REASONABLE.

        STRICT BUDGET & CONTENT RULES:
        - For ANY 'full_game_prediction', the budget MUST be at least 5 to 10 times the initial budget (e.g., if initial is $10k, full game must be $100k+).
        - NEVER suggest a full game budget lower than the initial input.
        - Descriptions must be professional, technical, and exhaustive.

        Return ONLY raw JSON (NO MARKDOWN) with this structure:
        {{
            "achievable_genres": [
                {{
                    "name": "Genre Name",
                    "reason": "Extensive competitive analysis and fit explanation (4+ sentences)...",
                    "cycle": "{duration} months (Full Release)",
                    "visual_prompt": "Cinematic English prompt for AAA concept art",
                    "classic_references": [{{"title": "Game Name", "url": "URL"}}],
                    "details": {{
                        "optimized_outline": "Exhaustive narrative structure and world-building (5+ sentences)...",
                        "protagonist": "Detailed character profile",
                        "storyline": "Comprehensive plot summary",
                        "release_blurb": "Punchy marketing hook",
                        "core_loop": "Deep dive into gameplay mechanics and player progression..."
                    }}
                }}
            ],
            "demo_ideas": [
                {{
                    "name": "Demo Name",
                    "reason": "Technical necessity and prototype goals (4+ sentences)...",
                    "cycle": "1-2 months (Vertical Slice)",
                    "visual_prompt": "English prompt focusing on core mechanic visualization",
                    "classic_references": [{{"title": "Game Name", "url": "URL"}}],
                    "details": {{
                        "optimized_outline": "Focus on the specific scope of the demo (4+ sentences)...",
                        "protagonist": "Character role in the demo",
                        "storyline": "The specific slice of story being tested",
                        "release_blurb": "Prototype goal statement",
                        "core_loop": "The single core mechanic being verified",
                        "full_game_prediction": {{
                            "cycle": "Projected full development time (e.g., 24 months)",
                            "budget": "Projected commercial budget (MUST be > 5x ${budget})"
                        }}
                    }}
                }}
            ]
        }}
        """

        if not story.strip():
            raise ValueError("Enter a story idea before starting analysis.")
        result = self._generate_json(prompt)
        for key in ("achievable_genres", "demo_ideas"):
            if not isinstance(result.get(key), list):
                raise ValueError(f"AI response is missing {key}. Please retry.")
            for item in result[key]:
                self._validate_item(item)
        return result

    def generate_image(self, prompt):
        if not self.hf_token:
            raise ValueError("Configure HF_TOKEN in .env to generate cover art.")
        client = InferenceClient(
            provider=os.getenv("HF_PROVIDER", "auto"),
            api_key=self.hf_token,
            timeout=120,
        )
        image = client.text_to_image(
            prompt, model=os.getenv("HF_IMAGE_MODEL", "stabilityai/stable-diffusion-xl-base-1.0")
        )
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("ascii")

    def generate_audio(self, prompt):
        """Generate real MusicGen audio locally or through a deployed HF endpoint."""
        backend = os.getenv("MUSIC_BACKEND", "hf").lower()
        if backend == "hf":
            endpoint = os.getenv("HF_MUSIC_ENDPOINT")
            if not self.hf_token or not endpoint:
                raise ValueError("HF music requires HF_TOKEN and a deployed HF_MUSIC_ENDPOINT.")
            audio_bytes = InferenceClient(token=self.hf_token, timeout=180).text_to_audio(
                prompt, model=endpoint
            )
        elif backend == "local":
            audio_bytes, error = generate_local_music(
                prompt,
                duration=os.getenv("LOCAL_MUSIC_DURATION", "8"),
                model_name=os.getenv("LOCAL_MUSIC_MODEL", "facebook/musicgen-small"),
                device=os.getenv("LOCAL_MUSIC_DEVICE") or None,
            )
            if not audio_bytes:
                raise RuntimeError(error or "MusicGen returned no audio.")
        else:
            raise ValueError("MUSIC_BACKEND must be local or hf.")
        return base64.b64encode(audio_bytes).decode("ascii")

    def generate_music_profile(self, data):
        details = data.get("details", {}) if isinstance(data, dict) else {}
        payload = {
            "name": data.get("name", "") if isinstance(data, dict) else "",
            "release_blurb": details.get("release_blurb", ""),
            "core_loop": details.get("core_loop", ""),
            "storyline": details.get("storyline", ""),
            "protagonist": details.get("protagonist", ""),
        }

        profile = None
        if self.api_key:
            prompt = (
                "You are a game music director. Given the game data JSON, "
                "produce a compact music brief in JSON with keys: "
                "mood (2-3 words), tempo_bpm (int 60-180), energy (0-1 float), "
                "instruments (list 3-6), style_tags (list 3-6), notes (1 short sentence). "
                "Return only JSON.\n"
                f"Game data: {json.dumps(payload, ensure_ascii=True)}"
            )
            try:
                profile = self._generate_json(prompt)
            except Exception as exc:
                print(f"Music profile generation failed: {exc}")

        if not isinstance(profile, dict):
            profile = self._fallback_music_profile(data)
        return profile

    def compose_music_prompt(self, data, profile=None):
        if profile is None:
            profile = self.generate_music_profile(data)

        details = data.get("details", {}) if isinstance(data, dict) else {}
        parts = [
            f"{data.get('name', 'Game')} game soundtrack" if isinstance(data, dict) else "Game soundtrack",
            details.get("release_blurb", ""),
            details.get("core_loop", ""),
        ]

        if profile:
            mood = profile.get("mood")
            if mood:
                parts.append(f"Mood: {mood}")
            tempo = profile.get("tempo_bpm")
            if tempo:
                parts.append(f"Tempo {tempo} BPM")
            instruments = profile.get("instruments")
            if instruments:
                if isinstance(instruments, (list, tuple)):
                    instruments = ", ".join(str(item) for item in instruments if item)
                parts.append(f"Instruments: {instruments}")
            style_tags = profile.get("style_tags")
            if style_tags:
                if isinstance(style_tags, (list, tuple)):
                    style_tags = ", ".join(str(item) for item in style_tags if item)
                parts.append(f"Style: {style_tags}")
            notes = profile.get("notes")
            if notes:
                parts.append(str(notes))

        parts.append("loopable, clean mix, game background music")
        return ", ".join([part for part in parts if part])

    def _fallback_music_profile(self, data):
        details = data.get("details", {}) if isinstance(data, dict) else {}
        text = " ".join(
            str(value)
            for value in [
                data.get("name", "") if isinstance(data, dict) else "",
                details.get("release_blurb", ""),
                details.get("core_loop", ""),
                details.get("storyline", ""),
            ]
        ).lower()

        if any(key in text for key in ("horror", "survival", "nightmare", "eerie")):
            return {
                "mood": "tense, eerie",
                "tempo_bpm": 80,
                "energy": 0.35,
                "instruments": ["low strings", "ambient drones", "sub bass"],
                "style_tags": ["dark", "atmospheric", "minimal"],
                "notes": "Sparse pulses and distant textures.",
            }
        if any(key in text for key in ("cyberpunk", "sci-fi", "sci fi", "futuristic", "neon")):
            return {
                "mood": "edgy, futuristic",
                "tempo_bpm": 120,
                "energy": 0.7,
                "instruments": ["synth bass", "analog pads", "electronic drums"],
                "style_tags": ["neon", "noir", "electronic"],
                "notes": "Driving groove with shimmering synth layers.",
            }
        if any(key in text for key in ("fantasy", "magic", "myth", "kingdom", "dragon")):
            return {
                "mood": "epic, hopeful",
                "tempo_bpm": 100,
                "energy": 0.6,
                "instruments": ["strings", "choir", "orchestral percussion"],
                "style_tags": ["cinematic", "orchestral", "heroic"],
                "notes": "Warm harmonies and sweeping melodies.",
            }
        if any(key in text for key in ("strategy", "tactics", "turn-based", "management", "simulation")):
            return {
                "mood": "focused, measured",
                "tempo_bpm": 90,
                "energy": 0.45,
                "instruments": ["piano", "soft synths", "light percussion"],
                "style_tags": ["minimal", "ambient", "steady"],
                "notes": "Subtle layers with a steady pulse.",
            }

        return {
            "mood": "cinematic, neutral",
            "tempo_bpm": 100,
            "energy": 0.5,
            "instruments": ["synth pads", "drums", "bass"],
            "style_tags": ["ambient", "cinematic", "modern"],
            "notes": "Balanced, unobtrusive background loop.",
        }

    def generate_gdd_enrichment(self, data):
        if not self.api_key or not isinstance(data, dict):
            return None

        details = data.get("details", {}) if isinstance(data, dict) else {}
        payload = {
            "title": data.get("name", ""),
            "release_blurb": details.get("release_blurb", ""),
            "core_loop": details.get("core_loop", ""),
            "storyline": details.get("storyline", ""),
            "protagonist": details.get("protagonist", ""),
            "optimized_outline": details.get("optimized_outline", ""),
            "reason": data.get("reason", ""),
            "cycle": data.get("cycle", ""),
            "classic_references": data.get("classic_references", []),
        }

        prompt = (
            "You are a senior game producer. Expand the provided game data into a professional "
            "GDD supplement for a PDF export. Keep it concise but complete. "
            "Return ONLY JSON with this schema:\n"
            "{\n"
            '  "executive_summary": "2-3 sentences",\n'
            '  "pillars": ["3-5 short bullets"],\n'
            '  "target_audience": "1-2 sentences",\n'
            '  "player_experience": "2-3 sentences",\n'
            '  "key_features": ["5-8 bullets"],\n'
            '  "progression": "1-2 sentences",\n'
            '  "content_scope": "1-2 sentences",\n'
            '  "art_direction": "1-2 sentences",\n'
            '  "audio_direction": "1-2 sentences",\n'
            '  "ui_ux": "1-2 sentences",\n'
            '  "accessibility": "1-2 sentences",\n'
            '  "tech_scope": "1-2 sentences",\n'
            '  "production_plan": [\n'
            '     {"phase": "Pre-production", "duration": "X weeks", "deliverables": "..."},\n'
            '     {"phase": "Production", "duration": "X weeks", "deliverables": "..."}\n'
            "  ],\n"
            '  "risks": ["3-5 bullets"],\n'
            '  "success_metrics": ["3-5 bullets"],\n'
            '  "monetization": "1-2 sentences",\n'
            '  "live_ops": "1-2 sentences",\n'
            '  "marketing_hooks": ["3-5 bullets"]\n'
            "}\n"
            f"Game data: {json.dumps(payload, ensure_ascii=True)}"
        )

        try:
            return self._generate_json(
                prompt,
                model=os.getenv("GDD_MODEL") or self.model,
                config={"temperature": 0.6, "max_output_tokens": 8192},
            )
        except Exception as exc:
            print(f"GDD enrichment unavailable: {exc}")
            return None

    def generate_html_design(self, data, img_b64=None, enrichment=None):
        if self.client is None:
            return get_fallback_html(data)
        prompt = (
            "Create a complete HTML game design document with internal CSS. "
            "Use simple PDF-compatible blocks, tables and headings; no scripts, "
            "external resources, flexbox or grid. Include all provided game details. "
            "Return only HTML, starting with <!DOCTYPE html>.\n"
            f"Game: {json.dumps(data, ensure_ascii=False)}\n"
            f"Supplement: {json.dumps(enrichment, ensure_ascii=False)}"
        )
        try:
            response = self.client.models.generate_content(
                model=self.model, contents=prompt,
                config={"max_output_tokens": 8192},
            )
            html = (response.text or "").strip()
            if html.startswith("```"):
                html = html.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            if "<html" not in html.lower() or "</html>" not in html.lower():
                raise ValueError("AI returned incomplete HTML.")
            if img_b64:
                html = html.replace("</body>", f'<img src="data:image/png;base64,{img_b64}" width="400" /></body>')
            return html
        except Exception as exc:
            print(f"HTML design unavailable: {exc}")
            return get_fallback_html(data)

    def export_pdf(self, data, img_b64=None, use_ai_design=False):

        enrichment = self.generate_gdd_enrichment(data)
        if use_ai_design:
            html_content = self.generate_html_design(data, img_b64, enrichment=enrichment)
            pdf_bytes = convert_html_to_pdf(html_content)
            if pdf_bytes:
                return pdf_bytes
        return create_manual_pdf(data, img_b64, enrichment=enrichment)


    def get_genre_wiki_info(self, genre_name):
        prompt = f"""
        Act as a gaming encyclopedia. For the game genre "{genre_name}":
        1. Write a strict 2-sentence "Wikipedia-style" definition.
        2. List 10 related sub-genres or mechanism tags (e.g., "Open World", "PVP").

        Return JSON: {{ "summary": "...", "tags": ["tag1", "tag2"...] }}
        """
        result = self._generate_json(prompt)
        if not isinstance(result.get("summary"), str) or not isinstance(result.get("tags"), list):
            raise ValueError("AI returned invalid genre information. Please retry.")
        if any(not isinstance(tag, str) for tag in result["tags"]):
            raise ValueError("AI returned invalid genre tags. Please retry.")
        return result

    def evaluate_specific_genre(self, genre, story, team, duration, budget):
        """
        Verify the feasibility of specific types.
        Logic:
        1. If budget/time is sufficient -> Generate full game proposal.
        2. If budget is insufficient but sufficient for a demo -> Generate demo proposal.
        3. If completely mismatched (e.g., FPS with only £100 budget) -> Return reason for non-feasibility.
        """
        prompt = f"""
        Act as a Senior Executive Producer.
        User wants to make a "{genre}" game.
        Constraints: Story: {story} | Team: {team} | Months: {duration} | Budget: ${budget}

        Analyze feasibility STRICTLY:
        1. **Feasible for Full Game**: If budget > $10,000 AND duration > 6 months (adjust threshold based on genre complexity).
        2. **Feasible for Demo**: If budget is low but enough for a prototype.
        3. **Not Feasible**: If constraints are ridiculous for this genre (e.g. MMORPG with $500).

        Return JSON:
        {{
            "status": "feasible_game" OR "feasible_demo" OR "impossible",
            "reason": "Explanation...",
            "instruction": "Include data only when feasible",
            "data": {{
                "name": "{genre} Project",
                "reason": "Why it works...",
                "cycle": "Est time",
                "visual_prompt": "Art prompt...",
                "classic_references": [{{"title": "Ref Game", "url": "#"}}],
                "details": {{
                    "optimized_outline": "...",
                    "protagonist": "...",
                    "storyline": "...",
                    "release_blurb": "...",
                    "core_loop": "...",
                    "full_game_prediction": {{ "cycle": "...", "budget": "..." }}
                }}
            }}
        }}
        """
        result = self._generate_json(prompt)
        if result.get("status") not in ("feasible_game", "feasible_demo", "impossible"):
            raise ValueError("AI returned an invalid feasibility status. Please retry.")
        if result["status"] != "impossible":
            self._validate_item(result.get("data"))
        return result
