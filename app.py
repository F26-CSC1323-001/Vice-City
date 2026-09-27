from flask import Flask

# starts the Flask app
app = Flask(__name__)

# home page of the server
@app.route("/")
def home():
    return "Smart Locker Room server is running"

# runs the app when this file is started
if __name__ == "__main__":
    app.run(debug=True)