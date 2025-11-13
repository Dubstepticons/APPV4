# Position State Analysis - Single Source of Truth

## Current Architecture (Problem Statement)

### Position State Storage Locations

Currently, position state is scattered across **3 different locations**:

#### 1. Panel2 (panels/panel2.py)
**Storage**: In-memory instance variables
```python
self.entry_price: Optional[float] = None
self.entry_qty: int = 0
self.is_long: Optional[bool] = None
self.target_price: Optional[float] = None
self.stop_price: Optional[float] = None
self.entry_time_epoch: Optional[int] = None
self._trade_min_price: Optional[float] = None
self._trade_max_price: Optional[float] = None
```

**Persistence**: JSON file (scoped by mode/account)
- File pattern: `state_{mode}_{account}.json` (dynamically generated)
- Saved on mode change and app close
- **CRITICAL**: Only saves timer state (entry_time_epoch, heat_start_epoch, trade_min/max_price)
- **DOES NOT** save position state (entry_price, entry_qty, is_long) ✅ This is actually good!

#### 2. StateManager (core/state_manager.py)
**Storage**: In-memory instance variables
```python
self.position_symbol: Optional[str] = None
self.position_qty: float = 0
self.position_entry_price: float = 0
self.position_entry_time: Optional[datetime] = None
self.position_side: Optional[str] = None  # "LONG" or "SHORT"
self.position_mode: Optional[str] = None  # "SIM" or "LIVE"
self.entry_vwap: Optional[float] = None
self.entry_cum_delta: Optional[float] = None
self.entry_poc: Optional[float] = None
```

**Persistence**: **NONE** - StateManager is purely in-memory, no persistence

#### 3. Database (data/schema.py)
**Storage**: TradeRecord table
```python
class TradeRecord(SQLModel, table=True):
    # Entry data
    entry_time: datetime
    entry_price: float

    # Exit data (empty until closed)
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    is_closed: bool = Field(default=False)

    # P&L (only for closed trades)
    realized_pnl: Optional[float] = None
```

**Persistence**: PostgreSQL/SQLite database
- **CRITICAL ISSUE**: TradeRecord only stores CLOSED trades (is_closed=True)
- **NO TABLE** exists for open positions
- When position is open, there's NO database record

---

## Current Position Lifecycle Flow

### 1. Position Entry (DTC Order Fill)
```
DTC Thread receives Order Fill (Type 301)
    ↓
MessageRouter processes message
    ↓
Panel2.set_position(qty, entry_price, is_long) called
    ↓
Panel2 updates in-memory state:
    - self.entry_qty = qty
    - self.entry_price = entry_price
    - self.is_long = is_long
    - self.entry_time_epoch = time.time()
    ↓
StateManager.open_position() called
    ↓
StateManager updates in-memory state:
    - self.position_qty = qty
    - self.position_entry_price = entry_price
    - self.position_mode = mode
    ↓
**NO DATABASE WRITE** - position only in memory
```

### 2. Position Exit (Trade Close)
```
Panel2 detects qty=0 (position closed)
    ↓
Panel2 calls notify_trade_closed()
    ↓
TradeManager.record_trade() called
    ↓
Database write: INSERT INTO traderecord (
    entry_time, entry_price,
    exit_time, exit_price,
    realized_pnl,
    is_closed=True
)
    ↓
Panel2 clears in-memory state
StateManager clears in-memory state
```

---

## Problem Scenarios

### Scenario 1: App Crash with Open Position ❌
```
1. Trader opens long position at $5050 (qty=1)
2. Position stored in Panel2 + StateManager (in-memory)
3. App crashes (power loss, Python exception)
4. App restarts
5. Panel2._load_state() loads JSON - only timer state, NOT position
6. StateManager has no persistence
7. Database has NO record (trade not closed yet)
8. **RESULT**: Position state lost, trader doesn't see open position
```

