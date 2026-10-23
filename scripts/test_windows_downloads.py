"""Exercise the installed downloader against a real loopback fault server.

This is fault injection, not evidence of official component acquisition or API success.
"""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path
import threading


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    spec=importlib.util.spec_from_file_location('installed',args.root/'launcher/portable.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    payload=b'T3 controlled transport fault fixture\n'*4096
    counts={}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            counts[self.path]=counts.get(self.path,0)+1
            n=counts[self.path]
            self.send_response(200);self.send_header('Content-Length',str(len(payload)));self.end_headers()
            if self.path=='/exhaust' or (self.path=='/recover' and n==2):
                self.wfile.write(b'X'*len(payload))
            elif self.path=='/recover' and n==1:
                self.wfile.write(payload[:100]);self.wfile.flush();self.close_connection=True
            else:self.wfile.write(payload)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    cache=args.output/'cache';cache.mkdir()
    item=dict(filename='transport-fixture.bin',url=f'http://127.0.0.1:{server.server_port}/recover',
              bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest())
    try:
        file=module.download_component(item,cache)
        assert file.read_bytes()==payload and counts['/recover']==3
        before=counts.copy();module.download_component(item,cache);assert counts==before
        file.write_bytes(b'corrupt cached file')
        item['url']=item['url'].replace('/recover','/valid')
        module.download_component(item,cache);assert file.read_bytes()==payload
        file.unlink();(cache/(file.name+'.partial')).write_bytes(b'prior interrupted bytes')
        module.download_component(item,cache);assert file.read_bytes()==payload
        item.update(filename='exhaust.bin',url=item['url'].replace('/valid','/exhaust'))
        try:module.download_component(item,cache)
        except RuntimeError as error:
            message=str(error)
            assert 'after 3 attempts' in message and 'source=http://127.0.0.1:' in message and 'SHA256' in message
        else:raise AssertionError('Corrupt download accepted')
        assert not (cache/item['filename']).exists()
        result=dict(passed=True,scope='installed production download function; real loopback HTTP fault injection only',
            officialDownloadEvidence=False,interruptedResponseRetried=True,wrongHashRetried=True,
            validCacheReusedWithoutNetwork=True,corruptCacheRetainedAndReacquired=True,stalePartialRetained=True,
            exhaustionRejected=True,requests=counts,retainedFailures=len(list(cache.glob('*.failed-*'))),error=message)
        (args.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    finally:server.shutdown();server.server_close()


if __name__=='__main__':main()
