# Sendspin Network Resilience Test Plan

## Purpose

Test whether poor connectivity between the LedFx host and the Sendspin server can trigger Sendspin stream failures, reconnect storms, forced event-loop shutdowns, or `Connector is closed` errors.

This plan is tailored to the current test setup:

- LedFx host: Windows notebook
- LedFx notebook IP: `192.168.1.146`
- Sendspin server host: Ubuntu VM inside Proxmox on the NUC
- Sendspin container: `sendspin-demo`
- Docker network mode: `host`
- Ubuntu VM interface toward notebook: `ens18`
- Sendspin port: `8927`

---

## Known Failure Pattern to Watch For

Look for these LedFx log lines during or after each test:

```text
Stopping Sendspin stream...
Sendspin thread did not exit within 5 s; force-stopping event loop
RuntimeError: Event loop stopped before Future completed.
Sendspin connection attempt failed: Connector is closed.
Audio source opened
Audio source closed
Starting Sendspin stream...
```

A failure is especially interesting if LedFx does not recover after the network is restored.

---

## Setup Variables

Run these on the Ubuntu VM before testing:

```bash
IFACE=ens18
NOTEBOOK_IP=192.168.1.146
PORT=8927
CONTAINER=sendspin-demo
```

---

## Pre-Test Checklist

### 1. Confirm route to notebook

```bash
ip route get $NOTEBOOK_IP
```

Expected:

```text
192.168.1.146 dev ens18 src 192.168.1.12
```

Checklist:

- [ ] Output uses `dev ens18`
- [ ] Source IP is the Sendspin VM IP, currently `192.168.1.12`

---

### 2. Confirm Sendspin container is running

```bash
docker ps | grep $CONTAINER
```

Checklist:

- [ ] `sendspin-demo` is running
- [ ] Sendspin server is reachable from LedFx before starting tests

---

### 3. Confirm Docker network mode

```bash
docker inspect $CONTAINER | grep -i networkmode
```

Expected:

```text
"NetworkMode": "host"
```

Checklist:

- [ ] Network mode is `host`

---

### 4. Confirm Sendspin is listening

```bash
ss -tulpen | grep $PORT
```

Checklist:

- [ ] Port `8927` is listening
- [ ] Sendspin is currently available to the notebook

---

### 5. Confirm no old network impairments are active

```bash
tc qdisc show dev $IFACE
sudo iptables -S INPUT | grep $PORT
```

Checklist:

- [ ] No existing `netem` rule is active on `ens18`
- [ ] No old `iptables` DROP or REJECT rule exists for port `8927`

If needed, cleanup first:

```bash
sudo tc qdisc del dev $IFACE root 2>/dev/null || true
sudo iptables -D INPUT -p tcp --dport $PORT -s $NOTEBOOK_IP -j DROP 2>/dev/null || true
sudo iptables -D INPUT -p tcp --dport $PORT -s $NOTEBOOK_IP -j REJECT 2>/dev/null || true
```

---

## Test 0 — Baseline Stability

### Goal

Confirm Sendspin is stable before introducing faults.

### Steps

1. Start LedFx using Sendspin.
2. Select the Sendspin source.
3. Use PCM first.
4. Let playback run normally for 5–10 minutes.

Checklist:

- [ ] Audio data is flowing
- [ ] No reconnects
- [ ] No `Stopping Sendspin stream...`
- [ ] No `Connector is closed`
- [ ] No forced event-loop shutdown

Notes:

```text
Baseline result:
```

---

## Test 1 — Moderate Latency and Jitter

### Goal

Simulate a poor but still connected network.

### Inject

```bash
sudo tc qdisc add dev $IFACE root netem delay 150ms 75ms
```

### Observe for 2–5 minutes

Checklist:

- [ ] Audio continues
- [ ] LedFx does not enter restart storm
- [ ] No forced event-loop shutdown
- [ ] No `Connector is closed`

### Cleanup

```bash
sudo tc qdisc del dev $IFACE root
```

### Verify cleanup

```bash
tc qdisc show dev $IFACE
```

Notes:

```text
Test 1 result:
```

---

## Test 2 — Severe Latency and Jitter

### Goal

Simulate a much worse connection while keeping the socket alive.

### Inject

```bash
sudo tc qdisc add dev $IFACE root netem delay 400ms 200ms
```

### Observe for 2–5 minutes

Checklist:

- [ ] Does audio continue with delay?
- [ ] Does LedFx stall silently?
- [ ] Does LedFx reconnect?
- [ ] Any buffer-related warnings?
- [ ] Any `Stopping Sendspin stream...` entries?

### Cleanup

```bash
sudo tc qdisc del dev $IFACE root
```

Notes:

```text
Test 2 result:
```

---

## Test 3 — Packet Loss

### Goal

Simulate lossy Wi-Fi or intermittent packet drops.

### Inject 5% loss

```bash
sudo tc qdisc add dev $IFACE root netem loss 5%
```

### Observe for 2–5 minutes

Checklist:

- [ ] Stream survives
- [ ] No restart storm
- [ ] No silent stall
- [ ] No forced event-loop shutdown

### Escalate to 15% loss

```bash
sudo tc qdisc change dev $IFACE root netem loss 15%
```

### Observe for 2–5 minutes

Checklist:

- [ ] Stream survives or reconnects cleanly
- [ ] No `Connector is closed` loop
- [ ] No permanent failure after cleanup

### Cleanup

```bash
sudo tc qdisc del dev $IFACE root
```

Notes:

```text
Test 3 result:
```

---

## Test 4 — Combined Bad Network

### Goal

