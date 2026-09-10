import json
import sqlite3
import time
from contextlib import contextmanager
from . import config


@contextmanager
def connect():
    con = sqlite3.connect(config.DB, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init():
    config.prepare()
    with connect() as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
          name TEXT NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL,
          active INTEGER NOT NULL DEFAULT 1, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(
          token TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id), expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS login_attempts(identity TEXT PRIMARY KEY,started REAL NOT NULL,hits INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS jobs(
          id TEXT PRIMARY KEY, url TEXT NOT NULL, owner TEXT REFERENCES users(id),
          status TEXT NOT NULL, stage TEXT NOT NULL, created REAL NOT NULL,
          updated REAL NOT NULL, payload TEXT NOT NULL DEFAULT '{}', error TEXT);
        CREATE INDEX IF NOT EXISTS jobs_created ON jobs(created DESC);
        """)


def setting(key, default=""):
    with connect() as con:
        row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def settings():
    with connect() as con:
        return {r["key"]: r["value"] for r in con.execute("SELECT * FROM settings")}


def save_settings(values):
    with connect() as con:
        con.executemany(
            "INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", values.items()
        )


def job(job_id):
    with connect() as con:
        row = con.execute(
            "SELECT j.*,u.name owner_name FROM jobs j JOIN users u ON u.id=j.owner WHERE j.id=?",
            (job_id,),
        ).fetchone()
    return unpack(row) if row else None


def unpack(row):
    result = dict(row)
    result["result"] = json.loads(result.pop("payload"))
    return result


def update(job_id, *, status=None, stage=None, result=None, error=None):
    assignments, values = ["updated=?", "error=?"], [time.time(), error]
    for key, value in [
        ("status", status),
        ("stage", stage),
        (
            "payload",
            json.dumps(result, ensure_ascii=False) if result is not None else None,
        ),
    ]:
        if value is not None:
            assignments.append(key + "=?")
            values.append(value)
    with connect() as con:
        con.execute(
            "UPDATE jobs SET " + ",".join(assignments) + " WHERE id=?",
            (*values, job_id),
        )
