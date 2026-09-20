"""Offline routing, source-integrity and native-provider equivalence checks."""
from pathlib import Path
from collections import defaultdict
import hashlib, ipaddress, json, re
import yaml
from build import GEMINI_ADD

ROOT=Path(__file__).resolve().parents[1]
def read(path):return (ROOT/path).read_text(encoding='utf-8-sig')
def rules(path):return [s.strip() for s in read(path).splitlines() if s.strip() and not s.startswith('#')]

class Router:
    """Index predicates independently from the builder; compare ordered policy chains."""
    def __init__(self,rows):
        self.exact=defaultdict(list);self.suffix=defaultdict(list);self.words=[];self.regex=[];self.nets=defaultdict(list)
        for index,(condition,policy) in enumerate(rows):
            a=condition.split(',');value=(index,policy)
            if a[0]=='DOMAIN':self.exact[a[1]].append(value)
            elif a[0]=='DOMAIN-SUFFIX':self.suffix[a[1]].append(value)
            elif a[0]=='DOMAIN-KEYWORD':self.words.append((a[1],value))
            elif a[0]=='DOMAIN-REGEX':self.regex.append((re.compile(a[1]),value))
            elif a[0] in ('IP-CIDR','IP-CIDR6'):
                n=ipaddress.ip_network(a[1]);self.nets[(n.version,n.prefixlen,int(n.network_address))].append(value)
    @staticmethod
    def policies(matches):return tuple(dict.fromkeys(p for _,p in sorted(matches)))
    def domain(self,host):
        found=list(self.exact.get(host,[]));parts=host.split('.')
        for k in range(len(parts)):found+=self.suffix.get('.'.join(parts[k:]),[])
        found += [value for word,value in self.words if word in host]
        found += [value for pattern,value in self.regex if pattern.search(host)]
        return self.policies(found)
    def ip(self,address):
        n=ipaddress.ip_address(address);bits=n.max_prefixlen;integer=int(n);found=[]
        for length in range(bits+1):
            start=(integer>>(bits-length))<<(bits-length)
            found += self.nets.get((n.version,length,start),[])
        return self.policies(found)

