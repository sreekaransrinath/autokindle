from flask import request, Flask
from requests import get, post
import smtplib
import ssl
from bs4 import BeautifulSoup
import os
import json
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)


@app.route("/")
def hello():
    bookDeets = request.args.get("deets")
    if bookDeets is None:
        return "Please enter a book title in the params."
    searchLibgen(bookDeets)
    return f"Processing request for {bookDeets}..."


# Enviroment variables
senderEmail = os.environ["SENDER_EMAIL"]
kindleEmail = os.environ["KINDLE_EMAIL"]
gmailPass = os.environ["GMAIL_APP_PASSWORD"]
venkiEmail = os.environ["VENKI_EMAIL"]
epubApiKey = os.environ["EPUB_API_KEY"]



headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36"
}

urls = []

formats = ["epub", "pdf"]
formatUsed = ""


def searchLibgen(bookDeets):
    for format in formats:
        print(f"Trying to find {bookDeets} in {format} format...")
        formatUsed = format
        searchPage = get(
            f"http://libgen.rs/fiction/?q={bookDeets}&language=English&format={format}",
            headers=headers,
        )
        soup = BeautifulSoup(searchPage.text, "html.parser")
        urlContainers = soup.findAll("ul", {"class": "record_mirrors_compact"})

        if urlContainers != []:
            print(f"{bookDeets} found in {format} format...")
            print("Parsing through the book url and fetching download link...")
            for urlContainer in urlContainers:
                for url in urlContainer.findAll("a"):
                    urls.append(url.get("href"))
            break

        else:
            print(f"{bookDeets} not found in {format} format.")
            continue

    if urls == []:
        print(f"No results found for {bookDeets} in any format. \nEmailing the user...")
        sendFailedEmail(bookDeets)

    downloadLink = getDownloadLink(urls, bookDeets)
    downloadBook(bookDeets, downloadLink, formatUsed)


def sendFailedEmail(bookDeets):
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(senderEmail, gmailPass)
    subject = "We searched far and wide, but found nothing."
    body = f"Unfortunately, we weren't able to find any results for your search for {bookDeets}. Feel free to try another title!"
    msg = "Subject: " + subject + "\n\n" + body
    server.sendmail(senderEmail, venkiEmail, msg)
    print("Email has been sent!", msg)
    server.quit()


def getDownloadLink(urls, bookDeets):
    for url in urls:
        response = get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")
        if "library.lol" in url or "libgen.gs" in url:
            print(f"Fetched download link for {bookDeets}.")
            return soup.find("a").get("href")
        elif "3lib.net" in url:
            pass


def downloadBook(bookDeets, downloadLink, formatUsed):
    print(f"Downloading {bookDeets} from {downloadLink} as {formatUsed}...")
    filename = f"{bookDeets}.{formatUsed}"
    response = get(downloadLink, headers=headers)
    with open(filename, "wb") as r:
        r.write(response.content)

    newFilename = filename
    # if formatUsed == "epub":
    #     newFilename = convertBook(filename)

    emailBook(
        kindleEmail,
        senderEmail,
        newFilename,
    )


def convertBook(filename):
    print(f"Converting downloaded epub file {filename} to .mobi...")
    url = "https://epub.to/v1/api"
    files = {"file": open(filename, "rb")}
    params = {"convert_to": "mobi"}
    data = {"data": json.dumps(params)}
    headers = {"Authorization": epubApiKey}
    r = post(url, files=files, data=data, headers=headers)

    newFilename = filename.split(".")[0] + ".mobi"

    with open(newFilename, "wb") as f:
        f.write(r.content)

    print(f"Converted {filename} to {newFilename}.")
    return newFilename


def emailBook(kindleEmail, senderEmail, filename):
    print(f"Sending {filename} to {kindleEmail}...")
    sender_email = senderEmail
    receiver_email = kindleEmail
    password = gmailPass

    # Create a multipart message and set headers
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email

    # Open PDF file in binary mode
    with open(filename, "rb") as attachment:
        # Add file as application/octet-stream
        # Email client can usually download this automatically as attachment
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())

    # Encode file in ASCII characters to send by email
    encoders.encode_base64(part)

    # Add header as key/value pair to attachment part
    part.add_header(
        "Content-Disposition",
        f"attachment; filename= {filename}",
    )

    # Add attachment to message and convert message to string
    message.attach(part)
    text = message.as_string()

    # Log in to server using secure context and send email
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(sender_email, password)
        if filename != "None.mobi":
            server.sendmail(sender_email, receiver_email, text)
            print(f"{filename} sent to {kindleEmail}!")
    deleteFile(filename)
    return filename


def deleteFile(filename):
    print(f"Deleting {filename}...")
    os.remove(filename)
    print(f"{filename} deleted.")
