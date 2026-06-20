"""Verify cron.scheduler_provider resolves correctly despite the
discord adapter inserting plugins/ into sys.path[0] at module level.

Regression test for: importing gateway.platforms.* triggers
plugins/platforms/discord/adapter.py's module-level
sys.path.insert(0, plugins/). Since plugins/cron/__init__.py exists,
``from cron.scheduler_provider import ...`` would resolve ``cron`` to
``plugins/cron/`` (which lacks scheduler_provider.py) instead of the
real ``cron/`` package. The fix ensures the import is cached at module
level in gateway/run.py before any platform adapter import fires.
"""

import importlib
import sys


class TestCronImportResolution:
    """cron.scheduler_provider must remain importable after the discord
    adapter inserts plugins/ into sys.path[0] at module import time."""

    def test_discord_adapter_inserts_plugins_into_syspath(self):
        """Evidence that the root cause exists.

        plugins/platforms/discord/adapter.py:101 does
        ``sys.path.insert(0, str(Path(__file__).resolve().parents[2]))``
        at module level, putting plugins/ at sys.path[0].
        """
        importlib.import_module("plugins.platforms.discord.adapter")

        assert "plugins" in sys.path[0], (
            f"Expected plugins/ in sys.path[0], got: {sys.path[0]}"
        )

    def test_cron_resolves_correctly_when_imported_before_shadow(self, monkeypatch):
        """The fix: cache cron.scheduler_provider before the discord
        adapter's sys.path.insert fires, so plugins/cron/ never wins.

        This matches what gateway/run.py does at module level: import
        cron.scheduler_provider BEFORE any gateway.platforms.* import.
        Once cron is in sys.modules, the shadowed path is irrelevant.
        """
        # Purge any cached cron modules so we start fresh
        for key in list(sys.modules):
            if key == "cron" or key.startswith("cron."):
                monkeypatch.delitem(sys.modules, key, raising=False)

        # Step 1: import cron.scheduler_provider first (like the fix)
        from cron.scheduler_provider import resolve_cron_scheduler

        assert callable(resolve_cron_scheduler)

        # Confirm it resolved to the real cron/
        import cron
        assert "plugins" not in cron.__file__, (
            f"cron resolved to wrong package: {cron.__file__}"
        )

        # Step 2: now trigger the discord adapter import, which does
        # sys.path.insert(0, plugins/) at module level
        importlib.import_module("plugins.platforms.discord.adapter")

        assert "plugins" in sys.path[0]

        # Step 3: cron must still resolve to the real package because
        # it's cached in sys.modules — the shadowed path is irrelevant
        import cron as cron2
        assert "plugins" not in cron2.__file__, (
            f"cron was re-resolved to wrong package after shadow: {cron2.__file__}"
        )
        assert callable(resolve_cron_scheduler)
