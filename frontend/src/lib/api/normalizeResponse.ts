/**
 * SMART DIAGNOSTICS - NORMALIZE RESPONSE
 * 
 * Eliminates "Unexpected token <" ambiguity forever.
 * Implements UI Constitution LAW 3 (Fail-Closed) with forensic error classification.
 * 
 * This wrapper:
 * - Detects non-JSON responses (HTML, nginx errors, login redirects)
 * - Provides typed errors with diagnostic hints
 * - Captures response snippets for forensic analysis
 * - Redacts secrets from error messages
 * 
 * Usage:
 *   const data = await fetchJSON<MyType>('/api/endpoint');
 */

/**
 * NON-JSON RESPONSE ERROR
 * Thrown when server returns non-JSON content (HTML, plain text, XML, etc.)
 */
export class NonJsonResponseError extends Error {
    name = 'NON_JSON_RESPONSE';
    http_status: number;
    content_type: string;
    endpoint: string;
    snippet: string;
    hint: string;

    constructor(
        http_status: number,
        content_type: string,
        endpoint: string,
        body_text: string
    ) {
        const snippet = body_text.slice(0, 200);
        const hint = classifyHint(body_text);

        super(`Received ${content_type} instead of JSON from ${endpoint} (HTTP ${http_status})`);

        this.http_status = http_status;
        this.content_type = content_type;
        this.endpoint = endpoint;
        this.snippet = snippet;
        this.hint = hint;
    }
}

/**
 * JSON PARSE ERROR
 * Thrown when response claims to be JSON but parsing fails
 */
export class JsonParseError extends Error {
    name = 'JSON_PARSE_ERROR';
    http_status: number;
    endpoint: string;
    snippet: string;

    constructor(
        http_status: number,
        endpoint: string,
        body_text: string,
        parseError: Error
    ) {
        const snippet = body_text.slice(0, 200);
        super(`Failed to parse JSON from ${endpoint}: ${parseError.message}`);

        this.http_status = http_status;
        this.endpoint = endpoint;
        this.snippet = snippet;
    }
}

/**
 * HTTP ERROR
 * Thrown for non-2xx status codes
 */
export class HttpError extends Error {
    name = 'HTTP_ERROR';
    http_status: number;
    endpoint: string;
    response_text?: string;

    constructor(
        http_status: number,
        endpoint: string,
        response_text?: string
    ) {
        super(`HTTP ${http_status} from ${endpoint}`);

        this.http_status = http_status;
        this.endpoint = endpoint;
        this.response_text = response_text ? response_text.slice(0, 200) : undefined;
    }
}

/**
 * HINT CLASSIFIER
 * Provides diagnostic hint based on response body content
 */
function classifyHint(body_text: string): string {
    const lower = body_text.toLowerCase();

    if (lower.includes('<html') || lower.includes('<!doctype')) {
        return 'HTML page (likely 404/error page or frontend route)';
    }

    if (lower.includes('nginx') || lower.includes('apache')) {
        return 'Proxy/web server error page';
    }

    if (lower.includes('login') || lower.includes('sign in') || lower.includes('authenticate')) {
        return 'Authentication redirect or login page';
    }

    if (lower.includes('404') || lower.includes('not found')) {
        return 'Endpoint not found (404)';
    }

    if (lower.includes('502') || lower.includes('bad gateway')) {
        return 'Bad gateway (502) - backend unreachable';
    }

    if (lower.includes('503') || lower.includes('service unavailable')) {
        return 'Service unavailable (503) - backend down';
    }

    if (lower.includes('500') || lower.includes('internal server error')) {
        return 'Internal server error (500)';
    }

    if (lower.includes('cors') || lower.includes('access-control')) {
        return 'CORS policy violation';
    }

    return 'Unknown non-JSON response';
}

/**
 * REDACT SECRETS
 * Remove sensitive values from text before displaying in UI
 */
