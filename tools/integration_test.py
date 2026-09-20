from pathlib import Path
import os, sys, json, subprocess, threading, time, urllib.request, urllib.parse, http.server, copy

import yaml

from finalize import finalize
import argparse
parser=argparse.ArgumentParser(description='隔离测试转换器和 Mihomo，需要提供官方二进制路径。')
parser.add_argument('--subconverter-dir',required=True,type=Path)
parser.add_argument('--mihomo',required=True,type=Path)
args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'.test-work/integration';RUN.mkdir(exist_ok=True,parents=True)
SUB=args.subconverter_dir.resolve()
CORE=args.mihomo.resolve()
LOCAL='http://127.0.0.1:25592/'
BASE='https://raw.githubusercontent.com/dearjnana/ClashRule/refs/heads/main/'
SYNTHETIC=['[MESL]🇺🇸 美国 01','[MESL]🇺🇸 美国 02','[MESL]🇦🇲 亚美尼亚 01','[MESL]🇭🇰 香港 01','[OTHER]🇺🇸 美国 01','[MESL]🇦🇺 Australia','[MESL]🇷🇺 Russia','[MESL]🇨🇾 Cyprus','[MESL]剩余流量 美国','[LD士多]JP-Tokyo-01']
def fetch(url):
    with urllib.request.urlopen(url,timeout=40) as r:return r.read()
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_GET(self):
        path=urllib.parse.unquote(urllib.parse.urlparse(self.path).path).lstrip('/')
        if path=='subscription.yaml':
            data=yaml.safe_dump({'proxies':[{'name':n,'type':'ss','server':'127.0.0.1','port':9,'cipher':'aes-128-gcm','password':'public-test-only','udp':True} for n in SYNTHETIC]},allow_unicode=True).encode()
        elif path=='health':self.send_response(204);self.end_headers();return
        else:
            file=(ROOT/path).resolve()
            if not file.is_relative_to(ROOT) or not file.is_file():self.send_error(404);return
            data=file.read_bytes().replace(BASE.encode(),LOCAL.encode())
        self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
def wait_for(url,proc):
    end=time.monotonic()+20
    while time.monotonic()<end:
        if proc.poll() is not None:raise RuntimeError('Process exited '+str(proc.returncode))
        try:return fetch(url)
        except Exception:time.sleep(.2)
    raise TimeoutError(url)
