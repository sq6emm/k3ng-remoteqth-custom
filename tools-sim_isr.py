# Simulate the SQ6EMM both-edge ISR (2 ms guard + level tracking) against a bouncing reed contact.
import random
def run(deg, speed_dps, duty, bounce_ms, glitch_prob, seed):
    rnd = random.Random(seed)
    period = 1000.0 / speed_dps                 # ms per degree (1 pulse per degree)
    events = []                                  # (t_ms, level) line transitions incl. bounce
    level = 1
    for k in range(deg):
        t0 = k * period
        for t_edge, new in ((t0, 0), (t0 + duty * period, 1)):   # close (low) then open (high)
            nb = rnd.randint(0, 4)               # bounce: extra toggles within bounce_ms
            times = sorted(t_edge + rnd.random() * bounce_ms for _ in range(2 * nb))
            seq = [t_edge] + times
            for i, tt in enumerate(seq):
                lvl = new if i % 2 == 0 else 1 - new
                events.append((tt, lvl))
        if rnd.random() < glitch_prob:          # isolated short glitch (EMI) in the middle of the open phase
            tg = t0 + (duty + (1 - duty) / 2) * period
            events += [(tg, 0), (tg + 0.05, 1)]
    events.sort()
    # ISR model: interrupt on every change; reads the line level at the time of the interrupt (+20 us latency)
    def line_at(t):
        lv = 1
        for tt, l in events:
            if tt <= t: lv = l
            else: break
        return lv
    pos, last_lvl, last_acc = 0.0, 1, -1e9
    prev = 1
    for tt, l in events:
        if l == prev: continue
        prev = l
        lv = line_at(tt + 0.02)
        if tt - last_acc < 2.0: continue        # 2 ms guard
        if lv == last_lvl: continue              # level tracking
        last_lvl = lv; last_acc = tt; pos += 0.5
    return pos
for duty in (0.5, 0.2, 0.05):
    for bounce in (0.5, 1.5):
        for glitch in (0.0, 0.05):
            errs = [run(360, 4.3, duty, bounce, glitch, s) - 360 for s in range(20)]
            print(f"duty {duty:4.2f} bounce {bounce} ms glitch {glitch:4.2f}: error after 360 deg  min {min(errs):+.1f}  max {max(errs):+.1f}")
