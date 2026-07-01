"""
tools/seed_availability.py

Seed script for populating Supabase availability table with demo slots.

Prerequisites:
1. Create tables in Supabase → SQL Editor, then run:

create table appointments (
  id uuid primary key default gen_random_uuid(),
  created_at timestamp with time zone default now(),
  naam text not null,
  telefoon text not null,
  datum date not null,
  tijdstip time not null,
  probleem text not null,
  status text default 'gepland'
);

create table availability (
  id uuid primary key default gen_random_uuid(),
  dag date not null,
  tijdslot time not null,
  beschikbaar boolean default true
);

2. Run this script from project root:
   python tools/seed_availability.py

3. Verify in Supabase Table Editor → availability table
"""

from supabase import create_client
import os
from dotenv import load_dotenv
from datetime import date, timedelta
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

slots = ["09:00:00", "10:00:00", "11:00:00", "13:00:00", "14:00:00", "15:00:00", "16:00:00"]
today = date.today()

rows = []
for i in range(1, 15):
    dag = today + timedelta(days=i)
    if dag.weekday() < 5:
        for tijdslot in slots:
            rows.append({"dag": dag.isoformat(), "tijdslot": tijdslot, "beschikbaar": True})

supabase.table("availability").insert(rows).execute()
print(f"Seeded {len(rows)} slots.")