server=http.server.ThreadingHTTPServer(('127.0.0.1',25592),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
pref=(SUB/'base/pref.example.ini').read_text(encoding='utf-8')
for old,new in [('listen=0.0.0.0','listen=127.0.0.1'),('port=25500','port=25591'),('enable_cache=true','enable_cache=false'),('async_fetch_ruleset=true','async_fetch_ruleset=false'),('request_deadline_ms=15000','request_deadline_ms=60000')]:pref=pref.replace(old,new)
(RUN/'pref.ini').write_text(pref,encoding='utf-8')
env=os.environ.copy();env['PREF_PATH']=str(RUN/'pref.ini');env['SUBCONVERTER_SECURITY_PROFILE']='lan'
log=(RUN/'subconverter.log').open('w',encoding='utf-8')
proc=subprocess.Popen([str(SUB/('subconverter.exe' if os.name=='nt' else 'subconverter')),'-f',str(RUN/'pref.ini')],cwd=SUB,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
summary={}
try:
    wait_for('http://127.0.0.1:25591/version',proc)
    for label,config in [('main','profiles/openclash.ini'),('expanded','profiles/expanded.ini'),('android','profiles/android.ini')]:
        url='http://127.0.0.1:25591/sub?'+urllib.parse.urlencode({'target':'clash','url':LOCAL+'subscription.yaml','config':LOCAL+config,'new_name':'true','expand':'true'})
        data=fetch(url);(RUN/(label+'.yaml')).write_bytes(data)
        parsed=finalize(yaml.safe_load(data));groups=parsed.get('proxy-groups',[])
        (RUN/(label+'-ready.yaml')).write_text(yaml.safe_dump(parsed,allow_unicode=True,sort_keys=False),encoding='utf-8')
        native=yaml.safe_load((ROOT/('templates/'+('openclash' if label=='main' else label)+'.yaml')).read_text(encoding='utf-8'))
        byname={g['name']:g for g in groups}
        differences=[g['name'] for g in native['x-clashrule-native-groups'] if byname.get(g['name'])!=g]
        summary[label]={'groups':len(groups),'rules':len(parsed.get('rules',[])),'group_differences':differences,'providers':len(parsed.get('rule-providers',{}))}
        (RUN/'conversion-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
        print(label,summary[label],flush=True)
        assert not differences, differences
        # 验证远程列表中的正则经过转换后完整保留，且仍位于原生域名集合之后。
        expected_regex=[r+',🥒 寡妇网' for r in (ROOT/'rules/network/ProxyLite.list').read_text(encoding='utf-8').splitlines() if r.startswith('DOMAIN-REGEX,')]
        actual_regex=[r for r in parsed['rules'] if r.startswith('DOMAIN-REGEX,') and r.endswith(',🥒 寡妇网')]
        assert actual_regex==expected_regex,(label,'转换后正则丢失、重复或被改写')
        if label!='expanded':
            anchor=parsed['rules'].index('RULE-SET,ProxyGFW,🥒 寡妇网')+1
            assert parsed['rules'][anchor:anchor+len(expected_regex)]==expected_regex
        summary[label]['proxy_regex_rules']=len(actual_regex)
        # 只检查规则和策略组，不打开代理端口。
        # 使用独立缓存中的规则集，避免依赖尚未发布的远程文件。
        corehome=RUN/label;corehome.mkdir(exist_ok=True)
        for provider in parsed.get('rule-providers',{}).values():
            path=corehome/provider['path'];path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes((ROOT/provider['url'].removeprefix(LOCAL)).read_bytes())
        test=subprocess.run([str(CORE),'-t','-d',str(corehome),'-f',str(RUN/(label+'-ready.yaml'))],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        (RUN/(label+'-mihomo.log')).write_text(test.stdout+test.stderr,encoding='utf-8')
        summary[label]['mihomo_exit']=test.returncode
        print(test.stdout[-3000:],test.stderr[-1000:],flush=True)
        assert test.returncode==0
        if label=='expanded':
            assert parsed['rules']==(ROOT/'reports/rules-expanded.txt').read_text(encoding='utf-8').splitlines()
        if label=='main':
            runtime=copy.deepcopy(parsed)
            runtime.update({'mixed-port':0,'socks-port':0,'port':0,'allow-lan':False,'external-controller':'127.0.0.1:25593','dns':{'enable':False},'tun':{'enable':False}})
            for g in runtime['proxy-groups']:
                if 'url' in g:g['url']=LOCAL+'health';g['interval']=0
            for p in runtime.get('proxy-providers',{}).values():p['health-check']['enable']=False
            runtimepath=RUN/'runtime.yaml';runtimepath.write_text(yaml.safe_dump(runtime,allow_unicode=True),encoding='utf-8')
            corelog=(RUN/'runtime.log').open('w',encoding='utf-8')
            running=subprocess.Popen([str(CORE),'-d',str(corehome),'-f',str(runtimepath)],stdout=corelog,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            try:
                wait_for('http://127.0.0.1:25593/version',running)
                groupurl='http://127.0.0.1:25593/proxies/'+urllib.parse.quote('🇺🇸 Gemini MESL美国',safe='')
                end=time.monotonic()+15
                while time.monotonic()<end:
                    selected=json.loads(fetch(groupurl))
                    if selected.get('all')==SYNTHETIC[:2]:break
                    time.sleep(.1)
                assert selected['all']==SYNTHETIC[:2],selected
                assert selected['now']==SYNTHETIC[0],selected
                empty=json.loads(fetch('http://127.0.0.1:25593/proxies/'+urllib.parse.quote('⚡🇰🇷 MESL-韩国',safe='')))
                assert empty['all']==['REJECT'],empty
                rp=json.loads(fetch('http://127.0.0.1:25593/providers/rules'))['providers']
                assert all(v['ruleCount']>0 for v in rp.values()),rp
                assert rp['ProxyGFW']['ruleCount']==len((ROOT/'providers/ProxyGFW.txt').read_text().splitlines())
                summary[label]['runtime']={'gemini_members':len(selected['all']),'gemini_default':'MESL US 01','armenia_excluded':True,'empty_group':'REJECT','rule_provider_counts':{k:v['ruleCount'] for k,v in rp.items()},'listeners':'loopback controller only; proxy ports and TUN disabled'}
                print(summary[label]['runtime'],flush=True)
            finally:running.terminate();running.wait(timeout=10);corelog.close()
    (RUN/'conversion-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
finally:
    proc.terminate();proc.wait(timeout=10);log.close();server.shutdown()
