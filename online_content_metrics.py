#!/usr/bin/env python3
"""
online_content_metrics.py

Simple database for tracking the effectiveness of published online content.

Structure:

Website / platform
    -> Post
        -> Measurement
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import date
from typing import Iterable, Optional


DEFAULT_DB = "online_content_metrics.db"


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------

def die(message: str, code: int = 2) -> None:
    print(f"Error: {message}", file=sys.stderr)
    sys.exit(code)


def connect_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialise_database(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS websites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            website_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            url TEXT,
            published_date TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (website_id)
                REFERENCES websites(id)
                ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            measurement_date TEXT NOT NULL,

            total_comments INTEGER NOT NULL,
            positive_comments INTEGER NOT NULL,
            negative_comments INTEGER NOT NULL,

            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (post_id)
                REFERENCES posts(id)
                ON DELETE RESTRICT,

            UNIQUE (post_id, measurement_date),

            CHECK (total_comments >= 0),
            CHECK (positive_comments >= 0),
            CHECK (negative_comments >= 0),
            CHECK (
                positive_comments + negative_comments
                <= total_comments
            )
        );

        CREATE INDEX IF NOT EXISTS idx_posts_website
            ON posts(website_id);

        CREATE INDEX IF NOT EXISTS idx_measurements_post
            ON measurements(post_id);

        CREATE INDEX IF NOT EXISTS idx_measurements_date
            ON measurements(measurement_date);
        """
    )

    conn.commit()


def valid_date(value: str) -> str:
    try:
        date.fromisoformat(value)
    except ValueError:
        die("Date must use YYYY-MM-DD format.")

    return value


def prompt_date(label: str, default: Optional[str] = None) -> str:
    if default:
        value = input(f"{label} [{default}]: ").strip()
        value = value or default
    else:
        value = input(f"{label} (YYYY-MM-DD): ").strip()

    return valid_date(value)


def prompt_nonnegative_int(label: str) -> int:
    while True:
        value = input(f"{label}: ").strip()

        try:
            number = int(value)
        except ValueError:
            print("Please enter a whole number.")
            continue

        if number < 0:
            print("Please enter 0 or a positive number.")
            continue

        return number


# ---------------------------------------------------------------------------
# Selection helpers
# ---------------------------------------------------------------------------

def select_website(conn: sqlite3.Connection) -> sqlite3.Row:
    websites = conn.execute(
        """
        SELECT id, name, url
        FROM websites
        ORDER BY name COLLATE NOCASE
        """
    ).fetchall()

    if not websites:
        die("No websites exist yet. Add one first with add-website.")

    print()
    print("Websites:")
    print()

    for website in websites:
        print(f"{website['id']}. {website['name']}")

    print()

    while True:
        value = input("Website ID: ").strip()

        try:
            website_id = int(value)
        except ValueError:
            print("Please enter a website ID.")
            continue

        for website in websites:
            if website["id"] == website_id:
                return website

        print("Website ID not found.")


def select_post(
    conn: sqlite3.Connection,
    website_id: Optional[int] = None,
) -> sqlite3.Row:

    if website_id is None:
        website = select_website(conn)
        website_id = website["id"]

    posts = conn.execute(
        """
        SELECT
            posts.id,
            posts.title,
            posts.published_date,
            posts.website_id,
            websites.name AS website_name
        FROM posts
        JOIN websites ON websites.id = posts.website_id
        WHERE posts.website_id = ?
        ORDER BY posts.published_date DESC, posts.id DESC
        """,
        (website_id,),
    ).fetchall()

    if not posts:
        die("No posts exist for that website.")

    print()
    print("Posts:")
    print()

    for post in posts:
        print(
            f"{post['id']}. {post['title']} "
            f"({post['published_date']})"
        )

    print()

    while True:
        value = input("Post ID: ").strip()

        try:
            post_id = int(value)
        except ValueError:
            print("Please enter a post ID.")
            continue

        for post in posts:
            if post["id"] == post_id:
                return post

        print("Post ID not found.")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_init(args: argparse.Namespace) -> None:
    conn = connect_db(args.db)

    try:
        initialise_database(conn)
    finally:
        conn.close()

    print(f"Database ready: {args.db}")


