import sqlite3
from flask import Flask, render_template, request, redirect, make_response
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)
client = OpenAI(api_key=api_key)
DB_PATH = "chat.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL
            )
        """)
        c.execute("SELECT COUNT(*) FROM messages")
        count = c.fetchone()[0]
        if count == 0:
            c.execute("INSERT INTO messages (role, content) VALUES (?, ?)", 
                      ("assistant", "How are you feeling today?"))
        conn.commit()

def save_message(role, content):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO messages (role, content) VALUES (?, ?)", (role, content))
        conn.commit()

def load_history():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT role, content FROM messages ORDER BY id ASC")
        return [{"role": row[0], "content": row[1]} for row in c.fetchall()]

def clear_history():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM messages")
        conn.commit()

@app.route("/", methods=["GET", "POST"])
def home():
    init_db()
    response_text = ""

    if request.method == "POST":
        user_input = request.form.get("user_input", "").strip()
        if user_input:
            save_message("user", user_input)

            messages = [{"role": "system", "content": "You're a compassionate mental health assistant. Respond with empathy and ask meaningful follow-up questions."}]
            messages += load_history()

            try:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=messages
                )
                reply = response.choices[0].message.content
                save_message("assistant", reply)
                response_text = reply
            except Exception as e:
                print("❌ OpenAI error:", e)
                response_text = "Something went wrong. Please try again."

    all_messages = load_history()
    return render_template("index_db.html", response_text=response_text, chat=all_messages)

@app.route("/reset", methods=["POST"])
def reset():
    clear_history()
    return redirect("/")

@app.route("/download", methods=["GET"])
def download_chat():
    messages = load_history()
    content = ""
    for msg in messages:
        content += f"{msg['role'].title()}: {msg['content']}\n\n"

    response = make_response(content)
    response.headers["Content-Disposition"] = "attachment; filename=chat_history.txt"
    response.headers["Content-Type"] = "text/plain"
    return response

# ✅ THIS MUST BE AT THE BOTTOM
if __name__ == "__main__":
    print("🔥 Flask starting...")
    app.run(debug=True)
