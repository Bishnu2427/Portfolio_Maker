"""
Section-based CV analyzer — RAG-like knowledge base.

Flow:
  1. Clean raw PDF/DOCX text  (fix ligature artifacts, normalise whitespace)
  2. Split CV into named section blocks by detecting headers
  3. Persist each section in MongoDB  (cv_sections collection)
  4. Extract structured data from the correct section for each field
     — AI first (single consolidated call), regex fallback per section type
  5. Return a complete cv_data dict ready for the portfolio generator
"""
import re
from app.models.cv_section import CVSection


# ── Section keyword catalogue ──────────────────────────────────────────────────
SECTION_PATTERNS = {
    'contact':        r'\b(contact|personal\s+info|personal\s+details)\b',
    'summary':        r'\b(summary|professional\s+summary|objective|career\s+objective|profile|about\s+me|about)\b',
    'experience':     r'\b(experience|work\s+experience|employment|work\s+history|professional\s+experience)\b',
    'education':      r'\b(education|academic(?:\s+background)?|qualifications?|degrees?|schooling)\b',
    'skills':         r'\b(skills?|technical\s+skills?|core\s+competencies|competencies|technologies|tech\s+stack|expertise|proficiencies)\b',
    'projects':       r'\b(projects?|personal\s+projects?|academic\s+projects?|key\s+projects?)\b',
    'certifications': r'\b(certifications?|certificates?|accreditations?|credentials?|licenses?)\b',
    'achievements':   r'\b(achievements?|accomplishments?|awards?|honors?|recognitions?)\b',
    'languages':      r'\b(languages?|spoken\s+languages?|language\s+proficiency)\b',
    'publications':   r'\b(publications?|papers?|research(?:\s+papers?)?|articles?)\b',
    'volunteer':      r'\b(volunteer(?:ing)?|community\s+service|social\s+work)\b',
    'interests':      r'\b(interests?|hobbies|activities|extracurricular)\b',
}

# Priority order when a line matches multiple patterns (most specific wins)
_HEADER_PRIORITY = [
    'summary', 'certifications', 'achievements', 'languages',
    'publications', 'volunteer', 'interests', 'contact',
    'skills', 'projects', 'education', 'experience',
]

# ── Compiled regexes ────────────────────────────────────────────────────────────
_EMAIL_RE = re.compile(r'[\w._%+\-]+@[\w.\-]+\.[a-zA-Z]{2,}')
_PHONE_RE = re.compile(
    r'(?<!\d)'                         # no digit immediately before
    r'(\+?[\d][\d\s\-().]{5,14}\d)'   # the number itself
    r'(?!\d)'                          # no digit immediately after
)
_LINKEDIN_RE = re.compile(r'linkedin\.com/in/[\w\-]+', re.IGNORECASE)
_GITHUB_RE   = re.compile(r'github\.com/[\w\-]+', re.IGNORECASE)
_WEBSITE_RE  = re.compile(r'https?://(?!(?:linkedin|github)\.com)[\w\-./]+', re.IGNORECASE)

_DATE_RE = re.compile(
    r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?'
    r'|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
    r'[.,]?\s*\d{4}'                                                      # Month YYYY
    r'|\b\d{4}\s*[-–to]+\s*(?:\d{4}|present|current|now|till\s+date|to\s+date)\b'  # YYYY - YYYY/Present
    r'|\b(?:0?[1-9]|1[0-2])[/\-]\d{4}\b'                                 # MM/YYYY
    r'|\b\d{4}\s*[-–]\s*(?:present|current|now)\b',                       # YYYY - Present
    re.IGNORECASE,
)

# Decorator characters that surround section headers in many CVs
_DECOR_RE = re.compile(r'[_\-=*#|●•▪►◆■◇~]{2,}')