def cmd_add_website(args: argparse.Namespace) -> None:
    conn = connect_db(args.db)

    try:
        initialise_database(conn)

        name = input("Website/platform name: ").strip()

        if not name:
            die("Website/platform name cannot be empty.")

        url = input("Website URL (optional): ").strip()
        notes = input("Notes (optional): ").strip()

        cursor = conn.execute(
            """
            INSERT INTO websites (name, url, notes)
            VALUES (?, ?, ?)
            """,
            (name, url or None, notes),
        )

        conn.commit()

        print()
        print(f"Website added with ID {cursor.lastrowid}: {name}")

    finally:
        conn.close()


def cmd_list_websites(args: argparse.Namespace) -> None:
    conn = connect_db(args.db)

    try:
        initialise_database(conn)

        websites = conn.execute(
            """
            SELECT
                websites.id,
                websites.name,
                websites.url,
                COUNT(posts.id) AS post_count
            FROM websites
            LEFT JOIN posts ON posts.website_id = websites.id
            GROUP BY websites.id
            ORDER BY websites.name COLLATE NOCASE
            """
        ).fetchall()

        if not websites:
            print("No websites found.")
            return

        print()
        print("Websites")
        print("--------")

        for website in websites:
            print(
                f"[{website['id']}] {website['name']} "
                f"- {website['post_count']} post(s)"
            )

            if website["url"]:
                print(f"    {website['url']}")

    finally:
        conn.close()


def cmd_add_post(args: argparse.Namespace) -> None:
    conn = connect_db(args.db)

    try:
        initialise_database(conn)

        website = select_website(conn)

        print()
        title = input("Post title: ").strip()

        if not title:
            die("Post title cannot be empty.")

        url = input("Post URL (optional): ").strip()

        published_date = prompt_date(
            "Publication date",
            default=date.today().isoformat(),
        )

        notes = input("Notes (optional): ").strip()

        cursor = conn.execute(
            """
            INSERT INTO posts (
                website_id,
                title,
                url,
                published_date,
                notes
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                website["id"],
                title,
                url or None,
                published_date,
                notes,
            ),
        )

        conn.commit()

        print()
        print(f"Post added with ID {cursor.lastrowid}: {title}")

    finally:
        conn.close()


def cmd_list_posts(args: argparse.Namespace) -> None:
    conn = connect_db(args.db)

    try:
        initialise_database(conn)

        posts = conn.execute(
            """
            SELECT
                posts.id,
                posts.title,
                posts.published_date,
                posts.url,
                websites.name AS website_name,
                COUNT(measurements.id) AS measurement_count
            FROM posts
            JOIN websites
                ON websites.id = posts.website_id
            LEFT JOIN measurements
                ON measurements.post_id = posts.id
            GROUP BY posts.id
            ORDER BY posts.published_date DESC, posts.id DESC
            """
        ).fetchall()

        if not posts:
            print("No posts found.")
            return

        print()
        print("Posts")
        print("-----")

        current_website = None

        for post in posts:
            if post["website_name"] != current_website:
                current_website = post["website_name"]
                print()
                print(current_website)

            print(
                f"  [{post['id']}] {post['title']} "
                f"- published {post['published_date']} "
                f"- {post['measurement_count']} measurement(s)"
            )

    finally:
        conn.close()


def cmd_add_measurement(args: argparse.Namespace) -> None:
    conn = connect_db(args.db)

    try:
        initialise_database(conn)

        website = select_website(conn)
        post = select_post(conn, website["id"])

        print()

        measurement_date = prompt_date(
            "Measurement date",
            default=date.today().isoformat(),
        )

        total = prompt_nonnegative_int("Total comments")
        positive = prompt_nonnegative_int(
            "Estimated positive comments"
        )
        negative = prompt_nonnegative_int(
            "Estimated negative comments"
        )

        if positive + negative > total:
            die(
                "Positive comments plus negative comments "
                "cannot exceed total comments."
            )

        notes = input("Notes (optional): ").strip()

        try:
            cursor = conn.execute(
                """
                INSERT INTO measurements (
                    post_id,
                    measurement_date,
                    total_comments,
                    positive_comments,
                    negative_comments,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    post["id"],
                    measurement_date,
                    total,
                    positive,
                    negative,
                    notes,
                ),
            )

            conn.commit()

        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint failed" in str(exc):
                die(
                    "A measurement already exists for this "
                    "post on that date."
                )

            raise

        print()
        print(
            f"Measurement added with ID {cursor.lastrowid} "
            f"for: {post['title']}"
        )

    finally:
        conn.close()


