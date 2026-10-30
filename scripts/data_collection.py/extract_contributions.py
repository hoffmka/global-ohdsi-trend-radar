
import re
import io
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

import requests
import pandas as pd
from bs4 import BeautifulSoup

try:
    import pdfplumber
except ImportError:
    pdfplumber = None


# ============================================================
# CONFIG
# ============================================================

EVENTS = {
    2023: {
        "overview": "https://www.ohdsi.org/2023-collaborator-showcase/",
        "pattern": r"/2023showcase-(\d+)/?$",
    },
    2024: {
        "overview": "https://www.ohdsi.org/2024-collaborator-showcase/",
        "pattern": r"/2024showcase-(\d+)/?$",
    },
    2025: {
        "overview": "https://www.ohdsi.org/2025-global-collaborator-showcase/",
        "pattern": r"/2025showcase-(\d+)/?$",
    },
}

OUTPUT_FILE = "ohdsi_evidence_master.xlsx"
MAX_WORKERS = 8
TIMEOUT = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/18.0 Safari/605.1.15"
    )
}


# ============================================================
# HTTP
# ============================================================

def get(url, retries=3):
    """GET request with retries."""
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=TIMEOUT,
            )
            response.raise_for_status()
            return response

        except Exception as e:
            last_error = e
            if attempt < retries:
                time.sleep(1.5 * attempt)

    raise last_error


# ============================================================
# TEXT HELPERS
# ============================================================

def clean_text(text):
    if not text:
        return ""

    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_url(url):
    return url.split("#")[0].rstrip("/") + "/"


# ============================================================
# CATEGORY
# ============================================================

VALID_CATEGORIES = [
    "Observational Data Standards",
    "Methodological Research",
    "Open-Source Analytics Development",
    "Clinical Applications",
    "Posters",
    "Software Demos",
    "Software Demonstrations",
    "Lightning Talks",
]


def nearest_category(a):
    """
    Find a recognizable category in previous structural headings.
    Award labels are never accepted as categories.
    """

    for element in a.find_all_previous(
        ["h1", "h2", "h3", "h4"]
    ):
        heading = clean_text(
            element.get_text(" ", strip=True)
        )
        low = heading.lower()

        if any(term in low for term in [
            "honoree",
            "best community contribution",
            "award",
            "winner",
            "finalist",
        ]):
            continue

        for category in VALID_CATEGORIES:
            if category.lower() in low:
                return category

    return ""


# ============================================================
# CONTRIBUTION ID AND TITLE
# ============================================================

def extract_displayed_id(soup):
    """
    Extract the official contribution ID from the visible page,
    preferably from a heading.

    Example:
        '505 – Contribution title' -> 505

    Returns None if no displayed ID can be identified.
    """

    # First choice: visible page headings.
    for heading in soup.find_all(
        ["h1", "h2", "h3", "h4"]
    ):
        text = clean_text(
            heading.get_text(" ", strip=True)
        )

        match = re.match(
            r"^\s*(\d{1,4})\s*\*?\s*[-–—:.)]\s*\S",
            text,
        )

        if match:
            return int(match.group(1))

    # Second choice: HTML page title.
    if soup.title:
        text = clean_text(
            soup.title.get_text(" ", strip=True)
        )

        match = re.match(
            r"^\s*(\d{1,4})\s*\*?\s*[-–—:.)]\s*\S",
            text,
        )

        if match:
            return int(match.group(1))

    # No reliable displayed ID found.
    return None


def remove_id_prefix(title):
    """Remove a leading contribution number from a title."""

    if not title:
        return ""

    return clean_text(
        re.sub(
            r"^\s*\d{1,4}\s*\*?\s*[-–—:.)]\s*",
            "",
            title,
            count=1,
        )
    )


def extract_title(soup):
    h1 = soup.find("h1")

    if h1:
        title = clean_text(
            h1.get_text(" ", strip=True)
        )
        return remove_id_prefix(title)

    title_tag = soup.find("title")

    if title_tag:
        title = clean_text(
            title_tag.get_text(" ", strip=True)
        )
        return remove_id_prefix(title)

    return ""


# ============================================================
# AUTHORS
# ============================================================

