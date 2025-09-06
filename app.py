from flask import Flask, send_from_directory
import subprocess
import os

app = Flask(__name__, static_folder="static")

@app.route("/")
def home():
    # Run your Python script before serving index.html
    subprocess.run(["python", "extract_emails.py"], check=True)
    return send_from_directory(app.static_folder, "index.html")

# Optional: serve JSON if needed directly
@app.route("/data/<path:filename>")
def data_files(filename):
    return send_from_directory("static", filename)

if __name__ == "__main__":
    app.run(debug=True)
