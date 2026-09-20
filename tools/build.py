"""Build the reviewed local rules from the immutable upstream snapshot.

No network requests, credentials, or modifications to a running router.
Python 3.10+; pip install -r tools/requirements.txt
"""
from pathlib import Path
from collections import Counter, defaultdict
import argparse, copy, hashlib, ipaddress, json, re
import yaml

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'audit/original'
BASE = 'https://raw.githubusercontent.com/dearjnana/ClashRule/refs/heads/main/'
HEALTH = 'https://cp.cloudflare.com/generate_204'
GEMINI = '🎐 Gemini'
GEMINI_MESL = '🇺🇸 Gemini MESL美国'
REGIONS = {
    '香港': r'🇭🇰|香港|hong\s*kong|\bhk\b|沪港|深港|广港',
    '台湾': r'🇹🇼|台湾|台灣|台北|台中|新北|高雄|桃园|taiwan|taipei|kaohsiung|taichung|taoyuan|\btw\b',
    '日本': r'🇯🇵|日本|东京|東京|大阪|埼玉|名古屋|福冈|福岡|京都|神户|japan|tokyo|osaka|nagoya|fukuoka|kyoto|kobe|\bjp\b|沪日|深日|泉日|川日',
    '韩国': r'🇰🇷|韩国|韓國|首尔|首爾|釜山|仁川|大邱|光州|大田|蔚山|korea|seoul|busan|incheon|daegu|gwangju|daejeon|ulsan|\bkr\b',
    '新加坡': r'🇸🇬|新加坡|狮城|獅城|singapore|\bsg\b',
    '美国': r'🇺🇸|美国|美國|united\s*states|\busa?\b|洛杉矶|洛杉磯|纽约|紐約|西雅图|西雅圖|圣何塞|硅谷|旧金山|華盛頓|华盛顿',
}
BAD = r'失联|超时|官网|售后|剩余|到期|自助|主流|套餐|过期'
GEMINI_ADD = [
    'DOMAIN-SUFFIX,gemini.google.com','DOMAIN-SUFFIX,gemini.google',
    'DOMAIN-SUFFIX,gemini.gstatic.com','DOMAIN-SUFFIX,bard.google.com',
    'DOMAIN-SUFFIX,aistudio.google.com','DOMAIN-SUFFIX,makersuite.google.com',
    'DOMAIN-SUFFIX,ai.studio','DOMAIN-SUFFIX,generativeai.google',
    'DOMAIN,ai.google.dev','DOMAIN,alkalicore-pa.clients6.google.com',
    'DOMAIN,alkalimakersuite-pa.clients6.google.com',
    'DOMAIN,webchannel-alkalimakersuite-pa.clients6.google.com',
    'DOMAIN-SUFFIX,generativelanguage.googleapis.com',
    'DOMAIN,robinfrontend-pa.googleapis.com','DOMAIN,webchannel-robinfrontend-pa.googleapis.com',
    'DOMAIN-SUFFIX,proactivebackend-pa.googleapis.com','DOMAIN,geller-pa.googleapis.com',
    'DOMAIN,geminiweb-pa.googleapis.com',
]
CATEGORIES = {
    'block': ['Adobe_DIRECT.list','Adobe_REJECT.list','BanProgramAD.list'],
    'media': ['pixiv.list','iwara.list','YouTube.list','Netflix.list','DisneyPlus.list','Bahamut.list','BilibiliHMT.list','Bilibili.list','ChinaMedia.list','NetEaseMusic.list'],
    'ai': ['AI.list','Gemini.list'],
    'services': ['GitHub_Cloudflare_Docker.list','CC.list','Samsung.list','Bing.list','OneDrive.list','Microsoft.list','Apple.list'],
    'google': ['GoogleFCM.list','GoogleCN.list','Google.list','GoogleEarth.list'],
    'privacy': ['rule-provider.yaml'],
    'messaging': ['Telegram.list'],
    'games': ['SteamCN.list','Epic.list','Origin.list','Sony.list','Steam.list','Nintendo.list'],
    'network': ['AccelerateDirectSites.list','LocalAreaNetwork.list','UnBan.list','ProxyGFWlist.list','ProxyLite.list','ChinaDomain.list','ChinaIp.list','ChinaCompanyIp.list','Download.list'],
}