# ── CID ligature table ──────────────────────────────────────────────────────────
# PDF fonts that use OpenType ligatures encode them as (cid:NNN) when the font's
# ToUnicode map is missing.  These mappings are confirmed from the user's PDF:
#   cid:415 = "ti"  (expertise, tion, tive, tic, …)
#   cid:332 = "ft"  (Microsoft → Microso_ft_)
#   cid:414 = "tf"  (platform → pla_tf_orm)
#   cid:425 = "tt"  (Flutter  → Flu_tt_er)
# Additional common OpenType ligature CIDs included for robustness.
_CID_MAP: dict[int, str] = {
    # Confirmed from user screenshots
    415: 'ti',
    332: 'ft',
    414: 'tf',
    425: 'tt',
    # Common OpenType / Adobe standard ligatures
    322: 'ff',
    323: 'fi',
    324: 'fl',
    325: 'ffi',
    326: 'ffl',
    327: 'st',
    328: 'ct',
    413: 'fi',
    416: 'tl',
    417: 'ft',
    418: 'ffi',
    419: 'ffl',
    420: 'ij',
    421: 'fj',
    426: 'th',
    427: 'ffi',
    428: 'ffl',
    364: 'fi',
    366: 'fl',
    381: 'ffi',
    382: 'ffl',
}

_CID_RE = re.compile(r'[(]cid:([0-9]+)[)]')


def _decode_cid(m: re.Match) -> str:
    cid = int(m.group(1))
    return _CID_MAP.get(cid, '')   # unknown CID → remove (AI can recover from context)


def clean_cid_artifacts(text: str) -> str:
    """Replace (cid:NNN) PDF ligature placeholders with their real characters."""
    return _CID_RE.sub(_decode_cid, text)


# ── Text cleaning ───────────────────────────────────────────────────────────────

def _clean_text(text: str) -> str:
    """Fix common PDF extraction artefacts and normalise whitespace."""
    # CID ligature artifacts  — must be first so later steps see clean text
    text = clean_cid_artifacts(text)

    # Θ placeholder (some fonts encode 'ti' as Θ)
    text = re.sub(r'([A-Za-z])\s?Θ\s?([A-Za-z])', r'\1ti\2', text)
    text = text.replace('Θ', 'ti')

    # Unicode ligatures / special chars -> plain ASCII
    # All non-ASCII chars written as \uXXXX escapes so the IDE parser
    # never sees a curly-quote character adjacent to a regular apostrophe.
    text = text.replace('ﬁ', 'fi')   # fi ligature
    text = text.replace('ﬂ', 'fl')   # fl ligature
    text = text.replace('ﬃ', 'ffi')  # ffi ligature
    text = text.replace('ﬄ', 'ffl')  # ffl ligature
    text = text.replace('ﬀ', 'ff')   # ff ligature
    text = text.replace('ﬅ', 'st')   # st ligature
    text = text.replace('ﬆ', 'st')   # st ligature
    text = text.replace('­', '')     # soft hyphen
    text = text.replace('​', '')     # zero-width space
    text = text.replace('‌', '')     # zero-width non-joiner
    text = text.replace('‍', '')     # zero-width joiner
    text = text.replace('‘', "'")   # left single quotation mark
    text = text.replace('’', "'")   # right single quotation mark
    text = text.replace('“', '"')   # left double quotation mark
    text = text.replace('”', '"')   # right double quotation mark
    text = text.replace('–', '-')    # en-dash
    text = text.replace('—', '-')    # em-dash
    text = text.replace('·', '.')    # middle dot

    # Collapse multiple spaces (preserve newlines)
    text = re.sub(r'[^\S\n]+', ' ', text)
    # Collapse 3+ blank lines → 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ── Section detection ───────────────────────────────────────────────────────────

def _is_section_header(line: str) -> str | None:
    """
    Return the canonical section type if *line* looks like a section header,
    else None. Resolves multi-pattern conflicts via _HEADER_PRIORITY.
    """
    stripped = line.strip()
    if not stripped or len(stripped) > 65:
        return None
    # Lines with date patterns are never headers
    if _DATE_RE.search(stripped):
        return None
    # Strip decorator characters and surrounding whitespace
    clean = _DECOR_RE.sub(' ', stripped).strip()
    if not clean or len(clean) < 3:
        return None

    matches = [
        stype for stype, pat in SECTION_PATTERNS.items()
        if re.search(pat, clean, re.IGNORECASE)
    ]
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    # Resolve conflicts: return the highest-priority match
    for stype in _HEADER_PRIORITY:
        if stype in matches:
            return stype
    return matches[0]


