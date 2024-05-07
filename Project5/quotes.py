from flask import Flask, render_template, request, make_response, redirect, flash, get_flashed_messages
from mongita import MongitaClientDisk
from bson import ObjectId
from passwords import hash_password,check_password

import logging
from logging.handlers import RotatingFileHandler


app = Flask(__name__)

app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

# Configure logging
logging.basicConfig(level=logging.INFO)
handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=1)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
app.logger.addHandler(handler)

# create a mongita client connection
client = MongitaClientDisk()

# open the quotes database
quotes_db = client.quotes_db
session_db = client.session_db
user_db = client.user_db

import uuid

user_collection = user_db.user_collection
session_collection = session_db.session_collection

@app.route("/", methods=["GET"])
@app.route("/quotes", methods=["GET"])
def get_quotes():
    session_id = request.cookies.get("session_id", None)
    if not session_id:
        response = redirect("/login")
        return response
    # open the session collection
    session_collection = session_db.session_collection
    # get the data for this session
    session_data = list(session_collection.find({"session_id": session_id}))
    if len(session_data) == 0:
        response = redirect("/logout")
        return response
    assert len(session_data) == 1
    session_data = session_data[0]
    # get some information from the session
    user = session_data.get("user", "unknown user")
    # open the quotes collection
    quotes_collection = quotes_db.quotes_collection
    # load the data
    data = list(quotes_collection.find({"owner":user}))
    for item in data:
        item["_id"] = str(item["_id"])
        item["object"] = ObjectId(item["_id"])
    # display the data
    html = render_template(
        "quotes.html",
        data=data,
        user=user,
    )
    response = make_response(html)
    response.set_cookie("session_id", session_id)
    return response

# ADDED ROUTE FOR LOGIN 
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        app.logger.info("lgoin button hit")
        username = request.form["username"]
        password = request.form["password"]
        # Check if the username exists in the database
        user_data = user_collection.find_one({"user": username})
        if user_data:
            # Validate the password
            if check_password(password, user_data["hashed_password"], user_data["salt"]):
                # Password is correct, create a new session
                session_id = str(uuid.uuid4())
                session_data = {"session_id": session_id, "user": username}
                session_collection.insert_one(session_data)
                response = redirect("/quotes")
                response.set_cookie("session_id", session_id)
                return response
        # Invalid username or password
        flash("Invalid username or password", "error")
        return redirect("/login")
    return render_template("login.html")


@app.route("/logout", methods=["GET"])
def get_logout():
    # get the session id
    session_id = request.cookies.get("session_id", None)
    if session_id:
        # open the session collection
        session_collection = session_db.session_collection
        # delete the session
        session_collection.delete_one({"session_id": session_id})
    response = redirect("/login")
    response.delete_cookie("session_id")
    return response


@app.route("/add", methods=["GET"])
def get_add():
    session_id = request.cookies.get("session_id", None)
    if not session_id:
        response = redirect("/login")
        return response
    return render_template("add_quote.html")


@app.route("/add", methods=["POST"])
def post_add():
    session_id = request.cookies.get("session_id", None)
    if not session_id:
        response = redirect("/login")
        return response
    # open the session collection
    session_collection = session_db.session_collection
    # get the data for this session
    session_data = list(session_collection.find({"session_id": session_id}))
    if len(session_data) == 0:
        response = redirect("/logout")
        return response
    assert len(session_data) == 1
    session_data = session_data[0]
    # get some information from the session
    user = session_data.get("user", "unknown user")
    text = request.form.get("text", "")
    author = request.form.get("author", "")
    if text != "" and author != "":
        # open the quotes collection
        quotes_collection = quotes_db.quotes_collection
        # insert the quote
        quote_data = {"owner": user, "text": text, "author": author}
        quotes_collection.insert_one(quote_data)
    # usually do a redirect('....')
    return redirect("/quotes")


@app.route("/edit/<id>", methods=["GET"])
def get_edit(id=None):
    session_id = request.cookies.get("session_id", None)
    if not session_id:
        response = redirect("/login")
        return response
    if id:
        # open the quotes collection
        quotes_collection = quotes_db.quotes_collection
        # get the item
        data = quotes_collection.find_one({"_id": ObjectId(id)})
        data["id"] = str(data["_id"])
        return render_template("edit_quote.html", data=data)
    # return to the quotes page
    return redirect("/quotes")


@app.route("/edit", methods=["POST"])
def post_edit():
    session_id = request.cookies.get("session_id", None)
    if not session_id:
        response = redirect("/login")
        return response
    _id = request.form.get("_id", None)
    text = request.form.get("text", "")
    author = request.form.get("author", "")
    if _id:
        # open the quotes collection
        quotes_collection = quotes_db.quotes_collection
        # update the values in this particular record
        values = {"$set": {"text": text, "author": author}}
        data = quotes_collection.update_one({"_id": ObjectId(_id)}, values)
    # do a redirect('....')
    return redirect("/quotes")


@app.route("/delete", methods=["GET"])

@app.route("/delete/<id>", methods=["GET"])
def get_delete(id=None):
    session_id = request.cookies.get("session_id", None)
    if not session_id:
        response = redirect("/login")
        return response
    if id:
        # open the quotes collection
        quotes_collection = quotes_db.quotes_collection
        # delete the item
        quotes_collection.delete_one({"_id": ObjectId(id)})
    # return to the quotes page
    return redirect("/quotes")

# ADDED ROUTE FOR REGISTER
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        app.logger.info("register button hit")
        username = request.form["username"]
        password = request.form["password"]
        # Check if the username is already taken
        if user_collection.find_one({"user": username}):
            flash("Username already taken. Please choose a different username.", "error")
            return redirect("/register")
        # Hash the password before storing it
        hashed_password, salt = hash_password(password)
        # Store the username, hashed password, and salt in the user collection
        user_data = {"user": username, "hashed_password": hashed_password, "salt": salt}
        user_collection.insert_one(user_data)
        flash("Registration successful. Please log in.", "success")

        # Log all entries in the user collection to the log file
        app.logger.info("All entries in the user collection:")
        for entry in user_collection.find():
            app.logger.info(entry)

        return redirect("/login")
    return render_template("register.html")