# Results

Every number here comes from a file in [`data/`](../data/). Re-derive them with:

```
python3 scripts/analyze_latency.py data/modbus_latency_1.0ms_20260716_230441.csv
```

---

## 1. Modbus round-trip latency

**File:** `data/modbus_latency_1.0ms_20260716_230441.csv`
**Conditions:** 1.0 ms OpenPLC scan cycle, 20,000 samples, no sensor in the loop,
trivial ST program (register mirrored to coil).

| Statistic | Value |
|---|---|
| Minimum | 0.1334 ms |
| 10th percentile (floor) | 0.2975 ms |
| Median | 0.6389 ms |
| Mean | 0.5846 ms |
| Standard deviation | 0.1766 ms |
| 90th percentile | 0.7500 ms |
| 99th percentile | 0.8982 ms |
| 99.9th percentile | 1.1640 ms |
| Maximum | 1.2851 ms |
| Samples over one cycle | 131 (0.66%) |

### What this says

The distribution has a hard floor at about 0.30 ms, which is the cost of two
Modbus TCP transactions plus Python overhead. No scan cycle setting can beat it.

The bulk of the spread between 0.30 and 1.0 ms is quantization. The trigger
arrives at an arbitrary point inside the scan window, so the wait for the next
scan is uniformly distributed across the cycle.

The tail is the interesting part, and it is short. The 99.9th percentile is
1.164 ms and the single worst sample in 20,000 is 1.285 ms. At a 1 ms cycle that
is one missed scan, never two. **The Pi did not drop out for multiple cycles even
once in 20,000 tries**, which is the result that matters for arguing it can serve
as a controller.

### One thing I cannot yet explain

If the trigger lands uniformly inside the scan window, the mean should sit half a
cycle above the floor — 0.30 + 0.50 = 0.80 ms. The measured mean is 0.585 ms, so
mean minus floor is 0.287 ms rather than 0.5 ms.

Possible causes I have not ruled out: the actual scan cycle is shorter than the
1 ms requested, the trigger arrival is correlated with the scan phase rather than
independent of it, or the floor is not as flat as the 10th percentile suggests.
Measuring the scan period directly would separate these.

---

## 2. The disappearing 3.6 ms spike

An earlier experiment (`data/Plunge Test Latency`, 28 trials) ran the same timing
measurement with a PT100 and a MAX31865 inside the loop. Most samples fell
between 0.45 and 1.1 ms, but one hit **3.643 ms**.

At the time I attributed that to OS scheduler preemption. The 20,000-sample run
with the sensor removed never exceeded 1.285 ms.

With 28 samples, a 1-in-20,000 event appearing once would be extraordinarily
unlucky, so the more plausible reading is that the spike came from the SPI read,
not the scheduler. That is a hypothesis, not a proof — confirming it means
re-running the 20,000-sample test *with* the sensor back in the loop and seeing
whether the tail returns.

Either way, the experiment did its job. Isolating the signal path turned an
assumption into a testable question.

---

## 3. Where the bottleneck actually is

The sensor-side measurements live in
[cryo-rtd-readout](https://github.com/williamsni14463/cryo-rtd-readout), but the
comparison belongs here because it decides how much the numbers above matter.

| Stage | Time |
|---|---|
| Modbus round trip | 0.6 ms |
| MAX31865 conversion | 16.7 ms |
| PT100 thermal response | 2,420 ms |

The probe is 145x slower than the conversion and about 4,000x slower than the
communication. For a thermal control loop on this hardware, the sensor's thermal
mass sets the bandwidth and everything electronic is free. Chasing milliseconds
off the scan cycle to improve a temperature loop would be wasted effort.

That conclusion does not carry over to pressure, where the sensor responds in
microseconds and the communication path becomes the limit instead. Which loop
you are closing decides whether any of the latency work above is worth doing.

---

## Reproducing

Each experiment has its own log in [`experiments/`](../experiments/) with the ST
program, the Modbus map, the wiring, and the exact command line used. The scripts
in [`scripts/`](../scripts/) take command-line arguments for sample count and
cycle time so the sweeps can be repeated without editing code.