def extract_authors(soup):
    # First try individual visible elements.
    for tag in soup.find_all(
        ["p", "div", "span", "strong", "b", "li"]
    ):
        text = clean_text(
            tag.get_text(" ", strip=True)
        )

        match = re.match(
            r"^Authors?\s*:\s*(.+)$",
            text,
            flags=re.IGNORECASE,
        )

        if match:
            return clean_text(match.group(1))

    # Fallback: whole page text.
    page_text = soup.get_text("\n", strip=True)

    match = re.search(
        r"Authors?\s*:\s*(.*?)(?:\n|Brief Report|$)",
        page_text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if match:
        return clean_text(match.group(1))

    return ""


# ============================================================
# BRIEF REPORT
# ============================================================

def extract_brief_report_url(soup, base_url):
    for a in soup.find_all("a", href=True):
        text = clean_text(
            a.get_text(" ", strip=True)
        )

        if "brief report" in text.lower():
            return urljoin(base_url, a["href"])

    return ""


# ============================================================
# PDF
# ============================================================

def extract_pdf_text(pdf_url):
    if not pdf_url or pdfplumber is None:
        return ""

    try:
        response = get(pdf_url)

        with pdfplumber.open(
            io.BytesIO(response.content)
        ) as pdf:
            pages = []

            for page in pdf.pages:
                text = page.extract_text()

                if text:
                    pages.append(text)

            return "\n".join(pages).strip()

    except Exception as e:
        print(f"    PDF ERROR: {pdf_url} -> {e}")
        return ""


def extract_abstract(text):
    """
    Extract an explicit Abstract section if present.
    Otherwise, return a limited introductory excerpt.
    No content is generated or interpreted.
    """

    if not text:
        return ""

    lines = [
        clean_text(line)
        for line in text.splitlines()
        if clean_text(line)
    ]

    if not lines:
        return ""

    # Explicit Abstract section.
    for i, line in enumerate(lines):
        if line.lower().rstrip(": ") == "abstract":
            content = []

            for next_line in lines[i + 1:]:
                low = next_line.lower().rstrip(": ")

                if low in {
                    "introduction",
                    "background",
                    "objective",
                    "objectives",
                    "methods",
                    "method",
                    "results",
                    "discussion",
                    "conclusion",
                    "conclusions",
                    "references",
                }:
                    break

                content.append(next_line)

            result = clean_text(" ".join(content))

            if result:
                return result

    # No explicit Abstract heading: use a limited excerpt.
    content = []

    for line in lines[1:]:
        low = line.lower().rstrip(": ")

        if low in {
            "methods",
            "method",
            "results",
            "discussion",
            "references",
        }:
            break

        content.append(line)

        if len(" ".join(content)) >= 2500:
            break

    return clean_text(" ".join(content))


# ============================================================
# OVERVIEW PAGE
# ============================================================

def collect_overview(year, overview_url):
    print(f"\n[{year}] Reading overview...")

    response = get(overview_url)
    soup = BeautifulSoup(response.text, "html.parser")
    pattern = EVENTS[year]["pattern"]

    # Key by URL, not by contribution number.
    # The URL number may differ from the displayed ID.
    entries = {}

    for a in soup.find_all("a", href=True):
        href = normalize_url(
            urljoin(overview_url, a["href"])
        )

        match = re.search(pattern, href)

        if not match:
            continue

        url_number = int(match.group(1))

        if href in entries:
            # If another link to the same page provides
            # a category, keep it rather than a blank value.
            category = nearest_category(a)

            if not entries[href]["Category"] and category:
                entries[href]["Category"] = category

            continue

        entries[href] = {
            "Year": year,

            # This is only the number encoded in the URL.
            # It will be replaced if the page shows another ID.
            "Number": url_number,

            # Keep the URL-derived number for traceability.
            "URL_Number": url_number,

            "Category": nearest_category(a),
            "Source_URL": href,
        }

    print(
        f"[{year}] Found {len(entries)} unique contribution URLs."
    )

    return list(entries.values())


# ============================================================
# PROCESS ONE CONTRIBUTION
# ============================================================

def process_entry(entry):
    result = dict(entry)
    url = entry["Source_URL"]

    try:
        response = get(url)
        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        # ----------------------------------------------------
        # ID: prefer the number displayed on the page
        # ----------------------------------------------------

        displayed_id = extract_displayed_id(soup)

        if displayed_id is not None:
            result["Number"] = displayed_id
            result["ID_Source"] = "Displayed on page"
        else:
            result["Number"] = entry["URL_Number"]
            result["ID_Source"] = "URL fallback"

        # ----------------------------------------------------
        # Basic metadata
        # ----------------------------------------------------

        result["Title"] = extract_title(soup)
        result["Authors"] = extract_authors(soup)

        # ----------------------------------------------------
        # Brief Report
        # ----------------------------------------------------

        brief_report_url = extract_brief_report_url(
            soup,
            url,
        )

        result["Brief_Report_URL"] = brief_report_url

        # ----------------------------------------------------
        # Abstract
        # ----------------------------------------------------

        if brief_report_url:
            report_text = extract_pdf_text(
                brief_report_url
            )

            result["Abstract"] = extract_abstract(
                report_text
            )

            result["Abstract_Available"] = (
                "Yes" if result["Abstract"] else "No"
            )

            result["Content_Source"] = "Brief Report PDF"

        else:
            result["Abstract"] = ""
            result["Abstract_Available"] = "No"
            result["Content_Source"] = "Showcase page only"

        # Flag differences between the visible ID and URL.
        result["ID_URL_Mismatch"] = (
            "Yes"
            if displayed_id is not None
            and displayed_id != entry["URL_Number"]
            else "No"
        )

        result["Status"] = "OK"

    except Exception as e:
        result["Title"] = ""
        result["Authors"] = ""
        result["Brief_Report_URL"] = ""
        result["Abstract"] = ""
        result["Abstract_Available"] = "No"
        result["Content_Source"] = ""
        result["ID_Source"] = "Extraction failed"
        result["ID_URL_Mismatch"] = ""
        result["Status"] = f"ERROR: {e}"

    return result


# ============================================================
# COLLECT ONE YEAR
# ============================================================

def collect_year(year):
    entries = collect_overview(
        year,
        EVENTS[year]["overview"],
    )

    results = []
    total = len(entries)

    print(
        f"[{year}] Processing {total} contributions "
        f"with {MAX_WORKERS} workers..."
    )

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = {
            executor.submit(process_entry, entry): entry
            for entry in entries
        }

        completed = 0

        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            completed += 1

            print(
                f"[{year}] {completed}/{total}",
                end="\r",
            )

    print()

    results.sort(
        key=lambda x: (
            x.get("Number") is None,
            x.get("Number", 0),
        )
    )

    return results


# ============================================================
# VALIDATION
# ============================================================

def validate(df):
    print("\nValidation:")

    # Duplicate displayed IDs.
    duplicates = df[
        df.duplicated(
            subset=["Year", "Number"],
            keep=False,
        )
    ]

    if not duplicates.empty:
        print("\nWARNING: duplicate Year/Number combinations:")
        print(
            duplicates[
                ["Year", "Number", "URL_Number", "Title", "Source_URL"]
            ].to_string(index=False)
        )

    # Missing IDs.
    missing_ids = df[df["Number"].isna()]

    print(f"Missing contribution IDs: {len(missing_ids)}")

    # URL and displayed ID mismatch.
    mismatches = df[df["ID_URL_Mismatch"] == "Yes"]

    print(f"Displayed ID differs from URL: {len(mismatches)}")

    if not mismatches.empty:
        print("\nID/URL mismatches:")
        print(
            mismatches[
                ["Year", "Number", "URL_Number", "Title", "Source_URL"]
            ].to_string(index=False)
        )

    # Missing titles.
    missing_titles = df[
        df["Title"].fillna("").str.strip() == ""
    ]

    print(f"Missing titles: {len(missing_titles)}")

    # Missing authors.
    missing_authors = df[
        df["Authors"].fillna("").str.strip() == ""
    ]

    print(f"Missing authors: {len(missing_authors)}")

    # Missing categories.
    missing_categories = df[
        df["Category"].fillna("").str.strip() == ""
    ]

    print(f"Missing categories: {len(missing_categories)}")

    # Abstract availability.
    print("\nAbstract availability:")

    print(
        df.groupby(
            ["Year", "Abstract_Available"],
            dropna=False,
        ).size()
    )

    return df


# ============================================================
# SAVE EXCEL
# ============================================================

def save_excel(df):
    columns = [
        "Year",
        "Category",
        "Number",
        "URL_Number",
        "ID_Source",
        "ID_URL_Mismatch",
        "Title",
        "Authors",
        "Abstract",
        "Abstract_Available",
        "Source_URL",
        "Brief_Report_URL",
        "Content_Source",
        "Status",
    ]

    for column in columns:
        if column not in df.columns:
            df[column] = ""

    df = df[columns].copy()

    df = df.sort_values(
        ["Year", "Number"],
        na_position="last",
    )

    with pd.ExcelWriter(
        OUTPUT_FILE,
        engine="openpyxl",
    ) as writer:

        # Master sheet.
        df.to_excel(
            writer,
            sheet_name="Evidence_Master",
            index=False,
        )

        # Individual years.
        for year in [2023, 2024, 2025]:
            df[df["Year"] == year].to_excel(
                writer,
                sheet_name=str(year),
                index=False,
            )

        # README.
        readme = pd.DataFrame({
            "Field": columns,
            "Description": [
                "Symposium year.",
                "Recognized OHDSI showcase category.",
                "Official contribution ID, preferably read from the page.",
                "Number encoded in the source URL.",
                "Whether the ID was read from the page or taken from the URL.",
                "Whether the displayed ID differs from the URL number.",
                "Contribution title.",
                "Authors as published by OHDSI.",
                "Abstract or introductory text extracted from the Brief Report.",
                "Whether usable abstract content was extracted.",
                "Official OHDSI showcase page.",
                "Official Brief Report PDF, where available.",
                "Source from which content was obtained.",
                "Technical extraction status.",
            ],
        })

        readme.to_excel(
            writer,
            sheet_name="README",
            index=False,
        )

    print(f"\nExcel written to: {OUTPUT_FILE}")


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 70)
    print("OHDSI EVIDENCE COLLECTION")
    print("2023–2025")
    print("=" * 70)

    all_results = []

    for year in [2023, 2024, 2025]:
        results = collect_year(year)
        all_results.extend(results)

    df = pd.DataFrame(all_results)

    df = validate(df)

    save_excel(df)

    print("\nRecords per year:")
    print(df.groupby("Year").size())

    print("\nDone.")


if __name__ == "__main__":
    main()