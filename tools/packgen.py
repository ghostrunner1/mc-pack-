import json,hashlib,os,sys,shutil,re
def sha(p,algo):
    h=hashlib.new(algo)
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()
RAW='https://raw.githubusercontent.com/ghostrunner1/mc-pack-/main/'
def tq(s): return json.dumps(s,ensure_ascii=False)
def build(spec,repo):
    import tempfile
    snap=tempfile.mkdtemp()
    for e in spec['entries']:
        if e.get('local','').startswith('repo:'):
            rel=e['local'][5:]; dst=os.path.join(snap,rel); os.makedirs(os.path.dirname(dst),exist_ok=True)
            shutil.copyfile(os.path.join(repo,rel),dst); e['local']=dst
    for n in os.listdir(repo):
        if n!='.git' and n not in spec.get('keep',[]):
            p=os.path.join(repo,n); shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    files=[]
    for e in spec['entries']:
        path=e['path']; d=os.path.dirname(path); fn=os.path.basename(path)
        os.makedirs(os.path.join(repo,d),exist_ok=True)
        if 'local' in e and e.get('side','both')!='both':
            hosted='_files/'+path
            os.makedirs(os.path.join(repo,os.path.dirname(hosted)),exist_ok=True)
            shutil.copyfile(e['local'],os.path.join(repo,hosted))
            e=dict(e,url=RAW+hosted,hash=sha(os.path.join(repo,hosted),'sha1'))
        if 'url' in e:
            name=e.get('name',re.sub(r'\.(jar|zip)$','',fn))
            meta=os.path.join(d,re.sub(r'\.(jar|zip)$','',fn)+'.pw.toml')
            txt=f'name = {tq(name)}\nfilename = {tq(fn)}\nside = {tq(e.get("side","both"))}\n\n[download]\nurl = {tq(e["url"])}\nhash-format = "{e.get("hash_format","sha1")}"\nhash = {tq(e["hash"])}\n'
            open(os.path.join(repo,meta),'w').write(txt)
            files.append({'file':meta,'metafile':True})
        else:
            shutil.copyfile(e['local'],os.path.join(repo,path))
            f={'file':path}
            if e.get('preserve'): f['preserve']=True
            files.append(f)
    # extra raw files (README etc) not in index
    for rel,content in spec.get('raw',{}).items():
        os.makedirs(os.path.dirname(os.path.join(repo,rel)) or repo,exist_ok=True); open(os.path.join(repo,rel),'w').write(content)
    idx='hash-format = "sha256"\n'
    for f in sorted(files,key=lambda x:x['file']):
        idx+=f'\n[[files]]\nfile = {tq(f["file"])}\nhash = {tq(sha(os.path.join(repo,f["file"]),"sha256"))}\n'
        if f.get('metafile'): idx+='metafile = true\n'
        if f.get('preserve'): idx+='preserve = true\n'
    open(os.path.join(repo,'index.toml'),'w').write(idx)
    v=spec['versions']
    pack=f'name = {tq(spec["name"])}\nauthor = "ghostrunner1"\nversion = {tq(spec["version"])}\npack-format = "packwiz:1.1.0"\n\n[index]\nfile = "index.toml"\nhash-format = "sha256"\nhash = {tq(sha(os.path.join(repo,"index.toml"),"sha256"))}\n\n[versions]\nminecraft = {tq(v["minecraft"])}\nneoforge = {tq(v["neoforge"])}\n'
    open(os.path.join(repo,'pack.toml'),'w').write(pack)
    print('entries',len(files))
if __name__=='__main__':
    repo=sys.argv[2] if len(sys.argv)>2 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    build(json.load(open(sys.argv[1] if len(sys.argv)>1 else os.path.join(repo,'tools','spec.json'))),repo)