def main():
    manifest=json.loads(read('audit/original/manifest.json'))
    for d in manifest['downloads']:
        assert hashlib.sha256((ROOT/d['path']).read_bytes()).hexdigest()==d['sha256'],d['path']
    meta=json.loads(read('audit/original/source-metadata.json'))
    assert hashlib.sha256((ROOT/'audit/original/MyRuleClash_Plus_V1.ini').read_bytes()).hexdigest()==meta['sha256']
    reviews=[json.loads(s) for s in read('audit/rule-review.jsonl').splitlines()]
    order=json.loads(read('audit/entry-order.json'));source=defaultdict(list)
    for r in reviews:source[r['source_name']]+=r['normalized']
    source['Gemini.list']+=GEMINI_ADD
    source['Telegram.list']+=['IP-CIDR,185.76.151.0/24,no-resolve','IP-CIDR6,2001:b28:f238::/48,no-resolve']
    before=[];after=[];domains=set();addresses=set()
    wildcard_cases=0
    for r in reviews:
        if r['original'].startswith('DOMAIN-SUFFIX,') and '*' in r['original']:
            host=r['original'].split(',')[1].replace('*','audit1')
            expression=re.compile(r['normalized'][0].split(',',1)[1])
            assert expression.search(host) and expression.search('child.'+host)
            assert not expression.search(host+'.invalid')
            domains.update((host,'child.'+host,host+'.invalid'));wildcard_cases+=3
    for e in order:
        if 'inline' in e:
            before.append((e['inline'],e['target']));after.append((e['inline'],e['target']));continue
        name=Path(e['path']).name
        if name=='IPAttribution.list':name='rule-provider.yaml'
        before += [(r,e['target']) for r in source[name]]
        rs=rules(e['path']);assert len(rs)==len(set(rs)),e['path']
        after += [(r,e['target']) for r in rs]
    for r,_ in before:
        a=r.split(',')
        if a[0] in ('DOMAIN','DOMAIN-SUFFIX'):
            assert not a[1].startswith('.')
            domains.update((a[1],'audit-sub.'+a[1],'unrelated-'+a[1],a[1]+'.invalid'))
        elif a[0] in ('IP-CIDR','IP-CIDR6'):
            n=ipaddress.ip_network(a[1]);start=int(n.network_address);end=int(n.broadcast_address)
            addresses.update((n.version,x) for x in (start-1,start,(start+end)//2,end,end+1) if 0<=x<2**n.max_prefixlen)
    pre,post=Router(before),Router(after)
    for d in domains:assert pre.domain(d)==post.domain(d),('Domain policy changed by dedup',d,pre.domain(d),post.domain(d))
    for version,integer in addresses:
        ip=str((ipaddress.IPv4Address if version==4 else ipaddress.IPv6Address)(integer))
        assert pre.ip(ip)==post.ip(ip),('IP policy changed by dedup',ip)
    before_ip=defaultdict(list);after_ip=defaultdict(list)
    for rows,out in [(before,before_ip),(after,after_ip)]:
        for rule,policy in rows:
            a=rule.split(',')
            if a[0] in ('IP-CIDR','IP-CIDR6'):out[(policy,a[0],tuple(a[2:]))].append(ipaddress.ip_network(a[1]))
    assert before_ip.keys()==after_ip.keys()
    for k in before_ip:assert list(ipaddress.collapse_addresses(before_ip[k]))==list(ipaddress.collapse_addresses(after_ip[k])),k
    cn=[ipaddress.ip_network(r.split(',')[1]) for name in ('ChinaIp','ChinaCompanyIp') for r in rules('rules/network/'+name+'.list')]
    assert list(ipaddress.collapse_addresses(cn))==[ipaddress.ip_network(s) for s in rules('providers/ChinaIP.txt')]
    gfw=rules('rules/network/ProxyGFWlist.list')
    assert all(s.startswith(('DOMAIN-SUFFIX,','DOMAIN-REGEX,')) for s in gfw)
    assert ['+.'+s.split(',')[1] for s in gfw if s.startswith('DOMAIN-SUFFIX,')]==rules('providers/ProxyGFW.txt')
    template=yaml.safe_load(read('templates/GeneralClashConfig.yaml'));groups=template['x-clashrule-native-groups'];names={g['name'] for g in groups}
    assert len(names)==len(groups)==80
    edges={g['name']:[n for n in g.get('proxies',[]) if n in names] for g in groups}
    def visit(name,stack):
        assert name not in stack,('Group cycle',name)
        for child in edges[name]:visit(child,stack|{name})
    for name in names:visit(name,set())
    for g in groups:
        assert all(p in names|{'DIRECT','REJECT'} for p in g.get('proxies',[])),g['name']
        if 'filter' in g:
            re.compile(g['filter']);assert g['empty-fallback']=='REJECT'
            assert 'REJECT' not in g.get('proxies',[])
    mesl=next(g for g in groups if g['name']=='🇺🇸 Gemini MESL美国')
    for good in ('[MESL]🇺🇸 美国 01','[MESL]US-Los Angeles','[MESL]USA 02'):assert re.search(mesl['filter'],good),good
    for bad in ('[MESL]🇦🇲 亚美尼亚 01','[MESL]Australia','[MESL]Russia','[MESL]Cyprus','[OTHER]🇺🇸 美国','[MESL]剩余流量 美国'):assert not re.search(mesl['filter'],bad),bad
    fixtures={'gemini.google.com':'🎐 Gemini','gemini.google':'🎐 Gemini','gemini.gstatic.com':'🎐 Gemini','aistudio.google.com':'🎐 Gemini','alkalicore-pa.clients6.google.com':'🎐 Gemini','robinfrontend-pa.googleapis.com':'🎐 Gemini','webchannel-robinfrontend-pa.googleapis.com':'🎐 Gemini','generativelanguage.googleapis.com':'🎐 Gemini','mtalk.google.com':'📢 谷歌FCM','apis.google.com':'✨ Google生态','oaistatic.com':'💬 OpenAi','cdn.oaistatic.com':'💬 OpenAi','cloudflare.com':'👨‍💻 GitHub','lcs-cops.adobe.io':'🎯 全球直连','other.adobe.io':'🛑 广告拦截'}
    for host,policy in fixtures.items():assert post.domain(host)[0]==policy,(host,post.domain(host))
    for host in ('fake-colab.example','developerprofiles.evil.invalid','cloudflare.com.attacker.invalid'):
        assert '🎐 Gemini' not in post.domain(host),host
    base=json.loads(read('audit/build-summary.json'))['base_url']
    for path in ['profiles/MyRuleClash_Plus_V1.optimized.ini','profiles/MyRuleClash_Plus_V1.expanded.ini']:
        for line in read(path).splitlines():
            if line.startswith(('ruleset=','clash_rule_base=')) and 'https://' in line:
                url=line[line.index('https://'):];assert url.startswith(base),url
                assert (ROOT/url[len(base):]).is_file(),url
    result={'source_downloads_sha256_verified':len(manifest['downloads']),'source_ini_sha256_verified':True,'source_rule_rows_reviewed':len(reviews),'domain_routing_cases':len(domains),'ip_boundary_routing_cases':len(addresses),'wildcard_regression_cases':wildcard_cases,'service_regression_cases':len(fixtures)+3,'policy_and_no_resolve_ip_unions':'identical after deduplication','native_provider_coverage':'identical','groups':len(groups),'group_graph':'no cycles or missing members','result':'PASS'}
    (ROOT/'audit/verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