def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8', newline='\n')

def dump(path, value):
    write(path, json.dumps(value, ensure_ascii=False, indent=2)+'\n')

def destination(name):
    category=next(k for k,v in CATEGORIES.items() if name in v)
    name='IPAttribution.list' if name=='rule-provider.yaml' else name
    return f'rules/{category}/{name}'

def filter_for(region=None, brand=None):
    s='(?i)^'
    if brand: s+='(?=.*'+re.escape(brand)+')'
    if region: s+='(?=.*(?:'+REGIONS[region]+'))'
    s+='(?!.*(?:'+BAD+'))'
    if region=='美国': s+='(?!.*(?:亚美尼亚|亞美尼亞|armenia|russia|australia|belarus|cyprus))'
    return s+'.*$'

def covers(a, b):
    """Does a condition unconditionally cover b? Options and policy checked by caller."""
    if a==b: return True
    x,y=a.split(','),b.split(',')
    if x[0]=='DOMAIN-SUFFIX' and y[0] in ('DOMAIN','DOMAIN-SUFFIX'):
        return y[1]==x[1] or y[1].endswith('.'+x[1])
    if x[0]=='DOMAIN-KEYWORD' and y[0] in ('DOMAIN','DOMAIN-SUFFIX'):
        return x[1] in y[1]
    if x[0] in ('IP-CIDR','IP-CIDR6') and x[0]==y[0] and x[2:]==y[2:]:
        return ipaddress.ip_network(y[1]).subnet_of(ipaddress.ip_network(x[1]))
    return False

def normalize(record):
    raw=record['original'];a=[v.strip() for v in raw.split(',')];name=record['source_name'];notes=record['notes']
    if a[0]=='URL-REGEX':
        notes.append('Mihomo 不支持 URL-REGEX；原转换器也会丢弃，保留于快照');return None
    if a[0]=='DOMAIN-SUFFIX' and '*' in a[1]:
        pattern=re.escape(a[1]).replace(r'\*',r'[^.]*')
        pattern=pattern.replace(r'[^.]*\.',r'[^.]+\.') if a[1].startswith('*.') else pattern
        notes.append('后缀规则中星号不是有效的域名后缀；改为锚定的域名正则，保留子域通配意图')
        return ['DOMAIN-REGEX,(?i)(^|\\.)'+pattern+'$']
    if a[0] in ('IP-CIDR','IP-CIDR6'):
        canonical=str(ipaddress.ip_network(a[1],strict=False))
        if canonical!=a[1]:notes.append('CIDR 去除主机位，网络覆盖范围不变')
        a[1]=canonical
    if name=='rule-provider.yaml' and any(v in ('DIRECT','REJECT') for v in a[2:]):
        notes.append('移除混入规则条件的策略字段，仍由 IP 归属地组控制；恢复源 no-resolve')
        a=[v for i,v in enumerate(a) if i<2 or v not in ('DIRECT','REJECT')]
    if name=='AI.list':
        if raw in ('DOMAIN,mtalk.google.com','DOMAIN,cloudflare.com'):
            notes.append('移除错误抢占，分别由 GoogleFCM / GitHub Cloudflare 规则承接');return None
        if raw=='DOMAIN,.oaistatic.com':
            a=['DOMAIN-SUFFIX','oaistatic.com'];notes.append('修正精确域名前导点')
        if raw=='IP-CIDR,17.253.4.125/32,no-resolve':
            notes.append('ARIN 归属 APPLE-WWNET，移除无依据的 Grok IP 规则，交由 Apple 规则');return None
    if name=='Gemini.list':
        replacements={
            'DOMAIN-KEYWORD,colab':['DOMAIN-SUFFIX,colab.research.google.com','DOMAIN-SUFFIX,colab.google','DOMAIN-SUFFIX,colab.googleusercontent.com'],
            'DOMAIN-KEYWORD,developerprofiles':['DOMAIN,developerprofiles-pa.googleapis.com'],
            'DOMAIN-KEYWORD,generativelanguage':['DOMAIN-SUFFIX,generativelanguage.googleapis.com'],
        }
        if raw in replacements:
            notes.append('宽泛关键词收窄到 Google 实际服务域名');return replacements[raw]
        if raw=='DOMAIN-SUFFIX,apis.google.com':
            notes.append('共享登录/JS API 不专属于 Gemini；交由通用 Google 组');return None
    if name=='CC.list' and a[0]=='DOMAIN-KEYWORD' and '.' in a[1]:
        a[0]='DOMAIN-SUFFIX';notes.append('完整域名使用后缀，避免相似域名误匹配')
    if a[0]=='PROCESS-NAME':notes.append('仅匹配运行 Mihomo 本机进程，无法识别 LAN 客户端进程；保留桌面复用')
    return [','.join(a)]

