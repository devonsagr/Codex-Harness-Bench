"""Only profile injection and evidence collection; Harbor owns execution."""
import hashlib
import json
from pathlib import Path
import shlex

from harbor.agents.installed.codex import Codex, CodexOptions

from chb.profiles import files_in, validate_profile, write_json


class ProfileOptions(CodexOptions):
    profile_path: str | None = None


class ProfileCodex(Codex):
    options_model = ProfileOptions

    def __init__(self, *args, profile_path, **kwargs):
        self.profile_path = Path(profile_path)
        self.profile, native = validate_profile(self.profile_path)
        self._profile_loads = 0
        if "config" in kwargs:
            raise ValueError("Native config comes exclusively from the frozen profile")
        super().__init__(*args, config=native, **kwargs)

    def build_cli_flags(self):
        return super().build_cli_flags() + " --strict-config"

    async def _upload_effective_config(self, environment, config, remote_path):
        await super()._upload_effective_config(environment, config, remote_path)
        instructions = self.profile_path / "AGENTS.md"
        target = str(self._REMOTE_CODEX_HOME / "AGENTS.md")
        await environment.upload_file(instructions, target)
        skill_files = files_in(self.profile_path / "skills") if (self.profile_path / "skills").exists() else {}
        expected_skills = {name: hashlib.sha256(data).hexdigest() for name, data in skill_files.items()}
        async def inventory():
            script = (
                "import pathlib,hashlib,json; p=pathlib.Path.home()/'.agents/skills'; "
                "entries=list(p.rglob('*')); "
                "assert not any(x.is_symlink() for x in [p]+entries), 'linked skill path'; "
                "print(json.dumps({x.relative_to(p).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() "
                "for x in entries if x.is_file()}))"
            )
            check = await environment.exec(command="python -c " + shlex.quote(script))
            if check.return_code != 0:
                raise RuntimeError("Cannot verify container skills")
            return json.loads(check.stdout)
        before = await inventory()
        # A resumed turn keeps this trial's skills. A fresh trial must be empty.
        if before != (expected_skills if self._profile_loads else {}):
            raise RuntimeError("Unexpected or changed user skills in container")
        for name in skill_files:
            remote = "/tmp/chb-user-skills/" + name
            parent = str(Path(name).parent).replace("\\", "/")
            await environment.exec(command="mkdir -p " + shlex.quote("/tmp/chb-user-skills/" + parent))
            await environment.upload_file(self.profile_path / "skills" / name, remote)
        if skill_files:
            await environment.exec(command='mkdir -p "$HOME/.agents/skills" && cp -R /tmp/chb-user-skills/. "$HOME/.agents/skills/"')
        if await inventory() != expected_skills:
            raise RuntimeError("Skill upload checksum mismatch")
        check = await environment.exec(command=f"sha256sum {shlex.quote(target)}")
        expected = hashlib.sha256(instructions.read_bytes()).hexdigest()
        if check.return_code != 0 or not (check.stdout or "").startswith(expected):
            raise RuntimeError("Instruction upload checksum mismatch")
        forbidden = await environment.exec(command="test ! -e /tests/verify.py && test ! -e /solution/solve.sh && test ! -S /var/run/docker.sock")
        if forbidden.return_code != 0:
            raise RuntimeError("Verifier, solution, or Docker socket exposed to agent")
        self._profile_loads += 1
        write_json(self.logs_dir / "effective-profile.json", {
            "profile": self.profile["name"], "native_config": config,
            "instructions_sha256": expected,
            "instructions_path": target,
            "skills": expected_skills, "skills_before_load": before,
            "load_index": self._profile_loads,
            "host_home_mounted": False,
            "verifier_present_during_agent": False,
            "loading_evidence": "uploaded bytes verified before model execution",
            "actual_skill_use": "not inferred from upload",
        })
