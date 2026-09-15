"""Build the isolated reviewer image, without running a model."""
from chb.cli import ROOT, command

if __name__ == '__main__':
    command(['docker', 'build', '-t', 'chb-reviewer:codex-0.154.0', str(ROOT/'reviewer')], timeout=600)
