"""Build the isolated reviewer image, without running a model."""
import subprocess
from chb.cli import ROOT, command

if __name__ == '__main__':
    base='chb-reviewer:base-20260927-cjk'
    try:command(['docker','image','inspect',base],capture_output=True,timeout=20)
    except subprocess.CalledProcessError:
        command(['docker','build','-f',str(ROOT/'reviewer'/'Dockerfile.base'),'-t',base,str(ROOT/'reviewer')],timeout=1800)
    command(['docker', 'build', '-t', 'chb-reviewer:machine-v1', str(ROOT/'reviewer')], timeout=900)
