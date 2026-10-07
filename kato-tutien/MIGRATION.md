# Migration v1.16.4 → v2.0.0

## Automatic on startup
1. Existing `_ensure_player_columns` adds any missing player columns.
2. New column: `loadout TEXT NOT NULL DEFAULT '{}'`
3. New table: `technique_mastery`
4. Legacy `equipped` still written; first equip migrates into loadout.

## Market
Seller proceeds after buy = seller_gain = int(total * 0.98); tax = total - seller_gain. 2% burned as tax.

## Safe
No DROP TABLE. No reset of inventory, market listings, or sect membership.


## Final balance pass (v2.0.0)
- No schema migration required for the mastery/accuracy fixes.
- Existing `technique_mastery` rows remain valid; mastery is now consumed per selected technique during combat.
- Existing character/equipment/market/sect data remains compatible.
