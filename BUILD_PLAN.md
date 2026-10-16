# ReqGuard — Build Plan (Claude Code-এর সাথে ধাপে ধাপে)

**কীভাবে ব্যবহার করবে**
- `CLAUDE.md` আর এই ফাইল দুটো repo-র root-এ রাখো। Claude Code প্রতিটা session-এর শুরুতে `CLAUDE.md` নিজে থেকেই পড়ে।
- প্রতিটা ধাপ আলাদা session-এ করো। শুরুতে **Plan mode** চালু করো (Shift+Tab)। Claude-কে আগে plan দেখাতে দাও, plan ঠিক থাকলে approve করো।
- প্রতিটা ধাপের নিচে দেওয়া **Prompt** হুবহু copy করে দাও।
- কাজ শেষ হলে **"Done when"** তালিকা নিজে মিলিয়ে দেখো, তারপর commit করো।
- একসাথে একটার বেশি ধাপ দিও না। কোথাও ভুল হলে ওই ধাপেই ঠিক করে তারপর পরের ধাপে যাও।
- M-1 = Zinain, M-2 = Touhidul। দুজন আলাদা branch-এ কাজ করে সপ্তাহ শেষে merge করবে।

---

## Step 0 — Account আর key জোগাড় (Day 1, দুজন মিলে, Claude লাগবে না)

| কী লাগবে | কোথা থেকে | `.env`-এ কী রাখবে |
|---|---|---|
| GitHub repo (`reqguard`) | github.com | — |
| Supabase project (Postgres + pgvector চালু) | supabase.com, free plan | `DATABASE_URL` |
| LLM API key | যেটা তোমাদের কাছে আছে (Anthropic / OpenAI / Gemini) | `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY` |
| Jira Cloud site (free) + API token | atlassian.com → account settings → API tokens | `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` |
| Slack workspace + Slack app (bot token; scope: `channels:history`, `channels:read`) | api.slack.com/apps | `SLACK_BOT_TOKEN` |
| Telegram bot | Telegram-এ @BotFather; bot-এর privacy mode বন্ধ রাখো যাতে group-এর message পড়তে পারে | `TELEGRAM_BOT_TOKEN` |
| Discord bot (Message Content intent চালু) | discord.com/developers | `DISCORD_BOT_TOKEN` |
| Google Cloud project, Gmail API, OAuth client (test mode, নিজেদের test user হিসেবে যোগ করো) | console.cloud.google.com | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` |
| GitHub token (repo read, PR comment) | GitHub → Developer settings | `GITHUB_TOKEN` |

Demo data-ও বানিয়ে রাখো: Jira-তে একটা project, Slack-এ `#client-acme` channel, Telegram আর Discord-এ একটা group, আর WhatsApp-এর একটা নমুনা chat export। সবগুলোতে একটা কাল্পনিক client-এর কথা লিখবে, যার মধ্যে ইচ্ছা করে অস্পষ্ট, duplicate আর দ্বন্দ্বপূর্ণ requirement রাখবে।

Local-এ install করো: Python 3.11, Node 20, Git, VS Code + Claude Code।

---

## Step 1 — Project skeleton (Week 1, M-1 backend + M-2 frontend)

**Prompt:**
```
Read CLAUDE.md. Create the monorepo skeleton exactly as in "Repository layout".
Backend: FastAPI app with /health, settings from env (pydantic-settings), SQLAlchemy 2 + Alembic connected to DATABASE_URL, pytest set up with one passing test. Add .env.example with every variable from BUILD_PLAN Step 0, and .gitignore.
Frontend: Next.js App Router + TypeScript + Tailwind, a simple layout with sidebar (Projects, Sources, Messages, Requirements, Test Cases, Tasks, Repository, Traceability, Analysis, Reports) and lib/api.ts that calls the backend URL from NEXT_PUBLIC_API_URL.
Do not implement features yet. Show me the plan first.
```
**Done when:** `uvicorn` চালালে `/health` থেকে ok আসে, `pytest` pass করে, `npm run dev`-এ sidebar দেখা যায়।

---

## Step 2 — Auth, project, team (Week 1, M-1)

**Prompt:**
```
Implement: User (name, email, password_hash), Project, TeamMember (project_id, name, email, skills: list[str], role: lead|developer|qa). 
JWT auth: register, login, me. Project CRUD (owner only). Team member CRUD inside a project.
Alembic migration, Pydantic schemas, routers, and pytest tests for auth and project access rules.
Frontend: login/register pages, project list/create page, team page where skills are entered as tags.
```
**Done when:** register → login → project তৈরি → team member যোগ, পুরোটা UI থেকে কাজ করে, আর test pass করে।

---

## Step 3 — Unified message model + file/export upload (Week 1, M-2)

