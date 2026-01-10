
import { simulatedBackend } from '../src/preview/simulatedBackend';
import { OpsState, SystemEvent, HealthcheckResponse } from '../src/api/types';

// Simple Assertion Helper
function assert(condition: boolean, msg: string) {
    if (!condition) {
        console.error(`❌ FAILED: ${msg}`);
        process.exit(1);
    } else {
        console.log(`✅ PASS: ${msg}`);
    }
}

console.log("Starting Parity Contract Verification...");

// 1. HEALTH CHECK CONTRACT
console.log("\n[1] Verifying Health Contract...");
const health = simulatedBackend.getHealth();
assert(typeof health.status === 'string', "Health.status must be string");
assert(typeof health.version === 'string', "Health.version must be string");
// HealthcheckResponse uses uptime_min
assert(typeof health.uptime_min === 'number', "Health.uptime_min must be number");

// 2. OPS STATE CONTRACT
console.log("\n[2] Verifying OpsState Contract...");
const ops = simulatedBackend.getOpsState();
const validModes = ['MANUAL', 'SEMI', 'AUTO', 'STOP'];
// exec_mode is optional in OpsState but simulatedBackend should return it
if (ops.exec_mode) {
    assert(validModes.includes(ops.exec_mode), "Invalid Exec Mode");
}
assert(typeof ops.auto_mode === 'boolean', "Auto Mode must be boolean");
assert(typeof ops.global_stop === 'boolean', "Global Stop must be boolean");
assert(ops.pnl_today !== undefined, "PnL Today must be defined");

// 3. SYSTEM EVENTS CONTRACT
console.log("\n[3] Verifying Events Contract...");
const events = simulatedBackend.getSystemEvents();
assert(Array.isArray(events.items), "Events must be an array");
if (events.items.length > 0) {
    const evt = events.items[0] as any; // Cast to allow checking severity if present
    assert(typeof evt.id === 'string', "Event ID must be string");
    // Severity is in PreviewStore events but not in shared SystemEvent type yet
    if (evt.severity) {
        assert(['INFO', 'WARNING', 'CRITICAL'].includes(evt.severity), "Invalid Severity");
    }
    assert(evt.timestamp !== undefined, "Timestamp required");
}

// 4. SCENARIO VALIDATION: GLOBAL STOP
console.log("\n[4] Scenario: Global Stop Parity...");
simulatedBackend.setGlobalStop(true);
const stopState = simulatedBackend.getOpsState();
assert(stopState.global_stop === true, "Global Stop should be TRUE");
assert(stopState.exec_mode === 'STOP', "Exec Mode should be STOP");
// Check strict optionality
if (stopState.veto_reason !== null) {
    assert(typeof stopState.veto_reason === 'string', "Veto reason must be string or null");
}
console.log("   -> Stop logic verified.");
simulatedBackend.setGlobalStop(false); // Reset

// 5. SCENARIO VALIDATION: DRIFT HARD -> DOWNGRADE
console.log("\n[5] Scenario: Drift HARD Downgrade...");
// Reset to AUTO first
simulatedBackend.setExecMode('AUTO');
const autoState = simulatedBackend.getOpsState();
assert(autoState.exec_mode === 'AUTO', "Setup: Exec Mode should be AUTO");

// Trigger HARD drift
simulatedBackend.triggerDrift('HARD');
const driftState = simulatedBackend.getOpsState();
assert(driftState.drift_status === 'HARD', "Drift Status should be HARD");
assert(driftState.exec_mode !== 'AUTO', "Exec Mode should NOT be AUTO (Downgraded)");
console.log(`   -> Drift Hard Downgrade verified (AUTO -> ${driftState.exec_mode}).`);

console.log("\n🎉 PARITY CHECK COMPLETE: SIMULATION MATCHES CONTRACTS.");