Simulate a very poor connection with latency, jitter, loss, and packet reordering.

### Inject

```bash
sudo tc qdisc add dev $IFACE root netem delay 300ms 150ms loss 10% reorder 5%
```

### Observe for 5 minutes

Checklist:

- [ ] Does audio keep flowing?
- [ ] Does LedFx detect problems?
- [ ] Does LedFx reconnect?
- [ ] Does LedFx stall without reconnecting?
- [ ] Any `Stopping Sendspin stream...`?
- [ ] Any `Connector is closed`?

### Cleanup

```bash
sudo tc qdisc del dev $IFACE root
```

Notes:

```text
Test 4 result:
```

---

## Test 5 — Hard Blackhole

### Goal

Simulate a Wi-Fi dropout or server becoming unreachable without a clean TCP close.

This is the most important reproduction test.

### Inject

```bash
sudo iptables -A INPUT -p tcp --dport $PORT -s $NOTEBOOK_IP -j DROP
```

### Hold the fault for 30 seconds

```bash
sleep 30
```

### Restore

```bash
sudo iptables -D INPUT -p tcp --dport $PORT -s $NOTEBOOK_IP -j DROP
```

### Observe after restore

Checklist:

- [ ] Does LedFx recover automatically?
- [ ] Does audio resume?
- [ ] Is there a reconnect attempt?
- [ ] Is there a rapid open/close storm?
- [ ] Do logs show `Sendspin thread did not exit within 5 s`?
- [ ] Do logs show `Event loop stopped before Future completed`?
- [ ] Do logs show `Connector is closed`?

Notes:

```text
Test 5 result:
```

---

## Test 6 — Fast Reject

### Goal

Simulate a hard failure where the server immediately rejects traffic instead of silently dropping it.

### Inject

```bash
sudo iptables -A INPUT -p tcp --dport $PORT -s $NOTEBOOK_IP -j REJECT
```

### Hold for 10 seconds

```bash
sleep 10
```

### Restore

```bash
sudo iptables -D INPUT -p tcp --dport $PORT -s $NOTEBOOK_IP -j REJECT
```

### Observe

Checklist:

- [ ] Does LedFx fail quickly?
- [ ] Does it reconnect cleanly?
- [ ] Any restart storm?
- [ ] Any `Connector is closed` after restore?

Notes:

```text
Test 6 result:
```

---

## Test 7 — Repeated Network Flap

### Goal

Simulate an unstable Wi-Fi path that repeatedly drops and returns.

### Start flapping

```bash
while true; do
  echo "DROP on"
  sudo iptables -A INPUT -p tcp --dport $PORT -s $NOTEBOOK_IP -j DROP
  sleep 10

  echo "DROP off"
  sudo iptables -D INPUT -p tcp --dport $PORT -s $NOTEBOOK_IP -j DROP
  sleep 10
done
```

Stop with `Ctrl+C`.

### Cleanup after stopping

```bash
sudo iptables -D INPUT -p tcp --dport $PORT -s $NOTEBOOK_IP -j DROP 2>/dev/null || true
```

### Observe

Checklist:

- [ ] LedFx survives multiple flaps
- [ ] No accumulation of errors
- [ ] No permanent `Connector is closed`
- [ ] No forced event-loop shutdown
- [ ] No rapid audio source open/close loop

Notes:

```text
Test 7 result:
```

---

## Test 8 — Bandwidth-Limited Link

### Goal

Simulate a connection that stays alive but cannot keep up with the audio stream.

### Inject

```bash
sudo tc qdisc add dev $IFACE root netem rate 256kbit
```

### Observe for 2–5 minutes

Checklist:

- [ ] Does audio lag?
- [ ] Does buffering grow?
- [ ] Does the stream recover after cleanup?
- [ ] Any silent stall?

### Cleanup

```bash
sudo tc qdisc del dev $IFACE root
```

Notes:

```text
Test 8 result:
```

---

## Emergency Cleanup

Run this if a test is interrupted or the network remains impaired:

```bash
sudo tc qdisc del dev $IFACE root 2>/dev/null || true
sudo iptables -D INPUT -p tcp --dport $PORT -s $NOTEBOOK_IP -j DROP 2>/dev/null || true
sudo iptables -D INPUT -p tcp --dport $PORT -s $NOTEBOOK_IP -j REJECT 2>/dev/null || true
```

Verify:

```bash
tc qdisc show dev $IFACE
sudo iptables -S INPUT | grep $PORT
```

---

## Interpreting Results

### If only FLAC fails

Likely FLAC decoder lifecycle, callback, or buffering issue.

### If PCM and FLAC both fail

Likely shared Sendspin lifecycle issue, such as:

- stop during connect/reconnect
- forced event-loop shutdown
- connector/session reuse after shutdown
- audio source open/close churn
- always-on guard not being respected
- stall not detected by watchdog

### If blackhole causes the exact failure

Strong evidence that poor connectivity triggers the Sendspin shutdown/reconnect race.

### If latency/loss causes silent audio death

Look for missing audio-stall detection or playback scheduler failure.

---

## Log Bundle to Save After Each Failure

Save:

- LedFx logs from 2 minutes before fault injection through 2 minutes after recovery
- Sendspin server logs
- Test number
- Exact command used
- Whether PCM or FLAC was active
- Whether `sendspin_always_on` was enabled
- Whether the stream recovered without manually restarting LedFx

Template:

```text
Test number:
Codec:
Fault command:
Fault duration:
Recovered automatically:
Manual restart required:
Key LedFx log lines:
Key Sendspin log lines:
Notes:
```