def load_groups(original):
    groups=[]
    for line in original.splitlines():
        if not line.startswith('custom_proxy_group='):continue
        f=line.split('=',1)[1].split('`');name,kind=f[:2];parts=f[2:]
        if kind in ('url-test','fallback'):parts=parts[:-2]
        literals=[v[2:] for v in parts if v.startswith('[]')]
        patterns=[v for v in parts if not v.startswith('[]')]
        g={'name':name,'type':kind}
        if patterns:
            region=next((r for r in REGIONS if name.endswith('-'+r) or name.endswith(r+'节点')),None)
            brand=next((b for b in ['良心云','赚钱','宝可梦','LD士多','MESL'] if b in name),None)
            g.update({'include-all':True,'filter':filter_for(region,brand),'empty-fallback':'REJECT'})
            literals=[x for x in literals if x!='REJECT']
        if literals:g['proxies']=list(dict.fromkeys(literals))
        if kind in ('url-test','fallback'):
            g.update({'url':HEALTH,'interval':300,'timeout':5000,'lazy':True,'expected-status':'204'})
            if kind=='url-test':g['tolerance']=150
        groups.append(g)
    gemini=next(g for g in groups if g['name']==GEMINI)
    gemini['proxies'].insert(0,GEMINI_MESL)
    groups.append({'name':GEMINI_MESL,'type':'select','include-all':True,'filter':filter_for('美国','MESL'),'empty-fallback':'REJECT','default-selected':'[MESL]🇺🇸 美国 01'})
    return groups

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--base-url',default=BASE);args=parser.parse_args()
    base=args.base_url.rstrip('/')+'/'
    manifest=json.loads((RAW/'manifest.json').read_text(encoding='utf-8'))
    original=(RAW/'MyRuleClash_Plus_V1.ini').read_text(encoding='utf-8-sig')
    downloads={d['url']:d for d in manifest['downloads']}
    for d in downloads.values():
        assert hashlib.sha256((ROOT/d['path']).read_bytes()).hexdigest()==d['sha256'],d['path']
    entries=[];records=[];files={};stats={};rid=0
    for e in manifest['entries']:
        if e['kind']!='ruleset':continue
        if e['ref'].startswith('[]'):
            entries.append({'target':e['target'],'inline':e['ref'][2:]});continue
        url=re.search(r'https?://\S+',e['ref'])[0];d=downloads[url];path=ROOT/d['path']
        name=path.name.split('-',1)[1];dest=destination(name)
        lines=path.read_text(encoding='utf-8-sig').splitlines();items=[]
        for no,line in enumerate(lines,1):
            s=line.strip()
            if not s or s.startswith(('#',';')) or s=='payload:':continue
            if name=='rule-provider.yaml':s=s.removeprefix('- ').strip().strip('"\'')
            rid+=1;rec={'id':rid,'source':d['path'],'source_name':name,'line':no,'original':s,'target':e['target'],'notes':[],'normalized':[],'status':'retained'}
            normalized=normalize(rec);rec['normalized']=normalized or []
            if not normalized:rec['status']='removed-unsupported-or-corrected'
            for r in normalized or []:items.append({'rule':r,'ids':[rid]})
            records.append(rec)
        if name=='Gemini.list':
            for r in GEMINI_ADD:items.append({'rule':r,'ids':[]})
        if name=='Telegram.list':
            for r in ['IP-CIDR,185.76.151.0/24,no-resolve','IP-CIDR6,2001:b28:f238::/48,no-resolve']:items.append({'rule':r,'ids':[]})
        # Within one policy file, any broader domain condition has identical action.
        # Remove exact duplicates and covered subdomains without moving rules across files.
        unique=[];seen={}
        for x in items:
            if x['rule'] in seen:
                for i in x['ids']:
                    records[i-1]['notes'].append('同文件完全重复：'+x['rule'])
                    records[i-1]['status']='deduplicated-within-file'
                seen[x['rule']]['ids']+=x['ids'];continue
            seen[x['rule']]=x;unique.append(x)
        suffix={x['rule'].split(',')[1]:x for x in unique if x['rule'].startswith('DOMAIN-SUFFIX,')}
        kept=[]
        for x in unique:
            a=x['rule'].split(',');parent=None
            if a[0] in ('DOMAIN','DOMAIN-SUFFIX'):
                labels=a[1].split('.')
                for k in range(0 if a[0]=='DOMAIN' else 1,len(labels)):
                    v='.'.join(labels[k:])
                    if v in suffix:parent=suffix[v];break
            if parent:
                for i in x['ids']:records[i-1]['notes'].append('同文件同策略的更宽后缀覆盖：'+parent['rule']);records[i-1]['status']='deduplicated-within-file'
            else:kept.append(x)
        files[dest]={'items':kept,'source_name':name,'url':url,'comments':[l for l in lines if l.lstrip().startswith('#')]}
        stats[dest]={'source':d['path'],'before':sum(r['source_name']==name for r in records),'after_local':len(kept)}
        entries.append({'target':e['target'],'path':dest})
    # Telegram additions now live in Telegram.list.
    entries=[e for e in entries if not(e.get('inline','').startswith(('IP-CIDR,185.76.151.0/24','IP-CIDR6,2001:b28:f238::/48')))]
    # Gemini and FCM must precede general AI and Google policies.
    lead=[e for e in entries if e.get('path','').endswith(('/Gemini.list','/GoogleFCM.list'))]
    entries=[e for e in entries if e not in lead]
    at=next(i for i,e in enumerate(entries) if e.get('path','').endswith('/AI.list'));entries[at:at]=lead
    # Existing root files belong to legacy profiles; leave them byte-for-byte intact.
    # Cross-file optimization only removes a condition already covered by the SAME
    # policy. Different policies remain because unsupported UDP can fall through.
    seen_rules=defaultdict(set);seen_suffix=defaultdict(dict);seen_keywords=defaultdict(list);seen_ips=defaultdict(dict)
    for e in entries:
        if 'path' not in e:continue
        f=files[e['path']];policy=e['target'];out=[]
        for x in f['items']:
            r=x['rule'];a=r.split(',');cover=None
            if r in seen_rules[policy]:cover=r
            elif a[0] in ('DOMAIN','DOMAIN-SUFFIX'):
                labels=a[1].split('.')
                cover=next((seen_suffix[policy]['.'.join(labels[k:])] for k in range(len(labels)) if '.'.join(labels[k:]) in seen_suffix[policy]),None)
                if not cover:cover=next((v for word,v in seen_keywords[policy] if word in a[1]),None)
            elif a[0] in ('IP-CIDR','IP-CIDR6'):
                net=ipaddress.ip_network(a[1]);opts=tuple(a[2:])
                # At most 33/129 prefix lookups instead of comparing every preceding CIDR.
                for length in range(net.prefixlen,-1,-1):
                    parent=net.supernet(new_prefix=length) if length<net.prefixlen else net
                    cover=seen_ips[policy].get((parent,opts))
                    if cover:break
            if cover:
                for i in x['ids']:records[i-1]['notes'].append('V1 顺序中被同策略较早规则覆盖：'+cover);records[i-1]['status']='deduplicated-cross-file'
                continue
            out.append(x);seen_rules[policy].add(r)
            if a[0]=='DOMAIN-SUFFIX':seen_suffix[policy][a[1]]=r
            elif a[0]=='DOMAIN-KEYWORD':seen_keywords[policy].append((a[1],r))
            elif a[0] in ('IP-CIDR','IP-CIDR6'):seen_ips[policy][(ipaddress.ip_network(a[1]),tuple(a[2:]))]=r
        f['items']=out;stats[e['path']]['after']=len(out)
    for dest,f in files.items():
        header=['# '+f['source_name']+' — reviewed local copy, 2026-09-20','# Source: '+f['url'],'# Policy and priority: profiles/MyRuleClash_Plus_V1.optimized.ini','# Cross-file deduplication is specific to this INI order.','# Rules: '+str(len(f['items']))]
        # Preserve original attribution without stale count/update claims.
        header += [l for l in f['comments'] if any(t in l for t in ['AUTHOR','REPO','来源','http','copyright','Copyright'])]
        write(ROOT/dest,'\n'.join(header+[x['rule'] for x in f['items']])+'\n')
    # Both large sets retain their exact predicate union, but become trie-backed providers.
    china=[]
    for n in ['ChinaIp.list','ChinaCompanyIp.list']:
        china += [ipaddress.ip_network(x['rule'].split(',')[1]) for x in files[destination(n)]['items']]
    collapsed=list(ipaddress.collapse_addresses(china))
    write(ROOT/'providers/ChinaIP.txt','\n'.join(map(str,collapsed))+'\n')
    gfw=[x['rule'].split(',')[1] for x in files[destination('ProxyGFWlist.list')]['items'] if x['rule'].startswith('DOMAIN-SUFFIX,')]
    write(ROOT/'providers/ProxyGFW.txt','\n'.join('+.'+v for v in gfw)+'\n')
    groups=load_groups(original)
    template={
        'mixed-port':7890,'socks-port':7891,'allow-lan':True,'bind-address':'*','ipv6':True,'mode':'rule','log-level':'info',
        'external-controller':'127.0.0.1:9090','profile':{'store-selected':True},
        # SubConverter-Extended rebuilds proxy-groups, so preserve native fields
        # under a separate key for the explicit, offline finalization step.
        'x-clashrule-native-groups':groups,
        'rule-providers':{
            'ChinaIP':{'type':'http','behavior':'ipcidr','format':'text','url':base+'providers/ChinaIP.txt','path':'./rule_provider/local-ChinaIP.txt','interval':86400},
            'ProxyGFW':{'type':'http','behavior':'domain','format':'text','url':base+'providers/ProxyGFW.txt','path':'./rule_provider/local-ProxyGFW.txt','interval':86400},
        },
    }
    write(ROOT/'templates/GeneralClashConfig.yaml','# SubConverter base. Run tools/finalize.py on the converted YAML before use.\n# DNS, authentication and firewall remain managed by OpenClash.\n'+yaml.safe_dump(template,allow_unicode=True,sort_keys=False,width=110))
    expanded_base=copy.deepcopy(template);expanded_base.pop('rule-providers')
    write(ROOT/'templates/GeneralClashConfig.expanded.yaml',yaml.safe_dump(expanded_base,allow_unicode=True,sort_keys=False,width=110))
    def make_ini(expanded=False):
        lines=['[custom]','; Local rule package — 2026-09-20','; Convert with expand=true, then run tools/finalize.py before use.','; Native group fields are preserved in the base template under x-clashrule-native-groups.','; Upload rules/, providers/, templates/ and this INI together.','']
        emitted_china=False
        for e in entries:
            if 'path' in e and not files[e['path']]['items']:continue
            if 'inline' in e:ref='[]'+e['inline']
            elif not expanded and e['path'] in [destination('ChinaIp.list'),destination('ChinaCompanyIp.list')]:
                if emitted_china:continue
                ref='[]RULE-SET,ChinaIP,no-resolve';emitted_china=True
            elif not expanded and e['path']==destination('ProxyGFWlist.list'):ref='[]RULE-SET,ProxyGFW'
            else:ref=base+e['path']
            lines.append('ruleset='+e['target']+','+ref)
            if not expanded and e.get('path')==destination('ProxyGFWlist.list'):
                for x in files[e['path']]['items']:
                    if not x['rule'].startswith('DOMAIN-SUFFIX,'):lines.append('ruleset='+e['target']+',[]'+x['rule'])
        lines+=['','; Compatibility groups are rebuilt by the converter; finalization replaces these.']
        for g in groups:
            parts=[g['name'],g['type']]+['[]'+v for v in g.get('proxies',[])]
            if 'filter' in g:parts+=[g['filter'],'[]REJECT']
            if g['type'] in ('url-test','fallback'):parts += [HEALTH,'300,5,150']
            lines.append('custom_proxy_group='+'`'.join(parts))
        lines+=['','clash_rule_base='+base+'templates/GeneralClashConfig'+('.expanded' if expanded else '')+'.yaml','enable_rule_generator=true','overwrite_original_rules=true','']
        return '\n'.join(lines)
    write(ROOT/'profiles/MyRuleClash_Plus_V1.optimized.ini',make_ini())
    write(ROOT/'profiles/MyRuleClash_Plus_V1.expanded.ini',make_ini(True))
    # Full flattened model is for offline equivalence tests, not a secret-bearing config.
    flattened=[]
    for e in entries:
        rs=[e['inline']] if 'inline' in e else [x['rule'] for x in files[e['path']]['items']]
        for r in rs:
            a=r.split(',');flattened.append(','.join(a+[e['target']]) if a[0]=='MATCH' else ','.join(a[:2]+[e['target']]+a[2:]))
    write(ROOT/'audit/rules-expanded.txt','\n'.join(flattened)+'\n')
    write(ROOT/'audit/rule-review.jsonl','\n'.join(json.dumps(r,ensure_ascii=False) for r in records)+'\n')
    dump(ROOT/'audit/file-summary.json',stats)
    summary={'source_files':len(downloads),'source_rule_records':len(records),'optimized_rule_records':sum(len(f['items']) for f in files.values()),'expanded_rules':len(flattened),'china_provider_prefixes':len(collapsed),'gfw_provider_domains':len(gfw),'main_rule_estimate':len(flattened)-sum(len(files[destination(n)]['items']) for n in ['ChinaIp.list','ChinaCompanyIp.list'])-len(gfw)+2,'groups':len(groups),'native_filtered_groups':sum('filter' in g for g in groups),'ruleset_references':len(entries)-1,'status_counts':dict(Counter(r['status'] for r in records)),'base_url':base}
    summary.pop('ruleset_references')
    summary['profile_rule_entries']={name:sum(line.startswith('ruleset=') for line in make_ini(expanded).splitlines()) for name,expanded in [('optimized',False),('expanded',True)]}
    dump(ROOT/'audit/build-summary.json',summary)
    dump(ROOT/'audit/entry-order.json',entries)
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
