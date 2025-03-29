#!/usr/bin/env python3
"""
archive.ph Python Client

A simple client for the archive.ph service that allows you to:
- Submit URLs for archiving
- Get the archive URL/ID
- List past snapshots of a URL (timemap)

Usage:
  python archive_today.py <url>                - Archive a URL and wait for completion
  python archive_today.py -r <url>             - Renew archive of a URL
  python archive_today.py -c <url>             - Submit URL but don't wait for completion
  python archive_today.py timemap <url>        - List past snapshots of a URL
  python archive_today.py -h                   - Show help message
"""

import argparse
import random
import re
import requests
import sys
import time
from datetime import datetime
from urllib.parse import urlparse, urlunparse

# List of common user agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0",
]

def get_random_user_agent():
    """Get a random user agent from the list."""
    return random.choice(USER_AGENTS)

def snapshot(url, domain="https://archive.ph", user_agent=None, renew=False, complete=True):
    """
    Submit a URL to archive.ph and get the archive URL.

    Args:
        url: The URL to archive
        domain: The archive.ph domain mirror to use
        user_agent: User agent to use (random if None)
        renew: Whether to request a fresh snapshot even if recently archived
        complete: Whether to wait for archiving to complete

    Returns:
        dict: Contains the archive URL, WIP URL (if applicable), and cache date (if applicable)
    """
    if not user_agent:
        user_agent = get_random_user_agent()

    headers = {
        "User-Agent": user_agent,
        "Content-Type": "application/x-www-form-urlencoded",
    }

    # Step 1: Initial request to get the submission token
    session = requests.Session()
    r = session.get(domain, headers=headers)
    r.raise_for_status()

    # Extract the submission token
    submit_id_match = re.search(r'name="submitid" value="([^"]+)"', r.text)
    if not submit_id_match:
        raise Exception("Could not find submission token")

    submit_id = submit_id_match.group(1)

    # Step 2: Submit the URL for archiving
    data = {
        "url": url,
        "submitid": submit_id,
    }

    if renew:
        data["anyway"] = 1

    r = session.post(domain + "/submit/", data=data, headers=headers, allow_redirects=False)

    result = {}

    # Check if we got a redirect to an existing snapshot
    if r.status_code == 302 and "Location" in r.headers:
        archive_url = r.headers["Location"]
        if not archive_url.startswith("http"):
            archive_url = domain + archive_url

        result["url"] = archive_url

        # Get the cache date
        r = session.get(archive_url, headers=headers)
        r.raise_for_status()

        date_match = re.search(r'Saved from.+?(\d{1,2} [a-zA-Z]+ \d{4} \d{2}:\d{2}:\d{2})', r.text)
        if date_match:
            result["cached_date"] = date_match.group(1)

        return result

    # If we're starting a new archive
    # Extract the WIP URL
    wip_match = re.search(r'document\.location\.replace\("([^"]+)"\)', r.text)
    if not wip_match:
        raise Exception("Could not find WIP URL")

    wip_url = wip_match.group(1)
    if not wip_url.startswith("http"):
        wip_url = domain + wip_url

    result["wip"] = wip_url

    # If we don't need to wait for completion, return the WIP URL
    if not complete:
        # The final URL will be the WIP URL with "/wip" removed
        final_url = wip_url.replace("/wip", "")
        result["url"] = final_url
        return result

    # Otherwise, wait for archiving to complete
    print("Waiting for archiving to complete...", file=sys.stderr)

    archive_url = None
    max_retries = 30
    retry_count = 0

    while retry_count < max_retries:
        r = session.get(wip_url, headers=headers)
        r.raise_for_status()

        # Check if archiving is complete
        if r.url != wip_url:
            archive_url = r.url
            break

        # Check for redirection in JavaScript
        redirect_match = re.search(r'document\.location\.replace\("([^"]+)"\)', r.text)
        if redirect_match:
            redirect_url = redirect_match.group(1)
            if not redirect_url.startswith("http"):
                redirect_url = domain + redirect_url

            # If the redirect is not to a WIP URL, we're done
            if "/wip" not in redirect_url:
                archive_url = redirect_url
                break

        retry_count += 1
        time.sleep(2)

    if not archive_url:
        raise Exception("Archiving did not complete in the expected time")

    result["url"] = archive_url
    return result

