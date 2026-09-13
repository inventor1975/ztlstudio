# ZTLStudio

**The AI translates; the measured core judges — truth is never granted on credit, not even to the translator.**

A local studio for judging **claims and paradoxes**. You state one in natural
language (any language); an LLM **only translates** it into ZFL, the formal
table language — it never judges. A deterministic, measured **ZTL core** does
the judging: verdicts with warranties, quarantine passports for self-referential
systems, and a deterministic **back-reading** that verbalizes exactly what the
core read from your table.

The pipeline embodies the logic it serves: the LLM's output is an **unverified
input** (the mark `Z`), and the core is the customs house — truth is never
granted on credit, not even to the translator.

```
human ──meta-chat──► the AI fills a ZFL table (rows + a claim), you sign off
                         │
                         ▼ validator ──► the deterministic core judges
                         ▼ back-reading (no AI — the second auditor)
                         ▼
                   verdict · warranty · passport · stipulations
```

## Run

```
python3 ztlstudio.py        # → http://localhost:8190
```

Python **stdlib only**; the ZTL core is vendored in `ztlcore/`, so a clone is
self-contained (no submodules, no dependencies). The AI is **optional**: with no
key the studio runs in **pro mode** — fill the ZFL table by hand. To enable AI
translation, open **⚙ Model**, pick a provider + model + key, or set the env
var, or drop a key into a local `.<provider>_key` file (all gitignored — **no
keys ship**).

## What you hand it: one table, no genre to declare

ZFL v2 is a single table of **rows** plus a **claim**. Each row states a fact,
its status (`T` verified / `F` refuted / `Z` unverified — the zero-trust
default), its ground, and — importantly — what it **means** in words (the
polarity auditor: it lets the back-reading catch an encoding that says the
opposite of what you intended). You never declare whether this is a "statement"
or a "paradox": **the genre is computed**, and whichever instruments apply fire
— a verdict + warranty for a claim, a passport for a self-referential system.

The studio ships **41 worked examples** — open one to see the exact shape of the
table, then edit it. The **back-reading** verbalizes what the core actually read,
so your translation is audited by a component that cannot hallucinate.

## The workflow

1. **Meta-chat** — describe the claim in your language; the AI fills the table's
   rows and asks only when formalization is genuinely blocked. It knows its
   boundary: arithmetic, quantities and numeric wordplay get an honest "does not
   formalize into propositional ZTL", never an invented encoding.
2. **The table** — a grid of rows, the grounds bar, and the claim line, all
   hand-editable (pros skip the chat entirely). **Run** validates and judges;
   validator issues are machine-readable and can be fed back to the AI to repair.
3. **The report** — the core's verdict, its **warranty grade** (hereditary /
   sound / until-verification), the passport of unverified inputs, and the
   completion table — followed by the deterministic back-reading and an optional
   AI explanation that **retells** the verdict and is forbidden to re-judge
   (labeled *unverified by definition*: the pipeline applies its own logic to
   itself).

## What the core reports

* **Claims** — the verdict (`T`/`F` — verdicts are always two-valued; `Z` is a
  mark on an *input*, never a verdict), the warranty grade, the passport of
  unverified inputs, and the completion table showing how the verdict behaves
  under every reading of the unverified rows.
* **Self-referential systems** — the grounded part (identical in every fixed
  point), the quarantine set, and a passport per component: PARADOX (no
  classical solution — permanent refusal, with the oscillation period),
  UNDERDETERMINED (refusal until stipulation), INPUT (until verification),
  DOWNSTREAM (inherited).

## Providers

Keys stay on this machine, read in order: the Settings field, the env var
(`GROQ_API_KEY`, `ANTHROPIC_API_KEY`, …), then a local `.<provider>_key` file.
Supported: **Groq, Anthropic (Claude), OpenAI, OpenRouter, DeepSeek, Gemini,
xAI, NVIDIA**. A stronger model formalizes cleaner; the core judges the same
regardless of who translated.

## Related

- **[ZTL](https://github.com/inventor1975/ZTL)** — the logic itself: the kernel,
  the papers, and the ZFL language.
- **[introspect](https://github.com/inventor1975/introspect)** — the same
  zero-trust core applied to code: a taint analyzer for seven languages.

## AI disclosure

Built by **Claude (Anthropic)** as architect and implementer, with **Vitaly
Reznik** as human curator and decision-maker, under a strict honesty discipline:
mark boundaries honestly, measure — don't guess, and never claim more than was
verified.

## License

Dual-licensed under **MIT** and **Apache-2.0** (see `LICENSE-MIT`,
`LICENSE-APACHE`).
