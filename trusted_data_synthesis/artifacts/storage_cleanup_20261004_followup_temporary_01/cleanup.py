import os,json,stat,datetime,hashlib,shutil,subprocess
PLAN='/tmp/codex-ds-followup-temporary-plan-20261004.json';RESULT='/tmp/codex-ds-followup-temporary-result-20261004.json'
plan=json.load(open(PLAN));root=plan['root'];os.chdir(root);env=dict(os.environ,GIT_OPTIONAL_LOCKS='0')
result={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'plan_sha256':hashlib.sha256(open(PLAN,'rb').read()).hexdigest(),'removed':[],'retained':[]}
def persist():
 with open(RESULT,'w') as f:json.dump(result,f,ensure_ascii=False,indent=2)
def inventory(path):
 b=0;cnt=0;links=0;hard=0;h=hashlib.sha256()
 for base,dirs,files in os.walk(path,followlinks=False):
  for p in [base]+[os.path.join(base,x) for x in sorted(files)]+[os.path.join(base,x) for x in sorted(dirs) if os.path.islink(os.path.join(base,x))]:
   s=os.lstat(p);b+=s.st_blocks*512;cnt+=stat.S_ISREG(s.st_mode);links+=stat.S_ISLNK(s.st_mode);hard+=stat.S_ISREG(s.st_mode) and s.st_nlink>1
   h.update(json.dumps([os.path.relpath(p,path),s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_mode]).encode())
 return {'bytes':b,'files':cnt,'symlinks':links,'hardlinks':hard,'metadata_sha256':h.hexdigest()}
def birth(pid):
 try:return open(f'/proc/{pid}/stat').read().rsplit(')',1)[1].split()[19]
 except OSError:return None
snapshot=json.load(open('/tmp/storage-cleanup-followup-20261004-s2p9fylm/process-before.json'))
processes=[p for p in snapshot['processes'] if '/Data-Synthesis/' in p.get('cwd','')]
result['processes_before']=[{'pid':p['pid'],'expected_birth':p['birth'],'observed_birth':birth(p['pid'])} for p in processes]
assert all(p['expected_birth']==p['observed_birth'] for p in result['processes_before']),'Experiment process identity changed before execution'
hits=[];failed=[];candidates=[os.path.join(root,r['path']) for r in plan['candidates']]
for n in os.listdir('/proc'):
 if not n.isdigit():continue
 try:
  proc='/proc/'+n
  if os.stat(proc).st_uid!=os.getuid():continue
  vals=[os.readlink(proc+'/cwd')]+[x.decode(errors='replace') for x in open(proc+'/cmdline','rb').read().split(b'\0') if x.startswith(b'/')]
  for fd in os.listdir(proc+'/fd'):
   try:vals.append(os.readlink(proc+'/fd/'+fd))
   except OSError:pass
  for v in vals:
   p=os.path.realpath(v) if v.startswith('/') else v
   for c in candidates:
    if p==c or p.startswith(c+'/'):hits.append({'pid':int(n),'path':p})
 except OSError:failed.append(int(n))
result['process_boundary']={'hits':hits,'inaccessible_or_exited':failed};persist();assert not hits
repos=sorted(set('/'.join(r['path'].split('/')[:2]) for r in plan['candidates'] if r['path'].startswith('.codex-worktrees/')))
def statuses():return {r:subprocess.check_output(['git','-C',r,'status','--porcelain=v1','--untracked-files=all'],text=True,env=env) for r in repos}
result['worktree_status_before']=statuses()
protected='.codex-worktrees/finqa-v13-material-20260930/trusted_data_synthesis/scripts/finqa_v13_support_report.py'
def identity(p):
 s=os.lstat(p);return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,hashlib.sha256(open(p,'rb').read()).hexdigest()]
result['user_script_before']=identity(protected)
assert shutil.rmtree.avoids_symlink_attacks
for row in plan['candidates']:
 p=os.path.join(root,row['path'])
 try:
  assert os.path.realpath(p)==p and not os.path.islink(p) and os.path.isdir(p)
  current=inventory(p);assert current=={k:row[k] for k in current},'candidate changed since plan'
  assert current['hardlinks']==0
  repo=root;local=row['path']
  if row['path'].startswith('.codex-worktrees/'):
   parts=row['path'].split('/');repo=os.path.join(root,*parts[:2]);local='/'.join(parts[2:])
  assert not subprocess.check_output(['git','-C',repo,'ls-files','--',local],env=env),'tracked file under candidate'
  if row['path'].endswith('/test_tmp'):
   children=row['structure']['children'];assert sorted(os.listdir(p))==children
   for name in children:
    child=os.path.join(p,name)
    if os.path.islink(child) or not os.path.isdir(child):os.unlink(child)
    else:shutil.rmtree(child)
   assert not os.listdir(p);after=os.lstat(p).st_blocks*512
  else:
   shutil.rmtree(p);assert not os.path.lexists(p);after=0
  out={'path':row['path'],'before_bytes':current['bytes'],'after_bytes':after,'removed_bytes':current['bytes']-after,'files':current['files'],'symlinks':current['symlinks'],'group':'retained_worktree_test_fixtures' if row['path'].startswith('.codex-worktrees/') else 'main_worktree_test_fixtures'}
  result['removed'].append(out);print(json.dumps(out),flush=True)
 except Exception as exc:result['retained'].append({'path':row['path'],'reason':str(exc)});print('RETAINED',row['path'],str(exc),flush=True)
 persist()
result['worktree_status_after']=statuses();result['user_script_after']=identity(protected)
result['processes_after']=[{'pid':p['pid'],'expected_birth':p['birth'],'observed_birth':birth(p['pid'])} for p in processes]
result['removed_bytes']=sum(r['removed_bytes'] for r in result['removed']);result['completed_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();persist()
assert result['worktree_status_before']==result['worktree_status_after']
assert result['user_script_before']==result['user_script_after']
print(json.dumps({'result':RESULT,'removed_bytes':result['removed_bytes'],'all_processes_unchanged':all(p['expected_birth']==p['observed_birth'] for p in result['processes_after']),'retained':result['retained']}))
