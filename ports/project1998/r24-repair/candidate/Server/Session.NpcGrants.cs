using Shared;

namespace Server;

internal enum NpcLearnResult { Learned, AlreadyKnown, NoRoom, ShortFee }

public sealed partial class Session
{
    /// <summary>Exchange an NPC turn-in without consuming the payment when the reward cannot fit.
    /// The reservation removes the exact low-slot payment first, so a slot it frees is usable. Item
    /// definitions and quantities remain supplied by the original quest, never invented here.</summary>
    internal bool ExchangeNpcItemAllOrNone(string takeKey, int takeAmount, string giveKey, int giveAmount)
        => ExchangeNpcItemsAllOrNone(new[] { (takeKey, takeAmount) }, giveKey, giveAmount);

    /// <summary>Reserve the entire original script-supplied multi-item payment before changing any
    /// stack. A borrowed tool and wool can free two slots; a rejected reward keeps their exact names,
    /// owners, durability and quest state. The enclosing offline action commits or restores the whole turn-in.</summary>
    internal bool ExchangeNpcItemsAllOrNone(IReadOnlyList<(string Item, int Amount)> fees,
        string giveKey, int giveAmount, bool bound = false)
    {
        using var held = EnterState();
        var give = Content.ItemByKey(giveKey);
        if (give is null || giveAmount <= 0 || fees.Count == 0 ||
            fees.Any(f => f.Amount <= 0 || Content.ItemByKey(f.Item) is null) ||
            (bound && (giveAmount != 1 || give.Stackable)))
            return false;
        var payments = fees.GroupBy(f => f.Item).Select(g => (Item: g.Key, Amount: g.Sum(f => f.Amount))).ToArray();
        if (payments.Any(f => CountItem(f.Item) < f.Amount)) return false;
        var reserved = _char.Inventory.Select(i => i.Clone()).ToList();
        foreach (var (key, amount) in payments)
        {
            var take = Content.ItemByKey(key)!;
            int paymentLeft = amount;
            foreach (var item in reserved.Where(i => i.ItemId == take.Id).OrderBy(i => i.Slot).ToList())
            {
                int used = Math.Min(paymentLeft, item.Amount);
                item.Amount -= used; paymentLeft -= used;
                if (item.Amount == 0) reserved.Remove(item);
                if (paymentLeft == 0) break;
            }
        }
        int carried = reserved.Where(i => i.ItemId == give.Id && i.CustomName == "").Sum(i => i.Amount);
        if (!_offlinePersistence && give.Stackable && give.CarryCap > 0 && (long)carried + giveAmount > give.CarryCap)
        { CarryCapNotice(give); return false; }
        long room = BagRoom(give, GrantInstance(give, owner: bound ? _char.Name : ""), reserved);
        if (room < giveAmount) { SendMiniText("You can't have more."); return false; }
        foreach (var (key, amount) in payments)
            if (!TakeItem(key, amount))
                throw new InvalidOperationException("NPC exchange payment changed inside the held session boundary.");
        if (!(bound ? GiveBoundItem(giveKey) : GiveRewardItemAllOrNone(giveKey, giveAmount)))
            throw new InvalidOperationException("NPC exchange reward changed inside the held session boundary.");
        return true;
    }

    /// <summary>A scripted teacher checks book space and every original item fee before taking any
    /// payment. In particular, refusal preserves named/owned payment stacks rather than replacing them
    /// with freshly created refunds. The existing known-spell behavior (true) is preserved.</summary>
    internal bool LearnNpcSpellForItems(SpellDef spell, IReadOnlyList<(string Item, int Amount)> fees)
    {
        using var held = EnterState();
        if (!_char.Spells.Contains(spell.Id) && _char.Spells.Count >= SpellBookCap) return false;
        if (fees.Any(i => i.Amount <= 0 || Content.ItemByKey(i.Item) is null)) return false;
        var grouped = fees.GroupBy(i => i.Item).Select(g => (Item: g.Key, Amount: g.Sum(i => i.Amount))).ToArray();
        if (grouped.Any(i => CountItem(i.Item) < i.Amount)) return false;
        foreach (var (item, amount) in grouped)
            if (!TakeItem(item, amount)) throw new InvalidOperationException("NPC spell fee changed inside the held session boundary.");
        if (!LearnSpellFromNpc(spell)) throw new InvalidOperationException("NPC spell book changed inside the held session boundary.");
        return true;
    }

