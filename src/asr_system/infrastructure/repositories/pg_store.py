"""PostgreSQL implementations of the repository ports using psycopg2."""

from __future__ import annotations

import logging
from typing import Sequence

import psycopg2
import psycopg2.extras
import psycopg2.pool

from asr_system.domain.entities import CallScore, Utterance
from asr_system.domain.ports import CallScoreRepositoryPort, UtteranceRepositoryPort
from asr_system.domain.value_objects import Emotion

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS utterances (
    id          BIGSERIAL    PRIMARY KEY,
    call_id     TEXT         NOT NULL,
    speaker     TEXT         NOT NULL,
    start_sec   DOUBLE PRECISION NOT NULL,
    end_sec     DOUBLE PRECISION NOT NULL,
    text        TEXT         NOT NULL,
    emotion     TEXT         NOT NULL,
    confidence  DOUBLE PRECISION NOT NULL,
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_utterances_call_id ON utterances(call_id);

CREATE TABLE IF NOT EXISTS call_scores (
    call_id                  TEXT         PRIMARY KEY,
    negative_index_client    DOUBLE PRECISION NOT NULL,
    negative_index_operator  DOUBLE PRECISION NOT NULL,
    updated_at               TIMESTAMPTZ  NOT NULL,
    overall_score            DOUBLE PRECISION NOT NULL DEFAULT 0,
    client_satisfaction      DOUBLE PRECISION NOT NULL DEFAULT 0,
    operator_quality         DOUBLE PRECISION NOT NULL DEFAULT 0,
    talk_ratio_operator      DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    total_duration_seconds   DOUBLE PRECISION NOT NULL DEFAULT 0
);

-- Migration: add new columns to existing tables that predate this schema version.
ALTER TABLE call_scores ADD COLUMN IF NOT EXISTS overall_score          DOUBLE PRECISION NOT NULL DEFAULT 0;
ALTER TABLE call_scores ADD COLUMN IF NOT EXISTS client_satisfaction    DOUBLE PRECISION NOT NULL DEFAULT 0;
ALTER TABLE call_scores ADD COLUMN IF NOT EXISTS operator_quality       DOUBLE PRECISION NOT NULL DEFAULT 0;
ALTER TABLE call_scores ADD COLUMN IF NOT EXISTS talk_ratio_operator    DOUBLE PRECISION NOT NULL DEFAULT 0.5;
ALTER TABLE call_scores ADD COLUMN IF NOT EXISTS total_duration_seconds DOUBLE PRECISION NOT NULL DEFAULT 0;
"""


def ensure_schema(pool: psycopg2.pool.ThreadedConnectionPool) -> None:
    """Create tables if they don't exist. Called once at startup."""
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(_DDL)
        conn.commit()
        logger.info("PostgreSQL schema initialised (utterances, call_scores)")
    finally:
        pool.putconn(conn)


def make_pool(dsn: str, minconn: int = 1, maxconn: int = 5) -> psycopg2.pool.ThreadedConnectionPool:
    pool = psycopg2.pool.ThreadedConnectionPool(minconn, maxconn, dsn)
    ensure_schema(pool)
    return pool


class PgUtteranceRepository(UtteranceRepositoryPort):
    def __init__(self, pool: psycopg2.pool.ThreadedConnectionPool) -> None:
        self._pool = pool

    def save_many(self, utterances: Sequence[Utterance]) -> None:
        if not utterances:
            return
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO utterances
                        (call_id, speaker, start_sec, end_sec, text, emotion, confidence)
                    VALUES %s
                    """,
                    [
                        (
                            u.call_id,
                            u.speaker,
                            u.start_sec,
                            u.end_sec,
                            u.text,
                            u.emotion.value,
                            u.confidence,
                        )
                        for u in utterances
                    ],
                )
            conn.commit()
        finally:
            self._pool.putconn(conn)

    def delete_by_call_id(self, call_id: str) -> None:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM utterances WHERE call_id = %s", (call_id,))
            conn.commit()
        finally:
            self._pool.putconn(conn)

    def get_by_call_id(self, call_id: str) -> list[Utterance]:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT call_id, speaker, start_sec, end_sec, text, emotion, confidence
                    FROM utterances
                    WHERE call_id = %s
                    ORDER BY start_sec
                    """,
                    (call_id,),
                )
                rows = cur.fetchall()
        finally:
            self._pool.putconn(conn)

        return [
            Utterance(
                call_id=row[0],
                speaker=row[1],
                start_sec=row[2],
                end_sec=row[3],
                text=row[4],
                emotion=Emotion(row[5]),
                confidence=row[6],
            )
            for row in rows
        ]


class PgCallScoreRepository(CallScoreRepositoryPort):
    def __init__(self, pool: psycopg2.pool.ThreadedConnectionPool) -> None:
        self._pool = pool

    def save(self, score: CallScore) -> None:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO call_scores (
                        call_id, negative_index_client, negative_index_operator, updated_at,
                        overall_score, client_satisfaction, operator_quality,
                        talk_ratio_operator, total_duration_seconds
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (call_id) DO UPDATE SET
                        negative_index_client   = EXCLUDED.negative_index_client,
                        negative_index_operator = EXCLUDED.negative_index_operator,
                        updated_at              = EXCLUDED.updated_at,
                        overall_score           = EXCLUDED.overall_score,
                        client_satisfaction     = EXCLUDED.client_satisfaction,
                        operator_quality        = EXCLUDED.operator_quality,
                        talk_ratio_operator     = EXCLUDED.talk_ratio_operator,
                        total_duration_seconds  = EXCLUDED.total_duration_seconds
                    """,
                    (
                        score.call_id,
                        score.negative_index_client,
                        score.negative_index_operator,
                        score.updated_at,
                        score.overall_score,
                        score.client_satisfaction,
                        score.operator_quality,
                        score.talk_ratio_operator,
                        score.total_duration_seconds,
                    ),
                )
            conn.commit()
        finally:
            self._pool.putconn(conn)

    def get(self, call_id: str) -> CallScore | None:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT call_id, negative_index_client, negative_index_operator, updated_at,
                           overall_score, client_satisfaction, operator_quality,
                           talk_ratio_operator, total_duration_seconds
                    FROM call_scores
                    WHERE call_id = %s
                    """,
                    (call_id,),
                )
                row = cur.fetchone()
        finally:
            self._pool.putconn(conn)

        if row is None:
            return None
        return CallScore(
            call_id=row[0],
            negative_index_client=row[1],
            negative_index_operator=row[2],
            updated_at=row[3],
            overall_score=row[4],
            client_satisfaction=row[5],
            operator_quality=row[6],
            talk_ratio_operator=row[7],
            total_duration_seconds=row[8],
        )

    def list_all(self) -> list[CallScore]:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT call_id, negative_index_client, negative_index_operator, updated_at,
                           overall_score, client_satisfaction, operator_quality,
                           talk_ratio_operator, total_duration_seconds
                    FROM call_scores
                    ORDER BY updated_at DESC
                    """
                )
                rows = cur.fetchall()
        finally:
            self._pool.putconn(conn)

        return [
            CallScore(
                call_id=row[0],
                negative_index_client=row[1],
                negative_index_operator=row[2],
                updated_at=row[3],
                overall_score=row[4],
                client_satisfaction=row[5],
                operator_quality=row[6],
                talk_ratio_operator=row[7],
                total_duration_seconds=row[8],
            )
            for row in rows
        ]
