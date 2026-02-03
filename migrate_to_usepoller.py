#!/usr/bin/env python3
"""
Batch migration script: usePolledResource → usePoller
Converts all files systematically with pattern matching.
"""

import re
import sys
from pathlib import Path

def migrate_file(filepath: Path, critical_endpoints: set) -> tuple[bool, str]:
    """Migrate a single file from usePolledResource to usePoller."""
    
    try:
        content = filepath.read_text()
        original_content = content
        
        # Step 1: Replace import
        content = content.replace(
            "import { usePolledResource } from '../../hooks/usePolledResource';",
            "import { usePoller } from '../../hooks/usePoller';"
        )
        content = content.replace(
            "import { usePolledResource } from '../hooks/usePolledResource';",
            "import { usePoller } from '../hooks/usePoller';"
        )
        
        # Step 2: Find and replace usePolledResource calls
        # Pattern: const X = usePolledResource<T>((signal) => apiCall(signal, client), interval, deps);
        pattern = r'const\s+(\w+)\s*=\s*usePolledResource<([^>]+)>\(\(s(?:ignal)?\)\s*=>\s*([^,]+),\s*(\d+),\s*\[[^\]]*\]\);'
        
        def replace_call(match):
            var_name = match.group(1)
            type_param = match.group(2)
            api_call = match.group(3)
            interval = match.group(4)
            
            # Infer if critical based on endpoint name
            is_critical = any(ep in api_call.lower() for ep in ['getopsstate', 'gethealth', 'getstatus'])
            endpoint = f'/api/{var_name}'  # Simplified inference
            
            # Generate usePoller call
            return f'''const {{ data: {var_name}Data, error: {var_name}Error, refresh: {var_name}Refresh }} = usePoller<{type_param}>({{
        key: '{var_name}',
        endpoint: '{endpoint}',
        fetcher: () => {api_call.replace('(s', '(new AbortController().signal')},
        interval_ms: {interval},
        critical: {str(is_critical).lower()}
    }});
    const {var_name} = {{ data: {var_name}Data, error: {var_name}Error, loading: false, refresh: {var_name}Refresh }};'''
        
        content = re.sub(pattern, replace_call, content)
        
        # Step 3: Simpler pattern without type param
        pattern2 = r'const\s+(\w+)\s*=\s*usePolledResource\(\(s(?:ignal)?\)\s*=>\s*([^,]+),\s*(\d+)(?:,\s*\[[^\]]*\])?\);'
        
        def replace_call2(match):
            var_name = match.group(1)
            api_call = match.group(2)
            interval = match.group(3)
            
            is_critical = any(ep in api_call.lower() for ep in ['getopsstate', 'gethealth'])
            endpoint = f'/api/{var_name}'
            
            return f'''const {{ data: {var_name}Data, error: {var_name}Error, refresh: {var_name}Refresh }} = usePoller({{
        key: '{var_name}',
        endpoint: '{endpoint}',
        fetcher: () => {api_call.replace('(s', '(new AbortController().signal')},
        interval_ms: {interval},
        critical: {str(is_critical).lower()}
    }});
    const {var_name} = {{ data: {var_name}Data, error: {var_name}Error, loading: false, refresh: {var_name}Refresh }};'''
        
        content = re.sub(pattern2, replace_call2, content)
        
        if content != original_content:
            filepath.write_text(content)
            return True, f"✅ Migrated: {filepath.relative_to(Path.cwd())}"
        else:
            return False, f"⏭️  Skipped (no changes): {filepath.relative_to(Path.cwd())}"
            
    except Exception as e:
        return False, f"❌ Error in {filepath}: {e}"

def main():
    frontend_src = Path("frontend/src")
    
    # Find all files using usePolledResource
    files_to_migrate = []
    for pattern in ["**/*.tsx", "**/*.ts"]:
        for f in frontend_src.glob(pattern):
            content = f.read_text()
            if "usePolledResource" in content and "usePolledResource.ts" not in str(f):
                files_to_migrate.append(f)
    
    print(f"🔄 Found {len(files_to_migrate)} files to migrate\\n")
    
    critical_endpoints = {'ops_state', 'health', 'status'}
    
    migrated_count = 0
    for filepath in files_to_migrate:
        success, msg = migrate_file(filepath, critical_endpoints)
        print(msg)
        if success:
            migrated_count += 1
    
    print(f"\\n✅ Migration complete: {migrated_count}/{len(files_to_migrate)} files migrated")
    
    # Verify
    remaining = sum(1 for f in frontend_src.glob("**/*.tsx") 
                    if "usePolledResource" in f.read_text() and "usePolledResource.ts" not in str(f))
    print(f"📊 Remaining usePolledResource references: {remaining}")

if __name__ == "__main__":
    main()