**Prompt:**
```
Implement the unified Message model from CLAUDE.md rule 1 (source, external_id, channel, author, sent_at, text, raw JSON, project_id) and a Source model (project_id, type, display_name, config JSON without secrets, last_synced_at).
Write connectors/base.py with a Connector interface: fetch(since) -> list[NormalizedMessage].
Implement parsers (no network): 
- whatsapp_export.py: parse WhatsApp "Export chat" .txt (handle both "dd/mm/yy, hh:mm - Name: text" and "[dd/mm/yy, hh:mm:ss] Name: text" formats, multi-line messages, skip "<Media omitted>").
- messenger_export.py: parse Facebook "Download your information" messages JSON (fix the mojibake latin-1/utf-8 encoding of text).
- files.py: .eml (subject + body, strip quoted replies) and .txt/.md meeting notes (one message per paragraph).
API: POST /projects/{id}/uploads (multipart), GET /projects/{id}/messages with filters (source, author, date, text search). De-duplicate by (source, external_id).
Add fixture files and pytest tests for each parser.
Frontend: Sources page with upload box, Messages page with a table and filters.
```
**Done when:** নমুনা WhatsApp, Messenger আর .eml ফাইল upload করলে Messages page-এ সব message ঠিকভাবে দেখা যায়।

---

## Step 4 — API connectors (Week 1, M-1: Jira, Slack, Gmail · M-2: Telegram, Discord)

**Prompt (M-1):**
```
Implement connectors using the Connector interface:
- jira.py: Jira Cloud REST API v3 with email + API token; import issues (summary + description) and comments of a chosen project key; convert Atlassian Document Format to plain text.
- slack.py: Slack Web API conversations.list and conversations.history (+ replies) for selected channels; handle pagination and rate limits.
- gmail.py: OAuth web flow (store refresh token encrypted in DB), list threads by a search query chosen by the user (e.g. from:client@x.com), import messages as plain text.
API: POST /projects/{id}/sources (create with type + settings), POST /sources/{id}/sync, GET /sources/{id}/status. Tokens come from env or encrypted DB fields, never returned to the frontend.
Mock all HTTP in tests (use respx or responses) with saved sample JSON.
Frontend: "Connect" cards for Jira, Slack, Gmail with a Sync button and last-synced time.
```
**Prompt (M-2):**
```
Implement connectors using the Connector interface:
- telegram.py: Telegram Bot API getUpdates (store last update_id) to import messages from groups where the bot is added.
- discord.py: Discord REST API: list channels of a guild and fetch channel messages with pagination (bot token, Message Content intent).
Same API endpoints and rules as the other connectors. Mock HTTP in tests.
Frontend: "Connect" cards for Telegram and Discord.
```
**Done when:** demo Jira, Slack, Telegram, Discord আর Gmail থেকে Sync চাপলে message আসে, আর দ্বিতীয়বার Sync করলে duplicate হয় না।

---

## Step 5 — LLM client + requirement extraction & classification (Week 2, M-1)

**Prompt:**
```
Create app/ai/llm.py: provider-agnostic client (LLM_PROVIDER/LLM_MODEL/LLM_API_KEY), function complete_json(prompt_name, variables, schema: type[BaseModel]) that loads app/ai/prompts/<name>.md, asks for JSON only, validates with Pydantic, retries once, logs tokens and latency.
Requirement extraction pipeline in app/nlp/extraction.py:
1. Split messages into sentences with spaCy.
2. Cheap filter: drop greetings/small talk with rules.
3. Send candidate sentences in batches (with neighbouring context) to the LLM prompt "extract_requirements": returns for each requirement: statement (rewritten as "The system shall ..."), type (functional / non-functional + subtype like performance, security, usability), actor, source_sentence, message_id, confidence.
4. Store Requirement (project_id, code like REQ-001, status=suggested, origin=ai) + RequirementVersion + RequirementSource links.
Also add a scikit-learn baseline classifier (TF-IDF + LogisticRegression) trained on eval/data/promise_nfr.csv for functional vs non-functional, used to compare with the LLM in evaluation.
API: POST /projects/{id}/requirements/extract (runs on new messages only), GET list, PATCH edit (creates a new version), POST accept/reject/merge.
Tests with a fake LLM client.
```
**Done when:** Extract চাপলে requirement-এর তালিকা আসে। প্রতিটার পাশে client-এর আসল লাইন দেখা যায়, আর edit করলে নতুন version তৈরি হয়।

## Step 6 — Requirement review screen (Week 2, M-2)

