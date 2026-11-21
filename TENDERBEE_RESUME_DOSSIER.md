# Professional Dossier & Resume Generation Input: Project TenderBee

This comprehensive document details your role, architectural contributions, engineering achievements, and technical implementations on **TenderBee**. It is structured in a high-density, structured format designed to serve directly as context/input for an AI resume builder or executive recruiter.

---

## 1. Candidate Persona & Role Identification

- **Recommended Resume Titles**: 
  - **Founding Full-Stack Architect & AI Systems Engineer**
  - **Lead Software Engineer — Distributed Systems & Document AI**
  - **Principal Backend & Applied AI Engineer**
- **Domain Specialization**: Intelligent Public Procurement, Document AI & OCR, Deterministic Rule Engines, Web Crawling/Autonomous Agents, Cryptographic Auditability, High-Throughput Distributed Systems.
- **Repository Track Record**: Authored 16,000+ lines of production Python & TypeScript code across 25+ major features, architecting the system end-to-end from monorepo inception to multi-portal production readiness.

---

## 2. Project Executive Overview (The "Elevator Pitch")

> **Project Name**: TenderBee  
> **Core Architectural Philosophy**: *"AI extracts. Deterministic rules decide. Official sources confirm."*  
> **Problem Solved**: Government and enterprise tender compliance is plagued by manual auditing errors, high bid disqualification rates, and AI hallucinations. TenderBee eliminates guesswork by pairing schema-constrained Document AI extraction with an immutable, pure-Python deterministic verification engine and live government registry validation.  
> **Scope**: Coverage across all **36 Indian States and Union Territories** (GePNIC, CPPP, GeM, State e-Procurement), supporting dual-mode tender inspection (sub-10ms skim vs. deep clause analysis) and tamper-evident cryptographic bid validation.

---

## 3. Technology & Skill Matrix (ATS Keywords)

