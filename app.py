"""
Investor Digest — Multi-user SaaS Flask app.
Run locally:  python app.py
Production:   gunicorn app:app
"""

import json
from datetime import date, datetime, timezone

from flask import (Flask, render_template, request, redirect,
                   url_for, flash, jsonify)
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user)

import config
from models import db, User, Holding, FilingSummary
import edgar
import summarizer
import emailer

# ── App setup ──────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config["SQLALCHEMY_DATABASE_URI"]        = config.DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view        = "login"
login_manager.login_message     = "Please log in to access your dashboard."
login_manager.login_message_category = "info"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()


# ── Core logic ─────────────────────────────────────────────────────────────────
def process_holding(holding: Holding) -> list[FilingSummary]:
    """Fetch new filings for a holding, summarise, and save. Returns new records."""
    filing_types = []
    user = holding.user
    if user.notify_on_8k:  filing_types.append("8-K")
    if user.notify_on_10k: filing_types.append("10-K")
    if user.notify_on_10q: filing_types.append("10-Q")
    if not filing_types:   filing_types = config.FILING_TYPES

    new_filings = edgar.get_new_filings_since(
        holding.ticker, since_date=holding.last_checked,
        filing_types=filing_types,
    )

    created = []
    for f in new_filings:
        if FilingSummary.query.filter_by(accession_number=f["accession_number"]).first():
            continue
        text    = edgar.fetch_filing_text(f["document_url"])
        summary = summarizer.summarize_filing(
            company=f["company"], ticker=f["ticker"],
            form_type=f["form"], filed_date=f["filed"], filing_text=text,
        )
        record = FilingSummary(
            holding_id=holding.id, ticker=f["ticker"], company=f["company"],
            form_type=f["form"], filed_date=f["filed"],
            accession_number=f["accession_number"], document_url=f["document_url"],
            headline=summary.get("headline",""),
            key_points=json.dumps(summary.get("key_points",[])),
            financials=summary.get("financials",""), risks=summary.get("risks",""),
            outlook=summary.get("outlook",""), sentiment=summary.get("sentiment","Neutral"),
            action_items=summary.get("action_items",""), raw_summary=summary.get("raw_summary",""),
        )
        db.session.add(record)
        created.append(record)

    if new_filings:
        holding.last_checked = date.today().isoformat()
    db.session.commit()
    return created


