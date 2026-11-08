"""User-level skill installer; protects unknown edits and creates an explicit backup."""
import argparse,hashlib,json,os,shutil,sys
from pathlib import Path

def files(root):return {str(p.relative_to(root)):p for p in Path(root).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def install(source,destination_root,expected_manifest=None,backup=None):
    source=Path(source).resolve();base=Path(destination_root).resolve();target=base/'swimming-buddy';current=files(source)
    assert (source/'SKILL.md').is_file()
    if target.exists():
        old=files(target)
        if set(old)==set(current) and all(digest(old[n])==digest(current[n]) for n in current):return {'status':'already_identical','target':str(target),'files':len(current)}
        if expected_manifest is None or backup is None:raise ValueError('已有同名技能；需要已比对的预期清单及技能目录外备份路径，不能覆盖不明修改')
        expected=json.loads(Path(expected_manifest).read_text(encoding='utf-8'));expected=expected.get('skill_files',expected)
        if set(old)!=set(expected) or any(digest(old[n])!=expected[n] for n in old):raise ValueError('安装目录有用户修改/未知文件，停止覆盖')
        backup=Path(backup).resolve()
        if backup.exists() or backup.is_relative_to(base):raise ValueError('备份需新路径且位于skills目录之外，避免重复发现')
        if target.resolve()!=base/'swimming-buddy' or target.is_symlink():raise ValueError('安装目标路径不符')
        backup.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(target),str(backup))
    target.mkdir(parents=True,exist_ok=False)
    for relative,p in current.items():
        out=target/relative;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,out)
    for relative,p in current.items():assert digest(target/relative)==digest(p)
    return {'status':'installed','target':str(target),'files':len(current),'hashes_match':True,'automatic_invocation_tested':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--destination-root',default=str(Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'skills'));p.add_argument('--expected-manifest');p.add_argument('--backup');a=p.parse_args()
    try:print(json.dumps(install(Path(__file__).resolve().parents[1],a.destination_root,a.expected_manifest,a.backup),ensure_ascii=False));return 0
    except (ValueError,OSError,AssertionError) as error:print(str(error));return 1
if __name__=='__main__':sys.exit(main())
