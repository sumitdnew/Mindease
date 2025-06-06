import sqlite3
from flask import Flask, render_template, request, redirect, session, url_for, send_file
from werkzeug.security import generate_password_hash, check_password_hash
import openai
from dotenv import load_dotenv
import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import io

# Load env vars
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)
app.secret_key = "your-secret-key"  # Change in production
openai.api_key=api_key
DB_PATH = "auth_chat.db"

# --------------- DB INIT -------------------
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL
                    )""")
        c.execute("""CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        role TEXT,
                        content TEXT,
                        FOREIGN KEY(user_id) REFERENCES users(id)
                    )""")
        conn.commit()

# --------------- Helpers -------------------
def get_user(username):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id, username, password_hash FROM users WHERE LOWER(username) = ?", (username.lower(),))
        row = c.fetchone()
        return {"id": row[0], "username": row[1], "hash": row[2]} if row else None

def save_message(user_id, role, content):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)", (user_id, role, content))
        conn.commit()

def load_history(user_id):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT role, content FROM messages WHERE user_id = ? ORDER BY id ASC", (user_id,))
        return [{"role": row[0], "content": row[1]} for row in c.fetchall()]

def clear_history(user_id):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))
        conn.commit()

# --------------- Routes -------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"].lower()
        password = generate_password_hash(request.form["password"])
        try:
            with sqlite3.connect(DB_PATH) as conn:
                c = conn.cursor()
                c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password))
                conn.commit()
            return redirect("/login")
        except sqlite3.IntegrityError:
            return "Username already exists."
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].lower()
        password = request.form["password"]
        user = get_user(username)
        if user and check_password_hash(user["hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect("/")
        return "Invalid credentials."
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/", methods=["GET", "POST"])
def home():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    response_text = ""

    history = load_history(user_id)
    if not history:
        save_message(user_id, "assistant", "How are you feeling today?")
        history = load_history(user_id)

    if request.method == "POST":
        user_input = request.form.get("user_input", "").strip()
        if user_input:
            save_message(user_id, "user", user_input)
            try:
                messages = [{"role": "system", "content": "You're a compassionate mental health assistant. Respond with empathy and ask thoughtful follow-up questions."}]
                messages += load_history(user_id)
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=messages
                )
                reply = response.choices[0].message.content
                save_message(user_id, "assistant", reply)
                response_text = reply
            except Exception as e:
                print("❌ OpenAI error:", e)
                response_text = "Something went wrong. Please try again."

    history = load_history(user_id)
    return render_template("index_auth.html", response_text=response_text, chat=history, username=session["username"])

@app.route("/reset", methods=["POST"])
def reset():
    if "user_id" in session:
        clear_history(session["user_id"])
    return redirect("/")

# --------------- PDF Export -------------------
@app.route("/download_pdf")
def download_pdf():
    if "user_id" not in session:
        return redirect("/login")

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 50

    messages = load_history(session["user_id"])

    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, y, f"MindEase Chat - {session['username']}")
    y -= 30
    p.setFont("Helvetica", 12)

    for msg in messages:
        lines = p.beginText(50, y)
        lines.textLines(f"{msg['role'].title()}: {msg['content']}")
        p.drawText(lines)
        y -= 60
        if y < 100:
            p.showPage()
            y = height - 50

    p.save()
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name="MindEase_Chat.pdf", mimetype="application/pdf")

# --------------- Run App -------------------
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


