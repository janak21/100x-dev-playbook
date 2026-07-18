# My Expense Tracker

A simple personal expense tracker that runs entirely in your web browser.
No installation, no account, no internet connection needed.

## How to use it

1. Open the `expense-tracker` folder.
2. Double-click `index.html` — it opens in your browser (Chrome, Safari, Edge, Firefox all work).
3. That's it. Bookmark the page so it's one click away next time.

## What it does

- **Add expenses** with an amount, category, date (defaults to today), and an optional note.
- **Monthly summary** — pick any month and see the total plus a per-category breakdown with bars.
- **Expense list** — all expenses for the selected month, newest first, with a Delete button on each.
- **Export CSV** — downloads all your expenses as a file you can open in Excel or Google Sheets.

## Where is my data stored?

In your browser's local storage, on your computer. Nothing is sent anywhere.

Two things to know:

- Your data lives in **one browser on one computer**. If you open the file in a different
  browser (or use private/incognito mode), you'll see an empty tracker.
- If you ever **clear your browser's site data/history**, your expenses could be deleted.
  Use the **Export CSV** button now and then as a backup.

## Small customizations (safe to try)

Open `index.html` in any text editor (TextEdit, Notepad):

- **Change the currency:** find the line `var CURRENCY = "₹";` and replace the value,
  e.g. `var CURRENCY = "$";`
- **Change the categories:** find the `<select id="category">` section near the top and
  add or edit the `<option>` lines.

Save the file and refresh the page in your browser.
