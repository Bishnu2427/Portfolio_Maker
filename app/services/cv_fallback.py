"""
Regex-based CV extractor — used when Gemini is unavailable.
Guarantees real data in the portfolio even without AI.
"""
import re


def extract(cv_text: str) -> dict:
    data = {
        'name': '', 'title': '', 'email': '', 'phone': '', 'location': '',
        'linkedin': '', 'github': '', 'website': '',
        'summary': '', 'skills': [], 'skill_categories': {},
        'experience': [], 'education': [], 'projects': [],
        'certifications': [], 'languages': [], 'achievements': [],
    }

    lines = [l.strip() for l in cv_text.splitlines() if l.strip()]

    # ---- Contact fields ----
    email = re.search(r'[\w._%+-]+@[\w.-]+\.[a-zA-Z]{2,}', cv_text)
    if email:
        data['email'] = email.group()

    phone = re.search(
        r'(?:\+?\d[\d\s\-().]{7,}\d)',
        cv_text
    )
    if phone:
        data['phone'] = phone.group().strip()

    linkedin = re.search(r'linkedin\.com/in/[\w\-]+', cv_text, re.IGNORECASE)
    if linkedin:
        data['linkedin'] = 'https://' + linkedin.group()

    github = re.search(r'github\.com/[\w\-]+', cv_text, re.IGNORECASE)
    if github:
        data['github'] = 'https://' + github.group()

    website = re.search(r'https?://(?!linkedin|github)[\w\-./]+', cv_text, re.IGNORECASE)
    if website:
        data['website'] = website.group()

    # ---- Name: first short line that has no special chars ----
    for line in lines[:6]:
        if (
            2 <= len(line.split()) <= 5
            and not any(c in line for c in ['@', ':', '/', '|', '+'])
            and not re.search(r'\d{4}', line)
        ):
            data['name'] = line
            break

    # ---- Title: second candidate short line after name ----
    found_name = False
    for line in lines[:10]:
        if line == data['name']:
            found_name = True
            continue
        if found_name and 2 <= len(line.split()) <= 8 and not re.search(r'\d{4}', line):
            data['title'] = line
            break

    # ---- Summary: longest paragraph in the first 400 chars ----
    paragraphs = [p.strip() for p in re.split(r'\n{2,}', cv_text) if len(p.strip()) > 60]
    if paragraphs:
        data['summary'] = paragraphs[0][:600]

    # ---- Skills: lines containing comma-separated short words ----
    skill_section = re.search(
        r'(?:skills?|technologies|tech stack)[^\n]*\n(.*?)(?:\n\n|\Z)',
        cv_text, re.IGNORECASE | re.DOTALL
    )
    if skill_section:
        raw = skill_section.group(1)
        candidates = re.split(r'[,|•·\n]', raw)
        data['skills'] = [s.strip() for s in candidates if 1 < len(s.strip()) < 30][:30]

    # ---- Experience: blocks with date patterns ----
    date_pat = r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)?\s*\d{4}'
    exp_blocks = re.findall(
        rf'(.{{5,80}})\n(.{{5,120}})\n.*?({date_pat}.*?(?:{date_pat}|Present|Current))',
        cv_text, re.IGNORECASE | re.DOTALL
    )
    for block in exp_blocks[:6]:
        data['experience'].append({
            'title': block[0].strip(),
            'company': block[1].strip(),
            'start_date': '',
            'end_date': block[2].strip(),
            'location': '',
            'description': [],
        })

    # ---- Education ----
    edu_keywords = r'(?:bachelor|master|b\.?s\.?|m\.?s\.?|ph\.?d|b\.?tech|m\.?tech|degree|university|college|institute)'
    edu_matches = re.finditer(
        rf'({edu_keywords}.{{0,120}})',
        cv_text, re.IGNORECASE
    )
    for m in list(edu_matches)[:4]:
        data['education'].append({
            'institution': '',
            'degree': m.group(1).strip(),
            'field': '',
            'start_date': '',
            'end_date': '',
            'gpa': '',
        })

    return data
