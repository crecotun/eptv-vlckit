#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
# Copyright 2026 Alexei Crecotun
from pathlib import Path
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import argparse

ROOT = Path(__file__).resolve().parents[1]

def collect(vlc, build_log, previous_inputs, output):
    log = build_log.read_text(errors='replace')
    prior = json.loads(previous_inputs.read_text())
    spec = importlib.util.spec_from_file_location('collector', ROOT / 'scripts/collect-vlckit-sources.py')
    collector = importlib.util.module_from_spec(spec); spec.loader.exec_module(collector)
    output.mkdir(parents=True, exist_ok=False)
    results={}
    for filename,component in sorted(set(re.findall(r'grep -- " ([^" ]+)\$" "\.\./src/([^/]+)/SHA512SUMS"',log))):
        if any(Path(name).name != name or name in {'.', '..'} for name in [filename, component]):
            raise ValueError('Unsafe native input name')
        sums=(vlc/'contrib/src'/component/'SHA512SUMS').read_text()
        expected=next(row.split()[0] for row in sums.splitlines() if row.split()[-1]==filename)
        archive=vlc/'contrib/tarballs'/filename
        if collector.digest(archive,'sha512')!=expected: raise ValueError('Native input checksum differs: '+component)
        if filename+': OK' not in log: raise ValueError('Missing native build checksum check: '+component)
        shutil.copy2(archive,output/filename)
        item={'filename':filename,'sha512':expected,'sha256':collector.digest(archive,'sha256'),
              'bytes':archive.stat().st_size,'evidence':'native build SHA512 check and pinned source recipe',
              'urls':prior['sources'].get(component,{}).get('urls',[])}
        item['license_files']=collector.licenses(output,component,filename)
        results[component]=item
    for component,item in prior['sources'].items():
        if not item.get('git_revision'): continue
        filename=item['filename'];revision=item['git_revision']
        recipe=(vlc/'contrib/src'/component/'rules.mak').read_text()
        if filename not in log or revision not in recipe or ('test "$h" = "'+revision+'"') not in log: continue
        archive=vlc/'contrib/tarballs'/filename
        if collector.digest(archive,'sha256')!=item['sha256']: raise ValueError('Cached exact Git archive differs: '+component)
        stamp=archive.with_name(archive.name.replace('.tar.xz','.githash')).read_text().split()[0]
        if stamp!=revision: raise ValueError('Git archive commit check differs: '+component)
        shutil.copy2(archive,output/filename)
        item=dict(item);item['evidence']='pinned Git source recipe, native commit check and unchanged verified archive SHA256'
        item['license_files']=collector.licenses(output,component,filename)
        results[component]=item
    # Preserve the unused Theora release input required by make fetch alongside its Git source.
    if 'theora' in results:
        for row in (vlc/'contrib/src/theora/SHA512SUMS').read_text().splitlines():
            expected,filename=row.split()
            archive=vlc/'contrib/tarballs'/filename
            if not archive.exists(): continue
            if collector.digest(archive,'sha512')!=expected: raise ValueError('Theora secondary source checksum differs')
            component='theora-release-input'
            shutil.copy2(archive,output/filename)
            results[component]={'filename':filename,'sha512':expected,'sha256':collector.digest(archive,'sha256'),
                'bytes':archive.stat().st_size,'evidence':'secondary fetch prerequisite; checked directly against pinned SHA512 recipe',
                'license_files':collector.licenses(output,component,filename)}
    packages=[]
    for match in re.finditer(r'^To-be-built packages:\n((?:  .*\n)+)',log,re.M):
        packages.append(sorted(match[1].split()))
    represented = set(results) | {'meson-machinefile'}
    # protoc is built from the same archive as protobuf, with a separate target.
    protobuf_recipe = (vlc / 'contrib/src/protobuf/rules.mak').read_text()
    if '.sum-protoc: .sum-protobuf' in protobuf_recipe and 'protobuf' in results:
        represented.add('protoc')
    expected = set().union(*(set(items) for items in packages))
    if not packages or expected - represented:
        raise ValueError('Unresolved native source inputs: ' + ', '.join(sorted(expected - represented)))
    manifest={'schema_version':1,'status':'SOURCE_INPUTS_VERIFIED','sources':dict(sorted(results.items())),
              'platform_inputs':packages,'vlc_revision':subprocess.check_output(['git','-C',str(vlc),'rev-parse','HEAD'],text=True).strip(),
              'license_review':'NAMED_REVIEW_REQUIRED',
              'scope':'source inputs actually checksum-checked by native builds; tools and optional sources included conservatively'}
    (output/'source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    header=(ROOT/'releases'/json.loads((ROOT/'compliance/vlckit-eptv-build.json').read_text())['pod_version']/'TransitiveNotices.txt').read_text().split('\n------------------------------------------------------------------------\n',1)[0]
    notices=header.replace('Selected alternatives:', 'Selected alternatives, where applicable:')
    for component,item in manifest['sources'].items():
        for legal in sorted(item['license_files'],key=lambda x:x['path']):
            data=(output/'licenses'/component/legal['path']).read_bytes()
            if hashlib.sha256(data).hexdigest()!=legal['sha256']: raise ValueError('Legal file changed')
            notices+='\n------------------------------------------------------------------------\n'+component+'/'+legal['path']+'\nSHA-256: '+legal['sha256']+'\n\n'+data.decode('utf-8',errors='replace')+'\n'
    (output/'TransitiveNotices.txt').write_text(notices)
    print('Collected',len(results),'verified source inputs;',sum(len(v['license_files']) for v in results.values()),'legal texts')

def main():
    parser = argparse.ArgumentParser(description='Collect exact source inputs from completed native build checksum checks.')
    parser.add_argument('--vlc-source', type=Path, required=True)
    parser.add_argument('--build-log', type=Path, required=True)
    parser.add_argument('--previous-inputs', type=Path, required=True, help='Verified prior Git input archive identities')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        collect(args.vlc_source, args.build_log, args.previous_inputs, args.output)
    except (OSError, ValueError, KeyError, StopIteration, subprocess.CalledProcessError) as error:
        parser.exit(1, 'Native source collection failed: ' + str(error) + '\n')

if __name__ == '__main__':
    main()
