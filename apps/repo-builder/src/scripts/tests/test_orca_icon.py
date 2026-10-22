from __future__ import annotations

import importlib.util
import json
import os
import socket
import sys
import tempfile
import threading
import unittest
import unittest.mock
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "orca_icon.py"
SPEC = importlib.util.spec_from_file_location("repo_builder_orca_icon", MODULE_PATH)
assert SPEC and SPEC.loader
orca_icon = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = orca_icon
SPEC.loader.exec_module(orca_icon)


class FakeRuntime:
    """A unix socket that answers requests the way Orca's runtime does.

    `answers` maps a method to a function of the request; each request comes
    on its own connection, as `orca_icon.call` opens one per call.
    """

    def __init__(self, directory: Path, answers: dict) -> None:
        self.endpoint = str(directory / "runtime.sock")
        self.answers = answers
        self.requests: list[dict] = []
        self.server = socket.socket(socket.AF_UNIX)
        self.server.bind(self.endpoint)
        self.server.listen(4)
        (directory / "orca-runtime.json").write_text(
            json.dumps(
                {
                    "authToken": "token",
                    "transports": [{"kind": "unix", "endpoint": self.endpoint}],
                }
            )
        )
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def serve(self) -> None:
        while True:
            try:
                connection, _ = self.server.accept()
            except OSError:
                return
            with connection:
                buffer = b""
                while b"\n" not in buffer:
                    buffer += connection.recv(65536)
                request = json.loads(buffer.split(b"\n")[0])
                self.requests.append(request)
                answer = self.answers[request["method"]](request)
                connection.sendall(b'{"_keepalive":true}\n')
                connection.sendall(json.dumps(answer).encode() + b"\n")

    def methods(self) -> list[str]:
        return [request["method"] for request in self.requests]

    def close(self) -> None:
        self.server.shutdown(socket.SHUT_RDWR)
        self.server.close()
        self.thread.join(timeout=5)


def found(icon: dict | None):
    repo = {} if icon is None else {"repoIcon": icon}
    return lambda request: {"id": request["id"], "ok": True, "result": {"repo": repo}}


def not_found(request: dict) -> dict:
    return {"id": request["id"], "ok": False, "error": {"code": "repo_not_found"}}


def stored(request: dict) -> dict:
    return {
        "id": request["id"],
        "ok": True,
        "result": {"repo": {"repoIcon": request["params"]["updates"]["repoIcon"]}},
    }


AVATAR = {"type": "image", "src": "https://github.com/owner.png", "source": "github"}


class SetIconTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.user_data = Path(temporary.name)
        patcher = unittest.mock.patch.dict(
            os.environ, {"ORCA_USER_DATA_PATH": str(self.user_data)}
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def runtime(self, **answers) -> FakeRuntime:
        answers = {key.replace("_", "."): value for key, value in answers.items()}
        runtime = FakeRuntime(self.user_data, answers)
        self.addCleanup(runtime.close)
        return runtime

    def test_replaces_the_avatar_past_keepalives(self) -> None:
        runtime = self.runtime(repo_show=found(AVATAR), repo_update=stored)
        result = orca_icon.set_icon(Path("/work/podcast"), " 🎙️ ")
        self.assertEqual(result["status"], "set")
        self.assertEqual(result["registered"], "already")
        self.assertEqual(result["icon"], {"type": "emoji", "emoji": "🎙️"})
        self.assertEqual(runtime.methods(), ["repo.show", "repo.update"])
        update = runtime.requests[1]
        self.assertEqual(update["authToken"], "token")
        self.assertEqual(update["params"]["repo"], "path:/work/podcast")

    def test_registers_a_clone_orca_does_not_know(self) -> None:
        runtime = self.runtime(
            repo_show=not_found, repo_add=found(None), repo_update=stored
        )
        result = orca_icon.set_icon(Path("/work/podcast"), "🎙️")
        self.assertEqual(result["registered"], "added")
        self.assertEqual(runtime.methods(), ["repo.show", "repo.add", "repo.update"])
        self.assertEqual(runtime.requests[1]["params"], {"path": "/work/podcast"})

    def test_keeps_an_emoji_already_chosen(self) -> None:
        existing = {"type": "emoji", "emoji": "🩺"}
        runtime = self.runtime(repo_show=found(existing))
        result = orca_icon.set_icon(Path("/work/podcast"), "🎙️")
        self.assertEqual(result["status"], "kept")
        self.assertEqual(result["icon"], existing)
        self.assertEqual(runtime.methods(), ["repo.show"])

    def test_an_icon_the_runtime_dropped_is_a_failure(self) -> None:
        self.runtime(repo_show=found(None), repo_update=found(None))
        with self.assertRaisesRegex(ValueError, "stored None"):
            orca_icon.set_icon(Path("/work/podcast"), "🎙️")

    def test_a_refused_add_is_a_failure(self) -> None:
        self.runtime(
            repo_show=not_found,
            repo_add=lambda request: {"ok": False, "error": {"code": "not_a_repo"}},
        )
        with self.assertRaisesRegex(ValueError, "not_a_repo"):
            orca_icon.set_icon(Path("/work/podcast"), "🎙️")

    def test_an_overlong_emoji_is_refused_before_sending(self) -> None:
        with self.assertRaises(ValueError):
            orca_icon.set_icon(Path("/work/podcast"), "🎙️" * 9)

    def test_no_runtime_is_unavailable(self) -> None:
        with self.assertRaises(orca_icon.OrcaUnavailable):
            orca_icon.set_icon(Path("/work/podcast"), "🎙️")

    def test_records_writes_the_result_beside_the_prefix(self) -> None:
        records = self.user_data / "run"
        (self.user_data / "run.orca.json").write_text("stale")
        argv = ["orca_icon.py", "--repository", "/work/podcast", "--emoji", "🎙️"]
        with (
            unittest.mock.patch.object(sys, "argv", [*argv, "--records", str(records)]),
            unittest.mock.patch("builtins.print"),
        ):
            status = orca_icon.main()
        self.assertEqual(status, 3)
        record = json.loads((self.user_data / "run.orca.json").read_text())
        self.assertEqual(record["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