def _search(url, domain, headers):
    # URL encode for the query parameter
    search_url = f"{domain}/search/?q={url}"
    r = requests.get(search_url, headers=headers)
    r.raise_for_status()

    pattern = r'<div[^>]*>((?:\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\s+\d{1,2}:\d{2})|(?:\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}))</div></a></div></div><div[^>]*><a[^>]*href="([^"]+)"'
    return re.findall(pattern, r.text, re.DOTALL)

def timemap(url, domain="https://archive.ph", user_agent=None):
    """
    Get a list of previous snapshots for a URL.

    Args:
        url: The URL to get snapshots for
        domain: The archive.ph domain mirror to use
        user_agent: User agent to use (random if None)

    Returns:
        list: List of dicts containing snapshot date and URL
    """
    if not user_agent:
        user_agent = get_random_user_agent()

    headers = {
        "User-Agent": user_agent,
    }

    matches = _search(url, domain, headers)
    print(matches)
    if not matches:
        parsed_url = urlparse(url)
        no_qp_url = urlunparse((
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            parsed_url.params,
            None,  # No query parameters
            parsed_url.fragment
        ))
        matches = _search(no_qp_url, domain, headers)

    print(f"Found {len(matches)} snapshots for {url}", file=sys.stderr)

    results = []
    for date_text, href in matches:
        snapshot_url = href
        date_text = date_text.strip()

        results.append({
            "url": snapshot_url,
            "date": date_text
        })

    return results

def get_latest_snapshot(url, domain="https://archive.ph", user_agent=None):
    """
    Get a latest snapshot URL for a given URL.

    Args:
        url: The URL to get snapshots for
        domain: The archive.ph domain mirror to use
        user_agent: User agent to use (random if None)

    Returns:
        str: The latest snapshot URL or None if not found
    """
    results = timemap(url, domain=domain, user_agent=user_agent)

    if not results:
        return None

    latest_entry = max(results, key=lambda x: datetime.strptime(x["date"], "%d %b %Y %H:%M"))
    return latest_entry["url"]

def main():
    parser = argparse.ArgumentParser(description="archive.ph Python Client")
    parser.add_argument("command", nargs="?", default="snapshot",
                      help="Command to run: 'snapshot' (default) or 'timemap'")
    parser.add_argument("url", nargs="?", help="The URL to archive or get snapshots for")
    parser.add_argument("-d", "--domain", default="https://archive.ph",
                      help="Domain mirror to use (default: https://archive.ph)")
    parser.add_argument("-q", "--quiet", action="store_true",
                      help="Only output the archive URL")
    parser.add_argument("-r", "--renew", action="store_true",
                      help="Request a fresh snapshot")
    parser.add_argument("-c", "--incomplete", action="store_true",
                      help="Don't wait for archiving to complete")
    parser.add_argument("-u", "--user-agent",
                      help="User agent override (defaults to a random user agent)")

    args = parser.parse_args()

    # Handle special case for "timemap" command
    if args.command == "timemap" and args.url is None:
        args.url = args.command
        args.command = "snapshot"

    # If URL is missing, show help and exit
    if args.url is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "timemap" or args.url == "timemap":
        # If the command is timemap, the URL is the second argument
        url = args.url if args.command == "timemap" else args.url
        try:
            mementos = timemap(url, domain=args.domain, user_agent=args.user_agent)
            if not mementos:
                print(f"{url} has not been archived yet.", file=sys.stderr)
                sys.exit(1)

            for memento in mementos:
                print(f"{memento['date']}: {memento['url']}")
        except Exception as e:
            print(f"Error: {str(e)}", file=sys.stderr)
            sys.exit(1)
    else:
        if not args.quiet:
            print(f"Snapshotting {args.url}...", file=sys.stderr)

        try:
            result = snapshot(
                args.url,
                domain=args.domain,
                user_agent=args.user_agent,
                renew=args.renew,
                complete=not args.incomplete
            )

            if args.quiet:
                print(result["url"])
            else:
                print(f"\nSnapshot: {result['url']}")

                if "wip" in result:
                    print(f"WIP: {result['wip']}")

                if "cached_date" in result:
                    print(f"Originally saved at {result['cached_date']}")
                    print("\n- Use the --renew flag to request a fresh snapshot of this URL.")
        except Exception as e:
            print(f"Error: {str(e)}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()