**Prompt:**
```
Frontend Requirements page: table with code, statement, type, status, confidence; side panel showing source messages (highlight the source sentence), version history diff, buttons Accept / Edit / Reject / Merge. Filters by status and type. Colour badges: AI-suggested vs user-confirmed.
```
**Done when:** প্রতিটা requirement-এর উৎস, version আর status UI-তে পরিষ্কার দেখা যায়।

---

## Step 7 — Requirement validation (Week 3, M-1)

**Prompt:**
```
Implement app/nlp/validate.py producing ValidationFinding(requirement_id, kind, severity, reason, evidence, related_requirement_id?):
- vague: lexicon of vague terms (fast, easy, user-friendly, many, some, flexible, etc. — keep the list in a yaml file) + LLM confirmation that the term has no measurable value.
- missing_info: LLM checks for missing actor, trigger, condition, limit/number, or error behaviour.
- duplicate: sentence-transformers cosine similarity >= 0.85 between requirements.
- conflict: for pairs with similarity >= 0.6, run the NLI model; contradiction score >= 0.7 → possible conflict; LLM writes the explanation.
- out_of_scope: compare with the project scope text and module list (new Project fields: scope_text, modules: list of {name, description}); low similarity to all modules + LLM check → possible extra work.
- module_alignment: assign best-matching module with score, or "no matching module".
Store findings; re-run only for changed requirements. Unit tests for each rule with small examples (fake LLM).
API: POST /projects/{id}/requirements/validate, GET findings.
```
**Done when:** demo data-র ইচ্ছা করে রাখা অস্পষ্ট, duplicate আর দ্বন্দ্বপূর্ণ requirement-গুলো ধরা পড়ে, আর প্রতিটা finding-এর কারণ লেখা থাকে।

## Step 8 — Clarification questions, approval, test cases (Week 3, M-2)

**Prompt:**
```
1. Clarification: LLM prompt "clarification_questions" turns findings into short, polite client questions (one per issue). Model ClarificationQuestion(requirement_id, text, status: draft|sent|answered, answer, answered_at). UI to edit, mark as sent, copy text, and record the client's answer; recording an answer asks the LLM to propose an updated requirement version which the lead accepts or edits.
2. Approval: only users with role lead can approve; approved requirements are locked unless a new version is created.
3. Test cases: LLM prompt "test_cases" for each approved requirement → acceptance criteria list + test cases (title, type positive/negative/boundary, Given, When, Then, linked criterion). Store with origin=ai, editable. Export approved requirements + test cases as DOCX/PDF and CSV.
Frontend pages: Clarifications, Test Cases.
```
**Done when:** একটা requirement অস্পষ্ট থেকে শুরু করে প্রশ্ন, উত্তর, approval হয়ে Given/When/Then test case পর্যন্ত পুরো পথটা UI থেকে করা যায়।

---

## Step 9 — Grouping & assignment (Week 4, M-2)

**Prompt:**
```
Group approved requirements: use the module from validation; inside large modules cluster with embeddings (AgglomerativeClustering, distance threshold) and let the LLM name each group.
Assignment suggestion: score = skill match (embedding similarity between group text and member skills) + workload balance (open tasks count). Return top 2 members with the reason. Lead confirms or changes. Create Task(group_id, requirement_ids, assignee_id, status). Optional: "Push to Jira" creates Jira issues for confirmed tasks.
Frontend Tasks page: board grouped by module, suggested assignee with reason, confirm/change.
```
**Done when:** group আর assignee-র প্রস্তাব আসে কারণসহ, আর lead এক click-এ confirm করতে পারে।

## Step 10 — Repository analysis & trace links (Week 4, M-1)

**Prompt:**
```
Part B start. Connect a GitHub repo (public or private with GITHUB_TOKEN), clone/fetch with GitPython to a cache dir.
Parser with Python ast: files, functions/classes (name, signature, docstring, line range, code), imports → import graph, and test functions (pytest naming) with their asserts.
Embeddings (sentence-transformers) for code chunks and tests stored in pgvector.
Trace link recovery: for each acceptance criterion retrieve top-k functions and tests by vector search, then LLM prompt "verify_link" keeps only real links with confidence and a one-line reason. TraceLink(requirement/criterion, target type code|test, target id, confidence, origin, status).
API + Traceability page: matrix (requirements × code × tests), accept/reject links, highlight requirements with no code or no test.
```
**Done when:** demo repo-তে matrix দেখা যায়, link accept বা reject করা যায়, আর যে requirement-এর test নেই সেটা আলাদা রঙে দেখায়।

---

## Step 11 — Change, drift, criterion test check, risk rules (Week 5, M-1)