# ── Public routes ──────────────────────────────────────────────────────────────
@app.route("/")
def landing():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        name     = request.form.get("name", "").strip()
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or not password:
            flash("Email and password are required.", "error")
            return render_template("auth/register.html")
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("auth/register.html")
        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
            return render_template("auth/register.html")
        user = User(name=name, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash(f"Welcome, {name or email}! Add your first stock below.", "success")
        return redirect(url_for("dashboard"))
    return render_template("auth/register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user     = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Incorrect email or password.", "error")
    return render_template("auth/login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("landing"))


# ── App routes ─────────────────────────────────────────────────────────────────
@app.route("/dashboard")
@login_required
def dashboard():
    holdings  = Holding.query.filter_by(user_id=current_user.id)\
                             .order_by(Holding.added_at.desc()).all()
    summaries = (FilingSummary.query
                 .join(Holding).filter(Holding.user_id == current_user.id)
                 .order_by(FilingSummary.created_at.desc())
                 .limit(50).all())
    return render_template("dashboard.html", holdings=holdings, summaries=summaries)


@app.route("/holdings/add", methods=["POST"])
@login_required
def add_holding():
    ticker = request.form.get("ticker", "").strip().upper()
    if not ticker:
        flash("Please enter a ticker symbol.", "error")
        return redirect(url_for("dashboard"))
    if Holding.query.filter_by(user_id=current_user.id, ticker=ticker).first():
        flash(f"{ticker} is already in your portfolio.", "warning")
        return redirect(url_for("dashboard"))

    # Look up CIK and company name in one call. If the network is down or the
    # ticker list hasn't loaded yet we still allow adding — we'll verify when
    # the first filing check runs.
    cik, company = edgar.get_cik_and_name(ticker)
    if not cik:
        # Could be a network error or a genuinely invalid ticker.
        # Warn the user but don't hard-block — they may just have a slow connection.
        flash(
            f"⚠️ Could not verify \"{ticker}\" on SEC EDGAR right now "
            f"(network issue or invalid ticker). It was added anyway — "
            f"if it's a valid US ticker, filings will appear when you check.",
            "warning"
        )

    holding = Holding(user_id=current_user.id, ticker=ticker, company=company or ticker)
    db.session.add(holding)
    db.session.commit()

    if cik:
        flash(f"Added {company} ({ticker}) to your portfolio.", "success")
    return redirect(url_for("dashboard"))


@app.route("/holdings/<int:holding_id>/delete", methods=["POST"])
@login_required
def delete_holding(holding_id):
    holding = Holding.query.filter_by(id=holding_id, user_id=current_user.id).first_or_404()
    ticker  = holding.ticker
    db.session.delete(holding)
    db.session.commit()
    flash(f"Removed {ticker} from your portfolio.", "success")
    return redirect(url_for("dashboard"))


@app.route("/holdings/<int:holding_id>/check", methods=["POST"])
@login_required
def check_holding(holding_id):
    holding = Holding.query.filter_by(id=holding_id, user_id=current_user.id).first_or_404()
    new_records = process_holding(holding)
    if new_records:
        flash(f"Found {len(new_records)} new filing(s) for {holding.ticker}.", "success")
    else:
        flash(f"No new filings found for {holding.ticker}.", "info")
    return redirect(url_for("dashboard"))


@app.route("/check-all", methods=["POST"])
@login_required
def check_all():
    holdings = Holding.query.filter_by(user_id=current_user.id).all()
    all_new  = []
    for h in holdings:
        all_new.extend(process_holding(h))
    if all_new:
        dicts   = [r.to_dict() for r in all_new]
        success = emailer.send_digest(dicts, recipient=current_user.digest_address)
        if success:
            for r in all_new:
                r.emailed = True
            db.session.commit()
            flash(f"Found {len(all_new)} new filing(s) — digest sent to {current_user.digest_address}!", "success")
        else:
            flash(f"Found {len(all_new)} new filing(s), but email failed. Check Settings.", "warning")
    else:
        flash("No new filings across your portfolio.", "info")
    return redirect(url_for("dashboard"))


@app.route("/send-digest", methods=["POST"])
@login_required
def send_digest():
    unsent = (FilingSummary.query.join(Holding)
              .filter(Holding.user_id == current_user.id, FilingSummary.emailed == False)
              .order_by(FilingSummary.created_at.desc()).all())
    if not unsent:
        flash("No unsent summaries to email.", "info")
        return redirect(url_for("dashboard"))
    success = emailer.send_digest([r.to_dict() for r in unsent],
                                  recipient=current_user.digest_address)
    if success:
        for r in unsent:
            r.emailed = True
        db.session.commit()
        flash(f"Digest sent with {len(unsent)} summary(-ies)!", "success")
    else:
        flash("Email failed. Check your Settings to make sure email is configured.", "error")
    return redirect(url_for("dashboard"))


@app.route("/summary/<int:summary_id>")
@login_required
def view_summary(summary_id):
    summary = (FilingSummary.query.join(Holding)
               .filter(FilingSummary.id == summary_id,
                       Holding.user_id == current_user.id).first_or_404())
    kp = []
    try:
        kp = json.loads(summary.key_points) if summary.key_points else []
    except Exception:
        pass
    return render_template("summary.html", summary=summary, key_points=kp)


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        current_user.name         = request.form.get("name", "").strip()
        current_user.digest_email = request.form.get("digest_email", "").strip()
        current_user.notify_on_8k  = "notify_8k"  in request.form
        current_user.notify_on_10k = "notify_10k" in request.form
        current_user.notify_on_10q = "notify_10q" in request.form
        # Password change
        new_pw = request.form.get("new_password", "")
        if new_pw:
            if len(new_pw) < 8:
                flash("New password must be at least 8 characters.", "error")
                return render_template("settings.html")
            current_user.set_password(new_pw)
        db.session.commit()
        flash("Settings saved.", "success")
        return redirect(url_for("settings"))
    return render_template("settings.html")


# ── Background scheduler ───────────────────────────────────────────────────────
def start_scheduler():
    from apscheduler.schedulers.background import BackgroundScheduler
    scheduler = BackgroundScheduler()

    def job():
        with app.app_context():
            users = User.query.all()
            for user in users:
                all_new = []
                for h in user.holdings:
                    all_new.extend(process_holding(h))
                if all_new:
                    if emailer.send_digest([r.to_dict() for r in all_new],
                                           recipient=user.digest_address):
                        for r in all_new:
                            r.emailed = True
                        db.session.commit()

    scheduler.add_job(job, "interval", minutes=config.CHECK_INTERVAL_MINUTES,
                      id="check_all_users", replace_existing=True)
    scheduler.start()
    return scheduler


if __name__ == "__main__":
    scheduler = start_scheduler()
    print(f"\n🚀 {config.APP_NAME} running at http://localhost:5000\n")
    try:
        app.run(debug=False, host="0.0.0.0", port=5000, use_reloader=False)
    finally:
        scheduler.shutdown()
