# This test spawns pgbench in a thread in the background and concurrently restarts pageserver,
# checking how client is able to transparently restore connection to pageserver
#
import threading
import time

from fixtures.log_helper import log
from fixtures.neon_fixtures import NeonEnv, PgBin


# Test restarting page server, while safekeeper and compute node keep
# running.
def test_pageserver_restarts_under_worload(neon_simple_env: NeonEnv, pg_bin: PgBin):
    env = neon_simple_env
    env.neon_cli.create_branch("test_pageserver_restarts")
    endpoint = env.endpoints.create_start("test_pageserver_restarts")
    n_restarts = 10
    scale = 10

    # the background task may complete the init task delay after finding an
    # active tenant, but shutdown starts right before Tenant::gc_iteration
    env.pageserver.allowed_errors.append(
        r".*Gc failed, retrying in \S+: Cannot run GC iteration on inactive tenant"
    )

    def run_pgbench(connstr: str):
        log.info(f"Start a pgbench workload on pg {connstr}")
        pg_bin.run_capture(["pgbench", "-i", f"-s{scale}", connstr])
        pg_bin.run_capture(["pgbench", f"-T{n_restarts}", connstr])

    thread = threading.Thread(target=run_pgbench, args=(endpoint.connstr(),), daemon=True)
    thread.start()

    for i in range(n_restarts):
        # Stop the pageserver gracefully and restart it.
        time.sleep(1)
        env.pageserver.stop()
        env.pageserver.start()

    thread.join()
