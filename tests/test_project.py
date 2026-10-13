import base64
import copy
import io
import json
import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image
from pypdf import PdfReader
from streamlit.testing.v1 import AppTest

from backend import GameAIClient
from backend.pdf_generator import create_manual_pdf, convert_html_to_pdf


ROOT = Path(__file__).resolve().parents[1]
ITEM = {
    "name": "Dream Detective",
    "reason": "A small puzzle game fits the team and budget.",
    "cycle": "6 months",
    "details": {
        "release_blurb": "Solve crimes in dreams.",
        "optimized_outline": "Explore three compact dream worlds.",
        "protagonist": "A detective",
        "storyline": "Find the lost memories.",
        "core_loop": "Explore, collect clues, solve puzzles.",
    },
}


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"GOOGLE_API_KEY": "", "HF_TOKEN": ""})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.client = GameAIClient()

    def test_missing_key_and_token_override(self):
        self.assertIsNone(self.client.client)
        with self.assertRaisesRegex(ValueError, "GOOGLE_API_KEY"):
            self.client.generate_proposal("A story", 3, 6, 1000)
        self.assertEqual(GameAIClient(hf_token="explicit-token").hf_token, "explicit-token")

    def test_proposal_validation_and_api_failure(self):
        self.client.client = Mock()
        generate = self.client.client.models.generate_content
        generate.return_value.text = json.dumps({"achievable_genres": [ITEM], "demo_ideas": []})
        result = self.client.generate_proposal("A story", 3, 6, 1000)
        self.assertEqual(result["achievable_genres"][0]["name"], ITEM["name"])
        generate.return_value.text = '{"achievable_genres": [null], "demo_ideas": []}'
        with self.assertRaises(ValueError):
            self.client.generate_proposal("A story", 3, 6, 1000)
        generate.side_effect = RuntimeError("quota exceeded")
        with self.assertRaisesRegex(RuntimeError, "quota exceeded"):
            self.client.generate_proposal("A story", 3, 6, 1000)

    @patch("backend.services.InferenceClient")
    def test_image_uses_token_and_returns_png(self, inference):
        self.client.hf_token = "test-token"
        inference.return_value.text_to_image.return_value = Image.new("RGB", (16, 16))
        image = base64.b64decode(self.client.generate_image("A cover"))
        self.assertTrue(image.startswith(b"\x89PNG"))
        self.assertEqual(inference.call_args.kwargs["api_key"], "test-token")

    @patch("backend.services.InferenceClient")
    def test_remote_music_and_failure_do_not_use_local_fallback(self, inference):
        self.client.hf_token = "test-token"
        with patch.dict(os.environ, {"MUSIC_BACKEND": "hf", "HF_MUSIC_ENDPOINT": "https://test.endpoints.huggingface.cloud"}):
            inference.return_value.text_to_audio.return_value = b"RIFF-test-audio"
            self.assertEqual(base64.b64decode(self.client.generate_audio("Ambient noir")), b"RIFF-test-audio")
            inference.return_value.text_to_audio.assert_called_once_with(
                "Ambient noir", model="https://test.endpoints.huggingface.cloud"
            )
            inference.return_value.text_to_audio.side_effect = RuntimeError("endpoint unavailable")
            with self.assertRaisesRegex(RuntimeError, "endpoint unavailable"):
                self.client.generate_audio("Ambient noir")

    def test_missing_music_endpoint(self):
        with patch.dict(os.environ, {"MUSIC_BACKEND": "hf", "HF_MUSIC_ENDPOINT": ""}):
            with self.assertRaisesRegex(ValueError, "HF_MUSIC_ENDPOINT"):
                self.client.generate_audio("Ambient")

    def test_manual_and_html_pdf_are_readable(self):
        pdf = create_manual_pdf(ITEM, enrichment={"pillars": ["Exploration", "Deduction"], "key_features": ["Dreams", "Puzzles"]})
        reader = PdfReader(io.BytesIO(pdf))
        text = "\n".join(page.extract_text() for page in reader.pages)
        self.assertIn("Deduction", text)
        self.assertIn("Puzzles", text)
        self.assertIn("Explore, collect clues", text)
        html = convert_html_to_pdf("<html><body><h1>Dream Detective</h1></body></html>")
        self.assertIn("Dream Detective", PdfReader(io.BytesIO(html)).pages[0].extract_text())

    def test_html_uses_gemini_without_hf_token(self):
        self.client.client = Mock()
        self.client.client.models.generate_content.return_value.text = "```html\n<html><body>Design</body></html>\n```"
        self.assertEqual(self.client.generate_html_design(ITEM), "<html><body>Design</body></html>")


