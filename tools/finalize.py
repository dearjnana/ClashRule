"""转换后恢复 Mihomo 原生策略组，输出一个新文件，不连接设备或下载资源。

用法：python tools/finalize.py 转换结果.yaml 可用配置.yaml
"""
from pathlib import Path
import argparse, os, tempfile
import yaml

def finalize(config):
    groups=config.pop('x-clashrule-native-groups',None)
    if not isinstance(groups,list) or not groups:
        raise ValueError('缺少原生策略组字段，请使用本仓库基础模板')
    names=[g['name'] for g in groups]
    if len(names)!=len(set(names)):raise ValueError('策略组名称重复')
    available=set(names)|{'DIRECT','REJECT','REJECT-DROP','PASS','COMPATIBLE'}|{p['name'] for p in config.get('proxies',[]) or []}
    for g in groups:
        if 'expected-status' in g:g['expected-status']=str(g['expected-status'])
        for name in g.get('proxies',[]):
            if name not in available:raise ValueError('找不到策略组成员：'+name)
    config['proxy-groups']=groups
    return config

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('output',type=Path);args=p.parse_args()
    if args.input.resolve()==args.output.resolve():p.error('输出路径不能与输入相同')
    if args.output.exists():p.error('输出文件已存在，请选择新文件名')
    config=finalize(yaml.safe_load(args.input.read_text(encoding='utf-8-sig')))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=args.output.parent,delete=False) as f:
        yaml.safe_dump(config,f,allow_unicode=True,sort_keys=False,width=120);temp=f.name
    try:os.replace(temp,args.output)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    print(f'已写入 {args.output}；导入前请使用 mihomo -t 验证。')

if __name__=='__main__':main()
