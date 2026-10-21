using System.Globalization;
using Protocol.Tk495;
using Shared;

namespace Server;

public sealed partial class Session
{
    // Source: pinned RTK Items/Premium/bags/*.lua. The source row's maxDura is material
    // capacity and each portable instance's dura is its current content count. The eight
    // source empty shells can become one of their family's quality-specific container IDs.
    // This offline adapter uses bounded menus and all-or-none transfers; it never adds slots.
    private bool TryUseRecoveredBag(InvItem item, ItemDef def)
    {
        if (RecoveredItemContent.Container(def.Id) is null
            && !RecoveredItemContent.All.Bags.Any(bag => bag.Shell == def.Id)) return false;
        if (DialogBusy) { SendMiniText("Finish the current conversation first."); return true; }
        _ = RunRecoveredBagAsync(item, def.Id, item.Slot, item.Owner);
        return true;
    }

    private async Task RunRecoveredBagAsync(InvItem item, int originalId, byte originalSlot, string originalOwner)
    {
        long generation = CaptureOfflineGeneration();
        try
        {
            using (EnterState())
            using (EnterOfflineEffect(generation))
                if (!RecoveredBagStillHere(item, originalId, originalSlot, originalOwner)) return;

            int operation = await DlgMenu(F1VirtualNpc,
                $"{Content.ItemById(originalId)!.Name}: What would you like to do?",
                new[] { "Add materials", "Remove materials" });
            RecoveredItemContent.Bag? rule;
            using (EnterState())
            using (EnterOfflineEffect(generation))
            {
                if (!RecoveredBagStillHere(item, originalId, originalSlot, originalOwner)) return;
                if (operation is not (1 or 2)) return;
                rule = RecoveredItemContent.Container(originalId);
                if (operation == 2 && (rule is null || item.Dura == 0))
                { SendMiniText("This container is empty."); return; }
            }

            if (rule is null)
            {
                // Seven quality rows plus previous/next keeps every native menu at nine rows.
                const int pageSize = 7;
                RecoveredItemContent.Bag[] variants;
                using (EnterState())
                using (EnterOfflineEffect(generation))
                {
                    if (!RecoveredBagStillHere(item, originalId, originalSlot, originalOwner)) return;
                    variants = RecoveredItemContent.All.Bags
                        .Where(bag => bag.Shell == originalId && RecoveredBagMaterialCount(bag.Content) > 0)
                        .OrderBy(bag => bag.Id).ToArray();
                    if (variants.Length == 0)
                    { SendMiniText("You have no matching materials to put in this container."); return; }
                }
                int page = 0;
                while (true)
                {
                    var rows = variants.Skip(page * pageSize).Take(pageSize).ToArray();
                    var labels = rows.Select(bag => Content.ItemById(bag.Content)!.Name).ToList();
                    int previous = 0, next = 0;
                    if (page > 0) { labels.Add("Previous page"); previous = labels.Count; }
                    if ((page + 1) * pageSize < variants.Length) { labels.Add("Next page"); next = labels.Count; }
                    int choice = await DlgMenu(F1VirtualNpc, "Which material will you store?", labels);
                    using (EnterState())
                    using (EnterOfflineEffect(generation))
                    {
                        if (!RecoveredBagStillHere(item, originalId, originalSlot, originalOwner)) return;
                        if (choice <= 0 || choice > labels.Count) return;
                        if (previous != 0 && choice == previous) { page--; continue; }
                        if (next != 0 && choice == next) { page++; continue; }
                        rule = rows[choice - 1];
                    }
                    break;
                }
            }

            string materialName;
            uint stored;
            using (EnterState())
            using (EnterOfflineEffect(generation))
            {
                if (!RecoveredBagStillHere(item, originalId, originalSlot, originalOwner)
                    || !RecoveredBagRuleCurrent(rule)) return;
                materialName = Content.ItemById(rule.Content)!.Name;
                stored = originalId == rule.Id ? item.Dura : 0;
                if (operation == 1 && stored >= rule.Capacity)
                { SendMiniText("This container is full."); return; }
                if (operation == 1 && RecoveredBagMaterialCount(rule.Content) == 0)
                { SendMiniText($"You have no unbound {materialName} to put in the container."); return; }
            }
            string? input = await DlgInput(F1VirtualNpc,
                $"How many {materialName} will you {(operation == 1 ? "add" : "remove")}? "
                + $"Stored: {stored}/{rule.Capacity}.");
            RunOfflineMutation(generation, () =>
            {
                if (!RecoveredBagStillHere(item, originalId, originalSlot, originalOwner)
                    || !RecoveredBagRuleCurrent(rule)) return;
                if (input is null) return;
                if (!int.TryParse(input.Trim(), NumberStyles.None, CultureInfo.InvariantCulture, out int amount)
                    || amount <= 0)
                { SendMiniText("Enter a positive whole number."); return; }
                if (operation == 1) RecoveredBagDeposit(item, rule, amount, originalId == rule.Id);
                else RecoveredBagWithdraw(item, rule, amount);
            });
        }
        catch (OfflineStoppedException) { /* explicit lifecycle cancellation, not a menu choice */ }
        catch (OfflinePausedException) { /* the pending conversation lost admission to pause */ }
        catch (Exception error)
        {
            // Match RunNpcAsync: an async continuation must surface a failure to the enclosing
            // offline action so its character and staged output roll back together.
            RecordOfflineHandlerFailure(error);
            Log.Error($"Container dialog for item {originalId} threw for '{_char.Name}': "
                + $"{LuaVerbHost.Describe(error)} — conversation abandoned", error);
        }
    }