class AppTests(unittest.TestCase):
    def setUp(self):
        # Keep real credentials out of UI tests; each test supplies its own client.
        loader = patch("dotenv.load_dotenv")
        loader.start()
        self.addCleanup(loader.stop)

    def button(self, app, label):
        return next(button for button in app.button if button.label == label)

    def test_start_without_credentials(self):
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "", "HF_TOKEN": ""}):
            app = AppTest.from_file(str(ROOT / "app1.py")).run(timeout=30)
            self.assertFalse(app.exception)
            self.assertTrue(self.button(app, "Analyze & Generate").disabled)

    def test_proposal_swap_detail_image_failure_and_pdf_persistence(self):
        fake = Mock(api_key="test", hf_token="test")
        reserve = {**copy.deepcopy(ITEM), "name": "Reserve idea"}
        fake.generate_proposal.return_value = {
            "achievable_genres": [copy.deepcopy(ITEM), {**copy.deepcopy(ITEM), "name": "Second"},
                                  {**copy.deepcopy(ITEM), "name": "Third"}, reserve],
            "demo_ideas": [],
        }
        fake.generate_image.side_effect = RuntimeError("Image provider unavailable")
        fake.export_pdf.return_value = create_manual_pdf(ITEM)
        with patch("backend.GameAIClient", return_value=fake):
            app = AppTest.from_file(str(ROOT / "app1.py")).run()
            self.button(app, "Analyze & Generate").click().run()
            self.button(app, "Analyze Dream Detective").click().run()
            self.button(app, "Not Interested (Hide & Swap)").click().run()
            self.assertIn("Reserve idea", [item["name"] for item in app.session_state.visible_items["achievable"]])
            self.button(app, "Analyze Reserve idea").click().run()
            self.button(app, "Interested (Deep Dive)").click().run()
            self.button(app, "Generate / Regenerate Cover Art").click().run()
            self.assertFalse(app.exception)
            self.assertIn("Image provider unavailable", app.error[0].value)
            self.button(app, "Export Professional GDD (PDF)").click().run()
            self.assertTrue(app.session_state.pdfs)
            app.run()
            self.assertTrue(app.session_state.pdfs)
            self.assertFalse(app.exception)

    def test_wiki_recommendation_survives_rerun(self):
        fake = Mock(api_key="test", hf_token="")
        fake.get_genre_wiki_info.return_value = {"summary": "A genre definition.", "tags": ["Exploration"]}
        fake.evaluate_specific_genre.return_value = {"status": "impossible", "reason": "Scope too large."}
        fake.generate_proposal.return_value = {"achievable_genres": [ITEM], "demo_ideas": []}
        with patch("backend.GameAIClient", return_value=fake):
            app = AppTest.from_file(str(ROOT / "app1.py")).run()
            self.button(app, "Roguelike").click().run()
            self.button(app, "Analyze Feasibility").click().run()
            app.run()
            self.button(app, "Auto-Recommend Suitable Genres").click().run()
            self.assertEqual(app.session_state.view, "home")
            self.assertTrue(app.session_state.proposals)
            self.assertFalse(app.exception)


if __name__ == "__main__":
    unittest.main()
