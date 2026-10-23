# Raspberry Pi as an Industrial PLC — Latency and Jitter Benchmarks

Measuring whether a Raspberry Pi 4 running OpenPLC can meet the timing
requirements normally expected of an industrial PLC.

A real PLC is judged on *predictability*, not average speed. A controller with a
0.8 ms mean and a 5 ms worst case is a different machine from one with a 0.8 ms
mean and a 0.1 ms standard deviation, even though the headline number is the
same. These experiments measure the whole distribution, not the average.

The work was done at Fermilab as part of the controls effort for MAMBA, a rapid
cycling bubble chamber prototype for the DUNE collaboration. The eventual target
is a Pi-based PLC driving a linear actuator and reading cryogenic sensors, so the
question is not academic.

---

## Results so far

**Modbus round-trip latency, 1.0 ms scan cycle, n = 20,000**

| | ms |
|---|---|
| Minimum | 0.133 |
| Floor (10th percentile) | 0.298 |
| Median | 0.639 |
| Mean | 0.585 |
| Standard deviation | 0.177 |
| 99th percentile | 0.898 |
| 99.9th percentile | 1.164 |
| **Maximum** | **1.285** |

Samples exceeding the 1.0 ms cycle time: 131, or 0.66%.

The number that matters is the maximum. **Across 20,000 consecutive samples at a
1 ms scan cycle, nothing took longer than 1.285 ms.** The tail is bounded. That
is a much stronger statement than the mean, and it is the statement a controls
engineer actually needs.

**The 3.6 ms spike did not reproduce.** An earlier 28-sample test with a PT100
sensor in the loop recorded a single 3.643 ms outlier, which I assumed at the time
was the OS scheduler preempting the PLC process. Removing the sensor and running
20,000 samples put a hard ceiling at 1.285 ms. The spike was in the SPI sensor
read, not in the scheduler. Isolating the signal path was the point of this
experiment and it paid off.

**MAX31865 conversion rate verified.** Measured interval between conversions in
continuous mode: 16.689 ms mean over 100 pulses (σ = 1.524 ms), which is 59.92 Hz
against a nominal 60 Hz. The amplifier does what it claims.

**PT100 thermal response dominates everything.** A step change reached 63.2% in
2.42 s and 90% in 7.86 s, so the sensor time constant is about 2.4 s. That is
145× slower than the conversion time and roughly 4,000× slower than the Modbus
round trip. For any thermal control loop built on this hardware, the probe is the
bottleneck and the electronics are free.

---

## What is measured, exactly

```
Python writes holding register (%QW0 = 1)
    -> OpenPLC scan cycle picks it up
        -> PLC logic sets coil (%QX0.0 = TRUE)
            -> Python reads the coil back over Modbus
```

Nothing else. No sensor, no GPIO, no human. The ST program is deliberately
trivial — it mirrors a register to a coil — so that what gets measured is
communication plus scan overhead and not program execution.

Three numbers come out of the distribution and each means something different:

- **Floor** — fixed cost of two Modbus TCP transactions plus Python. Irreducible
  with this software stack no matter how low the scan cycle goes.
- **Typical spread** — floor up to floor plus one cycle time. This is
  quantization: the trigger lands at a random point inside the scan window.
- **Tail beyond one cycle** — the PLC missed a scan. This is the jitter rate, and
  it is the number that decides whether the Pi is usable for a given application.

The expected mean is floor + cycle_time/2. Measured mean minus floor is 0.287 ms
against an expected 0.5 ms, which suggests the trigger is not landing uniformly
in the scan window. I don't have an explanation for that yet.

---

## Repository layout

```
setup/          Build the rig from a blank SD card. Do these in order.
experiments/    One markdown log per experiment: method, results, diagnosis.
scripts/        The Python used to run each experiment.
data/           Raw CSV output and figures.
issues/         Every bug worth remembering, with root cause and fix.
```

Start in [setup/](setup/) if you are reproducing this from scratch. The three
guides take you from flashing an SD card to a working button-and-LED ladder
program, which is the sanity check everything else assumes.

---

## Open questions

These are the experiments I have not run yet, roughly in order of how much they
would change the conclusion.

**Scan cycle floor.** Below 1 ms the OpenPLC program stops compiling. Mapping
where it becomes unstable, starts missing cycles, or refuses outright is the
single most important remaining measurement for the "can a Pi be a PLC" question.
Worth sweeping 0.5 ms through 50 ms and recording the failure mode at each step.

**Jitter versus scan cycle.** The 0.66% overrun rate at 1 ms is one point on a
curve. Does it get worse as the cycle shortens? That curve is the real answer.

**Behaviour under CPU load.** An industrial PLC has dedicated hardware. A Pi
shares a CPU with a general-purpose OS. Running a stress test in a second
terminal and re-measuring would show whether the bounded tail survives contention,
and I suspect this is the Pi's real weakness.

**PREEMPT_RT.** Raspberry Pi OS is not a real-time OS, so the scheduler can
preempt the runtime at any point. There is a PREEMPT_RT kernel patch for the Pi.
Measuring with and without it would isolate how much of the jitter is the OS and
how much is the software stack.

**Network baseline.** Raw ICMP ping between the two machines sets a floor for
what Modbus TCP can achieve independent of PLC overhead. Cheap to measure, and it
would tell me how much of the 0.298 ms floor is network versus Python.

**C++ runtime.** Python's `pymodbus` is convenient and slow. Whether a C++ client
moves the floor is worth knowing, though it would not touch the scan-cycle
quantization that dominates the spread.

**Comparison against a commercial PLC.** Everything above is only meaningful
relative to what a Beckhoff or Siemens unit does on the same test.

---

## Hardware

- Raspberry Pi 4, Raspberry Pi OS Bookworm 64-bit
- Adafruit MAX31865 RTD-to-digital amplifier (SPI)
- PT100 RTD, 4-wire
- Breadboard, pushbutton, LED, 220 Ω and 10 kΩ resistors

## Software

- OpenPLC Runtime v3 on the Pi, web UI on port 8080, Modbus TCP on port 502
- OpenPLC Editor on a laptop, Structured Text
- Python 3 with `pymodbus`, `adafruit-blinka`,
  `adafruit-circuitpython-max31865`, `RPi.GPIO`

Bookworm ships with a pip guard; installs need `--break-system-packages` or a
virtual environment. That and five other things that cost me time are written up
in [issues/KNOWN_ISSUES.md](issues/KNOWN_ISSUES.md).
