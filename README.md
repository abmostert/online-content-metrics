# Online Content Metrics

A simple local-first Python CLI for tracking the performance of published online content over time.

The program is designed to answer questions such as:

* Which websites or platforms generate the most engagement?
* Which individual posts perform best?
* How does engagement change over time after publication?
* What proportion of comments are broadly positive, negative, or neutral?
* What observations or patterns are associated with particular posts?

The project intentionally starts with a small, simple data model and can be extended with additional metrics later.

## Data structure

The database has three levels:

```text
Website / platform
    └── Post
          └── Measurement
```

For example:

```text
Reddit - r/Entrepreneur
│
└── Example post
    Published: 2026-09-15
    │
    ├── Measurement: 2026-09-15
    │   ├── Total comments: 20
    │   ├── Positive comments: 12
    │   ├── Negative comments: 3
    │   └── Notes: ...
    │
    └── Measurement: 2026-09-22
        ├── Total comments: 45
        ├── Positive comments: 30
        ├── Negative comments: 5
        └── Notes: ...
```

## Storage

The program uses SQLite.

The default database file is:

```text
online_content_metrics.db
```

The database is stored locally and is excluded from Git by `.gitignore`.

The repository therefore contains the program code, but not the user's real content-performance data.

## Requirements

* Python 3
* SQLite support included with Python

No external Python packages are currently required.

## Basic usage

Initialise the database:

```bash
python3 online_content_metrics.py init
```

### Websites

Add a website or platform:

```bash
python3 online_content_metrics.py add-website
```

List websites:

```bash
python3 online_content_metrics.py list-websites
```

Edit an existing website:

```bash
python3 online_content_metrics.py edit-website
```

A website can represent a platform or a specific publishing location, for example:

```text
Medium
X
LinkedIn
Reddit - r/Entrepreneur
Reddit - r/smallbusiness
```

### Posts

Add a published post:

```bash
python3 online_content_metrics.py add-post
```

List posts:

```bash
python3 online_content_metrics.py list-posts
```

Edit an existing post:

```bash
python3 online_content_metrics.py edit-post
```

Each post is associated with a website and includes:

* title
* publication date
* optional URL
* optional notes

### Measurements

Add a measurement:

```bash
python3 online_content_metrics.py add-measurement
```

Show a post and its measurement history:

```bash
python3 online_content_metrics.py show-post
```

Edit an existing measurement:

```bash
python3 online_content_metrics.py edit-measurement
```

Each measurement records:

* measurement date
* total number of comments
* estimated number of positive comments
* estimated number of negative comments
* optional notes

Comments that are neither classified as positive nor negative are treated as other/neutral:

```text
other = total comments - positive comments - negative comments
```

The program also calculates positive and negative comment percentages when displaying a post.

## Example workflow

Add a website:

```bash
python3 online_content_metrics.py add-website
```

Add a post under that website:

```bash
python3 online_content_metrics.py add-post
```

Add the first measurement:

```bash
python3 online_content_metrics.py add-measurement
```

A few days later, add another measurement for the same post:

```bash
python3 online_content_metrics.py add-measurement
```

View the measurement history:

```bash
python3 online_content_metrics.py show-post
```

## Database safeguards

The program currently enforces several basic rules:

* comment counts cannot be negative
* positive comments plus negative comments cannot exceed total comments
* posts must belong to an existing website
* measurements must belong to an existing post
* only one measurement can exist for a particular post on a particular date
* deleting related database records is restricted by foreign-key relationships

## Current commands

```text
init

add-website
list-websites
edit-website

add-post
list-posts
edit-post

add-measurement
show-post
edit-measurement
```

View the full CLI help with:

```bash
python3 online_content_metrics.py --help
```

## Current status

The core data-management layer is implemented.

The program can currently:

* create the SQLite database
* add, list, and edit websites
* add, list, and edit posts
* add and edit repeated dated measurements
* display measurement history for an individual post
* calculate basic positive, negative, and neutral comment proportions

## Planned development

The next development stage is analytics.

Planned features include:

* overall content metrics
* comment growth over time
* comments gained between measurements
* comments per day
* post age
* comparison between posts
* comparison between websites or platforms
* performance at comparable post ages
* graphs of engagement over time

The aim is to move from simple data collection toward understanding which content performs best, where it performs best, and how performance develops after publication.

## Project philosophy

The project is intended to remain:

* local-first
* simple
* transparent
* easy to back up
* easy to modify
* independent of external services

The emphasis is on collecting useful observations consistently first, then building analysis on top of reliable data.

