#!/usr/bin/env python3
"""Direct OpenRouter REST call — writes a hermes-style usage file for telemetry.
Requires OPENROUTER_API_KEY (see .env.example).
"""
import argparse, json, os, sys, time
import urllib.request

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True)
    ap.add_argument('--prompt', required=True)
    ap.add_argument('--usage-file', required=True)
    args = ap.parse_args()

    key = os.environ.get('OPENROUTER_API_KEY')
    if not key:
        sys.stderr.write('OPENROUTER_API_KEY is not set\n'); sys.exit(1)

    body = json.dumps({
        'model': args.model,
        'messages': [{'role': 'user', 'content': args.prompt}],
    }).encode('utf-8')

    req = urllib.request.Request(
        'https://openrouter.ai/api/v1/chat/completions',
        data=body,
        headers={
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://github.com/your-user/bonuslybench-starter',
            'X-Title': 'bonuslybench-starter',
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            data = json.loads(r.read().decode('utf-8'))
    except Exception as e:
        json.dump({'failed': True, 'error': str(e)}, open(args.usage_file, 'w'))
        print(f'API call failed: {e}')
        sys.exit(1)

    usage = data.get('usage', {})
    uf = {
        'failed': False,
        'provider': 'openrouter',
        'model': args.model,
        'prompt_tokens': usage.get('prompt_tokens', 0),
        'output_tokens': usage.get('completion_tokens', 0),
        'total_tokens': usage.get('total_tokens', 0),
        'cost_usd': usage.get('cost'),
    }
    content = data['choices'][0]['message']['content']
    json.dump(uf, open(args.usage_file, 'w'))
    print(content)

if __name__ == '__main__':
    main()
