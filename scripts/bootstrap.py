#!/usr/bin/env python3
"""Fetch exact revisions and create independent service environments. No root or Docker."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
 'vampi': ('https://github.com/erev0s/VAmPI.git','f16052dce83f05847133ec98f01c5193a41de7d8'),
 'dvga': ('https://github.com/dolevf/Damn-Vulnerable-GraphQL-Application.git','a961308c02d1fb462b192681c336b0739e432da7'),
 'boutique': ('https://github.com/GoogleCloudPlatform/microservices-demo.git','5b608cb1dfe317d05e4f1bb8c99b7618452fde87')}


def run(*args, **kwargs):
    subprocess.run(list(map(str,args)), check=True, **kwargs)


def main():
    lab = ROOT/'.lab'
    lab.mkdir(exist_ok=True)
    resolved = {}
    for name, (url, sha) in SOURCES.items():
        target = lab/name
        if not target.exists():
            run('git','clone','--no-checkout',url,target)
        run('git','-C',target,'checkout','--detach',sha)
        actual = subprocess.check_output(['git','-C',str(target),'rev-parse','HEAD'],text=True).strip()
        if actual != sha:
            raise RuntimeError('Source revision mismatch: '+name)
        # Never accept locally edited source silently.
        dirty = subprocess.check_output(['git','-C',str(target),'diff','--name-only','HEAD'],text=True)
        if dirty.strip():
            raise RuntimeError('Dirty upstream checkout: '+name)
        resolved[name] = {'url':url,'commit':actual}
        if name != 'boutique':
            env = lab/(name+'-env')
            if not env.exists(): run(sys.executable,'-m','venv',env)
            run(env/'bin/python','-m','pip','install','-r',ROOT/'scripts'/(name+'.lock'))
    run('go','build','-o',lab/'catalog', '.',cwd=lab/'boutique/src/productcatalogservice')
    (lab/'sources.json').write_text(json.dumps(resolved,indent=2)+'\n')
    print('Setup complete. Run: python scripts/run_lab.py')


if __name__ == '__main__': main()