| Domain | Technologies, Frameworks & Libraries |
| :--- | :--- |
| **Backend & APIs** | Python 3.12, Django 5.x, Django REST Framework (DRF), Pydantic v2, Celery, Redis, HTTPX, Asgiref, WSGI |
| **Frontend & UI** | Next.js 15 (App Router), React 19, TypeScript, Tailwind CSS, Lucide Icons, Soft UI / Neumorphism |
| **Document AI & OCR** | PyPDF, `pyHanko` (Digital Signatures / CMS / PKCS#7), Tesseract OCR, PyMuPDF, NFKC Normalization |
| **LLM & Agent Systems** | Google Gemini API (2.5/3.8 Flash), Schema-Constrained Structured Generation, TinyFish Autonomous Agent, Turnstile / CAPTCHA Bypass |
| **Databases & Storage** | Neon Serverless PostgreSQL (Dual pooled vs. direct migration connections), Cloudflare R2 / Backblaze B2 S3 API, SQLite3 Cache |
| **Security & Compliance** | Anti-SSRF URL Validators (CIDR private IP blocking), Prompt-Injection Detection, SHA-256 Merkle/Integrity Chaining, Immutable Audit Logs |
| **Testing & Reliability** | `pytest`, `pytest-django`, Golden Test Datasets, Seeded Defect Suites, Regression CI Gates (148+ tests, 0 false-pass tolerance) |

---

## 4. Key Architectural Pillars: "What I Did" & "How I Did It"

### Pillar 1: End-to-End Monorepo Architecture & Multi-Tenant Foundations
- **What I Did**: Bootstrapped and scaled TenderBee from scratch as a modular monorepo combining a high-throughput Django REST API backend with a Next.js 15 App Router frontend.
- **How I Did It**:
  - Designed decoupled service boundaries across `tenders`, `documents`, `rules`, `verify`, and `audit` apps.
  - Implemented dual-connection pooling for serverless PostgreSQL (Neon): pooled transaction connections (`DATABASE_URL`, `conn_max_age=0-60`) for auto-scaling HTTP workloads, paired with direct session strings (`DIRECT_URL`) for advisory lock migrations.
  - Built multi-tenant organization isolation (`org_id` scoping) across document vaults, tender discovery feeds, and audit trails.

### Pillar 2: All-India Government Tender Discovery & Scraping Engine
- **What I Did**: Architected a 4-tier scraper and discovery pipeline ingesting live tenders across all **36 Indian States & Union Territories** (41+ public platforms including GeM, CPPP, IREPS, and state portals).
- **How I Did It**:
  - Engineered the `UniversalTenderScraper` orchestrating dedicated adapters (`GeMAdapter`, `GePNICAdapter`, `DirectPDFDownloader`, and `TinyFishAutonomousAgent`).
  - Built an automated session-pooling manager (`PortalSessionPool`) and CAPTCHA solving engine with cookie lifecycle persistence.
  - Implemented Cloudflare Turnstile barrier detection, SSL resilience fallbacks, and anti-SSRF allowlisting (`.gov.in`, `.nic.in`, `.nprocure.com`) with strict private IPv4/IPv6 CIDR rejection.
  - Designed a high-speed tiered storage snapshot engine: cached hits return in `<10ms`, while cold tenders are scraped and snapshotted to Backblaze B2/Cloudflare R2.

### Pillar 3: Grounded Document AI & Anti-Hallucination Pipeline
- **What I Did**: Built an enterprise Document AI pipeline that converts messy, multi-page Indian tender PDFs and Notice Inviting Tenders (NITs) into validated, structured data with mathematical grounding.
- **How I Did It**:
  - Enforced the invariant: **Zero LLM Pass/Fail Decisions**. The LLM is strictly constrained to Pydantic-governed extraction (`TenderNoticeExtraction`, `TenderPDFExtractionResult`).
  - Invented the **Verbatim Grounding Gate**: Every AI-extracted field (financial turnover, EMD, liquidity, dates) must return a 1-indexed page number and an exact verbatim substring. Built an NFKC-normalized character matcher that validates quotes against raw PDF text, rejecting any ungrounded value.
  - Developed custom Indian financial format parsers capable of normalizing complex monetary notations (`Crore`, `Lakh`, `INR`, `₹`, comma grouping) into standardized floats.
  - Implemented UDIN (18-character ICAI Chartered Accountant identifier) and Udyam MSME registration format validators.
  - Deployed heuristic prompt-injection detectors screening incoming documents for prompt manipulation, jailbreaking, or role overrides before payload dispatch.

### Pillar 4: Deterministic Rules Engine & Cryptographic Freezing
- **What I Did**: Created an isolated, pure-Python deterministic compliance engine that automates bidder eligibility audits without runtime network or database dependencies.
- **How I Did It**:
  - Implemented the `RulePack` lifecycle: upon tender ingestion, draft rules (`R-DOC-UDYAM`, `R-TURNOVER-AVG3`, `R-EMD-EXEMPT`, etc.) are synthesized.
  - Engineered cryptographic freezing: when human auditors approve a rule pack, a SHA-256 digest is generated across all rule constraints, permanently locking it into `FROZEN` status to prevent post-intake tampering.
  - Enforced 4 discrete non-negotiable verification verdicts: `Pass`, `Fail`, `Discrepancy`, and `Incomplete` (eliminating silent failures).
  - Integrated `pyHanko` to cryptographically validate digital PKCS#7 signatures and certificate chains on uploaded bidder credentials.

### Pillar 5: Intelligent Search & Natural Language Query Engine
- **What I Did**: Engineered a multi-criteria search and discovery service capable of interpreting ambiguous user queries, messy state abbreviations, and direct tender IDs.
- **How I Did It**:
  - Implemented a multi-strategy query parser translating natural language prompts (e.g., *"roadways tender in jharkand above 10 cr"*) into typed `TenderSearchFilter` objects.
  - Built phonetic and typo-tolerant mapping for Indian states and cities (e.g., `"jharkand"` $\rightarrow$ `"Jharkhand"`, `"chattisgarh"` $\rightarrow$ `"Chhattisgarh"`, `"orissa"` $\rightarrow$ `"Odisha"`).
  - Added stem/plural keyword matching (`roadways` $\rightarrow$ `roadway`, `roads`, `road`) alongside exact Tender Number / RFQ ID lookups.
  - Engineered dual inspection modes: **Skim Mode** for instantaneous preview metadata and **Detailed Mode** which automatically triggers deep PDF acquisition, clause parsing, and rule-pack generation.

### Pillar 6: Modern Neumorphic UI & Interactive Evidence Workspace
- **What I Did**: Developed a responsive, modern frontend in Next.js 15 / TypeScript featuring a custom Soft UI (Neumorphism) design system and real-time auditability interfaces.
- **How I Did It**:
  - Designed the **Evidence Viewer Workspace**: split-screen interactive layout displaying parsed tender parameters on the left and direct highlighted citations/quotes on the right.
  - Built the **All-India State Portals Directory Modal**: giving users 1-click lookup access to 41+ national and state procurement platforms.
  - Engineered live intake progress bars, document vault uploaders, and readiness score metric cards.
  - Hardened frontend API consumers with trailing-slash auto-resolution, proxy loop breakers, and automatic fallback retries.

### Pillar 7: Test-Driven Reliability & CI Golden Dataset
- **What I Did**: Established an enterprise test suite of 148+ automated test cases with a 0-false-pass tolerance policy.
- **How I Did It**:
  - Built a "Golden Dataset" CI gate evaluating clean submissions, messy scans, and intentionally seeded defect cases (expired documents, forged certificates, turnover shortfalls).
  - Wrote comprehensive unit and integration tests across SSRF filters, OCR boundaries, prompt-injection scanners, and scraper circuit breakers.

---

## 5. Ready-to-Use Resume Bullet Points (STAR / Google XYZ Format)

*Agents/Resume Builders: Select from the bullet points below based on target job level.*

### Option Set A: For Founding Engineer / Lead Systems Architect Roles
- **Architected and scaled TenderBee**, an intelligent procurement compliance monorepo (Django REST Framework + Next.js 15 App Router) processing tender workflows across all **36 Indian States and Union Territories**.
- **Engineered a 4-pillar universal web scraping pipeline** featuring automated CAPTCHA solving, session pooling, and Cloudflare Turnstile barrier mitigation, achieving **<10ms cached tender lookups** and sub-second live ingestion across 41+ government platforms.
- **Pioneered an anti-hallucination Document AI framework** using Google Gemini and PyPDF; eliminated LLM compliance hallucinations by enforcing **0 LLM pass/fail decisions** and requiring **verbatim character-level quote grounding** against source PDFs.
- **Designed a pure-Python deterministic rules engine** operating with zero database/network latency, pairing automated draft `RulePack` synthesis with **SHA-256 cryptographic immutability hashing** to ensure audit-grade tamper resistance.
- **Implemented zero-trust security guardrails**, including anti-SSRF IPv4/IPv6 private CIDR filtering, PDF prompt-injection heuristic defenses, and `pyHanko` PKCS#7 digital signature verification.
- **Constructed a comprehensive 148+ test CI verification suite** containing golden and seeded-defect datasets, enforcing a strict **0-false-pass policy** on compliance audits.

### Option Set B: For Full-Stack / Backend & Applied AI Roles
- **Built an all-India e-procurement discovery engine** using Django and TypeScript, supporting natural language search, phonetic state/district normalization (e.g., handling spelling variants across 28 states), and dual-mode (*Skim* vs. *Detailed*) clause extraction.
- **Developed schema-constrained Document AI parsers** (Pydantic v2 + Gemini Flash) that reliably extract Indian tender thresholds (turnover in Crores/Lakhs, EMD, liquidity, UDINs) with 1-indexed page citations and NFKC string verification.
- **Configured serverless PostgreSQL (Neon) dual-connection topology**, decoupling connection-pooled web queries from direct-session migrations to handle serverless sleep/wake cycles seamlessly.
- **Created an interactive Next.js 15 compliance workspace** with soft-UI neumorphic design, featuring real-time document upload progress, evidence side-by-side citation inspection, and state portal directories.
- **Integrated multi-cloud S3 storage** (Backblaze B2 / Cloudflare R2) with local disk fallback caching, managing high-durability storage of raw PDFs, page crops, and tender snapshots.

---

## 6. Architecture & System Flow Diagrams (For Portfolio / Interviews)

### The 7-Stage End-to-End Pipeline
```text
[1. Upload & Integrity] ──► SHA-256 Digest & pyHanko Digital Signature Verification
         │
[2. Text & OCR Layer]   ──► PyPDF Digital Extraction + Tesseract Fallback + Heuristic Injection Filter
         │
[3. Document AI]        ──► Schema-Constrained Gemini Extraction (Pydantic, JSON Schema only)
         │
[4. Grounding Gate]     ──► Strict NFKC Verbatim Quote & Page Verification (Rejects Hallucinations)
         │
[5. Deterministic Rules]──► Pure-Python Compliance Engine (Turnover, MSME, EMD, UDIN)
         │
[6. Cryptographic Lock] ──► SHA-256 RulePack Freeze (Draft -> Frozen Audit Trail)
         │
[7. Verdict & Evidence] ──► Split-Screen UI with 4 Strict Outcomes: Pass, Fail, Discrepancy, Incomplete
```

---

## 7. Metrics & Tangible Engineering Impact Summary

- **Geographic & Portal Coverage**: 100% of Indian States & Union Territories (28 States, 8 UTs; 41+ platforms including GeM, CPPP, IREPS, State GePNIC portals).
- **Latency Performance**: **<10ms** for cached tender retrieval via SQLite/PostgreSQL snapshot cache; **sub-second** rule evaluation via pure-Python deterministic engine.
- **Model Hallucination Rate**: **0%** in compliance verdicts (guaranteed by isolating LLM strictly to entity extraction and enforcing character-level quote matching).
- **Codebase Scale**: **16,000+ lines** of production code authored; **148+ automated tests** maintaining high CI test coverage.
- **Security Posture**: Anti-SSRF private IP blocking, PDF prompt injection defense, SHA-256 tamper-evident integrity hashes, and PKCS#7 signature validation.
