#!/usr/bin/env node
/**
 * SAFE CODEMOD: usePolledResource → usePoller
 * 
 * Batch migration tool with pattern matching and critical endpoint detection.
 * Preserves variable names via destructuring for minimal code changes.
 */

const fs = require('fs');
const path = require('path');

// Critical endpoints that should mark critical: true
const CRITICAL_APIS = [
    'getopsstate',
    'gethealth',
    'getstatus',
    'getbalances'
];

// Known endpoint mappings (API function → endpoint path)
const ENDPOINT_MAP = {
    'getOpsState': '/api/ops/state',
    'getHealth': '/api/health',
    'getStatus': '/api/status',
    'getBalances': '/api/balances',
    'getOpsCapital': '/api/capital',
    'getStrategies': '/api/strategies',
    'getRisk': '/api/risk',
    'getLimits': '/api/limits',
    'getLogs': '/api/logs',
    'getFlags': '/api/flags',
    'getPortfolioSnapshot': '/api/portfolio/snapshot',
    'getPortfolioStructure': '/api/portfolio/structure',
    'getSystemEvents': '/api/events/system',
    'getActivity': '/api/activity',
    'getOrders': '/api/orders',
    'getAiProposals': '/api/ai/proposals',
    'getExchanges': '/api/exchanges',
    'getUserProfile': '/api/user/profile',
    'getFundOverview': '/api/fund/overview',
    'getFundPortfolio': '/api/fund/portfolio',
    'getFundStrategies': '/api/fund/strategies',
    'getAdminStats': '/api/admin/stats',
    'getUsers': '/api/admin/users',
    'getExchangeKeys': '/api/exchange/keys',
};

function deriveEndpoint(apiCall) {
    // Try to extract API function name
    const match = apiCall.match(/(\w+)\(/);
    if (match && ENDPOINT_MAP[match[1]]) {
        return ENDPOINT_MAP[match[1]];
    }
    return '/api/unknown';
}

function isCritical(apiCall) {
    const lower = apiCall.toLowerCase();
    return CRITICAL_APIS.some(api => lower.includes(api));
}

function migrateFile(filePath) {
    let content = fs.readFileSync(filePath, 'utf8');
    const original = content;
    let changes = 0;

    // Step 1: Replace import
    if (content.includes("from '../../hooks/usePolledResource'")) {
        content = content.replace(
            /import\s*{\s*usePolledResource\s*}\s*from\s*'\.\.\/\.\.\/hooks\/usePolledResource';/g,
            "import { usePoller } from '../../hooks/usePoller';"
        );
        changes++;
    }
    if (content.includes("from '../hooks/usePolledResource'")) {
        content = content.replace(
            /import\s*{\s*usePolledResource\s*}\s*from\s*'\.\.\/hooks\/usePolledResource';/g,
            "import { usePoller } from '../hooks/usePoller';"
        );
        changes++;
    }

    // Step 2: Transform usePolledResource calls
    // Pattern 1: const X = usePolledResource<Type>((signal) => apiCall(...), interval, [deps]);
    const pattern1 = /const\s+(\w+)\s*=\s*usePolledResource<([^>]+)>\(\(s(?:ignal)?\)\s*=>\s*([^)]+\([^)]*\)),\s*(\d+),\s*\[[^\]]*\]\);/g;
    content = content.replace(pattern1, (match, varName, typeParam, apiCall, interval) => {
        const endpoint = deriveEndpoint(apiCall);
        const critical = isCritical(apiCall);
        const key = `${varName}_${path.basename(filePath, '.tsx')}`;

        // Convert signal param to AbortController if needed
        const safeApiCall = apiCall.includes('(s')
            ? apiCall.replace(/\(s(?:ignal)?\b/, '(new AbortController().signal')
            : apiCall;

        changes++;
        return `const { data: ${varName}Data, error: ${varName}Error, refresh: ${varName}Refresh } = usePoller<${typeParam}>({\n` +
            `        key: '${key}',\n` +
            `        endpoint: '${endpoint}',\n` +
            `        fetcher: () => ${safeApiCall},\n` +
            `        interval_ms: ${interval},\n` +
            `        critical: ${critical}\n` +
            `    });\n` +
            `    const ${varName} = { data: ${varName}Data, error: ${varName}Error, loading: false, refresh: ${varName}Refresh };`;
    });

    // Pattern 2: const X = usePolledResource((signal) => ..., interval, [deps]) - no type param
    const pattern2 = /const\s+(\w+)\s*=\s*usePolledResource\(\(s(?:ignal)?\)\s*=>\s*([^)]+\([^)]*\)),\s*(\d+)(?:,\s*\[[^\]]*\])?\);/g;
    content = content.replace(pattern2, (match, varName, apiCall, interval) => {
        const endpoint = deriveEndpoint(apiCall);
        const critical = isCritical(apiCall);
        const key = `${varName}_${path.basename(filePath, '.tsx')}`;

        const safeApiCall = apiCall.includes('(s')
            ? apiCall.replace(/\(s(?:ignal)?\b/, '(new AbortController().signal')
            : apiCall;

        changes++;
        return `const { data: ${varName}Data, error: ${varName}Error, refresh: ${varName}Refresh } = usePoller({\n` +
            `        key: '${key}',\n` +
            `        endpoint: '${endpoint}',\n` +
            `        fetcher: () => ${safeApiCall},\n` +
            `        interval_ms: ${interval},\n` +
            `        critical: ${critical}\n` +
            `    });\n` +
            `    const ${varName} = { data: ${varName}Data, error: ${varName}Error, loading: false, refresh: ${varName}Refresh };`;
    });

    // Pattern 3: Destructured usage - const { data, error, loading, ... } = usePolledResource(...)
    const pattern3 = /const\s*{\s*([^}]+)\s*}\s*=\s*usePolledResource<([^>]+)>\(\(s(?:ignal)?\)\s*=>\s*([^)]+\([^)]*\)),\s*(\d+),\s*\[[^\]]*\]\);/g;
    content = content.replace(pattern3, (match, destructuredVars, typeParam, apiCall, interval) => {
        const endpoint = deriveEndpoint(apiCall);
        const critical = isCritical(apiCall);
        // Extract var names from destructured pattern
        const varList = destructuredVars.split(',').map(v => v.split(':')[0].trim());
        const hasData = varList.includes('data');
        const hasError = varList.includes('error');
        const hasRefresh = varList.includes('refresh');
        const hasLoading = varList.includes('loading');
        const hasLastUpdated = varList.includes('lastUpdated');

        const key = `${varList[0]}_${path.basename(filePath, '.tsx')}`;

        const safeApiCall = apiCall.includes('(s')
            ? apiCall.replace(/\(s(?:ignal)?\b/, '(new AbortController().signal')
            : apiCall;

        changes++;
        return `const { data, error, refresh } = usePoller<${typeParam}>({\n` +
            `        key: '${key}',\n` +
            `        endpoint: '${endpoint}',\n` +
            `        fetcher: () => ${safeApiCall},\n` +
            `        interval_ms: ${interval},\n` +
            `        critical: ${critical}\n` +
            `    });\n` +
            `    const loading = false;\n` +
            `    const lastUpdated = undefined;`;
    });

    if (content !== original) {
        fs.writeFileSync(filePath, content, 'utf8');
        return { success: true, changes, file: filePath };
    }

    return { success: false, changes: 0, file: filePath };
}

