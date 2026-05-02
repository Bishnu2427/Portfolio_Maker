import json
import re
from google import genai
from app.config import Config


class AIService:
    MODEL = 'gemini-2.0-flash'

    def __init__(self):
        if not Config.GEMINI_API_KEY:
            raise ValueError(
                'GEMINI_API_KEY is missing. Add it to your .env file:\n'
                'GEMINI_API_KEY=your-key-from-aistudio.google.com'
            )
        self.client = genai.Client(api_key=Config.GEMINI_API_KEY)

    # ------------------------------------------------------------------
    def parse_cv(self, cv_text: str) -> dict:
        prompt = f"""You are an expert CV/Resume parser.
Extract all information from the CV text below and return a single valid JSON object.

CV TEXT:
{cv_text}

Required JSON structure (use empty string or empty list when data is absent):
{{
  "name": "",
  "title": "",
  "email": "",
  "phone": "",
  "location": "",
  "linkedin": "",
  "github": "",
  "website": "",
  "summary": "",
  "skills": [],
  "skill_categories": {{}},
  "experience": [
    {{
      "company": "",
      "title": "",
      "start_date": "",
      "end_date": "",
      "location": "",
      "description": []
    }}
  ],
  "education": [
    {{
      "institution": "",
      "degree": "",
      "field": "",
      "start_date": "",
      "end_date": "",
      "gpa": ""
    }}
  ],
  "projects": [
    {{
      "name": "",
      "description": "",
      "technologies": [],
      "url": ""
    }}
  ],
  "certifications": [],
  "languages": [],
  "achievements": []
}}

Return ONLY the raw JSON with no markdown fences, no explanation."""
        text = self._call(prompt)
        return self._parse_json(text, self._default_cv())

    # ------------------------------------------------------------------
    def polish_prompt(self, user_prompt: str, style: str, cv_data: dict) -> str:
        name = cv_data.get('name', 'this professional')
        title = cv_data.get('title', 'professional')
        if not user_prompt:
            return (
                f"Create a stunning {style} portfolio for {name}, a {title}. "
                "Highlight key achievements, skills, and projects. "
                "Make it modern, professional, and recruiter-friendly."
            )
        prompt = f"""Rewrite and enhance the following portfolio brief to be more specific,
impactful, and actionable. Keep it under 150 words.

Original brief: {user_prompt}
Style: {style}
Person: {name} — {title}

Return only the enhanced brief, no preamble."""
        return self._call(prompt).strip() or user_prompt

    # ------------------------------------------------------------------
    def enhance_content(self, cv_data: dict, polished_prompt: str, style: str) -> dict:
        prompt = f"""You are a world-class portfolio content strategist.
Enhance the CV data below for a **{style}** portfolio.

Portfolio brief:
{polished_prompt}

Current CV data:
{json.dumps(cv_data, indent=2)}

Instructions:
- Rewrite the summary to be compelling and specific (3–4 sentences).
- Rewrite experience descriptions as quantified bullet points with action verbs.
- Enhance project descriptions to highlight technical depth and business impact.
- Group skills by category in skill_categories (e.g. Languages, Frameworks, Tools, Cloud).
- Keep all other fields intact.

Return ONLY the complete enhanced JSON with the same structure. No markdown fences."""
        text = self._call(prompt)
        enhanced = self._parse_json(text, cv_data)
        # Preserve original fields that AI may have dropped or emptied
        for k, v in cv_data.items():
            if k not in enhanced or not enhanced[k]:
                enhanced[k] = v
        return enhanced

    # ------------------------------------------------------------------
    def modify_portfolio(self, current_html: str, modification_prompt: str) -> str:
        prompt = f"""You are an expert front-end developer.
Apply the user's requested change to the portfolio HTML below.
Do NOT change anything that was not requested.

User request:
{modification_prompt}

Current HTML:
{current_html}

Return the complete modified HTML document only. No markdown, no explanation."""
        result = self._call(prompt).strip()
        result = re.sub(r'^```(?:html)?\s*', '', result, flags=re.IGNORECASE)
        result = re.sub(r'\s*```$', '', result)
        return result if result else current_html

    # ------------------------------------------------------------------
    def _call(self, prompt: str) -> str:
        response = self.client.models.generate_content(
            model=self.MODEL,
            contents=prompt,
        )
        return response.text.strip()

    def _parse_json(self, text: str, fallback: dict) -> dict:
        text = text.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*```$', '', text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return fallback

    @staticmethod
    def _default_cv() -> dict:
        return {
            'name': '',
            'title': '',
            'email': '',
            'phone': '',
            'location': '',
            'linkedin': '',
            'github': '',
            'website': '',
            'summary': '',
            'skills': [],
            'skill_categories': {},
            'experience': [],
            'education': [],
            'projects': [],
            'certifications': [],
            'languages': [],
            'achievements': [],
        }
