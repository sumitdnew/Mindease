from flask import Flask, render_template, request
from openai import OpenAI, RateLimitError
from dotenv import load_dotenv
import os

# Load .env and API key
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# ✅ This was missing!
app = Flask(__name__)

# ✅ OpenAI client setup
client = OpenAI(api_key=api_key)

@app.route("/", methods=["GET", "POST"])
def home():
    response_text = ""
    if request.method == "POST":
        user_input = request.form["user_input"]
        print("User said:", user_input)  # Debug log

        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You're a compassionate mental health assistant. Always reply empathetically and ask a meaningful follow-up question."},
                    {"role": "user", "content": user_input}
                ]
            )
            print("API raw response:", response)  # Debug log
            response_text = response.choices[0].message.content
        except RateLimitError:
            response_text = "Rate limit exceeded. Try again later."
        except Exception as e:
            print("Error:", e)
            response_text = "Something went wrong. Please try again."
    
    return render_template("index.html", response=response_text)

if __name__ == "__main__":
    app.run(debug=True)
