# -*- coding: utf-8 -*-
"""
BRM 주기 수집기 + 변경 이력 추적

공공데이터포털 API에서 BRM 데이터를 주기적으로 수집하고,
신규/수정/폐지 변경사항을 감지하여 Supabase DB에 누적 저장한다.

사용법:
    python -m src.brm.collector              # 1회 수집
    python -m src.brm.collector --schedule   # 매일 자동 수집 (cron용)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import httpx

KST = timezone(timedelta(hours=9))

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://wmrvypokepngnbcgsjkn.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndtcnZ5cG9rZXBuZ25iY2dzamtuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ4ODA4OTAsImV4cCI6MjA5MDQ1Njg5MH0.NK2DrPR2n_q8ChqjOrh0LRDCC0l6ZKHIQSj_jqjLRHE"
)

DATA_GO_KR_API_KEY = os.getenv("DATA_GO_KR_API_KEY",
    "54cc7e1280432ff67a19bbbdcf88021d35c4c7d34aef5ff81b6f4b948f8b9227"
)
BRM_API_URL = "https://api.odcloud.kr/api/15062615/v1/uddi:4f6f8261-0137-4cb1-be92-eee0752d3c1d"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def fetch_from_api(page: int = 1, per_page: int = 1000) -> list[dict]:
    """공공데이터포털 API에서 BRM 데이터 수집"""
    params = {
        "serviceKey": DATA_GO_KR_API_KEY,
        "page": page,
        "perPage": per_page,
        "returnType": "JSON",
    }
    with httpx.Client(timeout=30) as client:
        r = client.get(BRM_API_URL, params=params)
        if r.status_code == 200:
            data = r.json()
            return data.get("data", [])
        else:
            print(f"  API 오류: {r.status_code} {r.text[:200]}")
            return []


def fetch_all_from_api() -> list[dict]:
    """API에서 전체 BRM 데이터 수집 (페이지네이션)"""
    all_data = []
    page = 1
    while True:
        print(f"  API 페이지 {page} 수집 중...")
        batch = fetch_from_api(page=page, per_page=1000)
        if not batch:
            break
        all_data.extend(batch)
        if len(batch) < 1000:
            break
        page += 1
        time.sleep(0.5)  # Rate limit
    return all_data


def get_existing_nodes(client: httpx.Client) -> dict[str, dict]:
    """Supabase에서 현재 BRM 노드 전체 조회"""
    nodes = {}
    offset = 0
    limit = 1000
    while True:
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/brm_nodes",
            params={"select": "id,name,path,is_active", "offset": offset, "limit": limit},
            headers=HEADERS,
        )
        if r.status_code != 200:
            break
        batch = r.json()
        if not batch:
            break
        for row in batch:
            nodes[row["id"]] = row
        offset += limit
    return nodes


def upsert_nodes(client: httpx.Client, rows: list[dict], batch_size: int = 500) -> int:
    """BRM 노드 upsert"""
    success = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/brm_nodes",
            json=batch,
            headers={**HEADERS, "Prefer": "resolution=merge-duplicates"},
        )
        if r.status_code in (200, 201):
            success += len(batch)
        else:
            print(f"  upsert 실패: {r.status_code}")
        time.sleep(0.3)
    return success


def record_history(client: httpx.Client, entries: list[dict]) -> None:
    """변경 이력 기록"""
    if not entries:
        return
    for i in range(0, len(entries), 500):
        batch = entries[i:i + 500]
        client.post(
            f"{SUPABASE_URL}/rest/v1/brm_history",
            json=batch,
            headers=HEADERS,
        )
        time.sleep(0.2)


def log_collection(client: httpx.Client, source: str, version: str,
                   total: int, new: int, updated: int, deactivated: int,
                   status: str, error: str = "") -> None:
    """수집 로그 기록"""
    client.post(
        f"{SUPABASE_URL}/rest/v1/brm_collection_log",
        json={
            "source": source, "version": version,
            "total_nodes": total, "new_nodes": new,
            "updated_nodes": updated, "deactivated_nodes": deactivated,
            "status": status, "error_message": error,
        },
        headers=HEADERS,
    )


def collect_and_sync(source: str = "csv") -> dict[str, int]:
    """BRM 수집 + Supabase 동기화 + 변경 이력 추적"""
    version = datetime.now(KST).strftime("%Y%m%d")
    client = httpx.Client(timeout=30)
    result = {"total": 0, "new": 0, "updated": 0, "deactivated": 0}

    try:
        # 1. 데이터 수집
        if source == "api":
            print("[1/4] 공공데이터포털 API에서 수집 중...")
            raw_data = fetch_all_from_api()
            new_nodes = {}
            for item in raw_data:
                node_id = item.get("분류체계ID", "")
                if not node_id:
                    continue
                level = item.get("분류체계단계", "")
                if level not in {"정책분야", "정책영역", "대기능", "중기능", "소기능"}:
                    continue
                agencies_raw = item.get("수행기관", "")
                agencies = [a.strip() for a in agencies_raw.split("|") if a.strip()] if agencies_raw else []
                new_nodes[node_id] = {
                    "id": node_id,
                    "name": item.get("분류체계명", "").strip(),
                    "level": level,
                    "parent_id": item.get("상위과제ID", "0").strip(),
                    "path": item.get("분류체계경로", "").strip(),
                    "agencies": agencies,
                    "effective_date": item.get("시행시기", "").strip(),
                    "source": "api",
                    "version": version,
                    "is_active": True,
                }
        else:
            print("[1/4] CSV에서 로드 중...")
            from src.brm.parser import get_brm_tree
            tree = get_brm_tree()
            new_nodes = {}
            for node_id, node in tree.nodes.items():
                new_nodes[node_id] = {
                    "id": node_id,
                    "name": node.name,
                    "level": node.level,
                    "parent_id": node.parent_id,
                    "path": node.path,
                    "agencies": node.agencies,
                    "effective_date": node.effective_date,
                    "source": "csv",
                    "version": version,
                    "is_active": True,
                }

        result["total"] = len(new_nodes)
        print(f"  수집 완료: {result['total']}건")

        # 2. 기존 데이터 조회
        print("[2/4] 기존 DB 데이터 조회 중...")
        existing = get_existing_nodes(client)
        print(f"  기존: {len(existing)}건")

        # 3. 변경 감지
        print("[3/4] 변경 감지 중...")
        history_entries = []

        for nid, new_data in new_nodes.items():
            if nid not in existing:
                # 신규
                result["new"] += 1
                history_entries.append({
                    "brm_id": nid, "action": "created",
                    "new_name": new_data["name"], "new_path": new_data.get("path", ""),
                    "version": version,
                })
            else:
                old = existing[nid]
                if old.get("name") != new_data["name"] or old.get("path") != new_data.get("path", ""):
                    # 수정
                    result["updated"] += 1
                    history_entries.append({
                        "brm_id": nid, "action": "updated",
                        "old_name": old.get("name"), "new_name": new_data["name"],
                        "old_path": old.get("path"), "new_path": new_data.get("path", ""),
                        "version": version,
                    })

        # 폐지 감지 (기존에 있었는데 새 데이터에 없는 노드)
        for eid in existing:
            if eid not in new_nodes and existing[eid].get("is_active"):
                result["deactivated"] += 1
                history_entries.append({
                    "brm_id": eid, "action": "deactivated",
                    "old_name": existing[eid].get("name"),
                    "version": version,
                })

        print(f"  신규: {result['new']}건, 수정: {result['updated']}건, 폐지: {result['deactivated']}건")

        # 4. DB 동기화
        print("[4/4] DB 동기화 중...")
        upsert_rows = list(new_nodes.values())
        upserted = upsert_nodes(client, upsert_rows)
        print(f"  upsert: {upserted}건")

        # 변경 이력 기록
        if history_entries:
            record_history(client, history_entries)
            print(f"  이력: {len(history_entries)}건 기록")

        # 수집 로그
        log_collection(client, source, version, result["total"],
                       result["new"], result["updated"], result["deactivated"], "success")

    except Exception as e:
        print(f"  오류: {e}")
        log_collection(client, source, version, 0, 0, 0, 0, "error", str(e))

    client.close()
    return result


def main():
    parser = argparse.ArgumentParser(description="BRM 주기 수집기")
    parser.add_argument("--source", choices=["csv", "api"], default="api",
                        help="수집 소스 (csv: 로컬 파일, api: 공공데이터포털)")
    parser.add_argument("--schedule", action="store_true",
                        help="스케줄 모드 (cron/scheduled task용)")
    args = parser.parse_args()

    print()
    print("=" * 50)
    print(f"  BRM 수집기 ({args.source} 모드)")
    print(f"  {datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')}")
    print("=" * 50)
    print()

    result = collect_and_sync(source=args.source)

    print()
    print("=" * 50)
    print(f"  수집 완료!")
    print(f"  총: {result['total']}건")
    print(f"  신규: {result['new']}건")
    print(f"  수정: {result['updated']}건")
    print(f"  폐지: {result['deactivated']}건")
    print("=" * 50)


if __name__ == "__main__":
    main()
