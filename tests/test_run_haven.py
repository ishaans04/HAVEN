"""The launcher's preflight checks.

Both conditions it reports are ones the running system will not complain about.

A missing console export does not stop the API: `haven/api/main.py` mounts
`web/out` only if it exists, deliberately, so that `npm run dev` on a separate
port keeps working. The first symptom is therefore a 404 at the root of a server
that just reported itself healthy.

A stale export is worse, because nothing anywhere notices. The page loads, looks
correct, and renders a version of the UI built before the API it is now talking
to. That is how the Phase 9 authority labels were absent from a console being
used to demonstrate them.

Neither check refuses to start. A launcher that would not run without watsonx
credentials would contradict the offline guarantee it exists to launch.
"""

from __future__ import annotations

import scripts.run_haven as launcher


def test_a_missing_console_is_reported(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(launcher, "CONSOLE_DIR", tmp_path / "absent")

    assert launcher.check_console() is False
    out = capsys.readouterr().out
    assert "NOT BUILT" in out
    assert "npm run build" in out, "the fix has to be in the message, not in a doc somewhere"


def test_a_stale_console_is_reported(tmp_path, monkeypatch, capsys) -> None:
    """The failure that looks like success.

    Build the export, then touch a source file afterwards — exactly what editing
    a component and forgetting to rebuild leaves behind.
    """
    console = tmp_path / "out"
    console.mkdir()
    (console / "index.html").write_text("<html></html>", encoding="utf-8")

    source_dir = tmp_path / "web" / "src"
    source_dir.mkdir(parents=True)
    component = source_dir / "Component.tsx"
    component.write_text("export const x = 1;", encoding="utf-8")
    # Unambiguously newer than the export, without depending on clock resolution.
    import os

    stamp = (console / "index.html").stat().st_mtime + 60
    os.utime(component, (stamp, stamp))

    monkeypatch.setattr(launcher, "CONSOLE_DIR", console)
    monkeypatch.setattr(launcher, "REPO_ROOT", tmp_path)

    assert launcher.check_console() is False
    out = capsys.readouterr().out
    assert "STALE" in out
    assert "Component.tsx" in out, "name the file, so the reader can tell whether it matters"


def test_a_fresh_console_passes(tmp_path, monkeypatch, capsys) -> None:
    console = tmp_path / "out"
    console.mkdir()
    (source_dir := tmp_path / "web" / "src").mkdir(parents=True)
    (source_dir / "Component.tsx").write_text("export const x = 1;", encoding="utf-8")

    import os

    (console / "index.html").write_text("<html></html>", encoding="utf-8")
    stamp = (source_dir / "Component.tsx").stat().st_mtime + 60
    os.utime(console / "index.html", (stamp, stamp))

    monkeypatch.setattr(launcher, "CONSOLE_DIR", console)
    monkeypatch.setattr(launcher, "REPO_ROOT", tmp_path)

    assert launcher.check_console() is True
    assert "built" in capsys.readouterr().out


def test_a_mock_only_chain_is_called_out(capsys) -> None:
    """The suite pins the chain to mock, which is the condition being reported."""
    assert launcher.check_reasoning() is False
    out = capsys.readouterr().out
    assert "offline stand-in only" in out
    assert "HAVEN_LLM_CHAIN" in out


def test_watsonx_without_credentials_is_called_out(capsys) -> None:
    """Configured but uncredentialled is the case that looks like it works.

    Every request falls through to the stand-in, correctly and quietly, and the
    only sign is Zone 6. Saying so before the server starts is cheaper.
    """
    from haven.config import LLM

    original = LLM.chain
    object.__setattr__(LLM, "chain", "watsonx,mock")
    try:
        assert launcher.check_reasoning() is False
        assert "credentials are not set" in capsys.readouterr().out
    finally:
        object.__setattr__(LLM, "chain", original)


def test_the_corpus_line_names_the_manifest(capsys) -> None:
    """Which rulebook. Every decision records it, so the launcher shows it."""
    from haven.rag.corpus import CORPUS_MANIFEST

    launcher.check_corpus()
    assert CORPUS_MANIFEST[:12] in capsys.readouterr().out