function redactSecrets(text: string): string {
    // Redact patterns that look like tokens, API keys, passwords
    return text
        .replace(/Bearer\s+[A-Za-z0-9_\-\.]+/gi, 'Bearer [REDACTED]')
        .replace(/api[_-]?key["\s:=]+[A-Za-z0-9_\-\.]+/gi, 'api_key=[REDACTED]')
        .replace(/token["\s:=]+[A-Za-z0-9_\-\.]+/gi, 'token=[REDACTED]')
        .replace(/password["\s:=]+[^\s"]+/gi, 'password=[REDACTED]');
}

/**
 * FETCH JSON (SMART WRAPPER)
 * 
 * Fetches from endpoint and intelligently handles response:
 * - Checks content-type
 * - Parses JSON safely
 * - Throws typed errors with diagnostics
 * - Redacts secrets from error messages
 * - Emits NET events to eventBus (with noise filter)
 * 
 * @param endpoint - API endpoint (absolute or relative URL)
 * @param options - Fetch options (method, headers, body, signal)
 * @returns Parsed JSON response
 * @throws NonJsonResponseError, JsonParseError, HttpError
 */

// Noise filter state (in-memory map)
// Keyed by endpoint, tracks last emitted status to suppress repeated 200 OK
interface NoiseFilterState {
    last_status: number;
    last_emit_ts: number;
    first_good_emitted: boolean;
}

const noiseFilterMap = new Map<string, NoiseFilterState>();

export async function fetchJSON<T = any>(
    endpoint: string,
    options?: RequestInit
): Promise<T> {
    const startTime = Date.now();

    // Prepend API base URL if endpoint is relative
    const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080';
    const fullUrl = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;

    const response = await fetch(fullUrl, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options?.headers,
        },
    });

    const latency_ms = Date.now() - startTime;
    const content_type = response.headers.get('content-type') || 'unknown';
    const http_status = response.status;

    // Read body text (limit to 600 chars to avoid memory issues)
    const body_text = await response.text();
    const limited_text = body_text.slice(0, 600);
    const redacted_text = redactSecrets(limited_text);

    // Generate request ID (simple)
    const req_id = `req_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

    // --- NOISE FILTER + EVENT EMISSION ---
    // Only emit NET events if:
    // 1. First successful 200 for this endpoint (baseline)
    // 2. Status changed from last emitted status
    // 3. Status != 200 (errors always emit)

    const filterState = noiseFilterMap.get(endpoint);
    let shouldEmit = false;
    let emitReason = '';

    if (!filterState) {
        // First call for this endpoint
        if (http_status === 200) {
            shouldEmit = true;
            emitReason = 'first-good';
            noiseFilterMap.set(endpoint, {
                last_status: 200,
                last_emit_ts: Date.now(),
                first_good_emitted: true,
            });
        } else {
            shouldEmit = true;
            emitReason = 'first-error';
            noiseFilterMap.set(endpoint, {
                last_status: http_status,
                last_emit_ts: Date.now(),
                first_good_emitted: false,
            });
        }
    } else {
        // Subsequent call
        if (http_status !== 200) {
            // Always emit errors
            shouldEmit = true;
            emitReason = 'error';
            filterState.last_status = http_status;
            filterState.last_emit_ts = Date.now();
        } else if (filterState.last_status !== 200) {
            // Status recovered (error -> 200)
            shouldEmit = true;
            emitReason = 'recovered';
            filterState.last_status = 200;
            filterState.last_emit_ts = Date.now();
        } else if (!filterState.first_good_emitted) {
            // First 200 after previous non-200 calls
            shouldEmit = true;
            emitReason = 'first-good';
            filterState.first_good_emitted = true;
            filterState.last_emit_ts = Date.now();
        }
        // else: repeated 200 OK -> suppress (no emit)
    }

    // Lazy-load eventBus to avoid circular dependency
    const emitNetEvent = (error_type?: string, hint?: string, snippet?: string) => {
        if (!shouldEmit) return;

        // Dynamically import to avoid potential issues
        import('../runtime/eventBus').then(({ eventBus }) => {
            const fingerprint = `${endpoint}|${http_status}|${error_type || 'OK'}`;

            eventBus.emit({
                ts: Date.now(),
                kind: 'NET',
                sev: http_status >= 500 ? 'CRITICAL' : http_status >= 400 ? 'HIGH' : 'LOW',
                name: emitReason === 'recovered' ? 'NET_RECOVERED' : error_type ? 'NET_ERROR' : 'NET_RESPONSE',
                endpoint,
                http_status,
                latency_ms,
                content_type,
                error_type,
                hint,
                snippet: snippet ? snippet.slice(0, 200) : undefined,
                req_id,
                fingerprint,
                details: { emit_reason: emitReason },
            });
        }).catch(err => {
            console.error('[fetchJSON] Failed to emit NET event:', err);
        });
    };

    // Check if response is JSON
    if (!content_type.includes('application/json') && !content_type.includes('json')) {
        const hint = classifyHint(redacted_text);
        emitNetEvent('NonJsonResponseError', hint, redacted_text);

        throw new NonJsonResponseError(
            http_status,
            content_type,
            endpoint,
            redacted_text
        );
    }

    // Check HTTP status
    if (!response.ok) {
        emitNetEvent('HttpError', undefined, redacted_text);
        throw new HttpError(http_status, endpoint, redacted_text);
    }

    // Parse JSON safely
    try {
        const data = JSON.parse(body_text) as T;
        emitNetEvent(); // Success (if should emit based on noise filter)
        return data;
    } catch (parseError: any) {
        emitNetEvent('JsonParseError', parseError.message, redacted_text);

        throw new JsonParseError(
            http_status,
            endpoint,
            redacted_text,
            parseError
        );
    }
}

/**
 * TYPE GUARDS
 */
export function isNonJsonResponseError(error: unknown): error is NonJsonResponseError {
    return error instanceof NonJsonResponseError;
}

export function isJsonParseError(error: unknown): error is JsonParseError {
    return error instanceof JsonParseError;
}

export function isHttpError(error: unknown): error is HttpError {
    return error instanceof HttpError;
}
