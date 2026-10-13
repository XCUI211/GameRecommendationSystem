# Indie Game Studio Pro

An AI creative support tool for independent game developers during ideation and pre-production. Turn a story idea, team size, schedule and budget into feasible game concepts and prototype plans.

## Features

- **Feasibility analysis:** Gemini generates full-game recommendations and vertical-slice proposals, including narrative, mechanics and production estimates. Hide a recommendation to reveal another option.
- **Genre encyclopedia:** Explore definitions and mechanics, evaluate a specific genre, and request alternatives when the scope is too large.
- **Cover art:** Generate concept art through Hugging Face Inference Providers. Images are generated on request and retained in the current session.
- **AI soundtrack:** Generate real MusicGen audio through your deployed Hugging Face endpoint. An optional local MusicGen backend is also available. Failed generation is reported; it is never replaced with procedural audio.
- **GDD export:** Download a PDF containing the game design and an optional Gemini supplement. Choose an AI HTML layout or standard PDF typesetting. Exported files stay available across page reruns in the current session.

## Setup (Windows PowerShell)

Python 3.10+ is required for the main application. The main application was tested here with Python 3.14.4. Python 3.11 or 3.12 is recommended if you choose the optional local MusicGen backend.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` with your credentials and the endpoint you have deployed:

```dotenv
GOOGLE_API_KEY=your_google_api_key
HF_TOKEN=your_huggingface_token
MUSIC_BACKEND=hf
HF_MUSIC_ENDPOINT=https://your-endpoint.endpoints.huggingface.cloud
```

- `GOOGLE_API_KEY` enables proposals, genre analysis and AI document layout. Obtain a key from Google AI Studio.
- `HF_TOKEN` enables Hugging Face image and remote music requests. The token needs permission to access the relevant inference services.
- `HF_MUSIC_ENDPOINT` must be a running endpoint serving MusicGen with a compatible `text-to-audio` API returning audio bytes. A Hugging Face model page URL is not an API endpoint. As checked on 2026-10-13, [MusicGen Small](https://huggingface.co/facebook/musicgen-small) has no deployed Inference Provider; a token alone cannot enable hosted MusicGen generation.
- `GEMINI_MODEL` defaults to `gemini-2.5-flash`, the [documented model code](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash). Set it to another available model if necessary. `GDD_MODEL` optionally overrides the supplement model.
- `HF_IMAGE_MODEL` defaults to `stabilityai/stable-diffusion-xl-base-1.0`; `HF_PROVIDER` defaults to `auto`. Model availability, account permissions and provider billing still apply. Select a deployed model/provider if the default is unavailable. See [Hugging Face inference documentation](https://huggingface.co/docs/huggingface_hub/en/guides/inference).

Start the app:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app1.py
```

Open the URL printed by Streamlit (normally `http://localhost:8501`). Save `.env` and rerun or refresh the page after changing it; saved file values override previously loaded environment values. Restart after changing model settings. Without credentials the home page still opens and explains the missing configuration; AI actions are disabled. The IDE's terminal environment injection setting is not required: the application loads `.env` itself.

## Optional: run the real MusicGen model locally

Remote generation is the default. To run the model on your own computer instead:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-music.txt
```

```dotenv
MUSIC_BACKEND=local
LOCAL_MUSIC_MODEL=facebook/musicgen-small
LOCAL_MUSIC_DURATION=8
LOCAL_MUSIC_DEVICE=cpu
```

Set `LOCAL_MUSIC_DEVICE=cuda` with a compatible NVIDIA GPU and PyTorch installation, or leave it empty for automatic selection. The first request downloads the model weights; CPU generation may take several minutes. Duration is limited to 1–30 seconds. The implementation follows the [Transformers MusicGen interface](https://huggingface.co/docs/transformers/model_doc/musicgen). No local model is downloaded during normal remote operation.

## Project structure

```text
app1.py                    Streamlit interface and session state
backend/services.py        Gemini, Hugging Face and PDF orchestration
backend/text_to_music.py   Optional local MusicGen inference
backend/pdf_generator.py  Standard and HTML PDF conversion
requirements.txt          Main application dependencies
requirements-music.txt    Optional local music dependencies
.env.example              Configuration template, without credentials
tests/test_project.py     Backend and Streamlit interaction tests
```

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
```

The tests cover missing credentials, proposal validation, API failures, cover-art conversion, remote music routing, readable PDF export, recommendation replacement and encyclopedia navigation. External AI calls are mocked: passing tests verify the application logic, not your live API credentials, model availability or generated asset quality. Real remote music still needs your configured endpoint. Standard PDF export uses built-in Latin fonts; non-Latin text may be replaced with `?`.

## Privacy and limitations

Ideas are sent to Google and Hugging Face when the corresponding AI actions run. Application results and assets remain in the current Streamlit session; cover generation does not write files to the project. `.env` is excluded from version control. Local MusicGen stores downloaded weights in the Hugging Face cache.

Production and budget estimates are AI suggestions, not guarantees. Review generated content for accuracy, bias and licensing before using it in a released game. MusicGen model weights have their own license; consult the model card before commercial use.
