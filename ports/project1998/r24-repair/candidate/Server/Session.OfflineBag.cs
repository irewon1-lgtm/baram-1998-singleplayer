using Shared;

namespace Server;

public sealed partial class Session
{
    // User-requested offline bag policy (2026-10-22), not a historical balance claim.
    // The original registry and online server keep their original limits.
    private int BagStackCap(ItemDef def) => _offlinePersistence ? 99 : def.StackCap;
    private bool BagStackable(ItemDef def) => _offlinePersistence || def.Stackable;
    private static bool SameBagInstance(InvItem a, InvItem b) => a.ItemId == b.ItemId
        && a.CustomName == b.CustomName && a.Owner == b.Owner && a.Dura == b.Dura
        && a.Repair == b.Repair && a.Protected == b.Protected;
    private InvItem GrantInstance(ItemDef def, uint dura = 0, string customName = "", string owner = "", InvItem? instance = null)
    {
        var item = instance?.Clone() ?? new InvItem();
        item.ItemId = def.Id; item.Amount = 1;
        item.Dura = dura == 0 && (def.IsEquip || def.IsCharged) ? def.Durability : dura;
        item.CustomName = customName;
        item.Owner = owner.Length > 0 ? owner : def.Bonded ? _char.Name : "";
        return item;
    }
    private long BagRoom(ItemDef def, InvItem sample, IReadOnlyList<InvItem>? inventory = null)
    {
        inventory ??= _char.Inventory;
        int cap = BagStackCap(def);
        long room = BagStackable(def) ? inventory.Where(i => i.Amount > 0 && i.Amount < cap
            && SameBagInstance(i, sample)).Sum(i => (long)cap - i.Amount) : 0;
        for (int n = 0; n < _char.MaxInv; n++)
            if (inventory.All(i => i.Slot != n)) room += cap;
        return room;
    }

    // Entry-only migration, inside the host's normal staged FULL transaction.
    // Do not compact while a shop/quest continuation owns a slot or item reference.
    // Unknown IDs/invalid legacy slots remain untouched. If a legacy over-cap pile
    // cannot fit, retain the entire remainder in its original slot rather than lose it.
    public void CompactOfflineInventory()
    {
        using var held = EnterState();
        if (!_offlinePersistence || DialogBusy || _shopReply is not null) return;
        var before = _char.Inventory.ToDictionary(i => i.Slot, i => i.Clone());
        bool changed = false;
        foreach (var group in _char.Inventory.Where(i => i.Amount > 0 && i.Slot < _char.MaxInv
                     && Content.ItemById(i.ItemId) is not null).OrderBy(i => i.Slot)
                     .GroupBy(i => (i.ItemId, i.CustomName, i.Owner, i.Dura, i.Repair, i.Protected)).ToArray())
        {
            var entries = group.ToArray();
            long total = entries.Sum(i => (long)i.Amount);
            if (entries.Length == (total + 98) / 99 && entries.Select((item, index) =>
                    item.Amount == Math.Min(99L, total - index * 99L)).All(same => same)) continue;
            int free = Enumerable.Range(0, _char.MaxInv).Count(n => _char.Inventory.All(i => i.Slot != n));
            if ((total + 98) / 99 > entries.Length + free) continue;
            changed = true;
            foreach (var item in entries) _char.Inventory.Remove(item);
            int used = 0;
            while (total > 0)
            {
                int slot = used < entries.Length ? entries[used].Slot : FreeSlot();
                if (slot < 0) throw new InvalidOperationException("Bag normalization capacity changed under the held monitor.");
                var copy = entries[0].Clone(); copy.Slot = (byte)slot;
                copy.Amount = (int)Math.Min(99, total);
                _char.Inventory.Add(copy); total -= copy.Amount; used++;
            }
        }
        if (!changed) return;
        foreach (var old in before.Values)
            if (_char.Inventory.All(i => i.Slot != old.Slot)) SendDelItem(old.Slot, DelReason.Removed);
        foreach (var item in _char.Inventory.OrderBy(i => i.Slot))
            if (!before.TryGetValue(item.Slot, out var old) || !SameBagInstance(old, item) || old.Amount != item.Amount)
                SendAddItem(item);
        MarkDirty();
    }

    // Equipment already detaches one unit. Charged items, containers and cosmetics
    // mutate per-instance state, so detach ONE before their original handler runs.
    private bool DetachMutableBagUnit(InvItem item, ItemDef def)
    {
        if (!_offlinePersistence || item.Amount <= 1 || (!def.IsCharged && def.Type is not (21 or 23 or 24 or 25 or 27 or 28 or 29))) return true;
        int slot = FreeSlot();
        if (slot < 0) { SendMiniText("Free one inventory slot to use an item with individual charges or contents."); return false; }
        var remainder = item.Clone(); remainder.Slot = (byte)slot; remainder.Amount--;
        item.Amount = 1; _char.Inventory.Add(remainder);
        SendAddItem(item); SendAddItem(remainder); MarkDirty();
        return true;
    }
}
