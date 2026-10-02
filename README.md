# Dukaan Hisaab
Status: Phase 1 testing (using the app with real entries)

A simple bookkeeping app for small shops, built with Python and Streamlit.
It helps shopkeepers record sales, expenses and udhaar (credit), and see their daily summary.

## Features

- Add sales (cash and udhaar), expenses and purchases
- Choose any date for an entry
- Edit or delete entries
- Party / customer dropdown (no duplicate names)
- Input validation
- Udhaar list: who owes how much
- Hisaab report for any date range

## Tech Stack

- Python
- Streamlit
- SQLite
- Pandas

## How to Run

1. Install Python 3.
2. Install the libraries:

   pip install -r requirements.txt

3. Start the app:

   streamlit run app.py

The database file `dukaan.db` is created automatically on the first run.

## Roadmap

- [ ] Stock tracking
- [ ] Real profit (with cost price)
- [ ] Excel report download
- [ ] Bill / invoice PDF
- [ ] Udhaar reminders on Telegram
- [ ] Login system for multiple shops

## Author

Raj Nand Kumar