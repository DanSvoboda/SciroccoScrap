import os
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
import smtplib

try:
    from twilio.rest import Client
except ImportError:
    Client = None

URL = "https://www.sauto.cz/inzerce/osobni/volkswagen/scirocco?cena-do=200000&km-do=200000&razeni=od-nejlevnejsich"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
}
CSV_FILE = Path(__file__).with_name("car_listings.csv")


def normalize_text(element):
    if element is None:
        return ""
    return " ".join(element.get_text(" ", strip=True).split())


def send_whatsapp_notification(message):
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    whatsapp_from = os.getenv("TWILIO_WHATSAPP_FROM") or os.getenv("WHATSAPP_FROM")
    whatsapp_to = os.getenv("WHATSAPP_TO")

    if not all([account_sid, auth_token, whatsapp_from, whatsapp_to]) or Client is None:
        print("Skipping WhatsApp notification because Twilio credentials are not configured.")
        return

    try:
        client = Client(account_sid, auth_token)
        client.messages.create(to=whatsapp_to, from_=whatsapp_from, content_sid="HXfe5ab5f00277942d4d4200328b4d403c")
        print("WhatsApp message sent.")
    except Exception as exc:
        print(f"WhatsApp notification failed: {exc}")

    send_email_notification("Nové Scirocco na Sauto.cz", message, os.getenv("SMTP_TO", ""))


def send_email_notification(subject, body, to_email):
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM")

    if not all([smtp_username, smtp_password, smtp_from, to_email]):
        print("Skipping email notification because SMTP credentials are not configured.")
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = to_email

    try:
        with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
        print("Email sent successfully.")
    except Exception as exc:
        print(f"Email notification failed: {exc}")


def parse_car_listings(html):
    soup = BeautifulSoup(html, "html.parser")
    listings = []

    for item in soup.select("ul.c-item-list__list > li.c-item"):
        link = item.select_one("a.c-item__link")
        name = normalize_text(item.select_one("a.c-item__link > span.c-item__name"))
        info = normalize_text(item.select_one(".c-item__info"))
        price = normalize_text(item.select_one(".c-item__price"))
        seller = normalize_text(item.select_one(".c-item__seller"))
        locality = normalize_text(item.select_one(".c-item__locality"))
        href = link.get("href", "") if link else ""

        listings.append(
            {
                "name": name,
                "info": info,
                "price": price,
                "seller": seller,
                "locality": locality,
                "link": href,
            }
        )

    return listings


def main():
    response = requests.get(URL, headers=HEADERS, timeout=20)
    response.raise_for_status()
    html = response.text

    car_listings = parse_car_listings(html)
    print(f"Found {len(car_listings)} car listings.")

    if CSV_FILE.exists():
        existing_df = pd.read_csv(CSV_FILE)
    else:
        existing_df = pd.DataFrame(columns=["name", "info", "price", "seller", "locality", "link"])
        existing_df.to_csv(CSV_FILE, index=False)

    new_df = pd.DataFrame(car_listings)
    new_rows = 0

    for _, row in new_df.iterrows():
        if not ((existing_df["link"] == row["link"]).any()):
            existing_df = pd.concat([existing_df, pd.DataFrame([row])], ignore_index=True)
            new_rows += 1
            print(f"New listing added: {row['name']} - {row['link']}")
            send_whatsapp_notification(f"New car listing found: {row['name']} - {row['link']}")

    existing_df.to_csv(CSV_FILE, index=False)
    print(existing_df.head())
    print(f"Total listings in CSV: {len(existing_df)}")
    print(f"New listings added: {new_rows}")


if __name__ == "__main__":
    main()

