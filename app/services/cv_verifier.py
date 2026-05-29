"""
CVVerifier — post-extraction quality agent.

Responsibilities:
  1. Strip any residual (cid:NNN) artifacts from every string field.
  2. Validate contact fields (email/phone) actually appear in the source CV text.
  3. Clean malformed skills  (remove fragments that are full sentences or headers).
  4. Clean experience / project descriptions  (remove bullets that are clearly skills
     or garbled technology tags).
  5. Ensure mandatory fields (name, title) have meaningful values.
  6. Optionally ask AI to re-extract specific sections that failed quality checks.

Usage:
    verifier = CVVerifier(portfolio_id)
    cv_data  = verifier.verify(cv_data, cleaned_cv_text, sections, ai=ai_service)
"""
import re
from app.services.cv_analyzer import clean_cid_artifacts, _EMAIL_RE, _PHONE_RE


# ── Helpers ────────────────────────────────────────────────────────────────────

_ARTIFACT_RE = re.compile(r'[(]cid:[0-9]+[)]')  # catch any leftover CIDs


def _clean_str(s: str) -> str:
    """Remove residual CID artifacts and strip whitespace."""
    s = _ARTIFACT_RE.sub('', s)
    s = clean_cid_artifacts(s)
    return s.strip()


def _clean_val(v):
    """Recursively clean CID artifacts from any data structure."""
    if isinstance(v, str):
        return _clean_str(v)
    if isinstance(v, list):
        return [_clean_val(i) for i in v]
    if isinstance(v, dict):
        return {k: _clean_val(vv) for k, vv in v.items()}
    return v


def _has_value(v) -> bool:
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (list, dict)):
        return bool(v)
    return v is not None


def _looks_like_sentence(text: str) -> bool:
    """Return True if the text is too long/complex to be a skill tag or list item."""
    words = text.split()
    if len(words) > 8:
        return True
    # Ends with a period and is longer than 4 words
    if text.strip().endswith('.') and len(words) > 4:
        return True
    return False


def _looks_like_skill(text: str) -> bool:
    """Heuristic: short text with no internal date patterns is probably a skill."""
    if len(text.split()) > 6:
        return False
    if re.search(r'\b\d{4}\b', text):
        return False
    return True


# ── Verifier ───────────────────────────────────────────────────────────────────

