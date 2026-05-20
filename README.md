# ◈ MapGen — Dynamic Mind Map Generator

> Upload any structured PDF → Claude extracts the knowledge structure → renders as an interactive mind map → shareable via URL.

Secured by **DAF (Dynamic Auth Framework)** — built on the Dynamic Password Protocol (DPP), CompCom 2019, Springer Nature.

**Live demo:** coming soon

---

## What it does

Upload a structured PDF (lecture notes, course slides, textbook chapters) and MapGen:

1. Extracts text and detects lecture/section boundaries
2. Sends content to Claude API for structured knowledge extraction
3. Renders an interactive mind map with three views:
   - **Concept View** — navigate by theme → sub-cluster → definition, keypoints, example, formula
   - **Lecture View** — browse by lecture with concepts and formulae
   - **Graph View** — radial force-directed graph of the full knowledge structure
4. Persists the map to Supabase, scoped to your user account
5. Generates a shareable URL

---

## Security

Authentication is handled by **DAF — Dynamic Auth Framework**, built on the Dynamic Password Protocol (DPP):

- Passwords have two parts: a **static** part you remember, and **dynamic** positions filled by live UTC time
- Example: register with `Botxxnetxx` → login at 21:30 UTC with `Bot21net30`
- A stolen password expires in **60 seconds by design**
- Passwords hashed with **Argon2id** (OWASP 2024 recommended)
- All comparisons use **hmac.compare_digest** (constant-time, timing-attack resistant)

Maps are stored in Supabase and scoped to `user_id` — users can only access their own maps.

---

## Tech stack

| Layer | Technology |
|---|---|
| App | Streamlit |
| Auth | DAF / DPP + Argon2id + Supabase |
| Extraction | Claude API (Anthropic) |
| Storage | Supabase (PostgreSQL) |
| Rendering | D3.js (radial force graph) |
| PDF parsing | pypdf |

---

## Project structure

```
mindmap-app/
├── app.py            ← Streamlit app — orchestrates everything
├── auth.py           ← DPP auth — login, register, session management
├── db.py             ← Single shared Supabase client
├── extractor.py      ← PDF → Claude → JSON schema
├── storage.py        ← Supabase CRUD — user-scoped map persistence
├── renderer.py       ← Schema + template → rendered HTML
├── template.html     ← Mind map UI with injection points
├── schema.sql        ← Run once in Supabase SQL Editor
└── requirements.txt
```

---

## Local setup

### 1. Clone and create virtual environment

```bash
git clone https://github.com/your-username/mindmap-app.git
cd mindmap-app
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create `.env`

```bash
touch .env
```

Add the following — no quotes, no spaces around `=`:

```
ANTHROPIC_API_KEY=sk-ant-...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=eyJ...
```

### 4. Set up Supabase table

Run `schema.sql` once in your Supabase SQL Editor:
`https://supabase.com/dashboard/project/your-project/sql`

### 5. Run

```bash
streamlit run app.py
```

---

## Streamlit Cloud deployment

1. Push repo to GitHub (`.env` is gitignored — never committed)
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repo, set `app.py` as the entry point
4. Add secrets under **Settings → Secrets**:

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "eyJ..."
```

---

## Works best with

- Lecture slide decks exported as PDF
- Structured course notes with clear headings
- Textbook chapters with section hierarchy

Not supported: scanned PDFs, password-protected files, image-only documents.

---

## Roadmap

- [ ] PPTX support
- [ ] User review and edit step before rendering
- [ ] Export to PDF
- [ ] Public map sharing with read-only access
- [ ] Multi-language support

---

## Research foundation

Authentication built on:

> **"Dynamic Password Protocol for User Authentication"**
> H. Channabasava & S. Kanthimathi
> PES Institute of Technology, Bangalore
> *Computational Intelligence and Communication Networks (CompCom) 2019*
> *Springer Nature — AISC 998, pp. 597–611*
> DOI: [10.1007/978-3-030-22868-2_43](https://doi.org/10.1007/978-3-030-22868-2_43)

---

## License

MIT — free to use, adapt, and share.