def _split_sections(text: str) -> dict:
    """
    Split cleaned CV text into {section_type: raw_text_block}.
    Pre-header content (name, contact) is stored under 'header'.
    """
    lines = text.splitlines()
    buckets: dict[str, list[str]] = {'header': []}
    current = 'header'

    for line in lines:
        stype = _is_section_header(line)
        if stype:
            if stype not in buckets:
                buckets[stype] = []
            current = stype
        else:
            buckets[current].append(line)

    # Collapse each bucket; drop completely empty ones
    result = {k: '\n'.join(v).strip() for k, v in buckets.items() if any(l.strip() for l in v)}

    # If no sections were detected, the whole CV is in 'header' — try to rescue
    # by looking for common keyword lines as rough boundaries
    if len(result) == 1 and 'header' in result:
        result = _rescue_split(text)

    return result


def _rescue_split(text: str) -> dict:
    """
    Fallback for CVs where the primary section splitter found nothing.
    Tries to detect boundaries by looking for ALL-CAPS short lines.
    """
    buckets: dict[str, list[str]] = {'header': []}
    current = 'header'
    lines = text.splitlines()

    for line in lines:
        stripped = line.strip()
        # ALL-CAPS short line that looks like a section header
        if (stripped and stripped == stripped.upper()
                and 3 <= len(stripped) <= 50
                and re.search(r'[A-Z]', stripped)
                and not _DATE_RE.search(stripped)):
            stype = None
            clean = _DECOR_RE.sub(' ', stripped).strip()
            for st, pat in SECTION_PATTERNS.items():
                if re.search(pat, clean, re.IGNORECASE):
                    stype = st
                    break
            if stype:
                if stype not in buckets:
                    buckets[stype] = []
                current = stype
                continue
        buckets[current].append(line)

    return {k: '\n'.join(v).strip() for k, v in buckets.items() if any(l.strip() for l in v)}


# ── Per-section regex extractors ────────────────────────────────────────────────

def _extract_contact(sections: dict) -> dict:
    """
    Extract name, title, and all contact fields.
    Searches the 'header' and 'contact' sections; falls back to full text.
    """
    # Combine header + contact blocks (contact section may hold email/phone too)
    header = sections.get('header', '')
    contact_block = sections.get('contact', '')
    full_head = '\n'.join(filter(None, [header, contact_block]))
    # For links/email/phone, also search the first 800 chars of full text as last resort
    all_sections = '\n'.join(sections.values())
    src_contact = full_head or all_sections[:800]

    result = {
        'name': '', 'title': '', 'email': '', 'phone': '',
        'location': '', 'linkedin': '', 'github': '', 'website': '',
    }

    # ── Email ──────────────────────────────────────────────────────────
    m = _EMAIL_RE.search(src_contact) or _EMAIL_RE.search(all_sections)
    if m:
        result['email'] = m.group()

    # ── Phone ──────────────────────────────────────────────────────────
    # Avoid matching email addresses or years
    phone_src = re.sub(_EMAIL_RE, '', src_contact)
    m = _PHONE_RE.search(phone_src)
    if m:
        candidate = m.group(1).strip()
        # Reject if too many repeated digits (e.g., 2020-2023 style)
        if len(re.sub(r'[\s\-().]', '', candidate)) >= 7:
            result['phone'] = candidate

    # ── Social / web ───────────────────────────────────────────────────
    m = _LINKEDIN_RE.search(all_sections)
    if m:
        result['linkedin'] = 'https://' + m.group()
    m = _GITHUB_RE.search(all_sections)
    if m:
        result['github'] = 'https://' + m.group()
    m = _WEBSITE_RE.search(src_contact)
    if m:
        result['website'] = m.group()

    # ── Name ───────────────────────────────────────────────────────────
    # Strategy: first line in header that is all-alpha words (1-5), no digits,
    # no special chars, not a known section keyword
    for line in (full_head or all_sections[:400]).splitlines():
        line = line.strip()
        if not line:
            continue
        words = line.split()
        # Accept 1-5 word names; all chars must be letters, hyphens, or apostrophes
        if (1 <= len(words) <= 5
                and re.match(r"^[A-Za-z][A-Za-z'\- ]*$", line)
                and not any(c in line for c in ['@', ':', '/', '|', '+', '(', ')', '.'])
                and not _is_section_header(line)):
            result['name'] = line
            break

    # ── Title: next qualifying line after the name ──────────────────────
    if result['name']:
        name_found = False
        for line in (full_head or all_sections[:600]).splitlines():
            line = line.strip()
            if not line:
                continue
            if line == result['name']:
                name_found = True
                continue
            if name_found:
                words = line.split()
                if (2 <= len(words) <= 8
                        and not _DATE_RE.search(line)
                        and not _EMAIL_RE.search(line)
                        and not _PHONE_RE.search(line)
                        and not _is_section_header(line)
                        and not any(c in line for c in ['@', '/', '+', '(', ')'])):
                    result['title'] = line
                    break

    # ── Location ────────────────────────────────────────────────────────
    # Match "City, State/Country" pattern
    loc_m = re.search(
        r'\b([A-Z][a-z]+(?:[\s\-][A-Z][a-z]+)*,\s*[A-Z][a-z]+(?:[\s\-][A-Z][a-z]+)*)\b',
        src_contact
    )
    if loc_m:
        result['location'] = loc_m.group(1)

    return result


