# PortfolioForge

> Turn your CV into a live, hosted portfolio site in minutes — powered by Gemini AI and deployed free on GitHub Pages.

---

## What It Does

PortfolioForge takes your resume, a professional photo, and your style preferences, then uses Gemini AI to build a stunning portfolio website. You get a live local preview, can refine it with natural language prompts, and deploy it to GitHub Pages with one click — completely free.

**Flow:**
```
Upload CV + Photo + Style + Prompt
        ↓
Gemini AI parses & enhances content
        ↓
Portfolio site generated from template
        ↓
Live preview on localhost (unique port)
        ↓
Modify with natural language prompts
        ↓
Deploy to GitHub Pages → yourname.github.io/repo
```

---

## Features

- **AI-Powered Content** — Gemini 1.5 Flash parses your CV, enriches descriptions, quantifies achievements, and groups skills
- **4 Portfolio Styles** — Professional, Modern (dark), Minimal, Creative
- **Real-Time Progress** — Server-Sent Events show each build step live
- **AI Modification** — Describe changes in plain English, AI rewrites the HTML
- **Port Management** — Each preview gets a unique port (5001, 5002…), all tracked in MongoDB
- **One-Click Deploy** — Pushes static files to GitHub and enables GitHub Pages
- **No Local Storage** — All portfolio data, port registry, and state stored in MongoDB

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Flask 3, Python |
| Database | MongoDB (via PyMongo) |
| AI | Google Gemini 1.5 Flash |
| CV Parsing | PyPDF2, python-docx |
| Deployment | PyGithub → GitHub Pages |
| Frontend | HTML, CSS, Vanilla JS |
| Templates | Jinja2 |

---

## Project Structure

```
Portfolio_Maker/
├── run.py                          # Entry point — starts app on port 5000
├── requirements.txt
├── .env.example                    # Environment variable template
│
├── app/
│   ├── __init__.py                 # Flask app factory
│   ├── config.py                   # Config from .env
│   ├── extensions.py               # PyMongo instance
│   │
│   ├── models/
│   │   ├── portfolio.py            # Portfolio document (CRUD)
│   │   └── port_registry.py       # Port allocation + logging
│   │
│   ├── routes/
│   │   ├── main.py                 # UI pages: /, /create, /preview/<id>
│   │   ├── portfolio.py            # GET /api/portfolio/list, /<id>
│   │   ├── process.py              # POST /upload, GET /generate (SSE), POST /modify
│   │   └── deploy.py               # POST /api/deploy/github
│   │
│   ├── services/
│   │   ├── cv_parser.py            # Extracts text from PDF / DOCX / TXT
│   │   ├── ai_service.py           # Gemini: parse_cv, polish_prompt, enhance_content, modify_portfolio
│   │   ├── portfolio_generator.py  # Renders Jinja2 template → writes index.html + app.py
│   │   ├── port_manager.py         # Allocates next free port from MongoDB registry
│   │   ├── preview_manager.py      # Spawns subprocess Flask server per portfolio
│   │   └── github_service.py       # Creates repo + pushes files + enables Pages
│   │
│   ├── templates/
│   │   ├── base.html
│   │   ├── index.html              # Landing page
│   │   ├── create.html             # 3-step creation wizard
│   │   └── preview.html            # Live iframe + sidebar editor
│   │
│   └── static/
│       ├── css/app.css             # Dark theme UI
│       └── js/
│           ├── create.js           # Upload, stepper, SSE progress
│           └── preview.js          # iframe, modification, deployment
│
├── portfolio_templates/            # Source templates (Jinja2)
│   ├── professional/               # Navy + gold, timeline layout
│   ├── modern/                     # Dark GitHub-style, card grid
│   ├── minimal/                    # White, editorial typography
│   └── creative/                   # Gradient hero, bold animations
│
├── generated_portfolios/           # Runtime — one folder per portfolio
│   └── {portfolio_id}/
│       ├── index.html              # Rendered portfolio (served + deployed)
│       ├── static/css/style.css
│       ├── static/images/profile.* # Profile photo copy
│       ├── app.py                  # Mini Flask server for preview
│       └── requirements.txt
│
└── uploads/                        # Temporary CV + photo uploads
```

---

## Setup

### 1. Prerequisites

- Python 3.10+
- MongoDB running locally (`mongod`)
- A [Gemini API key](https://aistudio.google.com/app/apikey)
- A GitHub [Personal Access Token](https://github.com/settings/tokens/new?scopes=repo) (for deployment)

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```env
SECRET_KEY=your-secret-key-here
MONGO_URI=mongodb://localhost:27017/portfolio_maker
GEMINI_API_KEY=your-gemini-api-key
GITHUB_TOKEN=ghp_your_optional_default_token
```

### 4. Start MongoDB

```bash
mongod
```

### 5. Run the App

```bash
python run.py
```

Open **http://localhost:5000**

---

## How Ports Work

The main app runs on **port 5000**. Every portfolio preview gets its own port, starting from **5001**, tracked in MongoDB:

```
Main App          → port 5000
Portfolio #1      → port 5001  (PID 12345)
Portfolio #2      → port 5002  (PID 12346)
...
```

Port assignments are logged to the console on every allocation:

```
========================================
  PORT REGISTRY LOG
  Main App   : port 5000
  Portfolio  : port 5001  (PID 12345)
  Portfolio  : port 5002  (PID 12346)
========================================
```

All port data lives in the `port_registry` MongoDB collection — no `port.txt` files.

---

## MongoDB Collections

| Collection | Purpose |
|---|---|
| `portfolios` | Portfolio documents — CV text, parsed data, style, status, paths, GitHub URLs |
| `port_registry` | Active port assignments — portfolio_id → port → PID |

---

## Portfolio Styles

| Style | Look | Best For |
|---|---|---|
| **Professional** | Navy/gold, serif fonts, timeline | Corporate, finance, law |
| **Modern** | Dark theme, blue accents, cards | Tech, engineering, SWE |
| **Minimal** | White, clean typography, two-column | Design, academia, writing |
| **Creative** | Gradient hero, bold Poppins, animations | Design, art, marketing |

---

## AI Pipeline

```
1. parse_cv(cv_text)
   └─ Extracts: name, title, contact, summary, skills,
      experience, education, projects, certifications

2. polish_prompt(user_prompt, style, cv_data)
   └─ Enhances the user's brief into a detailed AI instruction

3. enhance_content(cv_data, polished_prompt, style)
   └─ Rewrites summaries, quantifies experience,
      groups skills by category, deepens project descriptions

4. [on modify] modify_portfolio(current_html, prompt)
   └─ Applies targeted changes to the rendered HTML
```

---

## Deployment to GitHub Pages

1. In the preview sidebar, enter your **GitHub Personal Access Token**
2. Choose a **repository name** (e.g. `my-portfolio`)
3. Click **Deploy to GitHub Pages**

PortfolioForge will:
- Create the repository (or update if it exists)
- Push `index.html`, CSS, and images
- Enable GitHub Pages on the default branch
- Return your live URL: `https://yourusername.github.io/my-portfolio`

> Pages may take 1–2 minutes to go live after the first deploy.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Flask session secret |
| `MONGO_URI` | Yes | MongoDB connection string |
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `GITHUB_TOKEN` | No | Default GitHub token (can also be entered in UI) |

---

## License

MIT — free to use, modify, and deploy.
