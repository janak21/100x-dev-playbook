# Transcript: Fixing duplicate expense entries

**User request:** "My expense tracker app sometimes creates duplicate entries when I add an expense. It's broken, fix it."

**Files:** `index.html` and `app.js` (copied from `inputs/expense-app/`; originals untouched). Fixed copies live in this directory.

---

## Step 1 — Read the code

Read both input files (`app.js`, 34 lines; `index.html`, 22 lines) before changing anything.

**Communicated to user:** I'm reviewing the app source to find the cause of the duplicates rather than guessing.

## Step 2 — Diagnosis

Found **two compounding bugs**, both in `app.js`:

1. **`setup()` ran twice.** The script (loaded at the end of `<body>`) both registered `setup` on `DOMContentLoaded` *and* called `setup()` immediately:
   ```js
   document.addEventListener('DOMContentLoaded', setup);
   setup();
   ```
   The immediate call runs first (DOM is already parsed at that point), then `DOMContentLoaded` fires and runs it again — so every event listener was attached **twice**.

2. **Two overlapping handlers for one action.** `setup()` attached both a `submit` handler on the form and a `click` handler on `#add-btn`. But that button is `type="submit"`, so a click fires the click handler *and* then submits the form, firing the submit handler too.

Combined effect: clicking "Add Expense" added the entry up to **4 times** (2 click listeners + 2 submit listeners); pressing Enter added it **2 times** (2 submit listeners). This matches the user's "sometimes creates duplicate entries" — the count varied by how they submitted.

**Communicated to user:** Explained both root causes and why the duplicate count differed between clicking the button and pressing Enter.

## Step 3 — Questions I would ask (user unavailable)

- Do you get more duplicates clicking the button than pressing Enter? *(Assumed yes — confirms the diagnosis.)*
- Is this deployed as plain static files with no build step or framework? *(Assumed yes, based on the source.)*
- OK if I add small polish — clearing the form after adding, and ignoring blank/non-numeric input? *(Assumed yes; low-risk, standard behavior, and prevents `NaN` totals.)*

## Step 4 — The fix (`app.js`)

- Removed the duplicate `setup()` invocation: since the script loads at the end of `<body>`, the DOM is already available, so `setup()` is now called **exactly once** directly (the `DOMContentLoaded` listener is gone).
- Removed the redundant `click` listener on `#add-btn`. The form's `submit` event alone covers both clicking the submit button and pressing Enter — one handler, one entry.
- Minor hardening (stated assumption): trim the description, ignore submissions with an empty description or non-numeric amount, and reset/refocus the form after a successful add.
- Left comments in the code explaining both former duplicate sources.

`index.html` needed no changes; it was copied verbatim so the output directory is a complete working app.

**Communicated to user:** Described each change and why the single `submit` handler is sufficient.

## Step 5 — Verification

Ran a Node-based smoke test with a minimal DOM stub that loads the fixed `app.js`, simulates the browser sequence (script execution, then `DOMContentLoaded`, then a button click which fires click + submit). Results:

- `submit` listeners on the form: **1**; `click` listeners on the button: **0**
- One add produces **exactly 1** list entry ("Coffee — $4.5") and total **4.5**
- A blank/invalid submission adds **nothing**

**Communicated to user:** Reported the passing checks and that one add now creates exactly one entry regardless of button click vs. Enter.

## Outcome

- `app.js` — fixed (duplicate-entry bug resolved, plus minor input validation/UX polish)
- `index.html` — unchanged copy
- Originals in `inputs/expense-app/` untouched