def _extract_summary(sections: dict) -> str:
    """
    Return the summary/objective text.
    Falls back to the first long paragraph in the header if no summary section.
    """
    text = sections.get('summary', '')
    if text:
        lines = [l for l in text.splitlines() if not _is_section_header(l)]
        cleaned = '\n'.join(lines).strip()
        if cleaned:
            return cleaned[:700]

    # Fallback: find a long paragraph inside the header block
    header = sections.get('header', '')
    paragraphs = [p.strip() for p in re.split(r'\n{2,}', header) if len(p.strip()) > 80]
    if paragraphs:
        # Prefer a paragraph that doesn't look like a contact line
        for para in paragraphs:
            if not _EMAIL_RE.search(para) and not _PHONE_RE.search(para):
                return para[:700]
        return paragraphs[0][:700]

    return ''


def _extract_skills(text: str) -> tuple[list, dict]:
    """Returns (flat_list, categories_dict)."""
    if not text:
        return [], {}

    skills: list[str] = []
    categories: dict[str, list[str]] = {}
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    for line in lines:
        if _is_section_header(line):
            continue
        # "Category: skill1, skill2, skill3" — category name must be short (≤4 words)
        cat_m = re.match(r'^([A-Za-z][A-Za-z\s/&]{1,30}):\s*(.+)$', line)
        if cat_m and len(cat_m.group(1).split()) <= 4:
            cat_name = cat_m.group(1).strip()
            raw_skills = cat_m.group(2)
            cat_skills = [s.strip() for s in re.split(r'[,|•·]', raw_skills) if 1 < len(s.strip()) < 40]
            if cat_name and cat_skills:
                categories.setdefault(cat_name, []).extend(cat_skills)
                skills.extend(cat_skills)
                continue
        # Plain comma / bullet separated list
        for part in re.split(r'[,|•·]', line):
            part = re.sub(r'^[-•*·▪►]\s*', '', part.strip())
            if 1 < len(part) < 40 and not _DATE_RE.search(part):
                skills.append(part)

    # Deduplicate preserving order
    seen: set[str] = set()
    flat: list[str] = []
    for s in skills:
        key = s.lower()
        if key not in seen:
            seen.add(key)
            flat.append(s)

    return flat[:40], categories


def _split_into_entry_blocks(text: str) -> list[list[str]]:
    """
    Split a section's text into individual entry blocks.
    Tries blank-line splitting first; if that yields only one large block with
    multiple date lines, splits on each date-containing line as a new boundary.
    """
    if not text:
        return []

    raw_blocks: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            if current:
                raw_blocks.append(current)
                current = []
        else:
            if not _is_section_header(s):
                current.append(s)
    if current:
        raw_blocks.append(current)

    # If we got one giant block with many date lines, split on date lines
    if len(raw_blocks) == 1 and raw_blocks[0]:
        block = raw_blocks[0]
        date_indices = [i for i, l in enumerate(block) if _DATE_RE.search(l)]
        if len(date_indices) > 1:
            # Re-split: each new entry starts with the line just before its date
            # (the title line), typically 1 line before the date
            refined: list[list[str]] = []
            prev = 0
            for di in date_indices[1:]:
                # Entry starts 1-2 lines before the date
                start = max(prev, di - 2)
                refined.append(block[prev:start])
                prev = start
            refined.append(block[prev:])
            raw_blocks = [b for b in refined if b]

    return raw_blocks


