import re
import csv
import io
from typing import List, Dict, Tuple, Optional, Set
from app.errors import ValidationException
from app.config import settings

# RFC 5322 compliant practical email pattern
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def is_valid_email(email: str) -> bool:
    """Validate email syntax against standard regex pattern."""
    if not email or len(email) > 255:
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def validate_recipient_item(
    name: Optional[str],
    email: Optional[str],
    course_title: Optional[str],
    seen_emails: Set[str]
) -> Tuple[bool, Optional[str], str, str, Optional[str]]:
    """
    Validate individual recipient data.
    
    Why: Instead of aborting the entire batch when an entry is bad,
    each item is evaluated individually so valid certificates can proceed.
    Duplicate emails are checked case-insensitively after trimming, flagging
    only the 2nd and subsequent occurrences.
    
    Returns:
        (is_valid, error_message, cleaned_name, cleaned_email, cleaned_course)
    """
    clean_name = (name or "").strip()
    clean_email = (email or "").strip()
    clean_course = (course_title or "").strip() if course_title else None

    # Check recipient name
    if not clean_name:
        return False, "Recipient name is required and cannot be empty", clean_name, clean_email, clean_course
    if len(clean_name) > 100:
        return False, "Recipient name exceeds maximum allowed length of 100 characters", clean_name, clean_email, clean_course

    # Check email format
    if not clean_email:
        return False, "Recipient email is required and cannot be empty", clean_name, clean_email, clean_course
    if not is_valid_email(clean_email):
        return False, f"Invalid email format: '{clean_email}'", clean_name, clean_email, clean_course

    # Check duplicates within batch (case-insensitive)
    lower_email = clean_email.lower()
    if lower_email in seen_emails:
        return False, f"Duplicate email '{clean_email}' found in this batch", clean_name, clean_email, clean_course
    
    seen_emails.add(lower_email)
    return True, None, clean_name, clean_email, clean_course


def parse_and_validate_csv(csv_content: bytes) -> List[Dict[str, Optional[str]]]:
    """
    Parse uploaded CSV bytes with utf-8-sig encoding and case-insensitive headers.
    
    Why: utf-8-sig gracefully strips UTF-8 BOM if present (common with Excel exports).
    Case-insensitive matching ensures resilience against 'Name' vs 'name'.
    Raises ValidationException (HTTP 422) if required columns are missing or file exceeds limits.
    """
    if len(csv_content) > settings.MAX_CSV_SIZE_BYTES:
        raise ValidationException(
            f"CSV file size exceeds the {settings.MAX_CSV_SIZE_BYTES // (1024*1024)}MB limit.",
            code="CSV_FILE_TOO_LARGE"
        )
    
    try:
        text = csv_content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValidationException("Invalid CSV encoding. Please upload a UTF-8 encoded CSV file.", code="INVALID_CSV_ENCODING")

    stream = io.StringIO(text)
    reader = csv.reader(stream)
    
    try:
        header_row = next(reader)
    except StopIteration:
        raise ValidationException("The uploaded CSV file is empty.", code="EMPTY_CSV")

    # Map normalized lowercase column name to column index
    header_map: Dict[str, int] = {}
    for idx, col in enumerate(header_row):
        col_clean = col.strip().lower()
        if col_clean:
            header_map[col_clean] = idx

    # Validate required columns
    required_cols = ["name", "email"]
    missing = [c for c in required_cols if c not in header_map]
    if missing:
        raise ValidationException(
            f"Missing required CSV column(s): {', '.join(missing)}. Headers must include 'name' and 'email'.",
            code="MISSING_CSV_COLUMNS"
        )

    course_idx = header_map.get("course_title")
    name_idx = header_map["name"]
    email_idx = header_map["email"]

    recipients: List[Dict[str, Optional[str]]] = []
    for row_num, row in enumerate(reader, start=2):
        # Skip completely blank lines
        if not row or not any(cell.strip() for cell in row):
            continue
        
        name = row[name_idx] if name_idx < len(row) else ""
        email = row[email_idx] if email_idx < len(row) else ""
        course = row[course_idx] if (course_idx is not None and course_idx < len(row)) else None

        recipients.append({
            "name": name,
            "email": email,
            "course_title": course
        })

    if not recipients:
        raise ValidationException("CSV file contains no recipient data rows.", code="EMPTY_CSV_DATA")

    return recipients
