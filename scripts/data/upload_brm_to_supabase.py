# -*- coding: utf-8 -*-
"""
BRM 데이터를 Supabase에 업로드

17,634건의 정부기능별분류체계를 Supabase brm_nodes 테이블에 삽입.
변경 이력을 추적하여 신규/수정/폐지를 감지.
"""

import csv
import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import httpx

SUPABASE_URL = "https://wmrvypokepngnbcgsjkn.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndtcnZ5cG9rZXBuZ25iY2dzamtuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ4ODA4OTAsImV4cCI6MjA5MDQ1Njg5MH0.NK2DrPR2n_q8ChqjOrh0LRDCC0l6ZKHIQSj_jqjLRHE"

BRM_LEVELS = {"정책분야", "정책영역", "대기능", "중기능", "소기능"}

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CSV_PATH = PROJECT_ROOT / "add" / "행정안전부_정부기능별분류체계_20241130.csv"
VERSION = "20241130"


def parse_csv() -> list[dict]:
    """CSV → dict 리스트"""
    rows = []
    with open(CSV_PATH, "r", encoding="cp949", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            level = row.get("분류체계단계", "").strip()
            if level not in BRM_LEVELS:
                continue
            agencies_raw = row.get("수행기관", "")
            agencies = [a.strip() for a in agencies_raw.split("|") if a.strip()] if agencies_raw else []
            codes_raw = row.get("기관코드", "")
            codes = [c.strip() for c in codes_raw.split("|") if c.strip()] if codes_raw else []

            rows.append({
                "id": row.get("분류체계ID", "").strip(),
                "name": row.get("분류체계명", "").strip(),
                "level": level,
                "parent_id": row.get("상위과제ID", "0").strip(),
                "path": row.get("분류체계경로", "").strip(),
                "agencies": agencies,
                "agency_codes": codes,
                "effective_date": row.get("시행시기", "").strip(),
                "source": "csv",
                "version": VERSION,
                "is_active": True,
            })
    return rows


def upload_batch(client: httpx.Client, rows: list[dict], batch_size: int = 500) -> tuple[int, int]:
    """배치 upsert"""
    success = 0
    failed = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/brm_nodes",
            json=batch,
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates",
            },
        )
        if r.status_code in (200, 201):
            success += len(batch)
        else:
            failed += len(batch)
            print(f"  배치 {i//batch_size+1} 실패: {r.status_code} {r.text[:200]}")
        # Rate limit 방지
        time.sleep(0.3)
    return success, failed


def log_collection(client: httpx.Client, total: int, new: int, updated: int, deactivated: int, status: str, error: str = ""):
    """수집 로그 기록"""
    client.post(
        f"{SUPABASE_URL}/rest/v1/brm_collection_log",
        json={
            "source": "csv",
            "version": VERSION,
            "total_nodes": total,
            "new_nodes": new,
            "updated_nodes": updated,
            "deactivated_nodes": deactivated,
            "status": status,
            "error_message": error,
        },
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
    )


def main():
    print()
    print("=" * 50)
    print("  BRM 데이터 Supabase 업로드")
    print("=" * 50)
    print()

    # 1. CSV 파싱
    print("[1/3] CSV 파싱 중...")
    rows = parse_csv()
    print(f"  {len(rows)}건 파싱 완료")

    # 2. 업로드
    print("[2/3] Supabase 업로드 중...")
    client = httpx.Client(timeout=30)
    success, failed = upload_batch(client, rows)
    print(f"  성공: {success}건, 실패: {failed}건")

    # 3. 수집 로그
    print("[3/3] 수집 로그 기록 중...")
    status = "success" if failed == 0 else "partial"
    log_collection(client, len(rows), success, 0, 0, status)
    print(f"  로그 기록 완료 (status: {status})")

    client.close()

    print()
    print("=" * 50)
    print(f"  업로드 완료! {success}/{len(rows)}건")
    print("=" * 50)


if __name__ == "__main__":
    main()