### Scenario 2: Mode Switch with Open Position ⚠️
```
1. Open SIM position at $5050
2. Sierra Chart sends LIVE account message
3. StateManager detects mode change SIM → LIVE
4. Panel2.set_trading_mode("LIVE") called
5. Panel2._save_state() saves SIM timer state to SIM JSON
6. Panel2._load_state() loads LIVE timer state from LIVE JSON
7. Panel2 position cleared (qty=0)
8. StateManager handles via handle_mode_switch() - closes SIM position
9. **RESULT**: SIM position closed, but trader may not realize
```

### Scenario 3: Database Query During Open Position ⚠️
```
1. Trader has open position at $5050 (qty=1, unrealized P&L = +$100)
2. Panel3 queries database for today's P&L
3. Query: SELECT SUM(realized_pnl) FROM traderecord WHERE date=today
4. **RESULT**: $0 (open position not in database, unrealized P&L not counted)
5. Trader sees incorrect P&L in stats panel
```

### Scenario 4: Reconnect After Network Loss 🔥
```
1. Open LIVE position at $5050 (qty=1)
2. Network to Sierra Chart drops
3. DTC connection lost, app still running
4. Position still in Panel2 + StateManager (in-memory)
5. Network restored, reconnect to Sierra Chart
6. Sierra Chart sends new Type 401 (account list)
7. Sierra Chart does NOT send position data (only market data Type 501)
8. **RESULT**: App has stale position, Sierra Chart may have already exited
```

---

## Root Cause Analysis

### Why No Open Position Table?

Looking at schema.py comments:
```python
"""
NO position data comes from Sierra - it only sends market data.
All position tracking must be INFERRED from order executions.
"""
```

**Decision**: Position tracking was designed to be purely in-memory, inferred from DTC order messages.

**Rationale**: Sierra Chart DTC protocol doesn't send position snapshots, only:
- Type 401: Account list
- Type 501: Market data
- Type 600: Account balance
- Type 301: Order fills

**Trade-off**: Simplified design (no position sync logic) vs. crash safety (lose position on crash)

### Why StateManager Doesn't Persist?

StateManager is designed as a **transient runtime state** holder:
- Shared state between threads (DTC + GUI)
- Notification via Qt signals
- NO persistence layer

**Rationale**: Keep StateManager simple, delegate persistence to specialized components

**Trade-off**: Clean separation vs. position state loss

---

## Proposed Solution: OpenPosition Table

### Design Principles

1. **Database is Source of Truth**: OpenPosition table is authoritative
2. **Panel2 is Projection**: Panel2 reads from DB, displays state
3. **StateManager is Cache**: StateManager mirrors DB for fast access
4. **Write-Through**: Every position change → immediate DB write
5. **Recovery on Startup**: Read OpenPosition table, restore to Panel2/StateManager

### Schema Design

```python
class OpenPosition(SQLModel, table=True):
    """
    Open position tracking - single source of truth.

    INVARIANT: Only 0 or 1 row per (mode, account) combination.
    """

    __tablename__ = "openposition"

    # Composite primary key: (mode, account)
    # Ensures only one open position per mode/account
    __table_args__ = (
        PrimaryKeyConstraint('mode', 'account'),
    )

    # Position identification
    mode: str  # "SIM" or "LIVE"
    account: str  # Account identifier
    symbol: str  # "MES", "MNQ", etc.

    # Position details
    qty: int  # Positive = long, negative = short
    side: str  # "LONG" or "SHORT"
    entry_price: float
    entry_time: datetime

    # Bracket orders (optional)
    target_price: Optional[float] = None
    stop_price: Optional[float] = None

    # Entry snapshots (for MAE/MFE tracking)
    entry_vwap: Optional[float] = None
    entry_cum_delta: Optional[float] = None
    entry_poc: Optional[float] = None

    # Trade extremes (for MAE/MFE)
    trade_min_price: Optional[float] = None
    trade_max_price: Optional[float] = None

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

### Write Operations

**Position Entry**:
```python
# When order fill arrives (DTC Type 301)
with session:
    # Upsert (INSERT or UPDATE if exists)
    open_pos = OpenPosition(
        mode=mode,
        account=account,
        symbol=symbol,
        qty=qty,
        side="LONG" if qty > 0 else "SHORT",
        entry_price=entry_price,
        entry_time=datetime.utcnow(),
        entry_vwap=vwap,
        entry_cum_delta=cum_delta,
        entry_poc=poc,
        trade_min_price=entry_price,
        trade_max_price=entry_price,
    )
    session.merge(open_pos)  # Upsert
    session.commit()
