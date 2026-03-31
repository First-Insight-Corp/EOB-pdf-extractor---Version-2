import sys
import os
import json

sys.path.append(os.getcwd())

from db import db
from sqlalchemy import text


RESPONSES_DIR = "responses"


def parse_json_maybe(value):
    if value is None:
        return None

    if isinstance(value, (dict, list)):
        return value

    if isinstance(value, str):
        s = value.strip()

        # Handle accidentally fenced markdown JSON blobs.
        if s.startswith("```json"):
            s = s[7:]
        if s.startswith("```"):
            s = s[3:]
        if s.endswith("```"):
            s = s[:-3]
        s = s.strip()

        try:
            return json.loads(s)
        except Exception:
            return value

    return value


def normalize_final_response(value):
    payload = parse_json_maybe(value)

    # Unwrap old API envelope if it was mistakenly saved as final_response.
    if isinstance(payload, dict) and "data" in payload and isinstance(payload["data"], (dict, list)):
        envelope_keys = {
            "status",
            "message",
            "document_info",
            "processed_id",
            "response_file",
            "processing_metadata",
            "data",
        }
        if any(k in payload for k in envelope_keys):
            payload = payload["data"]

    # Unwrap nested key if legacy scripts saved {"final_response": {...}}.
    if isinstance(payload, dict) and "final_response" in payload and isinstance(payload["final_response"], (dict, list)):
        payload = payload["final_response"]

    return payload


if not db:
    print("Database connection not available.")
    raise SystemExit(1)

updated_from_files = 0
updated_by_normalization = 0
updated_raw_text = 0
skipped = 0
errors = 0

# Ensure column exists for older databases.
with db.engine.begin() as conn:
    try:
        conn.execute(text("ALTER TABLE processed_files ADD COLUMN final_response JSON NULL"))
        print("Added final_response column to processed_files table.")
    except Exception as e:
        if "Duplicate column name" in str(e):
            print("Column final_response already exists.")
        else:
            print(f"Failed to add final_response column: {e}")
            raise

    try:
        conn.execute(text("ALTER TABLE processed_files ADD COLUMN final_response_raw_text LONGTEXT NULL"))
        print("Added final_response_raw_text column to processed_files table.")
    except Exception as e:
        if "Duplicate column name" in str(e):
            print("Column final_response_raw_text already exists.")
        else:
            print(f"Failed to add final_response_raw_text column: {e}")
            raise

# Backfill/fix existing values to match responses folder format.
with db.engine.begin() as conn:
    rows = conn.execute(
        text(
            """
            SELECT processed_file_id, request_logs, final_response, final_response_raw_text
            FROM processed_files
            WHERE final_response IS NOT NULL
            """
        )
    ).fetchall()

    print(f"Rows with existing final_response: {len(rows)}")

    for row in rows:
        processed_file_id = row[0]
        request_logs = parse_json_maybe(row[1])
        existing_final = parse_json_maybe(row[2])
        existing_raw_text = row[3]

        try:
            response_file = None
            if isinstance(request_logs, dict):
                response_file = request_logs.get("response_file")

            file_payload = None
            if response_file:
                response_path = os.path.join(RESPONSES_DIR, response_file)
                if os.path.exists(response_path):
                    with open(response_path, "r", encoding="utf-8") as handle:
                        file_raw_text = handle.read()
                    with open(response_path, "r", encoding="utf-8") as handle:
                        file_payload = json.load(handle)
                else:
                    file_raw_text = None
            else:
                file_raw_text = None

            # Highest priority: exact content from responses/*.json
            if file_payload is not None:
                needs_json_update = existing_final != file_payload
                needs_raw_update = existing_raw_text != file_raw_text

                if needs_json_update or needs_raw_update:
                    conn.execute(
                        text(
                            """
                            UPDATE processed_files
                            SET final_response = :payload,
                                final_response_raw_text = :raw_text
                            WHERE processed_file_id = :processed_file_id
                            """
                        ),
                        {
                            "payload": json.dumps(file_payload),
                            "raw_text": file_raw_text,
                            "processed_file_id": processed_file_id,
                        },
                    )
                    if needs_json_update:
                        updated_from_files += 1
                    if needs_raw_update:
                        updated_raw_text += 1
                else:
                    skipped += 1
                continue

            # Fallback: normalize currently stored value.
            normalized_payload = normalize_final_response(existing_final)
            normalized_raw_text = json.dumps(normalized_payload, indent=2)
            if normalized_payload != existing_final:
                conn.execute(
                    text(
                        """
                        UPDATE processed_files
                        SET final_response = :payload,
                            final_response_raw_text = :raw_text
                        WHERE processed_file_id = :processed_file_id
                        """
                    ),
                    {
                        "payload": json.dumps(normalized_payload),
                        "raw_text": normalized_raw_text,
                        "processed_file_id": processed_file_id,
                    },
                )
                updated_by_normalization += 1
            else:
                if existing_raw_text != normalized_raw_text:
                    conn.execute(
                        text(
                            """
                            UPDATE processed_files
                            SET final_response_raw_text = :raw_text
                            WHERE processed_file_id = :processed_file_id
                            """
                        ),
                        {
                            "raw_text": normalized_raw_text,
                            "processed_file_id": processed_file_id,
                        },
                    )
                    updated_raw_text += 1
                    continue
                skipped += 1
        except Exception as e:
            errors += 1
            print(f"[ERROR] processed_file_id={processed_file_id}: {e}")

print("Done.")
print(f"Updated from responses files: {updated_from_files}")
print(f"Updated by normalization: {updated_by_normalization}")
print(f"Updated raw text format: {updated_raw_text}")
print(f"Skipped (already correct): {skipped}")
print(f"Errors: {errors}")
