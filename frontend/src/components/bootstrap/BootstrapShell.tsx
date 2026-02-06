/**
 * Integration Gate I.1 + I.2 + I.3 — Bootstrap Shell Wrapper
 * 
 * Top-level component that wraps the entire app with bootstrap + auth + entitlement controllers.
 * Guarantees visible UI in all states.
 * 
 * CRITICAL INVARIANT: App renders ONLY when ALL THREE are READY:
 *   1. Bootstrap (backend health)
 *   2. Auth (session/identity)
 *   3. Entitlement (tier/subscription)
 */

import React from 'react';
import { useBootstrapController } from '../../hooks/useBootstrapController';
import { useAuthController } from '../../hooks/useAuthController';
import { useEntitlementController } from '../../hooks/useEntitlementController';
import { useAuth } from '../../hooks/useAuth';
import { BootstrapState } from '../../lib/bootstrapTypes';
import { AuthState } from '../../lib/authTypes';
import { EntitlementState } from '../../lib/entitlementTypes';
import {
    BootScreen,
    BackendDownScreen,
    BackendErrorScreen,
    UnauthorizedScreen,
    ForbiddenScreen,
    SystemHaltedScreen,
    GovernanceBlockedScreen,
} from './BootstrapScreens';
import {
    AuthBootingScreen,
    AuthUnavailableScreen,
    AuthServerErrorScreen,
} from '../auth/AuthScreens';
import {
    EntitlementBootingScreen,
    EntitlementUnavailableScreen,
    EntitlementServerErrorScreen,
    EntitlementMalformedScreen,
} from '../entitlement/EntitlementScreens';

interface Props {
    children: React.ReactNode;
}

export const BootstrapShell: React.FC<Props> = ({ children }) => {
    const bootstrap = useBootstrapController();
    const { bearerToken } = useAuth();
    const auth = useAuthController(bearerToken);
    const entitlement = useEntitlementController(bearerToken);

    // ═══════════════════════════════════════════════════════════════
    // PHASE 1: Bootstrap State Check (Backend health/governance)
    // ═══════════════════════════════════════════════════════════════

    switch (bootstrap.state) {
        case BootstrapState.BOOTING:
            return <BootScreen context={bootstrap} />;

        case BootstrapState.BACKEND_UNREACHABLE:
            return <BackendDownScreen context={bootstrap} />;

        case BootstrapState.BACKEND_ERROR:
            return <BackendErrorScreen context={bootstrap} />;

        case BootstrapState.UNAUTHORIZED:
            return <UnauthorizedScreen context={bootstrap} />;

        case BootstrapState.FORBIDDEN:
            return <ForbiddenScreen context={bootstrap} />;

        case BootstrapState.GLOBAL_STOP:
            return <SystemHaltedScreen context={bootstrap} />;

        case BootstrapState.GOVERNANCE_BLOCK:
            return <GovernanceBlockedScreen context={bootstrap} />;

        case BootstrapState.READY:
            // Bootstrap READY, now check auth state
            break;

        default:
            // FAIL-SAFE: Unknown bootstrap state
            console.error('[BootstrapShell] Unknown bootstrap state:', bootstrap.state);
            return <BackendDownScreen context={bootstrap} />;
    }

    // ═══════════════════════════════════════════════════════════════
    // PHASE 2: Auth State Check (Session/identity verification)
    // Only reached if bootstrap.state === READY
    // ═══════════════════════════════════════════════════════════════

    switch (auth.state) {
        case AuthState.AUTH_BOOTING:
            return <AuthBootingScreen context={auth} />;

        case AuthState.AUTH_ERROR_TRANSPORT:
            return <AuthUnavailableScreen context={auth} />;

        case AuthState.AUTH_ERROR_SERVER:
            return <AuthServerErrorScreen context={auth} />;

        case AuthState.AUTH_UNAUTHORIZED:
            return <UnauthorizedScreen context={{ ...bootstrap, errorMessage: auth.errorMessage }} />;

        case AuthState.AUTH_FORBIDDEN:
            return <ForbiddenScreen context={{ ...bootstrap, errorMessage: auth.errorMessage }} />;

        case AuthState.AUTH_READY:
            // Auth READY, now check entitlement state
            break;

        default:
            // FAIL-SAFE: Unknown auth state
            console.error('[BootstrapShell] Unknown auth state:', auth.state);
            return <AuthUnavailableScreen context={auth} />;
    }

    // ═══════════════════════════════════════════════════════════════
    // PHASE 3: Entitlement State Check (Tier/subscription validation)
    // Only reached if bootstrap.state === READY AND auth.state === AUTH_READY
    // ═══════════════════════════════════════════════════════════════

    switch (entitlement.state) {
        case EntitlementState.ENT_BOOTING:
            return <EntitlementBootingScreen context={entitlement} />;

        case EntitlementState.ENT_ERROR_TRANSPORT:
            return <EntitlementUnavailableScreen context={entitlement} />;

        case EntitlementState.ENT_ERROR_SERVER:
            return <EntitlementServerErrorScreen context={entitlement} />;

        case EntitlementState.ENT_MALFORMED:
            return <EntitlementMalformedScreen context={entitlement} />;

        case EntitlementState.ENT_FORBIDDEN:
            return <ForbiddenScreen context={{ ...bootstrap, errorMessage: entitlement.errorMessage }} />;

        case EntitlementState.ENT_EXPIRED:
            // Future: subscription expired screen
            return <ForbiddenScreen context={{ ...bootstrap, errorMessage: 'Subscription expired' }} />;

        case EntitlementState.ENT_READY:
            // CRITICAL: FINAL GATE - App renders ONLY HERE
            // All three controllers are READY
            return <>{children}</>;

        default:
            // FAIL-SAFE: Unknown entitlement state
            console.error('[BootstrapShell] Unknown entitlement state:', entitlement.state);
            return <EntitlementUnavailableScreen context={entitlement} />;
    }
};
