# Lunia Core - Preview Mode (Owner Demo)

## Overview
The **Preview Mode** is a special localized configuration designed to allow Product Owners and Stakeholders to interact with the Lunia Console UI even when the backend is offline or "Hard" governance blocks are active. It converts "Hard Blocks" (like System Halted) into "Soft Blocks" (dismissible warnings) and provides a simulated backend for "Happy Path" demonstration.

## Features

### 1. Preview Status Badge
When `VITE_PREVIEW_MODE=1` is set, a sticky badge appears in the bottom-right corner.
- **Visual**: "PREVIEW MODE" (Amber) or "SIMULATION" (Purple).
- **Diagnostics**: Click to see `SystemMode`, `Backend Health`, and `Simulation Status`.
- **Toggle**: You can toggle `Simulation` on/off from this badge.
- **Diagnostics Panel**: View real-time simulated ops state and audit log.

### 2. Soft Blocks (Safe Mode)
Normally, if the Backend reports a `CRITICAL` error or is unreachable, the UI locks down with a generic "System Halted" overlay.
In **Preview Mode**:
- The Overlay is translucent.
- It can be **Dismissed** (Top Right Close Button).
- A persistent "System Halted - Dismissed" banner remains at the bottom, but you can interact with the rest of the UI.
- **Honest UI**: Dismissing does NOT re-enable trading; it only allows you to browse the console.

### 3. Frontend-only Simulation
If `VITE_PREVIEW_SIMULATION=1` AND (backend is unreachable OR `Force Sim` is enabled):
- The Frontend switches to a **Simulated Backend**.
- **Health**: Reports `OK`.
- **Ops State**: Reports `AUTO` mode with realistic dummy data (PNL, Risk Score).
- **Interactivity**: You can "Start", "Stop", and trigger "Drift" events via the UI controls, which update the local simulation state.
- **Automatic Failover**: If the real backend goes down, the UI automatically switches to Simulation mode to prevent "Failed to fetch" errors.

## Configuration

To enable Preview Mode, set the following environment variables in your `.env` file (or use `start_preview.sh`):

```bash
# Enable the UI features (Badge, Soft Blocks)
VITE_PREVIEW_MODE=1

# Enable the Offline Simulation (Optional, defaults to off if omitted)
VITE_PREVIEW_SIMULATION=1
```

## Running the Demo

Use the helper script to spin up the environment with these flags automatically:

```bash
./start_preview.sh
```

## Verification Checklist

### 1. Backend Offline (Simulation Mode)
- [ ] Run `./start_preview.sh` and ensure Backend is NOT running (or kill it manually).
- [ ] Open `http://localhost:5173`.
- [ ] Verify Badge says **SIMULATION**.
- [ ] Verify **System Halted** overlay appears (since offline) but is dismissible.
- [ ] Click through **Trader, Portfolio, Risk, Admin** pages.
      - Ensure NO "Failed to fetch" errors.
      - Ensure simulated data (e.g., $1,250,000 Portfolio Value) is visible.

### 2. Backend Online (Live Mode)
- [ ] Start real backend.
- [ ] Click "Switch to LIVE" if prompted, or toggle "Force Sim" off.
- [ ] Verify Badge says **LIVE**.
- [ ] Verify real data is shown.

### 3. Honest UI
- [ ] In Simulation, trigger **Global Stop**.
- [ ] Verify Audit Log in Badge Diagnostics shows "Manual Emergency Stop Engaged" (SIMULATED).
- [ ] Ensure app does not claim to have executed real trades.
