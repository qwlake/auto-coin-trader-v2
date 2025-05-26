from config.settings import settings

def calc_obi(depth_snap: dict, level: int):
    bids = depth_snap["bids"][:level]
    asks = depth_snap["asks"][:level]
    bid_val = sum(float(p)*float(q) for p, q in bids)
    ask_val = sum(float(p)*float(q) for p, q in asks)
    return bid_val / (bid_val + ask_val)

def signal(depth_snap):
    obi = calc_obi(depth_snap, settings.DEPTH_LEVEL)
    if obi >= settings.OBI_LONG:
        return "LONG"
    elif obi <= settings.OBI_SHORT:
        return "SHORT"
    return None