"""
AI Service — dual-provider: Ollama (local) and Gemini (cloud).

Provider selection (LLM_PROVIDER env var):
  auto   → try Ollama first; fall back to Gemini on failure/unavailability
  ollama → Ollama only
  gemini → Gemini only
"""
import json
import re
import time
import requests as _requests
from app.config import Config


class AIService:
    def __init__(self):
        self._ollama_ok  = False
        self._gemini_ok  = False
        self._gemini_cli = None

        provider = Config.LLM_PROVIDER.lower()

        if provider in ('auto', 'ollama'):
            self._ollama_ok = self._probe_ollama()

        if provider in ('auto', 'gemini') and Config.GEMINI_API_KEY:
            try:
                from google import genai
                self._gemini_cli = genai.Client(api_key=Config.GEMINI_API_KEY)
                self._gemini_model = 'gemini-2.0-flash'
                self._gemini_fallback = 'gemini-2.0-flash-lite'
                self._gemini_active = self._gemini_model
                self._gemini_ok = True
            except Exception as e:
                print(f'[AIService] Gemini init failed: {e}')

        if not self._ollama_ok and not self._gemini_ok:
            raise ValueError(
                'No AI provider available.\n'
                '  • To use Ollama: run `docker compose up ollama` or `ollama serve`\n'
                '  • To use Gemini: set GEMINI_API_KEY in .env'
            )

        active = []
        if self._ollama_ok:
            active.append(f'Ollama ({Config.OLLAMA_MODEL}@{Config.OLLAMA_HOST})')
        if self._gemini_ok:
            active.append('Gemini')
        print(f'[AIService] Providers: {" → ".join(active)}')

    # ──────────────────────────────────────────────────────────────────
    # Public API (same interface as before — callers unchanged)
    # ──────────────────────────────────────────────────────────────────

    def parse_cv_sections(self, sections: dict) -> dict:
        section_text = '\n\n'.join(
            f'=== {k.upper()} ===\n{v}'
            for k, v in sections.items() if v.strip()
        )
        prompt = f"""You are an expert CV/Resume parser.
The CV below is pre-split into labelled sections. Extract ALL information and return ONE valid JSON object.

{section_text}

Required JSON structure (empty string / empty list when absent):
{{
  "name":"","title":"","email":"","phone":"","location":"",
  "linkedin":"","github":"","website":"","summary":"",
  "skills":[],"skill_categories":{{}},
  "experience":[{{"company":"","title":"","start_date":"","end_date":"","location":"","description":[]}}],
  "education":[{{"institution":"","degree":"","field":"","start_date":"","end_date":"","gpa":""}}],
  "projects":[{{"name":"","description":"","technologies":[],"url":""}}],
  "certifications":[],"languages":[],"achievements":[]
}}

Rules:
- name/title from HEADER or CONTACT section.
- summary: 3-4 compelling sentences.
- skill_categories: group by type (Languages, Frameworks, Tools, Cloud, etc.).
- experience descriptions: quantified bullets, action verbs, keep real numbers.
- Return ONLY raw JSON, no markdown, no explanation."""
        return self._parse_json(self._call(prompt, json_mode=True), self._default_cv())

    def parse_cv(self, cv_text: str) -> dict:
        prompt = f"""You are an expert CV/Resume parser. Extract all information and return ONE valid JSON object.

CV TEXT:
{cv_text}

Required JSON (empty string / list when absent):
{{
  "name":"","title":"","email":"","phone":"","location":"",
  "linkedin":"","github":"","website":"","summary":"",
  "skills":[],"skill_categories":{{}},
  "experience":[{{"company":"","title":"","start_date":"","end_date":"","location":"","description":[]}}],
  "education":[{{"institution":"","degree":"","field":"","start_date":"","end_date":"","gpa":""}}],
  "projects":[{{"name":"","description":"","technologies":[],"url":""}}],
  "certifications":[],"languages":[],"achievements":[]
}}
Return ONLY raw JSON, no markdown, no explanation."""
        return self._parse_json(self._call(prompt, json_mode=True), self._default_cv())

    def polish_prompt(self, user_prompt: str, style: str, cv_data: dict) -> str:
        name  = cv_data.get('name', 'this professional')
        title = cv_data.get('title', 'professional')
        if not user_prompt:
            return (
                f"Create a stunning {style} portfolio for {name}, a {title}. "
                "Highlight key achievements, skills, and projects. "
                "Make it modern, professional, and recruiter-friendly."
            )
        prompt = f"""Rewrite and enhance the following portfolio brief to be specific, impactful, and actionable. Under 150 words.

Original brief: {user_prompt}
Style: {style}
Person: {name} — {title}

Return only the enhanced brief, no preamble."""
        result = self._call(prompt, json_mode=False).strip()
        return result or user_prompt

    def enhance_content(self, cv_data: dict, polished_prompt: str, style: str) -> dict:
        prompt = f"""You are a world-class portfolio content strategist. Enhance the CV data for a **{style}** portfolio.

Portfolio brief: {polished_prompt}

CV data:
{json.dumps(cv_data, indent=2)}

Instructions:
- Rewrite summary: compelling, specific, 3-4 sentences.
- Experience descriptions: quantified bullet points with action verbs.
- Enhance project descriptions: technical depth + business impact.
- skill_categories: group by (Languages, Frameworks, Tools, Cloud, etc.).
- Keep ALL other fields intact.

Return ONLY the complete enhanced JSON with same structure. No markdown."""
        enhanced = self._parse_json(self._call(prompt, json_mode=True), cv_data)
        for k, v in cv_data.items():
            if k not in enhanced or not enhanced[k]:
                enhanced[k] = v
        return enhanced

    def modify_portfolio(self, current_html: str, modification_prompt: str) -> str:
        # Truncate HTML for Ollama (context limit); Gemini can handle more
        max_html = 60_000 if self._gemini_ok else 12_000
        html_input = current_html[:max_html]
        prompt = f"""You are an expert front-end developer. Apply the user's requested change to the portfolio HTML.
Do NOT change anything not requested.

User request: {modification_prompt}

HTML:
{html_input}

Return the complete modified HTML document only. No markdown, no explanation."""
        result = self._call(prompt, json_mode=False, prefer_gemini=True).strip()
        result = re.sub(r'```(?:html)?\s*', '', result, flags=re.IGNORECASE)
        result = re.sub(r'```', '', result)
        return result.strip() if result.strip() else current_html

    # ──────────────────────────────────────────────────────────────────
    # Internal call routing
    # ──────────────────────────────────────────────────────────────────

    def _call(self, prompt: str, json_mode: bool = False, prefer_gemini: bool = False) -> str:
        """
        Route to providers based on availability and preference.
        prefer_gemini=True: skip Ollama for large-context tasks (modify_portfolio).
        """
        errors = []

        if prefer_gemini and self._gemini_ok:
            try:
                return self._call_gemini(prompt)
            except Exception as e:
                errors.append(f'Gemini: {e}')

        if self._ollama_ok and not (prefer_gemini and self._gemini_ok):
            try:
                return self._call_ollama(prompt, json_mode)
            except Exception as e:
                errors.append(f'Ollama: {e}')
                print(f'[AIService] Ollama failed ({e}), trying Gemini…')

        if self._gemini_ok:
            try:
                return self._call_gemini(prompt)
            except Exception as e:
                errors.append(f'Gemini: {e}')

        raise RuntimeError(f'All AI providers failed: {"; ".join(errors)}')

    # ──────────────────────────────────────────────────────────────────
    # Ollama provider
    # ──────────────────────────────────────────────────────────────────

    def _probe_ollama(self) -> bool:
        try:
            r = _requests.get(f'{Config.OLLAMA_HOST}/api/tags', timeout=4)
            if r.status_code == 200:
                models = [m.get('name', '') for m in r.json().get('models', [])]
                model_base = Config.OLLAMA_MODEL.split(':')[0]
                available = any(model_base in m for m in models)
                if available:
                    print(f'[AIService] Ollama ready — model {Config.OLLAMA_MODEL} found')
                else:
                    print(f'[AIService] Ollama running but model {Config.OLLAMA_MODEL} not pulled yet')
                return True
        except Exception:
            pass
        print('[AIService] Ollama not reachable — will use Gemini')
        return False

    def _call_ollama(self, prompt: str, json_mode: bool = False) -> str:
        payload: dict = {
            'model':  Config.OLLAMA_MODEL,
            'prompt': prompt,
            'stream': False,
            'options': {'temperature': 0.1, 'num_predict': 4096},
        }
        if json_mode:
            payload['format'] = 'json'
        r = _requests.post(
            f'{Config.OLLAMA_HOST}/api/generate',
            json=payload,
            timeout=180,
        )
        r.raise_for_status()
        return r.json().get('response', '').strip()

    # ──────────────────────────────────────────────────────────────────
    # Gemini provider
    # ──────────────────────────────────────────────────────────────────

    def _call_gemini(self, prompt: str) -> str:
        models_to_try = [self._gemini_active]
        if self._gemini_active != self._gemini_fallback:
            models_to_try.append(self._gemini_fallback)

        last_exc = None
        for model in models_to_try:
            for attempt in range(2):
                try:
                    resp = self._gemini_cli.models.generate_content(
                        model=model, contents=prompt
                    )
                    if model != self._gemini_active:
                        self._gemini_active = model
                    return resp.text.strip()
                except Exception as exc:
                    last_exc = exc
                    msg = str(exc)
                    if '429' in msg or 'RESOURCE_EXHAUSTED' in msg:
                        m = re.search(r'retry[^\d]*(\d+)', msg, re.IGNORECASE)
                        wait = min(int(m.group(1)) if m else 5, 35)
                        print(f'[AIService] Gemini 429 on {model} (attempt {attempt+1}), waiting {wait}s…')
                        time.sleep(wait)
                    else:
                        break
        raise last_exc

    # ──────────────────────────────────────────────────────────────────
    # JSON parsing
    # ──────────────────────────────────────────────────────────────────

    def _parse_json(self, text: str, fallback: dict) -> dict:
        text = re.sub(r'```(?:json)?\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'```', '', text).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        for opener, closer in [('{', '}'), ('[', ']')]:
            s, e = text.find(opener), text.rfind(closer)
            if s != -1 and e > s:
                try:
                    return json.loads(text[s:e + 1])
                except json.JSONDecodeError:
                    pass
        return fallback

    @staticmethod
    def _default_cv() -> dict:
        return {
            'name': '', 'title': '', 'email': '', 'phone': '',
            'location': '', 'linkedin': '', 'github': '', 'website': '',
            'summary': '', 'skills': [], 'skill_categories': {},
            'experience': [], 'education': [], 'projects': [],
            'certifications': [], 'languages': [], 'achievements': [],
        }
