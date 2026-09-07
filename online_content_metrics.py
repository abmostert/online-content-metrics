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
from typing import Iterable, Optional


DEFAULT_DB = "online_content_metrics.db"


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
            (
                name,
                url or None,
                notes,
            ),
        )

        conn.commit()

        print()
        print(f"Website added with ID {cursor.lastrowid}: {name}")

    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="online_content_metrics.py",
        description="Track the effectiveness of online posts."
    )

    parser.add_argument(
        "--db",
        default=DEFAULT_DB,
        help=f"Database file (default: {DEFAULT_DB})"
    )

    sub = parser.add_subparsers(
        dest="command",
        required=True
    )

    init_parser = sub.add_parser(
        "init",
        help="Create the database and tables."
    )

    init_parser.set_defaults(func=cmd_init)

    add_website_parser = sub.add_parser(
        "add-website",
        help="Add a website or platform."
    )

    add_website_parser.set_defaults(func=cmd_add_website)

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
