import sqlite3
from datetime import date

import pandas as pd
import streamlit as st

DB = "dukaan.db"

KINDS = {
    "sale_cash": "Cash sale",
    "sale_udhaar": "Udhaar sale",
    "payment_received": "Udhaar ka paisa mila",
    "expense": "Kharcha",
    "purchase": "Maal kharida",
}
NEEDS_PARTY = {"sale_udhaar", "payment_received"}
NO_PARTY = "(koi nahi)"
NEW_PARTY = "+ Nayi party"


# ---------- Database ----------
@st.cache_resource
def get_conn():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS txns(
            id INTEGER PRIMARY KEY, date TEXT, kind TEXT,
            party TEXT, amount REAL, note TEXT)"""
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS parties(name TEXT PRIMARY KEY COLLATE NOCASE)"
    )
    # Purani entries ke party naam bhi parties list mein le aao
    conn.execute(
        """INSERT OR IGNORE INTO parties(name)
           SELECT DISTINCT TRIM(party) FROM txns
           WHERE party IS NOT NULL AND TRIM(party) != ''"""
    )
    conn.commit()
    return conn


conn = get_conn()


def clean_name(s):
    return " ".join((s or "").split()).title()


def party_list():
    return [r[0] for r in conn.execute("SELECT name FROM parties ORDER BY name")]


def add_party(name):
    """Party save karo aur jo naam database mein hai wahi wapas do (Ramesh/ramesh ek hi)."""
    name = clean_name(name)
    if not name:
        return ""
    conn.execute("INSERT OR IGNORE INTO parties(name) VALUES (?)", (name,))
    conn.commit()
    return conn.execute("SELECT name FROM parties WHERE name = ?", (name,)).fetchone()[0]


def load():
    return pd.read_sql("SELECT * FROM txns ORDER BY date DESC, id DESC", conn)


def party_baaki(party):
    d = load()
    d = d[d.party.fillna("").str.lower() == party.lower()]
    diya = d[d.kind == "sale_udhaar"].amount.sum()
    mila = d[d.kind == "payment_received"].amount.sum()
    return diya - mila


# ---------- Entry form (naya aur edit dono ke liye) ----------
def entry_inputs(key, d=None):
    """Entry ke input widgets dikhao. d = purani entry (edit ke time). Values wapas do."""
    d = d or {}
    c1, c2 = st.columns(2)
    dt = c1.date_input(
        "Date",
        value=pd.to_datetime(d["date"]).date() if d.get("date") else date.today(),
        max_value=date.today(),
        key=f"{key}_date",
    )
    kind_keys = list(KINDS)
    kind = c2.selectbox(
        "Kya hua?",
        kind_keys,
        index=kind_keys.index(d["kind"]) if d.get("kind") in KINDS else 0,
        format_func=lambda k: KINDS[k],
        key=f"{key}_kind",
    )

    parties = party_list()
    options = [NO_PARTY] + parties + [NEW_PARTY]
    cur = (d.get("party") or "").strip()
    if cur and cur in parties:
        idx = options.index(cur)
    else:
        idx = 0
    choice = st.selectbox("Party / Customer", options, index=idx, key=f"{key}_party")
    party = ""
    if choice == NEW_PARTY:
        party = st.text_input("Nayi party ka naam", key=f"{key}_newparty")
    elif choice != NO_PARTY:
        party = choice

    amount = st.number_input(
        "Amount (Rs)",
        min_value=0.0,
        step=10.0,
        value=float(d.get("amount", 0.0)),
        key=f"{key}_amount",
    )
    note = st.text_input("Note", value=d.get("note") or "", key=f"{key}_note")
    return dt, kind, party, amount, note


def validate(dt, kind, party, amount, edit_id=None):
    """Errors ki list wapas do. Khali list = sab theek."""
    errors = []
    if amount <= 0:
        errors.append("Amount 0 se zyada hona chahiye.")
    if dt > date.today():
        errors.append("Aage ki date nahi daal sakte.")
    if kind in NEEDS_PARTY and not party.strip():
        errors.append("Udhaar ya payment ke liye party ka naam zaruri hai.")
    if len(party) > 50:
        errors.append("Naam 50 akshar se chhota rakho.")
    return errors


# ---------- Pages ----------
st.set_page_config(page_title="Dukaan ka Hisaab", page_icon="📒")
st.title("Meri Dukaan ka Hisaab")
page = st.sidebar.radio(
    "Menu",
    ["Nayi entry", "Entries (edit/delete)", "Hisaab", "Udhaar list", "Parties"],
)

if "ver" not in st.session_state:
    st.session_state.ver = 0
if "msg" in st.session_state:
    st.success(st.session_state.pop("msg"))

# ----- 1. Nayi entry -----
if page == "Nayi entry":
    st.subheader("Nayi entry")
    key = f"new{st.session_state.ver}"  # save ke baad form khali ho jaye
    dt, kind, party, amount, note = entry_inputs(key)
    if st.button("Save", type="primary"):
        errors = validate(dt, kind, party, amount)
        if errors:
            for e in errors:
                st.error(e)
        else:
            if party.strip():
                party = add_party(party)
            if kind == "payment_received" and amount > party_baaki(party):
                st.warning(
                    f"Dhyan do: {party} ka baaki sirf Rs {max(party_baaki(party), 0):,.0f} tha, "
                    "payment usse zyada hai. Entry save ho gayi."
                )
            conn.execute(
                "INSERT INTO txns(date,kind,party,amount,note) VALUES (?,?,?,?,?)",
                (str(dt), kind, party, amount, note.strip()),
            )
            conn.commit()
            st.session_state.ver += 1
            st.session_state.msg = f"Entry save ho gayi: {KINDS[kind]} Rs {amount:,.0f}"
            st.rerun()

# ----- 2. Edit / Delete -----
elif page == "Entries (edit/delete)":
    st.subheader("Entries dekho, badlo ya hatao")
    d = load()
    if d.empty:
        st.info("Abhi koi entry nahi hai.")
    else:
        f1, f2 = st.columns(2)
        search = f1.text_input("Party ka naam dhundo")
        kind_filter = f2.selectbox(
            "Type", ["Sab"] + list(KINDS), format_func=lambda k: k if k == "Sab" else KINDS[k]
        )
        if search:
            d = d[d.party.fillna("").str.contains(search, case=False)]
        if kind_filter != "Sab":
            d = d[d.kind == kind_filter]

        show = d.copy()
        show["kind"] = show["kind"].map(KINDS)
        st.dataframe(show, hide_index=True)

        if d.empty:
            st.info("Is filter mein koi entry nahi mili.")
        else:
            st.markdown("---")
            labels = {
                int(r.id): f"#{r.id} | {r.date} | {KINDS.get(r.kind, r.kind)} | "
                f"{r.party or '-'} | Rs {r.amount:,.0f}"
                for r in d.itertuples()
            }
            eid = st.selectbox(
                "Kaun si entry badalni hai?", list(labels), format_func=lambda i: labels[i]
            )
            row = d[d.id == eid].iloc[0].to_dict()
            dt, kind, party, amount, note = entry_inputs(f"edit{eid}", row)

            b1, b2 = st.columns(2)
            if b1.button("Badlav save karo", type="primary"):
                errors = validate(dt, kind, party, amount, edit_id=eid)
                if errors:
                    for e in errors:
                        st.error(e)
                else:
                    if party.strip():
                        party = add_party(party)
                    conn.execute(
                        "UPDATE txns SET date=?, kind=?, party=?, amount=?, note=? WHERE id=?",
                        (str(dt), kind, party, amount, note.strip(), int(eid)),
                    )
                    conn.commit()
                    st.session_state.msg = f"Entry #{eid} badal di."
                    st.rerun()

            confirm = b2.checkbox("Haan, ye entry delete karni hai")
            if b2.button("Delete karo", disabled=not confirm):
                conn.execute("DELETE FROM txns WHERE id=?", (int(eid),))
                conn.commit()
                st.session_state.msg = f"Entry #{eid} delete ho gayi."
                st.rerun()

# ----- 3. Hisaab -----
elif page == "Hisaab":
    st.subheader("Hisaab")
    c1, c2 = st.columns(2)
    start = c1.date_input("Kab se", value=date.today(), max_value=date.today())
    end = c2.date_input("Kab tak", value=date.today(), max_value=date.today())
    if start > end:
        st.error("'Kab se' date 'Kab tak' se pehle honi chahiye.")
    else:
        d = load()
        d = d[(d.date >= str(start)) & (d.date <= str(end))]
        sale = d[d.kind.isin(["sale_cash", "sale_udhaar"])].amount.sum()
        udhaar = d[d.kind == "sale_udhaar"].amount.sum()
        kharcha = d[d.kind.isin(["expense", "purchase"])].amount.sum()
        cash_in = d[d.kind.isin(["sale_cash", "payment_received"])].amount.sum()
        m1, m2 = st.columns(2)
        m1.metric("Total sale", f"Rs {sale:,.0f}")
        m2.metric("Total kharcha", f"Rs {kharcha:,.0f}")
        m3, m4 = st.columns(2)
        m3.metric("Gale mein aaya (cash in)", f"Rs {cash_in:,.0f}")
        m4.metric("Udhaar diya", f"Rs {udhaar:,.0f}")
        st.caption(
            "Sale - kharcha = Rs "
            f"{sale - kharcha:,.0f}. Ye asli munafa nahi hai, kyunki maal ki cost "
            "alag se nahi joda hai (ye agle step mein aayega)."
        )

# ----- 4. Udhaar list -----
elif page == "Udhaar list":
    st.subheader("Kiska kitna baaki hai")
    d = load()
    d = d[d.party.fillna("") != ""]
    diya = d[d.kind == "sale_udhaar"].groupby("party").amount.sum()
    mila = d[d.kind == "payment_received"].groupby("party").amount.sum()
    baaki = diya.sub(mila, fill_value=0)
    baaki = baaki[baaki > 0].sort_values(ascending=False)
    if baaki.empty:
        st.info("Kisi ka udhaar baaki nahi hai.")
    else:
        st.metric("Kul baaki", f"Rs {baaki.sum():,.0f}")
        st.dataframe(
            baaki.rename("Baaki (Rs)").reset_index().rename(columns={"party": "Party"}),
            hide_index=True,
        )

# ----- 5. Parties -----
else:
    st.subheader("Parties / Customers")
    n1, n2 = st.columns([3, 1])
    newname = n1.text_input("Nayi party jodo", key="p_new")
    if n2.button("Add"):
        name = clean_name(newname)
        if not name:
            st.error("Naam khali nahi ho sakta.")
        elif len(name) > 50:
            st.error("Naam 50 akshar se chhota rakho.")
        else:
            add_party(name)
            st.session_state.msg = f"{name} jud gaya."
            st.rerun()

    parties = party_list()
    if parties:
        st.markdown("---")
        st.markdown("**Naam theek karo ya do naam ek karo**")
        st.caption(
            "Jaise 'Ramesh Ji' ko 'Ramesh' mein badlo. Agar 'Ramesh' pehle se hai, "
            "to dono ki entries ek ho jayengi."
        )
        old = st.selectbox("Kaun si party?", parties)
        new = st.text_input("Naya naam", value=old, key=f"rename_{old}")
        if st.button("Naam badlo"):
            new = clean_name(new)
            if not new:
                st.error("Naam khali nahi ho sakta.")
            elif len(new) > 50:
                st.error("Naam 50 akshar se chhota rakho.")
            elif new.lower() == old.lower():
                conn.execute("UPDATE parties SET name=? WHERE name=?", (new, old))
                conn.execute("UPDATE txns SET party=? WHERE LOWER(party)=LOWER(?)", (new, old))
                conn.commit()
                st.session_state.msg = "Naam badal diya."
                st.rerun()
            else:
                target = add_party(new)
                conn.execute(
                    "UPDATE txns SET party=? WHERE LOWER(party)=LOWER(?)", (target, old)
                )
                conn.execute("DELETE FROM parties WHERE name=?", (old,))
                conn.commit()
                st.session_state.msg = f"'{old}' ki entries ab '{target}' mein hain."
                st.rerun()