def _extract_experience(text: str) -> list:
    if not text:
        return []

    entries: list[dict] = []
    for block in _split_into_entry_blocks(text):
        if not block:
            continue
        entry = {
            'title': '', 'company': '', 'start_date': '', 'end_date': '',
            'location': '', 'description': [],
        }

        # Find date line
        date_idx = next((i for i, l in enumerate(block) if _DATE_RE.search(l)), None)

        if date_idx is not None:
            date_line = block[date_idx]
            dates = _DATE_RE.findall(date_line)
            if len(dates) >= 2:
                entry['start_date'] = dates[0].strip()
                entry['end_date']   = dates[1].strip()
            elif dates:
                # Single date — decide if it's start or end
                if re.search(r'present|current|now', date_line, re.IGNORECASE):
                    entry['end_date'] = 'Present'
                    # Extract the year before "present"
                    yr = re.search(r'\d{4}', date_line)
                    if yr:
                        entry['start_date'] = yr.group()
                else:
                    entry['end_date'] = dates[0].strip()

            header_lines = [l for l in block[:date_idx] if l]
            if header_lines:
                entry['title']   = header_lines[0]
            if len(header_lines) > 1:
                entry['company'] = header_lines[1]
            if len(header_lines) > 2:
                entry['location'] = header_lines[2]

            desc_lines = [l for l in block[date_idx + 1:] if l]
        else:
            # No date line — assume first two lines are title/company
            if block:
                entry['title']   = block[0]
            if len(block) > 1:
                entry['company'] = block[1]
            desc_lines = block[2:]

        entry['description'] = [
            re.sub(r'^[-•*·▪►]\s*', '', l)
            for l in desc_lines
            if len(l.strip()) > 10
        ][:8]

        if entry['title'] or entry['company']:
            entries.append(entry)

    return entries[:8]


def _extract_education(text: str) -> list:
    if not text:
        return []

    degree_re = re.compile(
        r'\b(bachelor|master|b\.?s\.?|m\.?s\.?|ph\.?d|b\.?tech|m\.?tech'
        r'|b\.?e\.?|m\.?e\.?|m\.?c\.?a\.?|b\.?c\.?a\.?'
        r'|associate|diploma|certificate|high\s+school|secondary)\b',
        re.IGNORECASE
    )
    gpa_re = re.compile(r'\b(?:gpa|cgpa|grade|percentage)[\s:]+(\d[\d.]+)', re.IGNORECASE)
    entries: list[dict] = []

    for block in _split_into_entry_blocks(text):
        entry = {
            'institution': '', 'degree': '', 'field': '',
            'start_date': '', 'end_date': '', 'gpa': '',
        }
        for line in block:
            if degree_re.search(line) and not entry['degree']:
                entry['degree'] = line
            elif _DATE_RE.search(line):
                dates = _DATE_RE.findall(line)
                if len(dates) >= 2:
                    entry['start_date'], entry['end_date'] = dates[0].strip(), dates[1].strip()
                elif dates:
                    entry['end_date'] = dates[0].strip()
            else:
                m = gpa_re.search(line)
                if m:
                    entry['gpa'] = m.group(1)
                elif not entry['institution'] and len(line.split()) >= 2:
                    entry['institution'] = line

        if entry['degree'] or entry['institution']:
            entries.append(entry)

    return entries[:6]


def _extract_projects(text: str) -> list:
    if not text:
        return []

    url_re  = re.compile(r'https?://[\w\-./]+')
    tech_re = re.compile(
        r'\b(?:built\s+with|technologies?|tech(?:nology)?|stack|using|tools?)[\s:]+(.+)',
        re.IGNORECASE
    )
    entries: list[dict] = []

    for block in _split_into_entry_blocks(text):
        entry = {'name': '', 'description': '', 'technologies': [], 'url': ''}
        desc_lines: list[str] = []
        for i, line in enumerate(block):
            if i == 0:
                entry['name'] = line
                continue
            m = url_re.search(line)
            if m:
                entry['url'] = m.group()
            m = tech_re.search(line)
            if m:
                techs = [t.strip() for t in re.split(r'[,|]', m.group(1)) if t.strip()]
                entry['technologies'].extend(techs)
            else:
                clean = re.sub(r'^[-•*·▪►]\s*', '', line)
                if len(clean) > 5:
                    desc_lines.append(clean)
        entry['description'] = ' '.join(desc_lines[:4])
        if entry['name']:
            entries.append(entry)

    return entries[:8]