function findFilesToMigrate(dir, files = []) {
    const entries = fs.readdirSync(dir, { withFileTypes: true });

    for (const entry of entries) {
        const fullPath = path.join(dir, entry.name);

        if (entry.isDirectory() && !entry.name.includes('node_modules')) {
            findFilesToMigrate(fullPath, files);
        } else if (entry.isFile() && (entry.name.endsWith('.tsx') || entry.name.endsWith('.ts'))) {
            const content = fs.readFileSync(fullPath, 'utf8');
            if (content.includes('usePolledResource') && !fullPath.includes('usePolledResource.ts')) {
                files.push(fullPath);
            }
        }
    }

    return files;
}

// Main execution
const frontendSrc = path.join(process.cwd(), 'frontend/src');
console.log('🔄 Starting safe codemod migration...\n');

const filesToMigrate = findFilesToMigrate(frontendSrc);
console.log(`📋 Found ${filesToMigrate.length} files to migrate\n`);

let migratedCount = 0;
let failedCount = 0;

for (const file of filesToMigrate) {
    const result = migrateFile(file);
    if (result.success) {
        console.log(`✅ ${path.relative(process.cwd(), file)} (${result.changes} transformations)`);
        migratedCount++;
    } else {
        console.log(`⏭️  ${path.relative(process.cwd(), file)} (no changes)`);
        failedCount++;
    }
}

console.log(`\n✅ Migration complete: ${migratedCount}/${filesToMigrate.length} files migrated`);
console.log(`⏭️  ${failedCount} files skipped (already migrated or no patterns matched)`);

// Verify
const remaining = findFilesToMigrate(frontendSrc).filter(f => {
    const content = fs.readFileSync(f, 'utf8');
    return content.includes('usePolledResource(') || content.includes('usePolledResource<');
});

console.log(`\n📊 Remaining usePolledResource usage: ${remaining.length} files`);
if (remaining.length > 0) {
    console.log('\n⚠️  Files still using usePolledResource:');
    remaining.forEach(f => console.log(`   - ${path.relative(process.cwd(), f)}`));
}
