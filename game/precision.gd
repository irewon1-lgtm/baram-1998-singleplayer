extends RefCounted
## Integer ratios and half-away rounding shared by runtime and import tests.
const EXACT_MAX = 9007199254740991

static func half_away(value: float) -> int:
    return floori(value+0.5) if value>=0 else ceili(value-0.5)

static func valid_ratio(ratio: Dictionary) -> bool:
    var n=ratio.get("numerator",-1)
    var d=ratio.get("denominator",0)
    return float(n)==float(int(n)) and float(d)==float(int(d)) and int(d)>0 and int(d)<=EXACT_MAX and int(n)>=0 and int(n)<=int(d)

static func bounded_random(rng: RandomNumberGenerator, maximum: int) -> int:
    if maximum<=0 or maximum>EXACT_MAX:return -1
    if maximum<=2147483647:return rng.randi_range(0,maximum-1)
    # 53 uniform bits, rejection sampling. No 32-bit truncation, modulo bias,
    # probability float conversion, or permanently fixed random seed.
    var span=9007199254740992
    var limit=span-span%maximum
    while true:
        var sample=(int(rng.randi())&2097151)*4294967296+int(rng.randi())
        if sample<limit:return sample%maximum
    return -1

static func roll(rng: RandomNumberGenerator, ratio: Dictionary) -> bool:
    if not valid_ratio(ratio):return false
    return bounded_random(rng,int(ratio.denominator))<int(ratio.numerator)

static func decimal_ratio(value: float) -> Dictionary:
    if not is_finite(value) or value<0 or value>1:return {}
    var denominator=1000000
    while denominator<=1000000000000000:
        var scaled=value*denominator
        var numerator=half_away(scaled)
        if (numerator>0 or value==0) and absf(scaled-numerator)<0.000001:
            return {"numerator":numerator,"denominator":denominator}
        denominator*=10
    return {} # unrepresentable is an error, never a silent 0% conversion

static func draw(rng: RandomNumberGenerator, mode: String, rolls: Array) -> Dictionary:
    if mode not in ["independent","exclusive","weighted","guaranteed"]:
        return {"ok":false,"error":"UNKNOWN_DROP_MODE","items":[]}
    var selected=[]
    if mode in ["independent","exclusive"]:
        var denominator=0
        var total=0
        for entry in rolls:
            var ratio=entry.get("ratio",entry.get("probability",{}))
            if typeof(ratio)!=TYPE_DICTIONARY or not valid_ratio(ratio):return {"ok":false,"error":"INVALID_RATIO","items":[]}
            if mode=="exclusive":
                if denominator!=0 and denominator!=int(ratio.denominator):return {"ok":false,"error":"EXCLUSIVE_DENOMINATOR_MISMATCH","items":[]}
                denominator=int(ratio.denominator);total+=int(ratio.numerator)
        if mode=="exclusive" and (denominator<=0 or total!=denominator):return {"ok":false,"error":"EXCLUSIVE_MISSING_OR_OVERLAPPING_OUTCOME","items":[]}
        if mode=="exclusive":
            var picked=bounded_random(rng,denominator)
            for entry in rolls:
                picked-=int(entry.get("ratio",entry.get("probability",{})).numerator)
                if picked<0:selected=[entry];break
        else:
            for entry in rolls:
                if roll(rng,entry.get("ratio",entry.get("probability",{}))):selected.append(entry)
    elif mode=="weighted":
        var total=0
        for entry in rolls:
            if not entry.has("weight") or float(entry.weight)!=float(int(entry.weight)) or int(entry.weight)<0:return {"ok":false,"error":"INVALID_WEIGHT","items":[]}
            total+=int(entry.weight)
        if total<=0 or total>EXACT_MAX:return {"ok":false,"error":"INVALID_WEIGHT_SUM","items":[]}
        var picked=bounded_random(rng,total)
        for entry in rolls:
            picked-=int(entry.weight)
            if picked<0:selected=[entry];break
    else:selected=rolls.duplicate(true)
    return {"ok":true,"items":selected,"error":""}