def _extract_list_section(text: str) -> list:
    """Generic extractor for certifications / achievements / languages."""
    if not text:
        return []
    items: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or _is_section_header(line):
            continue
        for part in re.split(r'[,|•·]', line):
            part = re.sub(r'^[-•*·▪►\d.)\s]+', '', part.strip())
            if len(part) > 3:
                items.append(part)
    return items[:20]


# ── Main analyzer ───────────────────────────────────────────────────────────────

class CVAnalyzer:
    """
    Analyze a CV using a section-based RAG approach.

        analyzer = CVAnalyzer(portfolio_id, ai_service_or_none)
        cv_data  = analyzer.analyze(raw_cv_text)
    """

    def __init__(self, portfolio_id: str, ai=None):
        self.portfolio_id = portfolio_id
        self.ai = ai

    # ------------------------------------------------------------------
    def analyze(self, raw_text: str) -> dict:
        # 1. Clean
        text = _clean_text(raw_text)

        # 2. Split into sections
        sections = _split_sections(text)
        detected = list(sections.keys())
        print(f'[CVAnalyzer] Detected sections: {detected}')

        # 3. Persist raw sections → MongoDB knowledge base
        CVSection.store(self.portfolio_id, {
            stype: {'raw_text': stxt, 'parsed': {}}
            for stype, stxt in sections.items()
        })

        # 4. Extract structured data
        cv_data = self._build_cv_data(sections)

        # 5. Persist parsed data back
        CVSection.store(self.portfolio_id, {
            stype: {'raw_text': stxt, 'parsed': cv_data}
            for stype, stxt in sections.items()
        })

        print(f'[CVAnalyzer] Result → name="{cv_data.get("name")}" '
              f'title="{cv_data.get("title")}" '
              f'exp={len(cv_data.get("experience", []))} '
              f'edu={len(cv_data.get("education", []))} '
              f'skills={len(cv_data.get("skills", []))}')
        return cv_data

    # ------------------------------------------------------------------
    def _build_cv_data(self, sections: dict) -> dict:
        # Always run regex extractors first (they are the guaranteed baseline)
        contact         = _extract_contact(sections)
        summary         = _extract_summary(sections)
        flat_skills, skill_cats = _extract_skills(sections.get('skills', ''))
        experience      = _extract_experience(sections.get('experience', ''))
        education       = _extract_education(sections.get('education', ''))
        projects        = _extract_projects(sections.get('projects', ''))
        certifications  = _extract_list_section(sections.get('certifications', ''))
        achievements    = _extract_list_section(sections.get('achievements', ''))
        languages       = _extract_list_section(sections.get('languages', ''))

        regex_result = {
            'name':             contact.get('name', ''),
            'title':            contact.get('title', ''),
            'email':            contact.get('email', ''),
            'phone':            contact.get('phone', ''),
            'location':         contact.get('location', ''),
            'linkedin':         contact.get('linkedin', ''),
            'github':           contact.get('github', ''),
            'website':          contact.get('website', ''),
            'summary':          summary,
            'skills':           flat_skills,
            'skill_categories': skill_cats,
            'experience':       experience,
            'education':        education,
            'projects':         projects,
            'certifications':   certifications,
            'achievements':     achievements,
            'languages':        languages,
        }

        # AI: one consolidated call, result overlays regex where AI has data
        if self.ai:
            ai_result = self._ai_extract(sections)
            if ai_result:
                for field, ai_val in ai_result.items():
                    # Only override regex value if AI produced something non-empty
                    has_value = (
                        (isinstance(ai_val, str)  and ai_val.strip()) or
                        (isinstance(ai_val, list) and ai_val) or
                        (isinstance(ai_val, dict) and ai_val)
                    )
                    if has_value:
                        regex_result[field] = ai_val
                # Always keep regex-extracted contact fields (AI may hallucinate these)
                for f in ('email', 'phone', 'linkedin', 'github', 'website'):
                    if contact.get(f):
                        regex_result[f] = contact[f]

        return regex_result

    # ------------------------------------------------------------------
    def _ai_extract(self, sections: dict) -> dict:
        """Single consolidated Gemini call. Returns {} on any failure."""
        try:
            return self.ai.parse_cv_sections(sections)
        except Exception as exc:
            print(f'[CVAnalyzer] AI extraction failed: {exc}')
            return {}
