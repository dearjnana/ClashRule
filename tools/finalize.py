"""Restore native Mihomo groups after SubConverter; write a NEW local YAML only.

python tools/finalize.py converted.yaml ready.yaml
Does not connect to routers, reload services or download resources.
"""
from pathlib import Path
import argparse, os, tempfile
import yaml

def finalize(config):
    groups=config.pop('x-clashrule-native-groups',None)
    if not isinstance(groups,list) or not groups:
        raise ValueError('Missing x-clashrule-native-groups: use this repository base template')
    names=[g['name'] for g in groups]
    if len(names)!=len(set(names)):raise ValueError('Duplicate group name')
    available=set(names)|{'DIRECT','REJECT','REJECT-DROP','PASS','COMPATIBLE'}|{p['name'] for p in config.get('proxies',[]) or []}
    for g in groups:
        if 'expected-status' in g:g['expected-status']=str(g['expected-status'])
        for name in g.get('proxies',[]):
            if name not in available:raise ValueError('Unknown member: '+name)
    config['proxy-groups']=groups
    return config

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('output',type=Path);args=p.parse_args()
    if args.input.resolve()==args.output.resolve():p.error('Output must differ from input; keep the original for rollback')
    if args.output.exists():p.error('Output already exists; choose a new filename')
    config=finalize(yaml.safe_load(args.input.read_text(encoding='utf-8-sig')))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=args.output.parent,delete=False) as f:
        yaml.safe_dump(config,f,allow_unicode=True,sort_keys=False,width=120);temp=f.name
    try:os.replace(temp,args.output)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    print(f'Wrote {args.output}; validate with mihomo -t before importing into OpenClash.')

if __name__=='__main__':main()
