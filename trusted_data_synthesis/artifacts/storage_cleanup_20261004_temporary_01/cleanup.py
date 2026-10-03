import os,json,hashlib,stat,subprocess,shutil,datetime
PLAN='/tmp/codex-ds-storage-cleanup-plan-20261004.json'; RESULT='/tmp/codex-ds-storage-cleanup-result-20261004.json'
plan=json.load(open(PLAN)); root=plan['root']; os.chdir(root); env=dict(os.environ,GIT_OPTIONAL_LOCKS='0')
result={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'plan_sha256':hashlib.sha256(open(PLAN,'rb').read()).hexdigest(),'removed':[],'retained':[],'process_checks':[]}
def persist():
 with open(RESULT,'w') as f:json.dump(result,f,ensure_ascii=False,indent=2)
def inventory(path):
 b=0;cnt=0;links=0;hard=0;h=hashlib.sha256()
 for base,dirs,files in os.walk(path,followlinks=False):
  for p in [base]+[os.path.join(base,x) for x in sorted(files)]+[os.path.join(base,x) for x in sorted(dirs) if os.path.islink(os.path.join(base,x))]:
   s=os.lstat(p);b+=s.st_blocks*512;cnt+=stat.S_ISREG(s.st_mode);links+=stat.S_ISLNK(s.st_mode);hard+=stat.S_ISREG(s.st_mode) and s.st_nlink>1
   h.update(json.dumps([os.path.relpath(p,path),s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode],ensure_ascii=False).encode())
 return {'allocated_bytes':b,'files':cnt,'symlinks':links,'hardlinked_files':hard,'metadata_sha256':h.hexdigest()}
def birth(pid):
 try:return open(f'/proc/{pid}/stat').read().rsplit(')',1)[1].split()[19]
 except OSError:return None
def process_check():
 candidates=[os.path.join(root,x['path']) for x in plan['temporary']+plan['worktrees']]
 hits=[];failed=[];uid=os.getuid()
 for name in os.listdir('/proc'):
  if not name.isdigit():continue
  proc='/proc/'+name
  try:
   if os.stat(proc).st_uid!=uid:continue
   vals=[os.readlink(proc+'/cwd')]
   args=open(proc+'/cmdline','rb').read().split(b'\0');vals += [x.decode(errors='replace') for x in args if x.startswith(b'/')]
   for f in os.listdir(proc+'/fd'):
    try:vals.append(os.readlink(proc+'/fd/'+f))
    except OSError:pass
   for path in vals:
    normalized=os.path.realpath(path) if path.startswith('/') else path
    for c in candidates:
     if normalized==c or normalized.startswith(c+'/'):hits.append({'pid':int(name),'path':path,'candidate':c})
  except OSError:failed.append(int(name))
 check={'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'hits':hits,'inaccessible_or_exited':failed};result['process_checks'].append(check);persist()
 if hits:raise RuntimeError('Candidate is used by live process: '+str(hits))
prior=json.load(open('/tmp/codex-storage-cleanup-20261004-ohgn4dem/process-before.json'))
prior=[p for p in prior if '/Data-Synthesis/' in p['cwd']]
result['experiment_processes_before']=[{'pid':p['pid'],'expected_birth':p['birth'],'observed_birth':birth(p['pid'])} for p in prior]
if any(p['expected_birth']!=p['observed_birth'] for p in result['experiment_processes_before']):raise RuntimeError('Experiment process changed before cleanup; inspect first')
process_check(); disk=os.statvfs(root);result['disk_available_before']=disk.f_bavail*disk.f_frsize
assert shutil.rmtree.avoids_symlink_attacks
for row in plan['temporary']:
 rel=row['path'];p=os.path.join(root,rel)
 try:
  assert os.path.realpath(p)==p and os.path.isdir(p) and not os.path.islink(p)
  tracked=subprocess.check_output(['git','ls-files','--',rel],text=True,env=env)
  assert not tracked,'tracked content exists'
  now=inventory(p); assert now=={k:row[k] for k in now},'metadata changed since plan'
  assert not now['hardlinked_files'],'hardlinks present'
  if 'remove_children' in row:
   assert sorted(os.listdir(p))==row['remove_children']
   for n in row['remove_children']:
    child=os.path.join(p,n)
    if os.path.islink(child) or not os.path.isdir(child):os.unlink(child)
    else:shutil.rmtree(child)
   after=os.lstat(p).st_blocks*512
   assert not os.listdir(p)
  else:
   shutil.rmtree(p);after=0;assert not os.path.lexists(p)
  out={'path':rel,'before_bytes':now['allocated_bytes'],'after_bytes':after,'removed_bytes':now['allocated_bytes']-after,'files':now['files'],'symlinks':now['symlinks']}
  if 'remove_children' in row:out['removed_children']=row['remove_children']
  result['removed'].append(out);print(json.dumps(out,ensure_ascii=False),flush=True)
 except Exception as exc:
  result['retained'].append({'path':rel,'reason':str(exc)});print('RETAINED',rel,str(exc),flush=True)
 persist()
for row in plan['worktrees']:
 rel=row['path'];p=os.path.join(root,rel)
 try:
  process_check()
  assert subprocess.check_output(['git','-C',p,'rev-parse','HEAD'],text=True).strip()==row['head'],'HEAD changed'
  assert not subprocess.check_output(['git','-C',p,'status','--porcelain=v1','--untracked-files=all'],text=True,env=env),'worktree dirty'
  assert subprocess.run(['git','merge-base','--is-ancestor',row['head'],'HEAD']).returncode==0,'not merged'
  ignored=subprocess.check_output(['git','-C',p,'ls-files','--others','--ignored','--exclude-standard','-z'],env=env).split(b'\0')
  for b in ignored:
   if not b:continue
   f=b.decode();assert any(v in f.split('/') for v in ('__pycache__','.pytest_cache','.ruff_cache','.mypy_cache')) or f.endswith('.pyc'),'non-tool ignored file '+f
  before=int(subprocess.check_output(['du','-x','-B1','-s',p],text=True).split()[0]);assert before==row['bytes'],'worktree size changed'
  removal=subprocess.run(['git','worktree','remove',p],capture_output=True,text=True)
  assert removal.returncode==0,removal.stderr
  assert not os.path.lexists(p) and not os.path.lexists(row['gitdir'])
  out={'path':rel,'head':row['head'],'before_bytes':row['bytes'],'gitdir_before_bytes':row['gitdir_bytes'],'after_bytes':0,'removed_bytes':row['bytes']+row['gitdir_bytes'],'method':'git worktree remove (no force)'}
  result['removed'].append(out);print(json.dumps(out),flush=True)
 except Exception as exc:
  result['retained'].append({'path':rel,'reason':str(exc)});print('RETAINED',rel,str(exc),flush=True)
 persist()
result['experiment_processes_after']=[{'pid':p['pid'],'expected_birth':p['birth'],'observed_birth':birth(p['pid'])} for p in prior]
disk=os.statvfs(root);result['disk_available_after']=disk.f_bavail*disk.f_frsize
result['removed_bytes']=sum(x['removed_bytes'] for x in result['removed']);result['completed_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();persist()
print(json.dumps({'result_path':RESULT,'removed_bytes':result['removed_bytes'],'retained':result['retained'],'processes_unchanged':all(p['expected_birth']==p['observed_birth'] for p in result['experiment_processes_after'])},ensure_ascii=False))