def cmd_show_post(args: argparse.Namespace) -> None:
    conn = connect_db(args.db)

    try:
        initialise_database(conn)

        website = select_website(conn)
        selected_post = select_post(conn, website["id"])

        post = conn.execute(
            """
            SELECT
                posts.*,
                websites.name AS website_name
            FROM posts
            JOIN websites
                ON websites.id = posts.website_id
            WHERE posts.id = ?
            """,
            (selected_post["id"],),
        ).fetchone()

        measurements = conn.execute(
            """
            SELECT *
            FROM measurements
            WHERE post_id = ?
            ORDER BY measurement_date
            """,
            (post["id"],),
        ).fetchall()

        print()
        print("=" * 60)
        print(post["title"])
        print("=" * 60)
        print(f"Website:   {post['website_name']}")
        print(f"Published: {post['published_date']}")

        if post["url"]:
            print(f"URL:       {post['url']}")

        if post["notes"]:
            print(f"Notes:     {post['notes']}")

        print()
        print("Measurements")
        print("------------")

        if not measurements:
            print("No measurements recorded.")
            return

        for measurement in measurements:
            total = measurement["total_comments"]
            positive = measurement["positive_comments"]
            negative = measurement["negative_comments"]
            neutral = total - positive - negative

            if total > 0:
                positive_pct = 100 * positive / total
                negative_pct = 100 * negative / total
            else:
                positive_pct = 0.0
                negative_pct = 0.0

            print()
            print(measurement["measurement_date"])
            print(f"  Total comments:     {total}")
            print(
                f"  Positive comments:  {positive} "
                f"({positive_pct:.1f}%)"
            )
            print(
                f"  Negative comments:  {negative} "
                f"({negative_pct:.1f}%)"
            )
            print(f"  Other/neutral:      {neutral}")

            if measurement["notes"]:
                print(f"  Notes: {measurement['notes']}")

    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="online_content_metrics.py",
        description="Track the effectiveness of online posts.",
    )

    parser.add_argument(
        "--db",
        default=DEFAULT_DB,
        help=f"Database file (default: {DEFAULT_DB})",
    )

    sub = parser.add_subparsers(
        dest="command",
        required=True,
    )

    init_parser = sub.add_parser(
        "init",
        help="Create the database and tables.",
    )
    init_parser.set_defaults(func=cmd_init)

    add_website_parser = sub.add_parser(
        "add-website",
        help="Add a website or platform.",
    )
    add_website_parser.set_defaults(func=cmd_add_website)

    list_websites_parser = sub.add_parser(
        "list-websites",
        help="List websites and platforms.",
    )
    list_websites_parser.set_defaults(func=cmd_list_websites)

    add_post_parser = sub.add_parser(
        "add-post",
        help="Add a published post.",
    )
    add_post_parser.set_defaults(func=cmd_add_post)

    list_posts_parser = sub.add_parser(
        "list-posts",
        help="List published posts.",
    )
    list_posts_parser.set_defaults(func=cmd_list_posts)

    add_measurement_parser = sub.add_parser(
        "add-measurement",
        help="Add a metric measurement for a post.",
    )
    add_measurement_parser.set_defaults(func=cmd_add_measurement)

    show_post_parser = sub.add_parser(
        "show-post",
        help="Show a post and its measurements.",
    )
    show_post_parser.set_defaults(func=cmd_show_post)

    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()

    args = parser.parse_args(
        list(argv) if argv is not None else None
    )

    args.func(args)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
