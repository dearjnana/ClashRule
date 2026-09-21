"""检查规则格式、仓库内链接、中文注释和客户端规则优先级。"""
from pathlib import Path
import json, ipaddress, re, ast, tokenize
from urllib.parse import unquote
import yaml
from build import ROOT, BASE, read
from verify_party import validate_override

def main():
    files=[p for p in ROOT.rglob('*') if p.is_file() and not any(x in p.parts for x in ('.git','.test-work','__pycache__','reports'))]
    allowed={'DOMAIN','DOMAIN-SUFFIX','DOMAIN-KEYWORD','DOMAIN-REGEX','IP-CIDR','IP-CIDR6','PROCESS-NAME','PROCESS-PATH','GEOIP','DST-PORT'}
    rules_count=links=comments=0
    for p in files:
        if p.suffix not in ('.md','.py','.js','.yaml','.yml','.toml','.ini','.list','.txt','.json') and p.name not in ('.gitattributes','.gitignore'):continue
        text=p.read_text(encoding='utf-8')
        assert not text.startswith('\ufeff'),p
        assert b'\r' not in p.read_bytes(),p
        if p.suffix=='.list':
            seen=set()
            for line in text.splitlines():
                if not line.strip() or line.startswith('#'):continue
                a=line.split(',');assert a[0] in allowed,(p,line)
                assert line not in seen,(p,'重复条件',line)
                seen.add(line);rules_count+=1
                if a[0] in ('DOMAIN','DOMAIN-SUFFIX'):
                    assert not a[1].startswith('.') and '*' not in a[1],(p,line)
                if a[0] in ('IP-CIDR','IP-CIDR6'):ipaddress.ip_network(a[1])
                assert all(x not in ('DIRECT','PROXY','REJECT') for x in a[2:]),(p,line)
        if p.suffix in ('.yaml','.yml'):yaml.safe_load(text)
        if p.suffix=='.json':json.loads(text)
        if p.suffix=='.py':ast.parse(text)
        for m in re.finditer(re.escape(BASE)+r'([^\s,`\)\]"\'<>?#]+)',text):
            target=ROOT/unquote(m[1]);assert target.is_file(),(p,'无效仓库链接',m[1]);links+=1
        if p.suffix=='.md':
            for target in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)',text):
                if target.startswith(('https:','http:','#')):continue
                target=unquote(target.split('#')[0]);assert (p.parent/target).exists(),(p,'无效文档链接',target);links+=1
        if p.suffix=='.py':
            with tokenize.open(p) as f:
                for token in tokenize.generate_tokens(f.readline):
                    if token.type==tokenize.COMMENT:
                        assert re.search(r'[\u4e00-\u9fff]',token.string),(p,'非中文注释',token.string)
                        comments+=1
        elif p.suffix in ('.ini','.list','.yaml','.yml','.toml') or p.name in ('.gitattributes','.gitignore'):
            for line in text.splitlines():
                if line.lstrip().startswith(('#',';')):
                    assert re.search(r'[\u4e00-\u9fff]',line),(p,'非中文注释',line)
                    comments+=1
    party=yaml.safe_load(read('clients/clash-party/override.yaml'))
    validate_override(party)
    for removed in ('audit','archive','snippets','custom','profiles/legacy','docs/legacy'):
        assert not (ROOT/removed).exists(),removed
    print(json.dumps({'files':len(files),'rule_conditions':rules_count,'links_checked':links,'chinese_comments':comments,'result':'PASS'},ensure_ascii=False))

if __name__=='__main__':main()
