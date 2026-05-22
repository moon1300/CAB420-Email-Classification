import os
import re
import pandas as pd
from email import message_from_string
from email.utils import parseaddr

MAILDIR_PATH = "data/maildir"
OUTPUT_PATH = "data/Enron_processed.csv"
MAX_EMAILS = 1000


def extract_email_body(raw_email):
    try:
        msg = message_from_string(raw_email)

        if msg.is_multipart():
            parts = []
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                if content_type == "text/plain" and "attachment" not in content_disposition:
                    payload = part.get_payload(decode=True)

                    if payload:
                        charset = part.get_content_charset() or "latin-1"
                        parts.append(payload.decode(charset, errors="ignore"))

            return "\n".join(parts)

        payload = msg.get_payload(decode=True)

        if payload:
            charset = msg.get_content_charset() or "latin-1"
            return payload.decode(charset, errors="ignore")

        return msg.get_payload()

    except Exception:
        return raw_email


def extract_sender(raw_email, folder_sender):
    from_match = re.search(r"^From:\s*(.+)$", raw_email, flags=re.MULTILINE | re.IGNORECASE)
    
    if from_match:
        from_value = from_match.group(1).strip()
        name, email_address = parseaddr(from_value)
        
        if email_address:
            return email_address.lower()
    
    xfrom_match = re.search(r"^X-From:\s*(.+)$", raw_email, flags=re.MULTILINE | re.IGNORECASE)
    
    if xfrom_match:
        xfrom_value = xfrom_match.group(1).strip()
        xfrom_cleaned = re.sub(r"<.*?>", "", xfrom_value).strip()
        
        name, email_address = parseaddr(xfrom_cleaned)
        
        if email_address:
            return email_address.lower()
        
        return xfrom_cleaned.lower()
    
    return folder_sender.lower()


def extract_x_from(raw_email):
    match = re.search(r"^X-From:\s*(.+)$", raw_email, flags=re.MULTILINE | re.IGNORECASE)
    
    if match:
        xfrom_value = match.group(1).strip()
        xfrom_cleaned = re.sub(r"<.*?>", "", xfrom_value).strip()
        return xfrom_cleaned
    
    return None


def extract_date(raw_email):
    match = re.search(r"^Date:\s*(.+)$", raw_email, flags=re.MULTILINE | re.IGNORECASE)
    
    if match:
        return match.group(1).strip()
    
    return None


def remove_forwarded_and_reply_chains(text):
    cutoff_patterns = [
        r"\n[-]{2,}\s*Forwarded by.*?[-]{2,}",
        r"\n[-]{2,}\s*Original Message\s*[-]{2,}",
        r"\n[-]{2,}\s*Original Appointment\s*[-]{2,}",
        r"\n=+\s*$",
        r"\n=+\s*\n",
        r"\nFrom:\s+.*@.*",
        r"\nSent:\s+.*",
        r"\nTo:\s+.*",
        r"\nSubject:\s+.*",
    ]

    cutoff_positions = []

    for pattern in cutoff_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            cutoff_positions.append(match.start())

    if cutoff_positions:
        text = text[:min(cutoff_positions)]

    return text


def clean_text(text):
    if not isinstance(text, str):
        return ""

    text = remove_forwarded_and_reply_chains(text)

    text = re.sub(r"Message-ID:\s*<.*?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"Date:\s.*", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"X-(?!From).*?:\s.*", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"X-From:\s.*", " ", text, flags=re.IGNORECASE)

    text = re.sub(r"\S+@\S+", " ", text)
    text = re.sub(r"http\S+|www\.\S+", " ", text)
    text = re.sub(r"[-_=]{3,}", " ", text)
    text = re.sub(r"\s+", " ", text)

    disclaimer_patterns = [
        r"this message is intended only for.*",
        r"copyright.*",
        r"all rights reserved.*",
        r"please do not transmit orders.*",
        r"notice regarding privacy.*",
    ]

    for pattern in disclaimer_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.DOTALL)

    return text.strip()


