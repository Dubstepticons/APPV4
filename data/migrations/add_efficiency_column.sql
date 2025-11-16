-- Migration: Add efficiency column to traderecord table
-- Date: 2025-01-12
-- Purpose: Add efficiency metric (capture ratio: realized_pnl / mfe)

-- Add efficiency column (nullable, since existing trades won't have this value)
-- SQLite-compatible syntax (no IF NOT EXISTS support with ALTER TABLE)
ALTER TABLE traderecord ADD COLUMN efficiency REAL;