    /// <summary>Reserve every kit item against a private bag using GivePlaced's exact count/slot rules.
    /// An empty-name stack may be filled, legacy over-cap/out-of-range entries are left alone, and repeated
    /// keys reserve from the same remaining carry/stack room. No inventory or output is changed on refusal.</summary>
    internal bool GrantNpcClassKit(int path, IReadOnlyList<(string Item, int Amount)> kit)
    {
        using var held = EnterState();
        if (CharClassId != 0) return false; // a late duplicate reply cannot pay a second class kit
        if (!CanCreditGold(500)) return false; // original kit's purse credit must fit before any item/path changes
        var reserved = _char.Inventory.Select(i => i.Clone()).ToList();
        foreach (var (key, amount) in kit)
        {
            var def = Content.ItemByKey(key);
            if (def is null || amount <= 0) return false;
            int carried = reserved.Where(i => i.ItemId == def.Id && i.CustomName == "").Sum(i => i.Amount);
            if (!_offlinePersistence && def.Stackable && def.CarryCap > 0 && (long)carried + amount > def.CarryCap)
            { CarryCapNotice(def); return false; }
            int left = amount, cap = BagStackCap(def);
            if (BagStackable(def))
                foreach (var stack in reserved.Where(i => SameBagInstance(i, GrantInstance(def)) && i.Amount < cap))
                {
                    int put = Math.Min(cap - stack.Amount, left);
                    stack.Amount += put; left -= put;
                    if (left == 0) break;
                }
            while (left > 0)
            {
                int slot = -1;
                for (int n = 0; n < _char.MaxInv; n++)
                    if (reserved.All(i => i.Slot != n)) { slot = n; break; }
                if (slot < 0) { SendMiniText("You can't have more."); return false; }
                int put = Math.Min(cap, left);
                var sample = GrantInstance(def); sample.Slot = (byte)slot; sample.Amount = put;
                reserved.Add(sample); left -= put;
            }
        }
        // The session monitor stays held throughout preflight and placement; no dialog await intervenes.
        // Each SaveChar is deferred by the embedded host's enclosing ExecuteOfflineAction, so kit, purse,
        // class and success frames commit together or its existing complete-character rollback restores them.
        foreach (var (key, amount) in kit)
            if (!GiveRewardItemAllOrNone(key, amount))
                throw new InvalidOperationException("Class kit capacity changed inside the held session boundary.");
        AwardGold(500);
        SetCharClass(path);
        return true;
    }

    /// <summary>A trainer cannot debit a fee for a spell that cannot enter the book. Costs remain the
    /// original per-base-path rows; no fee or capacity is invented here.</summary>
    internal NpcLearnResult LearnNpcSecretWithFee(SpellDef spell)
    {
        using var held = EnterState();
        if (_char.Spells.Contains(spell.Id)) return NpcLearnResult.AlreadyKnown;
        if (_char.Spells.Count >= SpellBookCap) return NpcLearnResult.NoRoom;
        var cost = Content.LearnCostFor(spell, CharBasePathId);
        if (cost is not null)
        {
            // Sum repeated fee keys too, so no earlier debit can make a later same-key debit fail.
            var fees = cost.Items.GroupBy(i => i.Item).Select(g => (Item: g.Key, Amount: g.Sum(i => i.Amount))).ToArray();
            if (fees.Any(i => CountItem(i.Item) < i.Amount) || _char.Coins < (uint)cost.Gold)
                return NpcLearnResult.ShortFee;
            foreach (var (item, amount) in fees)
                if (!TakeItem(item, amount)) throw new InvalidOperationException("Trainer fee changed inside the held session boundary.");
            if (cost.Gold > 0 && !SpendGold((uint)cost.Gold))
                throw new InvalidOperationException("Trainer gold changed inside the held session boundary.");
        }
        if (!LearnSpellFromNpc(spell))
            throw new InvalidOperationException("Trainer book capacity changed inside the held session boundary.");
        return NpcLearnResult.Learned;
    }
}