**Prompt:**
```
Analysis run between two commits (base, head):
- diff: added/modified/deleted files and functions; dependency file changes (requirements.txt, pyproject.toml).
- impact: affected components via the import graph (reverse dependencies, depth 2).
- drift rules (deterministic): R1 requirement version changed after base but linked code/tests unchanged; R2 linked code changed but requirement and tests unchanged.
- criterion test check: for each affected acceptance criterion, LLM prompt "criterion_check" reads the linked test code and answers verified / not verified / not enough information, quoting the test lines.
- risk rules: test gap, drift, dependency change, critical module change (modules marked critical), traceability gap.
Finding(category, severity, evidence_path like REQ-17 → reset_password() → test_link_expiry(), recommended_check, origin rule|ai).
Unit tests for all rules with a tiny sample repo in tests/fixtures.
```
**Done when:** দুটো commit বেছে নিলে finding আসে, প্রতিটার সাথে evidence path থাকে।

## Step 12 — Report, PDF, PR comment (Week 5, M-2)

**Prompt:**
```
Report builder: status summary (counts by severity), affected requirements, findings with evidence, open clarifications, requirements without tests, recommended checks; LLM writes a short plain-language summary using only stored findings (prompt "report_summary").
Dashboard Report page + PDF export (WeasyPrint or react-pdf).
GitHub Action in .github/workflows/reqguard.yml (in the analysed repo) that calls POST /analysis/run for the PR's base/head and posts the report summary as a PR comment using GITHUB_TOKEN.
Impact graph view with React Flow.
```
**Done when:** PDF download হয়, আর demo repo-তে PR খুললে comment আসে।

---

## Step 13 — Evaluation (Week 5–6, দুজন)

**Prompt:**
```
Create eval/:
- data/promise_nfr.csv (we will add the file), data/conversations/*.json (20 client conversations we write, each with gold labels: requirements and issues vague/missing/duplicate/conflict/out_of_scope).
- scripts/eval_extraction.py: precision/recall/F1 of extracted requirements vs gold (match by embedding similarity >= 0.8 + manual check list).
- scripts/eval_validation.py: P/R/F1 per issue kind; baselines: keyword-only rules, and a single LLM prompt without the pipeline.
- scripts/eval_classification.py: F1 on PROMISE NFR for LLM vs TF-IDF baseline.
- scripts/eval_partB.py: fault injection on 8–10 small repos (remove a test, change requirement only, change code only, change dependency); P/R per fault type vs changed-files heuristic and LLM-diff-only baseline.
- results/*.csv and a matplotlib chart per table.
```
নিজেদের কাজ: ২০টা conversation লেখা আর হাতে label করা, আর generated প্রশ্ন ও test case-এর একটা sample মানুষ দিয়ে rate করানো (useful / partly / not)।

**Done when:** `results/`-এ সব table আর chart তৈরি হয়ে গেছে, যেগুলো report-এ বসানো যাবে।

---

## Step 14 — Testing, deploy, demo (Week 6)

**Prompt:**
```
1. Run all tests, fix failures, add missing tests for rules and parsers (target: all rules covered).
2. Add seed script that loads the demo project (messages, requirements, repo) for the presentation.
3. Deploy: backend to Render/Railway (Dockerfile, env vars, Alembic upgrade on start), frontend to Vercel. Update README with setup, env vars, and screenshots.
```
**Demo script (৫ মিনিট):** Slack আর WhatsApp থেকে message আনা → requirement extract → validation-এ "fast" আর conflict ধরা পড়া → client-কে প্রশ্ন আর উত্তর → approve → test case → assign → repo-তে link → code বদলে PR → drift finding আর report।

---

## সাপ্তাহিক সারসংক্ষেপ

| Week | M-1 (Zinain) | M-2 (Touhidul) |
|---|---|---|
| 1 | Step 1 backend, Step 2, Step 4 (Jira, Slack, Gmail) | Step 1 frontend, Step 3, Step 4 (Telegram, Discord) |
| 2 | Step 5 | Step 6 |
| 3 | Step 7 | Step 8 |
| 4 | Step 10 | Step 9 |
| 5 | Step 11 | Step 12 |
| 6 | Step 13–14 | Step 13–14 |

## Claude Code ব্যবহারের টিপস
- বড় কাজ শুরুর আগে Claude-কে বলো: "show me the plan first"।
- প্রতিটা ধাপ শেষে Claude-কে বলো: "run the tests and summarise what changed"। তারপর diff নিজে দেখে commit করো।
- `.env` কখনো commit করবে না। ভুল করে করে ফেললে সাথে সাথে key বদলে ফেলো।
- কোনো API কাজ না করলে Claude-কে আসল error message-টা paste করে দাও, অনুমান করতে দিও না।
- Report লেখার সময় sir-এর সতর্কবার্তা মনে রেখো। Code Claude লিখতে পারে, কিন্তু report-এর লেখা নিজেদের ভাষায় লিখতে হবে।
