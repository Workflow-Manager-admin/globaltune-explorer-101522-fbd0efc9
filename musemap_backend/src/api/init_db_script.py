"""
Script to initialize SQLite database and tables for MuseMap backend.
Should be used to ensure the DB file exists before backend is run by frontend or behind a proxy.
"""

from main import init_db

if __name__ == "__main__":
    print("Initializing MuseMap SQLite DB...")
    init_db()
    print("Initialization complete. You should now see musemap.sqlite3 in the project root.")
