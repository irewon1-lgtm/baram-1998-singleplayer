using Shared;

namespace Server;

public sealed partial class Session
{
    // User-authorized offline reconstruction. No historical smith tariff was recovered:
    // charge ceil(10% of the unchanged source buy price x missing durability fraction), min 1 gold.
    // Existing item identity, repairability, binding, protection and maximum durability stay intact.
    internal async Task DlgRepair(Mob npc)
    {
        long generation = CaptureOfflineGeneration();
        if (IsDead) { await DlgSay(npc, "Return to life before repairing equipment."); return; }
        var items = _char.Inventory.Select(i => (Item: i, Worn: false))
            .Concat(_char.Equipment.Select(i => (Item: i, Worn: true)))
            .Where(i => Content.ItemById(i.Item.ItemId) is { IsEquip: true, Repairable: true, Indestructible: false } d
                && i.Item.Dura > 0 && i.Item.Dura < d.Durability).ToArray();
        if (items.Length == 0) { await DlgSay(npc, "There is no damaged repairable equipment."); return; }
        int page = 0;
        while (true)
        {
            var rows = items.Skip(page * 9).Take(9).ToArray();
            var names = rows.Select(i => i.Worn
                ? $"{Content.ItemById(i.Item.ItemId)!.Name} [worn {i.Item.Slot}]"
                : $"{Content.ItemById(i.Item.ItemId)!.Name} [bag {i.Item.Slot + 1}]");
            int pick = await DlgMenu(npc, "Choose damaged equipment to repair.",
                names.Concat(new[] { "Next page", "Previous page", "Leave" }).ToArray());
            if (pick == rows.Length + 1) { page = (page + 1) * 9 < items.Length ? page + 1 : 0; continue; }
            if (pick == rows.Length + 2) { page = page > 0 ? page - 1 : (items.Length - 1) / 9; continue; }
            if (pick < 1 || pick > rows.Length) return;
            var selected = rows[pick - 1];
            var item = selected.Item;
            var owned = selected.Worn ? _char.Equipment : _char.Inventory;
            if (!owned.Contains(item) || Content.ItemById(item.ItemId) is not { IsEquip: true, Repairable: true, Indestructible: false } def
                || item.Dura == 0 || item.Dura >= def.Durability)
            { await DlgSay(npc, "That equipment changed. Choose it again."); return; }
            uint before = item.Dura;
            byte slot = item.Slot;
            int id = item.ItemId;
            string owner = item.Owner;
            ulong denominator = (ulong)def.Durability * 10;
            uint price = (uint)Math.Max(1UL,
                ((ulong)Math.Max(0, def.BuyPrice) * (def.Durability - before) + denominator - 1) / denominator);
            int yes = await DlgMenu(npc, $"Repair {def.Name} for {price} gold?", new[] { "Repair", "Cancel" });
            if (yes != 1) return;
            string outcome = "Your equipment is fully repaired.";
            RunOfflineMutation(generation, () =>
            {
            // Reacquire the current character graph. A rollback may replace both lists during the dialog.
            var current = (selected.Worn ? _char.Equipment : _char.Inventory).FirstOrDefault(x => x.Slot == slot);
            if (!ReferenceEquals(current, item) || current.ItemId != id || current.Owner != owner
                || current.Dura != before || IsDead
                || Content.ItemById(id) is not { IsEquip: true, Repairable: true, Indestructible: false } now
                || now.Durability != def.Durability || now.BuyPrice != def.BuyPrice)
            { outcome = "That equipment changed. Choose it again."; return; }
            if (_char.Coins < price) { outcome = "You do not have enough gold for repairs."; return; }
            _char.Coins -= price;
            item.Dura = def.Durability;
            if (selected.Worn) SendEquip(item); else SendAddItem(item);
            SendStats(); SaveChar();
            });
            await DlgSay(npc, outcome);
            return;
        }
    }
}