class CVVerifier:

    def __init__(self, portfolio_id: str):
        self.portfolio_id = portfolio_id
        self._log: list[str] = []

    # ------------------------------------------------------------------
    def verify(self, cv_data: dict, cv_text: str, ai=None) -> dict:
        """
        Run all verification passes and return a cleaned, validated cv_data dict.
        Pass ai=AIService() instance to enable AI re-extraction of failed fields.
        """
        self._log.clear()

        # Pass 1: strip any residual CID artifacts from all fields
        cv_data = _clean_val(cv_data)
        self._log.append('[Verifier] Pass 1: artifact stripping done')

        # Pass 2: validate contact fields against source text
        cv_data = self._validate_contacts(cv_data, cv_text)

        # Pass 3: clean skills
        cv_data = self._clean_skills(cv_data)

        # Pass 4: clean experience descriptions
        cv_data = self._clean_experience(cv_data)

        # Pass 5: clean projects
        cv_data = self._clean_projects(cv_data)

        # Pass 6: ensure mandatory fields
        cv_data = self._ensure_mandatory(cv_data, cv_text)

        # Pass 7 (optional): AI re-extraction for empty/suspect fields
        if ai:
            cv_data = self._ai_recheck(cv_data, cv_text, ai)

        for msg in self._log:
            print(msg)
        return cv_data

    # ------------------------------------------------------------------
    def _validate_contacts(self, cv_data: dict, cv_text: str) -> dict:
        """
        Verify email and phone actually appear in the source CV text.
        If they don't, try to re-extract them from the text directly.
        """
        email = cv_data.get('email', '').strip()
        if email and email not in cv_text:
            m = _EMAIL_RE.search(cv_text)
            if m:
                cv_data['email'] = m.group()
                self._log.append(f'[Verifier] Email corrected to: {cv_data["email"]}')
            else:
                cv_data['email'] = ''
                self._log.append('[Verifier] Email removed (not found in source)')

        phone = cv_data.get('phone', '').strip()
        if phone:
            # Normalise phone to digits for comparison
            phone_digits = re.sub(r'\D', '', phone)
            if len(phone_digits) < 7 or phone_digits not in re.sub(r'\D', '', cv_text):
                m = _PHONE_RE.search(re.sub(_EMAIL_RE, '', cv_text[:500]))
                if m:
                    candidate = m.group(1).strip()
                    if len(re.sub(r'\D', '', candidate)) >= 7:
                        cv_data['phone'] = candidate
                        self._log.append(f'[Verifier] Phone corrected to: {cv_data["phone"]}')
                else:
                    cv_data['phone'] = ''
                    self._log.append('[Verifier] Phone removed (not found in source)')

        return cv_data

    # ------------------------------------------------------------------
    def _clean_skills(self, cv_data: dict) -> dict:
        """
        Remove skill items that are clearly not skills:
        - Full sentences (>8 words)
        - Contain date ranges
        - Look like experience / project description lines
        """
        raw = cv_data.get('skills', [])
        cleaned = []
        for s in raw:
            s = s.strip()
            if not s:
                continue
            if _looks_like_sentence(s):
                self._log.append(f'[Verifier] Dropped non-skill: {s[:60]}')
                continue
            if re.search(r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b', s, re.IGNORECASE):
                self._log.append(f'[Verifier] Dropped date-like skill: {s[:60]}')
                continue
            cleaned.append(s)

        cv_data['skills'] = cleaned

        # Also clean skill_categories
        cats = cv_data.get('skill_categories', {})
        clean_cats = {}
        for cat, items in cats.items():
            cat = _clean_str(cat)
            if not cat or _looks_like_sentence(cat):
                continue
            clean_items = [
                s.strip() for s in items
                if s.strip() and not _looks_like_sentence(s.strip())
            ]
            if clean_items:
                clean_cats[cat] = clean_items
        cv_data['skill_categories'] = clean_cats

        return cv_data

    # ------------------------------------------------------------------
    def _clean_experience(self, cv_data: dict) -> dict:
        """
        Clean experience entries:
        - Remove description bullets that look like skill tags (short, no verbs)
        - Remove bullets containing only technology/tool names
        - Ensure title/company are not swapped
        """
        entries = cv_data.get('experience', [])
        for entry in entries:
            desc = entry.get('description', [])
            good_bullets = []
            for bullet in desc:
                bullet = bullet.strip()
                if not bullet:
                    continue
                # Skip if the bullet is just a comma-separated skill list
                parts = [p.strip() for p in re.split(r'[,|]', bullet)]
                if len(parts) >= 3 and all(_looks_like_skill(p) for p in parts):
                    self._log.append(f'[Verifier] Dropped skill-list bullet: {bullet[:60]}')
                    continue
                # Skip single-word bullets (probably a tag leaked in)
                if len(bullet.split()) == 1:
                    continue
                good_bullets.append(bullet)
            entry['description'] = good_bullets

        cv_data['experience'] = entries
        return cv_data

    # ------------------------------------------------------------------
    def _clean_projects(self, cv_data: dict) -> dict:
        """
        Clean project entries:
        - Remove technology items that are full sentences
        - Trim descriptions that are too long or contain CID artifacts
        """
        projects = cv_data.get('projects', [])
        for proj in projects:
            # Clean technologies list
            techs = proj.get('technologies', [])
            proj['technologies'] = [
                t.strip() for t in techs
                if t.strip() and not _looks_like_sentence(t.strip())
            ]
            # Clean description
            desc = proj.get('description', '')
            if isinstance(desc, list):
                desc = ' '.join(desc)
            proj['description'] = _clean_str(str(desc))[:600]

        cv_data['projects'] = projects
        return cv_data

    # ------------------------------------------------------------------
    def _ensure_mandatory(self, cv_data: dict, cv_text: str) -> dict:
        """
        Ensure name and title are populated.
        If name is missing, try a quick regex from the first 300 chars of CV text.
        """
        if not cv_data.get('name'):
            for line in cv_text[:400].splitlines():
                line = line.strip()
                words = line.split()
                if (1 <= len(words) <= 5
                        and re.match(r"^[A-Za-z][A-Za-z' -]*$", line)
                        and not re.search(r'\d', line)):
                    cv_data['name'] = line
                    self._log.append(f'[Verifier] Name rescued: {line}')
                    break

        if not cv_data.get('title'):
            # Look for a short line after the name
            name = cv_data.get('name', '')
            if name:
                found_name = False
                for line in cv_text[:600].splitlines():
                    line = line.strip()
                    if line == name:
                        found_name = True
                        continue
                    if found_name and 2 <= len(line.split()) <= 8:
                        if not re.search(r'[@:/+()]', line) and not re.search(r'\d{4}', line):
                            cv_data['title'] = line
                            self._log.append(f'[Verifier] Title rescued: {line}')
                            break

        return cv_data

    # ------------------------------------------------------------------
    def _ai_recheck(self, cv_data: dict, cv_text: str, ai) -> dict:
        """
        If key sections are empty after all regex passes, ask AI to re-extract
        only the missing pieces from the source text.
        """
        missing = []
        if not cv_data.get('summary'):
            missing.append('summary')
        if not cv_data.get('experience'):
            missing.append('experience')
        if not cv_data.get('skills'):
            missing.append('skills')

        if not missing:
            return cv_data

        self._log.append(f'[Verifier] AI re-extraction for: {missing}')

        field_schemas = {
            'summary': '"summary": "<3-4 sentence professional summary>"',
            'experience': (
                '"experience": [{"title":"","company":"","start_date":"",'
                '"end_date":"","location":"","description":[]}]'
            ),
            'skills': '"skills": [], "skill_categories": {}',
        }

        schema_parts = ', '.join(field_schemas[f] for f in missing)
        prompt = f"""You are an expert CV parser. Extract ONLY these missing fields from the CV text.

CV TEXT:
{cv_text[:6000]}

Return ONLY a JSON object with these fields: {{{schema_parts}}}
Rules:
- summary: 3-4 compelling sentences, no placeholders.
- experience: real jobs only, quantified bullets.
- skills: group in skill_categories by type.
- Return raw JSON, no markdown."""

        try:
            result = ai._parse_json(ai._call(prompt, json_mode=True), {})
            for field in missing:
                if field in result and _has_value(result[field]):
                    cv_data[field] = _clean_val(result[field])
                    self._log.append(f'[Verifier] AI filled: {field}')
                    # Also fill skill_categories if skills were missing
                    if field == 'skills' and 'skill_categories' in result:
                        cv_data['skill_categories'] = _clean_val(result['skill_categories'])
        except Exception as exc:
            self._log.append(f'[Verifier] AI re-check failed: {exc}')

        return cv_data
