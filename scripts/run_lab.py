#!/usr/bin/env python3
"""Own child processes, run tests, always stop lab. Exit red for real security failures."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def wait_for(port, process):
    deadline = time.monotonic()+45
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f'Service exited before ready on {port}; inspect artifacts/*.log')
        try:
            with socket.create_connection(('127.0.0.1',port),timeout=1): return
        except OSError: time.sleep(.25)
    raise TimeoutError(f'Service not ready on port {port}')


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Launch vulnerable labs only in a disposable isolated VM/CI runner')
    parser.add_argument('--isolated-lab', action='store_true', help='Confirm this is a disposable isolated lab, not a shared machine')
    args = parser.parse_args()
    if not args.isolated_lab:
        parser.error('Use a disposable isolated VM. The upstream gRPC server listens on all interfaces. Then pass --isolated-lab.')
    lab = ROOT/'.lab'
    artifacts = ROOT/'artifacts'
    artifacts.mkdir(exist_ok=True)
    processes, streams = [], []
    try:
        # Fail before starting anything if a port belongs to some other process.
        for port in (5101,5102,5013,3550):
            with socket.socket() as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(('127.0.0.1',port))
        for name, kind, port, extra in [
            ('vampi-secure','vampi',5101,{'vulnerable':'0'}),
            ('vampi-vulnerable','vampi',5102,{'vulnerable':'1'}),
            ('dvga','dvga',5013,{})]:
            source = lab/(name+'-runtime')
            if source.exists(): shutil.rmtree(source)
            shutil.copytree(lab/kind,source,ignore=shutil.ignore_patterns('.git','__pycache__'))
            output = open(artifacts/(name+'.log'),'w'); streams.append(output)
            process = subprocess.Popen([str(lab/(kind+'-env')/'bin/python'),str(ROOT/'launcher.py'),kind,str(source),str(port)],
                env={**os.environ,**extra,'tokentimetolive':'600'},stdout=output,stderr=subprocess.STDOUT)
            processes.append(process)
            wait_for(port,process)
        output = open(artifacts/'catalog.log','w'); streams.append(output)
        process = subprocess.Popen([str(lab/'catalog')],cwd=lab/'boutique/src/productcatalogservice',
            env={**os.environ,'DISABLE_PROFILER':'1','PORT':'3550'},stdout=output,stderr=subprocess.STDOUT)
        processes.append(process); wait_for(3550,process)
        for port in (5101,5102):
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/createdb',timeout=5) as response:
                assert response.status == 200
        env = {**os.environ,'QA_SOURCE_ROOT':str(lab)}
        common = [sys.executable,'-m','qa']
        first = subprocess.run(common+['--junitxml=artifacts/all-apis.xml','--html=artifacts/all-apis.html'],cwd=ROOT,env=env)
        second = subprocess.run(common+['--modules','test_security','-k','rest_','--vampi-url=http://127.0.0.1:5101',
                                      '--junitxml=artifacts/secure-mode.xml','--html=artifacts/secure-mode.html'],cwd=ROOT,env=env)
        return max(first.returncode,second.returncode)
    finally:
        for process in reversed(processes):
            process.terminate()
        for process in processes:
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill(); process.wait()
        for stream in streams: stream.close()


if __name__ == '__main__': sys.exit(main())