def is_valid_email(text, sender, x_from):
    if not text or len(text) < 20:
        return False
    
    text_lower = text.lower()
    
    forward_indicators = [
        "forwarded by",
        "original message",
        "-----forwarded",
        "begin forwarded message",
        "fwd:",
    ]
    if any(indicator in text_lower for indicator in forward_indicators):
        return False
    
    newsletter_indicators = [
        "to unsubscribe",
        "click here to unsubscribe",
        "remove me from this list",
        "newsletter",
        "daily digest",
        "mailing list",
        "press release",
        "breaking news",
        "in today's edition",
    ]
    if any(indicator in text_lower for indicator in newsletter_indicators):
        return False
    
    disclaimer_indicators = [
        "this message is intended only for",
        "confidential and privileged",
        "if you are not the intended recipient",
        "privilege and confidential",
        "unauthorized disclosure",
        "legally privileged",
    ]
    if any(indicator in text_lower for indicator in disclaimer_indicators):
        return False
    
    system_indicators = [
        "automatic reply",
        "out of office",
        "auto-reply",
        "delivery failure",
        "undeliverable",
        "mailer-daemon",
        "postmaster",
        "system administrator",
        "do not reply to this email",
        "this is an automated message",
    ]
    if any(indicator in text_lower for indicator in system_indicators):
        return False
    
    system_senders = [
        "noreply",
        "no-reply",
        "mailer-daemon",
        "postmaster",
        "administrator",
    ]
    if any(system_sender in sender.lower() for system_sender in system_senders):
        return False
    
    word_count = len(text.split())
    if word_count > 1500:
        return False
    
    spam_indicators = [
        "click here now",
        "limited time offer",
        "act now",
        "special promotion",
        "unsubscribe",
        "opt out",
        "privacy policy",
        "terms and conditions",
        "viagra",
        "casino",
        "winner",
        "congratulations you",
    ]
    spam_count = sum(1 for indicator in spam_indicators if indicator in text_lower)
    if spam_count >= 2:
        return False
    
    if word_count < 5:
        return False
    
    return True


def load_enron_maildir(maildir_path, max_emails=1000):
    rows = []
    count = 0

    if not os.path.exists(maildir_path):
        raise FileNotFoundError(
            f"Could not find {maildir_path}. "
            "Make sure you run this script from the project root folder."
        )

    for folder_sender in os.listdir(maildir_path):
        sender_path = os.path.join(maildir_path, folder_sender)

        if not os.path.isdir(sender_path):
            continue

        for root, dirs, files in os.walk(sender_path):
            for filename in files:
                if count >= max_emails:
                    return pd.DataFrame(rows)

                file_path = os.path.join(root, filename)

                try:
                    with open(file_path, "r", encoding="latin-1", errors="ignore") as f:
                        raw_email = f.read()

                    sender = extract_sender(raw_email, folder_sender)
                    x_from = extract_x_from(raw_email)
                    
                    if "@enron.com" not in sender:
                        continue
                    
                    body = extract_email_body(raw_email)
                    cleaned_body = clean_text(body)

                    if not is_valid_email(cleaned_body, sender, x_from):
                        continue

                    rows.append({
                        "sender": sender,
                        "x_from": x_from,
                        "date": extract_date(raw_email),
                        "text": cleaned_body
                    })

                    count += 1

                except Exception as e:
                    print(f"Skipped file: {file_path}")
                    print(f"Reason: {e}")

    return pd.DataFrame(rows)


if __name__ == "__main__":
    print(f"Loading up to {MAX_EMAILS} emails from {MAILDIR_PATH}...")
    df = load_enron_maildir(MAILDIR_PATH, MAX_EMAILS)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    print("\n" + "="*60)
    print("Preprocessing complete!")
    print("="*60)
    print(f"Saved to: {OUTPUT_PATH}")
    print(f"Total rows: {len(df)}")
    print(f"Columns: {list(df.columns)}")
    print("\nFirst few rows:")
    print(df.head())