    private bool RecoveredBagStillHere(InvItem item, int originalId, byte originalSlot, string originalOwner)
    {
        if (_char.Hp == 0) { SendMiniText("Spirits can't do that."); return false; }
        if (BlockedByMount()) return false;
        if (!ReferenceEquals(InvAt(originalSlot), item) || item.ItemId != originalId
            || item.Slot != originalSlot || item.Amount != 1 || item.Owner != originalOwner)
        { SendMiniText("The container changed. Use it again to start a new transfer."); return false; }
        if (item.Owner.Length > 0 && !item.Owner.Equals(_char.Name, StringComparison.OrdinalIgnoreCase))
        { SendMiniText("That container belongs to someone else."); return false; }
        return true;
    }

    private static bool RecoveredBagRuleCurrent(RecoveredItemContent.Bag rule)
        => rule == RecoveredItemContent.Container(rule.Id) && rule.Capacity > 0
            && Content.ItemById(rule.Id) is { Type: 21 }
            && Content.ItemById(rule.Content) is not null
            && Content.ItemById(rule.Shell) is { Type: 18 };

    // Contents cannot encode an individual material's name, bond or protection metadata.
    // Preserve those instances rather than silently stripping their identity on withdrawal.
    private static bool PlainRecoveredBagMaterial(InvItem item)
        => item.Amount > 0 && item.Owner.Length == 0 && item.CustomName.Length == 0
            && item.Dura == 0 && item.Repair == 0 && item.Protected == 0;

    private long RecoveredBagMaterialCount(int content)
        => _char.Inventory.Where(item => item.ItemId == content && PlainRecoveredBagMaterial(item))
            .Sum(item => (long)item.Amount);

    private void RecoveredBagDeposit(InvItem item, RecoveredItemContent.Bag rule, int amount, bool typed)
    {
        uint stored = typed ? item.Dura : 0;
        if (stored >= rule.Capacity || (uint)amount > rule.Capacity - stored)
        { SendMiniText("That amount will not fit in this container."); return; }
        if (RecoveredBagMaterialCount(rule.Content) < amount)
        { SendMiniText("You do not carry that many matching, unbound materials."); return; }

        // No await or save occurs between the complete preflight, exact material debit,
        // and the same-instance container update. The outer original action owns commit.
        int left = amount;
        foreach (var material in _char.Inventory
            .Where(entry => entry.ItemId == rule.Content && PlainRecoveredBagMaterial(entry))
            .OrderBy(entry => entry.Slot).ToArray())
        {
            int take = Math.Min(material.Amount, left);
            material.Amount -= take; left -= take;
            if (material.Amount == 0)
            { _char.Inventory.Remove(material); SendDelItem(material.Slot, DelReason.Removed); }
            else SendAddItem(material);
            if (left == 0) break;
        }
        if (left != 0) throw new InvalidOperationException("Container material debit changed inside the held state boundary.");
        item.ItemId = rule.Id;
        item.Dura = stored + (uint)amount;
        SendAddItem(item);
        MarkDirty(); SaveChar();
        SendMiniText($"Stored {amount} {Content.ItemById(rule.Content)!.Name}. "
            + $"Container: {item.Dura}/{rule.Capacity}.");
    }

    private void RecoveredBagWithdraw(InvItem item, RecoveredItemContent.Bag rule, int amount)
    {
        if ((uint)amount > item.Dura)
        { SendMiniText("The container does not hold that many materials."); return; }
        var material = Content.ItemById(rule.Content)!;
        if (CarryRoom(material) < amount)
        { CarryCapNotice(material); return; }
        // Match GivePlaced's strict plain-instance compatibility, valid free slots and
        // source carry/stack caps. Emptying retains the shell in the SAME occupied slot.
        long room = material.Stackable ? _char.Inventory.Where(entry =>
                entry.ItemId == material.Id && entry.CustomName.Length == 0 && entry.Owner.Length == 0
                && entry.Dura == 0 && entry.Repair == 0 && entry.Protected == 0
                && entry.Amount < material.StackCap)
            .Sum(entry => (long)material.StackCap - entry.Amount) : 0;
        for (int slot = 0; slot < _char.MaxInv; slot++)
            if (_char.Inventory.All(entry => entry.Slot != slot)) room += material.StackCap;
        if (room < amount)
        { SendMiniText("Free space in your inventory before removing those materials."); return; }

        var snapshot = SnapshotBag();
        try
        {
            item.Dura -= (uint)amount;
            if (item.Dura == 0) item.ItemId = rule.Shell;
            if (GivePlaced(material, amount, instance: new InvItem(0, material.Id, 1)) != amount)
                throw new InvalidOperationException("Container output capacity changed inside the held state boundary.");
            SendAddItem(item);
            MarkDirty(); SaveChar();
            SendMiniText($"Removed {amount} {material.Name}. Stored: {item.Dura}.");
        }
        catch
        {
            RestoreBag(snapshot);
            throw;
        }
    }
}
