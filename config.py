import sqlite3
from typing import List, Tuple

def init_database(db_path: str = "mobile_network.db") -> None:
    """Initialize the SQLite database with the required schema."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables
    cursor.executescript("""
    -- Countries table
    CREATE TABLE IF NOT EXISTS countries (
        mcc TEXT PRIMARY KEY,
        country_name TEXT NOT NULL
    );

    -- Operators table (can operate in multiple countries)
    CREATE TABLE IF NOT EXISTS operators (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        operator_name TEXT NOT NULL UNIQUE
    );

    -- Operator Country Mappings (handles different MNCs per country)
    CREATE TABLE IF NOT EXISTS operator_country_mappings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        operator_id INTEGER,
        mcc TEXT,
        mnc TEXT,
        FOREIGN KEY (operator_id) REFERENCES operators(id),
        FOREIGN KEY (mcc) REFERENCES countries(mcc),
        UNIQUE(mcc, mnc)
    );

    -- Frequency Bands
    CREATE TABLE IF NOT EXISTS frequency_bands (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        earfcn_arfcn TEXT,
        frequency_mhz REAL,
        bandwidth_mhz REAL,
        technology TEXT CHECK(technology IN ('2G', '3G', '4G', '5G'))
    );

    -- Operator Frequency Mappings
    CREATE TABLE IF NOT EXISTS operator_frequency_mappings (
        operator_country_id INTEGER,
        frequency_band_id INTEGER,
        active_since DATE,
        notes TEXT,
        FOREIGN KEY (operator_country_id) REFERENCES operator_country_mappings(id),
        FOREIGN KEY (frequency_band_id) REFERENCES frequency_bands(id),
        PRIMARY KEY (operator_country_id, frequency_band_id)
    );
    """)
"""
    # Insert some sample data
    sample_data = [
        ("INSERT INTO countries (mcc, country_name) VALUES (?, ?)",
         [('208', 'France'), ('234', 'United Kingdom'), ('310', 'United States')]),
        
        ("INSERT INTO operators (operator_name) VALUES (?)",
         [('Orange',), ('Vodafone',), ('T-Mobile',)]),
        
        ("INSERT INTO operator_country_mappings (operator_id, mcc, mnc) VALUES (?, ?, ?)",
         [(1, '208', '01'), (2, '234', '15'), (3, '310', '260')])
    ]

    for query, data in sample_data:
        try:
            cursor.executemany(query, data)
        except sqlite3.IntegrityError:
            print(f"Some sample data already exists, skipping...")

    conn.commit()
    conn.close()
"""
def add_frequency_band(db_path: str, earfcn_arfcn: str, frequency_mhz: float, 
                      bandwidth_mhz: float, technology: str) -> None:
    """Add a new frequency band to the database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
    INSERT INTO frequency_bands (earfcn_arfcn, frequency_mhz, bandwidth_mhz, technology)
    VALUES (?, ?, ?, ?)
    """, (earfcn_arfcn, frequency_mhz, bandwidth_mhz, technology))
    
    conn.commit()
    conn.close()

def get_operator_frequencies(db_path: str, country_name: str, operator_name: str) -> List[Tuple]:
    """Get all frequencies for a specific operator in a country."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT f.earfcn_arfcn, f.frequency_mhz, f.bandwidth_mhz, f.technology,
           ofm.active_since, ofm.notes
    FROM frequency_bands f
    JOIN operator_frequency_mappings ofm ON f.id = ofm.frequency_band_id
    JOIN operator_country_mappings ocm ON ofm.operator_country_id = ocm.id
    JOIN operators o ON ocm.operator_id = o.id
    JOIN countries c ON ocm.mcc = c.mcc
    WHERE c.country_name = ? AND o.operator_name = ?
    """, (country_name, operator_name))
    
    results = cursor.fetchall()
    conn.close()
    return results

if __name__ == "__main__":
    init_database()