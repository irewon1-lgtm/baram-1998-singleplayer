using System.Collections.Immutable;
using Shared;

namespace Server;

/// <summary>Immutable inspection of an existing item, never a second inventory or save schema.</summary>
public sealed record OfflineItemInspection(byte WireSlot, ItemDef Definition, int Amount, uint Dura,
    byte Repair, byte Protected, string Owner, string CustomName, string PathName,
    string UseVerb, string UseAmount, string UseFull, string UseHpCost, string UseDuration,
    string UseName, string UseStat)
{
    internal bool Matches(InvItem item, bool equipment) =>
        WireSlot == (equipment ? item.Slot : item.Slot + 1) && Definition.Id == item.ItemId &&
        Amount == item.Amount && Dura == item.Dura && Repair == item.Repair && Protected == item.Protected &&
        Owner == item.Owner && CustomName == item.CustomName && ReferenceEquals(Definition, Content.ItemById(item.ItemId));
}

public sealed record OfflineInventoryInspection(ImmutableArray<OfflineItemInspection> Inventory,
    ImmutableArray<OfflineItemInspection> Equipment)
{
    public static OfflineInventoryInspection Empty { get; } = new([], []);
    public OfflineItemInspection? Find(byte wireSlot, bool equipment)
    {
        foreach (var item in equipment ? Equipment : Inventory)
            if (item.WireSlot == wireSlot) return item;
        return null;
    }
}

public sealed partial class Session
{
    private OfflineInventoryInspection _lastCapturedInventory = OfflineInventoryInspection.Empty;
    private object? _lastInspectionDefinitions;
    public OfflineInventoryInspection CommittedInventoryInspection => Volatile.Read(ref _committedAppearance).Items;

    private static bool InspectionUnchanged(List<InvItem> live, ImmutableArray<OfflineItemInspection> previous, bool equipment)
    {
        if (live.Count != previous.Length) return false;
        for (int n = 0; n < live.Count; n++) if (!previous[n].Matches(live[n], equipment)) return false;
        return true;
    }

    private OfflineInventoryInspection CaptureOfflineInventoryInspection()
    {
        AssertStateHeld("item inspection");
        object definitions = Content.Items;
        if (ReferenceEquals(_lastInspectionDefinitions, definitions) &&
            InspectionUnchanged(_char.Inventory, _lastCapturedInventory.Inventory, false) &&
            InspectionUnchanged(_char.Equipment, _lastCapturedInventory.Equipment, true)) return _lastCapturedInventory;
        OfflineItemInspection? Inspect(InvItem item, bool equipment)
        {
            var definition = Content.ItemById(item.ItemId);
            if (definition is null) return null; // Unknown held IDs remain held, without invented stats/actions.
            Content.ItemParams.TryGetValue(definition.Key, out var use);
            string Param(string key) => use?.GetValueOrDefault(key) ?? "";
            return new(checked((byte)(equipment ? item.Slot : item.Slot + 1)), definition, item.Amount,
                item.Dura, item.Repair, item.Protected, item.Owner, item.CustomName,
                Content.Paths.GetValueOrDefault(definition.PathId) ?? "", Param("verb"), Param("amount"),
                Param("full"), Param("hpcost"), Param("duration"), Param("wardname"), Param("stat"));
        }
        _lastInspectionDefinitions = definitions;
        return _lastCapturedInventory = new(
            _char.Inventory.Select(item => Inspect(item, false)).OfType<OfflineItemInspection>().ToImmutableArray(),
            _char.Equipment.Select(item => Inspect(item, true)).OfType<OfflineItemInspection>().ToImmutableArray());
    }
}