```

**Position Update** (price extremes for MAE/MFE):
```python
# Every 100ms when position is open
with session:
    open_pos = session.query(OpenPosition).filter_by(mode=mode, account=account).first()
    if open_pos:
        open_pos.trade_min_price = min(open_pos.trade_min_price, current_price)
        open_pos.trade_max_price = max(open_pos.trade_max_price, current_price)
        open_pos.updated_at = datetime.utcnow()
        session.commit()
```

**Position Exit**:
```python
# When position closes (qty=0)
with session:
    # 1. Read open position for trade record
    open_pos = session.query(OpenPosition).filter_by(mode=mode, account=account).first()

    if open_pos:
        # 2. Create closed trade record
        trade = TradeRecord(
            symbol=open_pos.symbol,
            side=open_pos.side,
            qty=abs(open_pos.qty),
            mode=open_pos.mode,
            entry_time=open_pos.entry_time,
            entry_price=open_pos.entry_price,
            exit_time=datetime.utcnow(),
            exit_price=exit_price,
            realized_pnl=realized_pnl,
            is_closed=True,
            entry_vwap=open_pos.entry_vwap,
            entry_cum_delta=open_pos.entry_cum_delta,
            # Calculate MAE/MFE from trade extremes
            mae=calculate_mae(open_pos),
            mfe=calculate_mfe(open_pos),
        )
        session.add(trade)

        # 3. Delete open position
        session.delete(open_pos)

        session.commit()
```

### Read Operations (Recovery)

**App Startup**:
```python
def recover_open_positions():
    """
    Called on app startup to restore open positions from database.
    """
    with session:
        # Query all open positions
        open_positions = session.query(OpenPosition).all()

        for open_pos in open_positions:
            # Restore to StateManager
            state_manager.open_position(
                symbol=open_pos.symbol,
                qty=open_pos.qty,
                entry_price=open_pos.entry_price,
                entry_time=open_pos.entry_time,
                mode=open_pos.mode,
            )

            # Restore entry snapshots
            state_manager.entry_vwap = open_pos.entry_vwap
            state_manager.entry_cum_delta = open_pos.entry_cum_delta
            state_manager.entry_poc = open_pos.entry_poc

            # Restore to Panel2 (if mode matches current mode)
            if open_pos.mode == state_manager.current_mode:
                panel2.set_position(
                    qty=abs(open_pos.qty),
                    entry_price=open_pos.entry_price,
                    is_long=(open_pos.qty > 0),
                )
                panel2.entry_time_epoch = int(open_pos.entry_time.timestamp())
                panel2._trade_min_price = open_pos.trade_min_price
                panel2._trade_max_price = open_pos.trade_max_price
```

**Mode Switch**:
```python
def switch_mode(new_mode: str, new_account: str):
    """
    Handle mode switch with database-backed position recovery.
    """
    # 1. Save current Panel2 timer state (if needed)
    panel2._save_state()

    # 2. Update mode
    state_manager.current_mode = new_mode
    state_manager.current_account = new_account

    # 3. Load open position from DB for new mode
    with session:
        open_pos = session.query(OpenPosition).filter_by(
            mode=new_mode,
            account=new_account
        ).first()

        if open_pos:
            # Restore position to Panel2
            panel2.set_position(
                qty=abs(open_pos.qty),
                entry_price=open_pos.entry_price,
                is_long=(open_pos.qty > 0),
            )
        else:
            # No open position in this mode
            panel2.set_position(qty=0, entry_price=None, is_long=None)
