using Protocol.Tk495;
using Shared;

namespace Server;

public sealed partial class Session
{
    // User-authorized offline adapters for later item classes. Source definitions, ordinary
    // use verbs and original wire layouts remain untouched. Per-category provenance is in
    // RecoveredItems.json. Cosmetic skins use a reversible local overlay, not gear-stat edits.
    private bool TryUseRecoveredItem(Shared.InvItem item, ItemDef def)
    {
        if (TryUseRecoveredBag(item, def)) return true;
        if (TryUseRecoveredGuide(item, def)) return true;
        if (TryUseRecoveredArrows(item, def)) return true;
        if (def.Type is not (24 or 25 or 27 or 28 or 29)) return false;
        if (def.Level > _char.Level) { SendMiniText("You need more experience."); return true; }
        if (Asleep || Paralyzed) { SendMiniText("You cannot do that right now."); return true; }
        if (def.Type == 24)
        {
            if (_char.Mounted)
            {
                // The original dismount returns a ridden wild horse to the world. Owned
                // item mounts use its separate no-spawn branch, so neither kind is lost.
                TryRideHorse();
                return true;
            }
            else
            {
                if (Content.MapMeta.TryGetValue(_char.Map, out var map) && !map.CanMount)
                { SendMiniText("You cannot use mount items in this area."); return true; }
                if (Stealthed || _morphLook > 0 || Content.IsPvpMap(_char.Map)
                    )
                { SendMiniText("You cannot mount while transformed, hidden, or in a battle area."); return true; }
                _char.Mounted = true; _char.RecoveredMountItemId = def.Id;
                SendMiniText($"Riding {def.Name}. Use the mount item again to dismount.");
            }
        }
        else if (def.Type == 27)
        {
            var weapon = _char.Equipment.FirstOrDefault(e => e.Slot == 1 && Content.ItemById(e.ItemId)?.Type == 3);
            if (weapon is null) { SendMiniText("Wield a weapon before applying a weapon appearance."); return true; }
            _char.RecoveredWeaponSkinId = _char.RecoveredWeaponSkinId == def.Id ? 0 : def.Id;
            _char.RecoveredSkinBaseItemId = weapon.ItemId;
            SendMiniText("Weapon appearance changed. Combat values are unchanged. Use it again to remove it.");
        }
        else
        {
            if (DialogBusy) { SendMiniText("Close the current conversation first."); return true; }
            _ = ApplyRecoveredCosmetic(item, def);
            return true;
        }
        RefreshAppearance();
        MarkDirty();
        return true;
    }

    private async Task ApplyRecoveredCosmetic(InvItem item, ItemDef def)
    {
        long generation = CaptureOfflineGeneration();
        byte slot = item.Slot;
        string owner = item.Owner;
        try
        {
            if (def.Type == 29 && _char.RecoveredBeardItemId != 0)
            { SendMiniText("Remove your current beard at the recovery workshop first."); return; }
            if (await DlgMenu(F1VirtualNpc, $"Apply {def.Name}? This item is consumed.", new[] { "Apply", "Cancel" }) != 1) return;
            RunOfflineMutation(generation, () =>
            {
            // The item and eligibility may have changed while the confirmation was open.
            if (!ReferenceEquals(InvAt(slot), item) || item.ItemId != def.Id || item.Owner != owner
                || item.Amount <= 0 || _char.Hp == 0 || _char.Mounted
                || Asleep || Paralyzed || def.Level > _char.Level || !CanUsePath(def))
            { SendMiniText("That item or your condition changed. Choose it again."); return; }
            var rule = RecoveredItemContent.Find(def.Id);
            if (rule is null) { SendMiniText("That isn't working right now."); return; }
            if (def.Type == 25)
            { _char.Face = (ushort)Math.Clamp(rule.Face, 0, FaceCount - 1); _char.RecoveredFaceItemId = def.Id; }
            else if (def.Type == 28)
            { _char.HairColor = def.LookColor; _char.RecoveredHairItemId = def.Id; }
            else
            {
                if (_char.RecoveredBeardItemId != 0) return;
                _char.RecoveredBeardItemId = def.Id;
            }
            SpendRecoveredItem(item);
            RefreshAppearance(); SaveChar();
            SendMiniText("Your appearance has changed.");
            });
        }
        catch (OfflineStoppedException) { }
        catch (OfflinePausedException) { }
        catch (Exception e) { RecordOfflineHandlerFailure(e); Log.Error("Recovered cosmetic action failed", e); }
    }

    internal void RemoveRecoveredBeard()
    {
        long generation = CaptureOfflineGeneration();
        RunOfflineMutation(generation, () =>
        {
            _char.RecoveredBeardItemId = 0;
            RefreshAppearance(); MarkDirty();
            SendMiniText("Your beard has been removed.");
        });
    }

    internal bool BuyRecoveredItem(int itemId, uint price, long generation, out bool insufficientGold)
    {
        bool poor = false, granted = false;
        RunOfflineMutation(generation, () =>
        {
        poor = _char.Coins < price;
        if (poor) return;
        // A queued dialog can resume outside the host's original reply transaction.
        // Reserve/grant without an intermediate save, debit under the same state lease,
        // and persist the completed purchase once, never an unpaid half-purchase.
        if (!GiveRewardItemAllOrNone(Content.ItemById(itemId), 1, persist: false)) return;
        _char.Coins -= price;
        SendStats();
        SaveChar();
        granted = true;
        });
        insufficientGold = poor;
        return granted;
    }

    public RecoveredAppearance CaptureRecoveredAppearance()
    {
        using var held = EnterState();
        var hair = _char.RecoveredHairItemId == 0 ? null : RecoveredItemContent.Find(_char.RecoveredHairItemId);
        var beard = _char.RecoveredBeardItemId == 0 ? null : RecoveredItemContent.Find(_char.RecoveredBeardItemId);
        var skin = _char.RecoveredWeaponSkinId == 0 ? null : Content.ItemById(_char.RecoveredWeaponSkinId);
        bool skinActive = skin is not null && _char.Inventory.Any(i => i.ItemId == skin.Id)
            && _char.Equipment.Any(i => i.Slot == 1 && i.ItemId == _char.RecoveredSkinBaseItemId);
        return new(true, hair?.ColorRgb ?? -1, beard?.Style ?? 0, beard?.ColorRgb ?? 0x24201c,
            skinActive ? skin!.ClientIcon : -1, _char.Mounted ? _char.RecoveredMountItemId : 0,
            _char.RecoveredFaceItemId, _char.RecoveredHairItemId, _char.RecoveredBeardItemId,
            skinActive ? skin!.Id : 0);
    }

    private void SpendRecoveredItem(Shared.InvItem item)
    {
        item.Amount--;
        if (item.Amount <= 0) { _char.Inventory.Remove(item); SendDelItem(item.Slot, DelReason.Used); }
        else SendAddItem(item);
        MarkDirty();
    }
}
