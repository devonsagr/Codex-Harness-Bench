"""Only profile injection and evidence collection; Harbor owns execution."""
import hashlib
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
        # Start from the dedicated container's empty user skill directory.
        check = await environment.exec(command='find "$HOME/.agents/skills" -type f 2>/dev/null || true')
        if (check.stdout or "").strip():
            raise RuntimeError("Unexpected pre-existing user skills in fresh container")
        for name in skill_files:
            remote = "/tmp/chb-user-skills/" + name
            parent = str(Path(name).parent).replace("\\", "/")
            await environment.exec(command="mkdir -p " + shlex.quote("/tmp/chb-user-skills/" + parent))
            await environment.upload_file(self.profile_path / "skills" / name, remote)
        if skill_files:
            await environment.exec(command='mkdir -p "$HOME/.agents/skills" && cp -R /tmp/chb-user-skills/. "$HOME/.agents/skills/"')
        check = await environment.exec(command=f"sha256sum {shlex.quote(target)}")
        expected = hashlib.sha256(instructions.read_bytes()).hexdigest()
        if check.return_code != 0 or not (check.stdout or "").startswith(expected):
            raise RuntimeError("Instruction upload checksum mismatch")
        forbidden = await environment.exec(command="test ! -e /tests/verify.py && test ! -e /solution/solve.sh && test ! -S /var/run/docker.sock")
        if forbidden.return_code != 0:
            raise RuntimeError("Verifier, solution, or Docker socket exposed to agent")
        write_json(self.logs_dir / "effective-profile.json", {
            "profile": self.profile["name"], "native_config": config,
            "instructions_sha256": expected,
            "instructions_path": target,
            "skills": {name: hashlib.sha256(data).hexdigest() for name, data in skill_files.items()},
            "host_home_mounted": False,
            "verifier_present_during_agent": False,
            "loading_evidence": "uploaded bytes verified before model execution",
            "actual_skill_use": "not inferred from upload",
        })