```

---

## Implementation Plan

### Phase 1: Add OpenPosition Table
- [ ] Add OpenPosition model to data/schema.py
- [ ] Create database migration (add table)
- [ ] Add unit tests for OpenPosition CRUD operations

### Phase 2: Implement Repository Pattern
- [ ] Create PositionRepository class (data/position_repository.py)
- [ ] Methods: save_open_position(), get_open_position(), close_position()
- [ ] Unit tests for repository

### Phase 3: Update Position Entry/Exit
- [ ] Modify Panel2.set_position() to write to DB
- [ ] Modify Panel2.notify_trade_closed() to move from OpenPosition → TradeRecord
- [ ] Update StateManager to sync with DB

### Phase 4: Implement Recovery Logic
- [ ] Add recover_open_positions() function
- [ ] Call from app_manager.py on startup
- [ ] Add reconciliation logic (handle conflicts)

### Phase 5: Update Mode Switching
- [ ] Modify Panel2.set_trading_mode() to load from DB
- [ ] Remove Panel2 JSON state file (deprecated)
- [ ] Ensure StateManager syncs correctly

### Phase 6: Testing
- [ ] Integration test: open position → crash → restart → verify recovery
- [ ] Test mode switching with open position
- [ ] Test concurrent access (thread safety)

---

## Benefits of This Design

### ✅ Crash Safety
- Open position persisted to database immediately
- Full recovery after crash/restart
- No position state loss

### ✅ Single Source of Truth
- Database is authoritative
- Panel2 reads from DB (projection)
- StateManager mirrors DB (cache)
- No conflicting state

### ✅ Mode Switching
- Load correct position for each mode
- Clean separation between SIM/LIVE
- No stale state after mode change

### ✅ Audit Trail
- All position changes logged in DB
- Can query position history
- Supports debugging and compliance

### ✅ Correct P&L
- Unrealized P&L calculable from OpenPosition
- Stats queries include open positions
- No missing trades in reports

---

## Migration Strategy

### Backward Compatibility

**Concern**: Existing Panel2 JSON files have timer state (entry_time_epoch, heat_start_epoch)

**Solution**: Keep Panel2 timer persistence, add DB position persistence
```python
# Panel2._save_state() - keep timer persistence
data = {
    "entry_time_epoch": self.entry_time_epoch,
    "heat_start_epoch": self.heat_start_epoch,
}
save_json_atomic(data, state_path)

# NEW: Also save position to DB
if self.entry_qty > 0:
    position_repo.save_open_position(...)
```

**Migration Path**:
1. Deploy code with OpenPosition table
2. On first run, check for open positions in Panel2 (entry_qty > 0)
3. If found, migrate to database
4. Continue normal operation

---

## Open Questions

### 1. Trade Extremes Update Frequency
**Question**: How often should we update trade_min_price/trade_max_price in OpenPosition?
- Option A: Every price tick (high DB write load)
- Option B: Every 100ms (current Panel2 timer)
- Option C: Only on significant moves (>= 0.25 points)

**Recommendation**: Option B (every 100ms) - balances accuracy with DB load

### 2. Network Reconnect Reconciliation
**Question**: When reconnecting to Sierra Chart, how do we reconcile DB position with Sierra Chart reality?
- Sierra Chart doesn't send position snapshots
- Can't verify if position still open

**Recommendation**:
- On reconnect, check if we have open position in DB
- Show warning dialog to trader: "Open position detected: LONG 1 MES @ 5050. Verify with broker."
- Trader confirms or manually closes stale position

### 3. Multiple Account Support
**Question**: Should we support multiple concurrent open positions (different accounts)?
- Current design: One position per (mode, account)
- Allows SIM + LIVE simultaneously (different accounts)

**Recommendation**: YES - keep composite key (mode, account) for flexibility

---

## Next Steps

1. Review this analysis with team
2. Get approval on OpenPosition table design
3. Start Phase 1: Add table to schema
4. Implement incrementally with tests at each phase

---

**Author**: Claude (Position State Audit)
**Date**: 2025-11-13
**Status**: Proposal - Awaiting Review
