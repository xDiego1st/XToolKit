"""Query offer metadata for explicit Google Play product IDs.

Usage: python query_sku.py g1.2tb.ai.subs_variant [OTHER_SKUS...]
"""
import json
import sys
import threading
import time

import frida

import ultra0


def main():
    skus = sys.argv[1:] or ["g1.2tb.ai.subs_variant"]
    dev = frida.get_device_manager().add_remote_device("127.0.0.1:27042")
    pid = 0
    for p in dev.enumerate_processes():
        if "subscriptions.red" in p.name or p.name == "Google One":
            pid = p.pid
            break
    if not pid:
        raise SystemExit("Google One process was not found")

    js = ultra0.build_js("5x", True)
    js = js.replace('var PRODUCTS=["g1.play.20tb"];', 'var PRODUCTS=' + json.dumps(skus) + ';', 1)

    sess = dev.attach(pid)
    done = threading.Event()
    offers = []

    def on_msg(m, d):
        p = m.get("payload") or {}
        if p.get("ev") == "offer":
            offers.append(p)
        elif p.get("ev") in ("list_only", "no_trial", "query_err", "no_offers", "pd"):
            if p.get("ev") != "pd":
                done.set()

    sc = sess.create_script(js)
    sc.on("message", on_msg)
    sc.load()
    done.wait(timeout=25)
    time.sleep(1)

    print(f"\n=== {', '.join(skus)} ===")
    if not offers:
        print("  (No offers were returned)")
    for o in offers:
        micros = str(o.get("micros"))
        price = "Free introductory phase" if micros == "0" else f"${int(micros)/1_000_000:.2f}"
        print(f"  offerId={str(o.get('id')):22s} {price:>9s}  {o.get('period')}   [{o.get('title') or o.get('name') or ''}]")
        if micros == "0":
            print(f"      token={o.get('token')}")
    try:
        sess.detach()
    except Exception:
        pass


if __name__ == "__main__":
    main()
